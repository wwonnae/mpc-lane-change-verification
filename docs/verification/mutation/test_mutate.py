"""mutate.py(직접 만든 변이기) 자체 테스트 — 도구 신뢰성 확인(PREREGISTRATION.md §6).

실행(저장소 루트): python -m pytest docs/verification/mutation/test_mutate.py -q
기본 테스트 수집 경로(thesis_v2/tests, thesis_v2/anomaly/tests) 밖에 있어 제품 테스트 수에 포함되지 않는다.
"""
import ast
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mutate as M  # noqa: E402

SNIPPET = '''def f(a, b, x):
    s = "가나다" if a < b and not x else "라"
    y = a + b * 2
    if a >= 0 or b == 1:
        return y
    y -= 1
    return None
'''


def _line(text, n):
    return text.splitlines()[n - 1]


def _muts(text=SNIPPET):
    return M.generate_from_text("snip", "snip.py", text, [(1, 100)])


# ---------------- 연산자 단위: 기대한 소스가 정확히 나오는가 ----------------
@pytest.mark.parametrize("op, line, expected", [
    ("rel", 2, '    s = "가나다" if a <= b and not x else "라"'),
    ("bool", 2, '    s = "가나다" if a < b or not x else "라"'),
    ("operand_drop", 2, '    s = "가나다" if not x else "라"'),
    ("operand_drop", 2, '    s = "가나다" if a < b else "라"'),
    ("not_rm", 2, '    s = "가나다" if a < b and x else "라"'),
    ("arith", 3, "    y = a - b * 2"),
    ("arith", 3, "    y = a + b / 2"),
    ("const", 3, "    y = a + b * 0"),
    ("rel", 4, "    if a > 0 or b == 1:"),
    ("rel", 4, "    if a >= 0 or b != 1:"),
    ("bool", 4, "    if a >= 0 and b == 1:"),
    ("const", 4, "    if a >= 1 or b == 1:"),
    ("return_none", 5, "        return None"),
    ("arith", 6, "    y += 1"),
    ("assign_del", 6, "    pass"),
    ("assign_del", 2, "    pass"),
])
def test_operator_produces_expected_line(op, line, expected):
    got = {_line(M.mutated_text(SNIPPET, m), line) for m in _muts() if m.operator == op and m.line == line}
    assert expected in got, got


def test_return_none_literal_is_not_mutated():
    assert not [m for m in _muts() if m.operator == "return_none" and m.line == 7]


def test_non_ascii_line_offsets():
    """AST col_offset은 UTF-8 바이트 — 한글이 앞에 있는 줄에서도 정확한 위치를 바꿔야 한다(개발 중 발견한 버그의 회귀 테스트)."""
    for m in _muts():
        if m.line == 2 and m.operator in ("rel", "bool", "not_rm"):
            new = _line(M.mutated_text(SNIPPET, m), 2)
            assert new.startswith('    s = "가나다" if ') and new.endswith(' else "라"'), new


# ---------------- 대상 모듈 전체: 적용 확인 ----------------
@pytest.mark.parametrize("module", list(M.TARGETS))
def test_all_target_mutants_apply_only_at_their_span(module):
    text = (M.ROOT / M.TARGETS[module]["path"]).read_text(encoding="utf-8")
    muts = M.generate(module, text)
    assert muts
    src = M.Source(text)
    for m in muts:
        assert M.validate(text, m) is None, (m.id, M.validate(text, m))
        new = M.mutated_text(text, m)
        lo = min(e.start[0] for e in m.edits)
        hi = max(e.end[0] for e in m.edits)
        a, b = text.splitlines(), new.splitlines()
        assert len(a) == len(b)
        diff = [i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y]
        assert diff and all(lo <= d <= hi for d in diff), (m.id, diff, lo, hi)
        if m.operator in ("rel", "arith", "const"):
            assert src.seg(m.edits[0].start, m.edits[0].end) == m.original, m.id


def _independent_counts(text, ranges):
    """mutate.py와 별도로 작성한 지점 수 계산(같은 규칙)."""
    tree = ast.parse(text)
    c = dict(rel=0, bool=0, operand_drop=0, not_rm=0, const=0, arith=0, return_none=0, assign_del=0)
    ar = (ast.Add, ast.Sub, ast.Mult, ast.Div)
    for n in ast.walk(tree):
        ln = getattr(n, "lineno", None)
        if ln is None or not any(a <= ln <= b for a, b in ranges):
            continue
        if isinstance(n, ast.Compare):
            c["rel"] += len(n.ops)
        if isinstance(n, ast.BoolOp):
            c["bool"] += 1
            c["operand_drop"] += len(n.values)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not):
            c["not_rm"] += 1
        if isinstance(n, ast.Constant) and type(n.value) in (int, float):
            c["const"] += 1
        if isinstance(n, (ast.BinOp, ast.AugAssign)) and isinstance(n.op, ar):
            c["arith"] += 1
        if isinstance(n, ast.Return) and n.value is not None and \
                not (isinstance(n.value, ast.Constant) and n.value.value is None):
            c["return_none"] += 1
        if isinstance(n, (ast.Assign, ast.AugAssign)) or (isinstance(n, ast.AnnAssign) and n.value is not None):
            c["assign_del"] += 1
    return c


@pytest.mark.parametrize("module", list(M.TARGETS))
def test_mutant_counts_match_independent_count(module):
    cfg = M.TARGETS[module]
    text = (M.ROOT / cfg["path"]).read_text(encoding="utf-8")
    got = {}
    for m in M.generate(module, text):
        got[m.operator] = got.get(m.operator, 0) + 1
    want = {k: v for k, v in _independent_counts(text, cfg["ranges"]).items() if v}
    assert got == want


# ---------------- 실행기: 바이트코드 캐시, 기준 변이, 원본 무변경 ----------------
def test_same_length_mutation_is_not_masked_by_bytecode_cache(tmp_path):
    (tmp_path / "modx.py").write_text("def f():\n    return 1 + 2\n", encoding="utf-8")
    (tmp_path / "test_x.py").write_text("from modx import f\n\ndef test_f():\n    assert f() == 3\n", encoding="utf-8")
    assert M.run_pytest(tmp_path, ["test_x.py"], 60)["status"] == "pass"
    (tmp_path / "modx.py").write_text("def f():\n    return 1 - 2\n", encoding="utf-8")  # 같은 길이, 같은 초
    M._clear_pycache(tmp_path)
    assert M.run_pytest(tmp_path, ["test_x.py"], 60)["status"] == "killed"


def test_golden_diff_parser():
    out = "[PASS] paper seed=0: 일치 (max|diff|=0.000000 rad)\n[PASS] left_obstacle seed=2: 일치 (max|diff|=0.000412 rad)\n"
    assert [float(x) for x in M.DIFF_RE.findall(out)] == [0.0, 0.000412]


def test_identity_passes_and_known_mutant_is_killed_on_copy():
    """깨끗한 사본은 L1을 통과하고, fsm.py:55 '<'→'<='(경계 front_gap=G_TRIG)는 test_mcdc_d1이 잡아야 한다."""
    target = M.ROOT / M.TARGETS["fsm"]["path"]
    before = hashlib.sha256(target.read_bytes()).hexdigest()
    tmp = Path(tempfile.mkdtemp(prefix="mutself_"))
    try:
        M.make_copy(tmp)
        M._clear_pycache(tmp)
        assert M.run_pytest(tmp, M.TARGETS["fsm"]["l1"], 120)["status"] == "pass"
        text = target.read_text(encoding="utf-8")
        mu = [m for m in M.generate("fsm", text) if m.line == 55 and m.operator == "rel" and m.original == "<"]
        assert len(mu) == 1
        (tmp / M.TARGETS["fsm"]["path"]).write_text(M.mutated_text(text, mu[0]), encoding="utf-8")
        M._clear_pycache(tmp)
        r = M.run_pytest(tmp, M.TARGETS["fsm"]["l1"], 120)
        assert r["status"] == "killed" and "test_mcdc_d1" in (r["first_failure"] or "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == before  # 원본 작업 트리는 바뀌지 않는다
