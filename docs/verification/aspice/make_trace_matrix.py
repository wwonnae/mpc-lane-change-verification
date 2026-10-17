"""양방향 추적 매트릭스 생성기 — REQ → 설계 → 코드 → 테스트 → 평가 문서, 그리고 역방향.

docs/verification/aspice/TRACE_MATRIX.md, trace_matrix.json을 만든다. 모든 연결은 아래 규칙으로 **자동** 결정한다
(사람이 손으로 잇지 않는다). 연결 근거가 없으면 고아로 남긴다.

입력(읽기만 함):
- REQ 정의: repro/docs/SPEC.md 표 행, repro/docs/SETTINGS_DECISION.md 절 제목(`## §n. REQ-…`)
- 설계: SETTINGS_DECISION.md·DESIGN_BASELINE.md의 `## ` 절 안 REQ 인용
- 코드: thesis_v2/{baseline,improved,anomaly}(tests 제외) 주석·docstring의 REQ 인용(AST로 감싸는 함수까지),
        thesis_v2/tests/TRACEABILITY.md 코드 열
- 테스트: pytest 수집 결과(함수 단위), TRACEABILITY.md 테스트 열, 테스트 함수 안의 REQ 인용
- 평가 문서: MEASURE_PLAN·ROBUSTNESS_PLAN·RESULT_*·STAGE3_SUMMARY의 REQ 인용(**인용 = 평가로 검증됨이 아님**)
- 이상탐지 별도 표: 아래 ANOMALY_CHAIN(사람이 고른 목록 — 경로·절·태그는 실행 때마다 자동 확인)

사용(저장소 루트):
  python docs/verification/aspice/make_trace_matrix.py          # 생성
  python docs/verification/aspice/make_trace_matrix.py --check  # 다시 생성해 저장본과 바이트 비교(다르면 exit 1)
출력은 POSIX 경로·LF 줄바꿈·정렬 고정이라 OS와 무관하게 같은 바이트가 나와야 한다.
테스트 수집에 pytest를 부르므로 테스트 의존성(torch 포함)이 설치된 환경에서 돌린다.
"""
import argparse
import ast
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = Path(__file__).resolve().parent
OUT_MD = OUT_DIR / "TRACE_MATRIX.md"
OUT_JSON = OUT_DIR / "trace_matrix.json"
REGEN_CMD = "python docs/verification/aspice/make_trace_matrix.py && git diff -- docs/verification/aspice/TRACE_MATRIX.md docs/verification/aspice/trace_matrix.json"

SPEC = "repro/docs/SPEC.md"
DECISION = "repro/docs/SETTINGS_DECISION.md"
DESIGN_DOCS = [DECISION, "repro/docs/DESIGN_BASELINE.md"]
TRACE_TABLE = "thesis_v2/tests/TRACEABILITY.md"
CODE_DIRS = ["thesis_v2/baseline", "thesis_v2/improved", "thesis_v2/anomaly"]
TEST_DIRS = ["thesis_v2/tests", "thesis_v2/anomaly/tests"]
EVAL_DOCS = ["repro/docs/MEASURE_PLAN.md", "repro/docs/ROBUSTNESS_PLAN.md", "repro/docs/RESULT_BASELINE.md",
             "repro/docs/RESULT_ROBUSTNESS.md", "repro/docs/RESULT_IMPROVED.md", "repro/docs/RESULT_STUDENT.md",
             "repro/docs/RESULT_I4.md", "repro/docs/STAGE3_SUMMARY.md"]

# 고아 테스트 범주 규칙(순서대로 첫 번째 일치):
#  1) 경로가 thesis_v2/anomaly/tests/ → "이상탐지(REQ 체계 밖)"
#  2) 테스트 파일이 thesis_v2.improved를 import → "improved(SPEC에 REQ 없음)"
#  3) 파일명 test_<대상>.py의 대상 모듈이 INFRA_TARGETS → "인프라·도구(요구사항 수준 아님)"
#  4) 나머지 → "기타"
INFRA_TARGETS = {"envinfo", "summary", "logger", "metrics", "run_cli", "check_golden"}
CATEGORIES = ["이상탐지(REQ 체계 밖)", "improved(SPEC에 REQ 없음)", "인프라·도구(요구사항 수준 아님)", "기타"]

# 이상탐지 별도 표: (항목, DESIGN 절 번호들, 스크립트, 결과 폴더, 폴더 이름 태그). 스크립트 소스에 태그 문자열이 있고
# 폴더 이름이 그 태그로 끝나는지, 절 제목·경로가 존재하는지를 매번 확인한다.
ANOMALY_DESIGN = "thesis_v2/anomaly/DESIGN.md"
ANOMALY_CHAIN = [
    ("탐지기 A 임계값(iteration 3)", [13, 18], "thesis_v2/anomaly/calibrate_a.py",
     "thesis_v2/results/anomaly/20261002_104706_3층PC108_it3_threshold_a", "_threshold_a"),
    ("탐지기 B1·B2 학습(iteration 2)", [15, 17], "thesis_v2/anomaly/train_b.py",
     "thesis_v2/results/anomaly/20261002_001009_DESKTOP-MDCKRJS_it2_train_b", "_train_b"),
    ("하이브리드 학습(iteration 3)", [20], "thesis_v2/anomaly/train_hybrid.py",
     "thesis_v2/results/anomaly/20261002_111909_3층PC108_it3_train_hybrid", "_train_hybrid"),
    ("오프라인 평가(seed 4000~4099)", [13, 19, 21], "thesis_v2/anomaly/eval_offline.py",
     "thesis_v2/results/anomaly/20261002_145638_3층PC108_it3_eval_offline_eval", "_eval_offline_"),
    ("오프라인 평가 재현 확인(--check)", [27], "thesis_v2/anomaly/eval_offline.py",
     "thesis_v2/results/anomaly/20261012_3층PC109_run_logs", None),
    ("폐루프 평가(seed 5000~5099, 6조합 = 11 run × 100 seed = 1,100회)", [24], "thesis_v2/anomaly/closed_loop.py",
     "thesis_v2/results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval", "_closed_loop_"),
    ("폐루프 평가 재현 확인(--check)", [28], "thesis_v2/anomaly/closed_loop.py",
     "thesis_v2/results/anomaly/20261012_3층PC109_run_logs", None),
    ("탐지기 계산 시간(공식 조건)", [29], "thesis_v2/anomaly/benchmark_detector_timing.py",
     "thesis_v2/results/anomaly/20261012_232824_DESKTOP-MDCKRJS_detector_timing", "detector_timing"),
]

ID_RE = re.compile(r"REQ-([A-Z]+)-(\d+)([a-z]?)")
# REQ-X-NN 뒤에 붙는 '/ MMa' 연속 표기, 'NNa~MMb' 범위 표기(문서에서는 GitHub 취소선을 피하려고 – 도 씀)
CITE_RE = re.compile(r"REQ-([A-Z]+)-(\d+[a-z]?)((?:\s*/\s*\d+[a-z]?)*)(?:\s*[~–]\s*(\d+[a-z]?))?")


def rel(p: Path) -> str:
    return p.resolve().relative_to(ROOT).as_posix()


def read_lines(path: str):
    return (ROOT / path).read_text(encoding="utf-8").splitlines()


def _key(num_letter: str):
    m = re.match(r"(\d+)([a-z]?)", num_letter)
    return int(m.group(1)), m.group(2)


def cite_ids(text: str, universe=None):
    """텍스트 안 REQ 인용을 (ID, 종류) 목록으로. 종류: 직접 / 연속(/) / 범위(~).
    범위는 universe 안에서 [시작, 끝]에 드는 ID로만 펼친다(universe 없으면 범위를 펼치지 않음)."""
    out = []
    for m in CITE_RE.finditer(text):
        area, first, cont, last = m.group(1), m.group(2), m.group(3), m.group(4)
        out.append((f"REQ-{area}-{first}", "직접"))
        for extra in re.findall(r"\d+[a-z]?", cont or ""):
            out.append((f"REQ-{area}-{extra}", "연속(/)"))
        if last and universe is not None:
            lo, hi = _key(first), _key(last)
            for rid in universe:
                a = ID_RE.fullmatch(rid)
                if a and a.group(1) == area and lo <= (int(a.group(2)), a.group(3)) <= hi and rid != f"REQ-{area}-{first}":
                    out.append((rid, "범위(`~`)"))
    return out


def sort_req(rid: str):
    m = ID_RE.fullmatch(rid)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else (rid, 0, "")


# ---------------------------------------------------------------- REQ 정의
def load_spec():
    spec = {}
    for i, line in enumerate(read_lines(SPEC), 1):
        m = re.match(r"^\| (REQ-[A-Z]+-\d+[a-z]?) \|([^|]*)\|", line)
        if m:
            summary = re.sub(r"\s+", " ", m.group(2).replace("*", "")).strip()
            spec[m.group(1)] = dict(where=f"{SPEC}:{i}", summary=summary[:70] + ("…" if len(summary) > 70 else ""))
    return spec


def load_decision_defs():
    defs = {}
    for i, line in enumerate(read_lines(DECISION), 1):
        m = re.match(r"^## §(\d+)\. (REQ-[A-Z]+-\d+[a-z]?)", line)
        if m:
            defs.setdefault(m.group(2), f"{DECISION}:{i} (§{m.group(1)})")
    return defs


# ---------------------------------------------------------------- 코드·테스트 소스 스캔
class DefIndex:
    """파일의 (시작행, 끝행, 정규 이름) 목록 — 행을 감싸는 가장 안쪽 정의를 찾는다."""

    def __init__(self, path: Path):
        self.tree = ast.parse(path.read_text(encoding="utf-8"))
        self.spans = []
        self.names = set()

        def walk(node, prefix):
            for ch in ast.iter_child_nodes(node):
                if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    q = f"{prefix}{ch.name}"
                    start = min([ch.lineno] + [d.lineno for d in ch.decorator_list])
                    self.spans.append((start, ch.end_lineno, q))
                    self.names.add(ch.name)
                    self.names.add(q)
                    walk(ch, q + ".")
                elif isinstance(ch, (ast.Assign, ast.AnnAssign)) and node is self.tree:
                    for tgt in (ch.targets if isinstance(ch, ast.Assign) else [ch.target]):
                        if isinstance(tgt, ast.Name):
                            self.names.add(tgt.id)
        walk(self.tree, "")

    def enclosing(self, line: int) -> str:
        best = None
        for s, e, q in self.spans:
            if s <= line <= e and (best is None or s >= best[0]):
                best = (s, e, q)
        return best[2] if best else "<module>"


def py_files(dirs, exclude_tests):
    out = []
    for d in dirs:
        for p in sorted((ROOT / d).rglob("*.py")):
            parts = p.relative_to(ROOT).parts
            if exclude_tests and "tests" in parts:
                continue
            if "results" in parts:
                continue
            out.append(p)
    return out


def collect_tests():
    """pytest 수집 결과를 함수 단위 (파일, 함수)로. 파라미터 변형 수도 센다."""
    cmd = [sys.executable, "-m", "pytest", *TEST_DIRS, "--collect-only", "-q", "-p", "no:cacheprovider"]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0:
        sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit("pytest 수집 실패")
    funcs, n_items = {}, 0
    for line in r.stdout.splitlines():
        if "::" not in line:
            continue
        n_items += 1
        f, rest = line.split("::", 1)
        name = rest.split("::")[-1].split("[")[0]
        funcs.setdefault((f, name), 0)
        funcs[(f, name)] += 1
    return funcs, n_items


# ---------------------------------------------------------------- TRACEABILITY.md
def split_row(line):
    cells = re.split(r"(?<!\\)\|", line.strip())
    return [c.strip() for c in cells[1:-1]]


def parse_trace_table(universe):
    rows = []
    section = "baseline"
    for i, line in enumerate(read_lines(TRACE_TABLE), 1):
        if line.startswith("## I4"):
            section = "student_i4"
        if not line.startswith("| ") or line.startswith("| REQ ID |") or line.startswith("| 요구/결정 |"):
            continue
        cells = split_row(line)
        if len(cells) != 3 or set(cells[0]) <= set("-: "):
            continue
        ids = []
        for rid, _ in cite_ids(cells[0]):
            if rid not in ids:
                ids.append(rid)
        rows.append(dict(line=i, label=cells[0], reqs=ids, code=cells[1], tests=cells[2], section=section))
    return rows


def resolve_code_tokens(cell, section, code_index, unresolved, where):
    links = []
    for tok in re.findall(r"`([^`]+)`", cell):
        m = re.match(r"^([\w/]+\.py)(?::(.+))?$", tok.strip())
        if not m:
            continue
        fpart, names = m.group(1), m.group(2)
        cands = [p for p in code_index if p.endswith("/" + fpart) or p == fpart]
        if len(cands) > 1:
            pref = "thesis_v2/improved/student_i4/" if section == "student_i4" else "thesis_v2/baseline/"
            cands = [p for p in cands if p.startswith(pref)] or cands
        if len(cands) != 1:
            unresolved.append(f"{where}: 코드 `{tok}` (파일 후보 {len(cands)}개)")
            continue
        path = cands[0]
        if not names:
            links.append(f"{path}")
            continue
        for nm in [n.strip() for n in re.split(r"[,/]", names) if n.strip()]:
            if "*" in nm and fnmatch.filter(sorted(code_index[path].names), nm):
                links.append(f"{path}:{nm}")
            elif nm in code_index[path].names:
                links.append(f"{path}:{nm}")
            else:
                unresolved.append(f"{where}: 코드 `{path}:{nm}` (정의 없음)")
    return links


def resolve_test_tokens(cell, test_funcs, unresolved, where):
    """반환: [(file, func, 종류)]. 종류: 함수 명시 / 파일 단위."""
    by_name = {}
    for (f, n) in test_funcs:
        by_name.setdefault(n, []).append(f)
    files = sorted({f for f, _ in test_funcs})
    links, ctx_file, prev_name = [], None, None
    for tok in re.findall(r"`([^`]+)`", cell):
        tok = tok.strip()
        m = re.match(r"^(?:([\w/]+\.py)::)?([\w.]+?)(?:\[.*\])?$", tok)
        if tok.endswith(".py"):
            if not Path(tok).name.startswith("test_"):
                continue  # 설명문 속 스크립트 이름(예: `run.py`) — 테스트가 아님
            cands = [f for f in files if f.endswith("/" + tok)]
            if len(cands) == 1:
                ctx_file = cands[0]
                links += [(f, n, "파일 단위") for (f, n) in sorted(test_funcs) if f == cands[0]]
            else:
                unresolved.append(f"{where}: 테스트 파일 `{tok}` (후보 {len(cands)}개)")
            continue
        if not m:
            continue
        fpart, name = m.group(1), m.group(2)
        if name.startswith("..."):
            suffix = name[3:]
            # 생략 표기 = 직전 토큰 이름의 뒷부분을 바꾼 것: 후보 이름이 suffix로 끝나고, 그 앞부분이 직전 이름의 접두사
            pool = [(f, n) for (f, n) in test_funcs if f == ctx_file and n.endswith(suffix)
                    and prev_name and prev_name.startswith(n[:len(n) - len(suffix)])] if ctx_file else []
            if len(pool) == 1:
                links.append((pool[0][0], pool[0][1], "함수 명시"))
            else:
                unresolved.append(f"{where}: 테스트 `{tok}` (생략 표기, 후보 {len(pool)}개)")
            continue
        if not name.startswith("test_"):
            continue
        if fpart:
            cands = [f for f in by_name.get(name, []) if f.endswith("/" + fpart)]
        elif ctx_file and name in [n for (f, n) in test_funcs if f == ctx_file]:
            cands = [ctx_file]
        else:
            cands = by_name.get(name, [])
        if len(cands) == 1:
            ctx_file, prev_name = cands[0], name
            links.append((cands[0], name, "함수 명시"))
        else:
            unresolved.append(f"{where}: 테스트 `{tok}` (후보 {len(cands)}개)")
    return links


# ---------------------------------------------------------------- 문서 절 인용
def section_citations(path, universe):
    """`## ` 절 단위로 REQ 인용을 모은다: {REQ: [(절 이름, 시작행, 종류)]}."""
    out = {}
    lines = read_lines(path)
    heads = [(i, l) for i, l in enumerate(lines, 1) if l.startswith("## ")]
    for k, (start, head) in enumerate(heads):
        end = heads[k + 1][0] - 1 if k + 1 < len(heads) else len(lines)
        title = head[3:].strip()
        m = re.match(r"(§\d+|[\w-]+)[.\s]", title)
        short = m.group(1) if m else title[:20]
        short = f"§{short}" if short.isdigit() else short
        found = {}
        for rid, _ in cite_ids(head, universe):
            found[rid] = "절 제목"
        for ln in lines[start:end]:
            for rid, _ in cite_ids(ln, universe):
                found.setdefault(rid, "본문 인용")
        for rid, kind in found.items():
            if rid in universe:
                out.setdefault(rid, []).append(f"{Path(path).name} {short} (행 {start}, {kind})")
    return out


def line_citations(path, universe):
    out = {}
    for i, ln in enumerate(read_lines(path), 1):
        for rid, _ in cite_ids(ln, universe):
            if rid in universe:
                out.setdefault(rid, [])
                if i not in out[rid]:
                    out[rid].append(i)
    return {rid: f"{Path(path).name}:" + ",".join(map(str, v)) for rid, v in out.items()}


# ---------------------------------------------------------------- 고아 범주
def test_file_imports(path: Path):
    mods = set()
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module)
        elif isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
    return mods


def categorize(test_file: str):
    if test_file.startswith("thesis_v2/anomaly/tests/"):
        return CATEGORIES[0]
    if any(m.startswith("thesis_v2.improved") for m in test_file_imports(ROOT / test_file)):
        return CATEGORIES[1]
    target = Path(test_file).stem[len("test_"):]
    if target in INFRA_TARGETS:
        return CATEGORIES[2]
    return CATEGORIES[3]


# ---------------------------------------------------------------- 이상탐지 별도 표
def anomaly_chain():
    errors, rows = [], []
    heads = {}
    for i, l in enumerate(read_lines(ANOMALY_DESIGN), 1):
        m = re.match(r"^## (\d+)\. (.*)", l)
        if m:
            heads[int(m.group(1))] = (i, m.group(2).strip())
    for item, secs, script, folder, tag in ANOMALY_CHAIN:
        sec_txt = []
        for s in secs:
            if s not in heads:
                errors.append(f"DESIGN §{s} 없음")
                continue
            ln, title = heads[s]
            sec_txt.append(f"§{s}(행 {ln})")
        for p in (script, folder):
            if not (ROOT / p).exists():
                errors.append(f"경로 없음: {p}")
        if tag:
            if tag.strip("_") not in (ROOT / script).read_text(encoding="utf-8"):
                errors.append(f"{script}에 태그 '{tag.strip('_')}' 없음")
            if tag not in Path(folder).name and not Path(folder).name.endswith(tag.rstrip("_") + "_eval"):
                errors.append(f"{folder} 이름에 태그 '{tag}' 없음")
        rows.append(dict(item=item, design=sec_txt, script=script, result=folder,
                         tag_checked=bool(tag)))
    return rows, errors


# ---------------------------------------------------------------- 생성
def build():
    spec = load_spec()
    dec_defs = load_decision_defs()
    code_files = py_files(CODE_DIRS, exclude_tests=True)
    test_files = py_files(TEST_DIRS, exclude_tests=False)
    code_index = {rel(p): DefIndex(p) for p in code_files}
    # TRACEABILITY 코드 열의 `tests/check_golden.py` 같은 검증 도구 모듈(테스트 함수 파일 아님)도 해석 대상
    code_index_trace = dict(code_index)
    code_index_trace.update({rel(p): DefIndex(p) for p in test_files if not p.name.startswith("test_")})
    test_index = {rel(p): DefIndex(p) for p in test_files if p.name.startswith("test_")}

    # REQ 대상: SPEC 표 행 ∪ thesis_v2 코드·테스트에서 직접 인용된 ID
    universe = set(spec)
    for p in code_files + test_files:
        for rid, kind in cite_ids(p.read_text(encoding="utf-8")):
            if kind == "직접":
                universe.add(rid)
    universe = sorted(universe, key=sort_req)

    req = {}
    for rid in universe:
        if rid in spec:
            d = dict(status="SPEC 정의", where=spec[rid]["where"], summary=spec[rid]["summary"])
        elif rid in dec_defs:
            d = dict(status="SETTINGS_DECISION 정의(SPEC 표 없음)", where=dec_defs[rid], summary="")
        else:
            d = dict(status="정의 없음", where="SPEC.md·SETTINGS_DECISION.md에 정의 행 없음", summary="")
        d.update(design=[], code=[], tests=[], evals=[])
        req[rid] = d

    for doc in DESIGN_DOCS:
        for rid, items in section_citations(doc, universe).items():
            req[rid]["design"] += items

    # 코드: 주석·docstring 인용
    code_rev = {}
    for path, idx in code_index.items():
        for i, ln in enumerate(read_lines(path), 1):
            for rid, kind in cite_ids(ln, universe):
                if rid not in req:
                    continue
                loc = f"{path}:{idx.enclosing(i)}"
                entry = f"{loc} (행 {i}, 주석·{kind})"
                if entry not in req[rid]["code"]:
                    req[rid]["code"].append(entry)
                code_rev.setdefault(loc, set()).add(rid)

    # 테스트 수집 + 테스트 내 인용
    test_funcs, n_items = collect_tests()
    links = {k: [] for k in test_funcs}  # (file, func) -> [(REQ, 종류)]
    for (f, n) in test_funcs:
        idx = test_index.get(f)
        if not idx:
            continue
        src_lines = read_lines(f)
        for s, e, q in idx.spans:
            if q == n:
                for rid, kind in cite_ids("\n".join(src_lines[s - 1:e]), universe):
                    if rid in req and (rid, "테스트 내 인용") not in links[(f, n)]:
                        links[(f, n)].append((rid, "테스트 내 인용"))

    # TRACEABILITY.md
    unresolved, nonreq_rows = [], []
    for row in parse_trace_table(universe):
        where = f"{TRACE_TABLE}:{row['line']}"
        code_links = resolve_code_tokens(row["code"], row["section"], code_index_trace, unresolved, where)
        test_links = resolve_test_tokens(row["tests"], test_funcs, unresolved, where)
        targets = [r for r in row["reqs"] if r in req]
        if not targets:
            nonreq_rows.append(dict(where=where, label=re.sub(r"\s+", " ", row["label"]),
                                    tests=sorted({f"{f}::{n}" for f, n, _ in test_links})))
            for f, n, kind in test_links:
                links[(f, n)].append((f"(비-REQ 행) {row['label'][:30]}", "추적표 비-REQ 행"))
            continue
        for rid in targets:
            for c in code_links:
                e = f"{c} (추적표 {row['line']}행)"
                if e not in req[rid]["code"]:
                    req[rid]["code"].append(e)
            for f, n, kind in test_links:
                if (rid, f"추적표·{kind}") not in links[(f, n)]:
                    links[(f, n)].append((rid, f"추적표·{kind}"))

    for (f, n), ls in links.items():
        for rid, kind in ls:
            if rid in req:
                req[rid]["tests"].append(f"{f}::{n} ({kind})")

    for doc in EVAL_DOCS:
        for rid, txt in line_citations(doc, universe).items():
            req[rid]["evals"].append(txt)

    for rid in req:
        for k in ("design", "code", "tests", "evals"):
            req[rid][k] = sorted(set(req[rid][k]))

    # 역방향·고아
    tests_out, orphan_tests = [], []
    for (f, n) in sorted(test_funcs):
        reqs = sorted({r for r, _ in links[(f, n)] if r in req}, key=sort_req)
        nonreq = sorted({r for r, _ in links[(f, n)] if r not in req})
        rec = dict(test=f"{f}::{n}", variants=test_funcs[(f, n)], reqs=reqs, nonreq_rows=nonreq)
        if not reqs:
            rec["category"] = categorize(f)
            orphan_tests.append(rec)
        tests_out.append(rec)
    orphan_reqs = [r for r in universe if not req[r]["tests"]]
    nocode_reqs = [r for r in universe if not req[r]["code"]]
    code_out = [dict(location=k, reqs=sorted(v, key=sort_req),
                     undefined=sorted([r for r in v if req[r]["status"] == "정의 없음"], key=sort_req))
                for k, v in sorted(code_rev.items())]

    chain, chain_errors = anomaly_chain()
    if chain_errors:
        raise SystemExit("이상탐지 별도 표 확인 실패: " + "; ".join(chain_errors))

    data = dict(
        inputs=dict(spec=SPEC, decision=DECISION, design=DESIGN_DOCS, trace_table=TRACE_TABLE,
                    code_dirs=CODE_DIRS, test_dirs=TEST_DIRS, eval_docs=EVAL_DOCS),
        counts=dict(
            req_total=len(universe),
            req_by_status={s: sum(1 for r in universe if req[r]["status"] == s)
                           for s in sorted({req[r]["status"] for r in universe})},
            req_with_tests=len(universe) - len(orphan_reqs), req_without_tests=len(orphan_reqs),
            req_without_code=len(nocode_reqs),
            test_functions=len(test_funcs), test_items_with_params=n_items,
            tests_with_req=len(test_funcs) - len(orphan_tests), tests_without_req=len(orphan_tests),
            tests_without_req_by_category={c: sum(1 for t in orphan_tests if t["category"] == c) for c in CATEGORIES},
            unresolved_trace_tokens=len(unresolved), nonreq_trace_rows=len(nonreq_rows),
        ),
        reqs={r: req[r] for r in universe},
        orphan_reqs=orphan_reqs, reqs_without_code=nocode_reqs,
        tests=tests_out, code=code_out, nonreq_trace_rows=nonreq_rows,
        unresolved_trace_tokens=sorted(unresolved), anomaly_chain=chain,
    )
    return data


def esc(s: str) -> str:
    return s.replace("|", "\\|")


def render_md(d) -> str:
    c = d["counts"]
    L = []
    L.append("# 양방향 추적 매트릭스 (자동 생성)")
    L.append("")
    L.append("<!-- make_trace_matrix.py가 생성. 손으로 고치지 않는다. 확인: python docs/verification/aspice/make_trace_matrix.py --check -->")
    L.append("")
    L.append("연결 규칙과 입력 문서는 `make_trace_matrix.py` 머리말에 있다. 평가 문서 열은 **REQ ID를 인용한 행**이며, 그 행이 해당 REQ를")
    L.append("평가로 검증했다는 뜻은 아니다. 고아 항목은 억지로 연결하지 않고 그대로 센다.")
    L.append("")
    L.append("## 요약")
    L.append("")
    L.append("| 항목 | 값 |")
    L.append("|---|---|")
    L.append(f"| REQ 대상(SPEC 표 행 ∪ thesis_v2 코드·테스트 직접 인용) | {c['req_total']} |")
    for s, n in c["req_by_status"].items():
        L.append(f"| — {s} | {n} |")
    L.append(f"| 테스트가 1개 이상 연결된 REQ | {c['req_with_tests']} |")
    L.append(f"| **테스트 없는 REQ(고아)** | **{c['req_without_tests']}** |")
    L.append(f"| 코드 연결 없는 REQ | {c['req_without_code']} |")
    L.append(f"| 테스트 함수(파라미터 변형 포함 수집 항목) | {c['test_functions']} ({c['test_items_with_params']}) |")
    L.append(f"| REQ가 연결된 테스트 함수 | {c['tests_with_req']} |")
    L.append(f"| **REQ 없는 테스트 함수(고아)** | **{c['tests_without_req']}** |")
    for cat, n in c["tests_without_req_by_category"].items():
        L.append(f"| — {cat} | {n} |")
    L.append(f"| TRACEABILITY.md 비-REQ 행 | {c['nonreq_trace_rows']} |")
    L.append(f"| TRACEABILITY.md에서 해석하지 못한 표기 | {c['unresolved_trace_tokens']} |")
    L.append("")
    L.append("고아 테스트 범주 규칙(순서대로 첫 일치): ① `thesis_v2/anomaly/tests/` → 이상탐지 ② 테스트 파일이 `thesis_v2.improved`를 import → improved")
    L.append(f"③ 파일명 `test_<대상>.py`의 대상이 {sorted(INFRA_TARGETS)} → 인프라·도구 ④ 나머지 → 기타.")
    L.append("")
    L.append("## 정방향: REQ → 설계 → 코드 → 테스트 → 평가 문서")
    L.append("")
    L.append("| REQ | 정의 | 설계 | 코드 | 테스트 | 평가 문서(인용 행) |")
    L.append("|---|---|---|---|---|---|")
    for rid, r in d["reqs"].items():
        defn = f"{r['status']}<br>`{r['where']}`" + (f"<br>{esc(r['summary'])}" if r["summary"] else "")
        cell = lambda xs: "<br>".join(esc(x) for x in xs) if xs else "**없음**"
        L.append(f"| {rid} | {defn} | {cell(r['design'])} | {cell(r['code'])} | {cell(r['tests'])} | {cell(r['evals'])} |")
    L.append("")
    L.append("## 고아: 테스트 없는 REQ")
    L.append("")
    for rid in d["orphan_reqs"]:
        r = d["reqs"][rid]
        L.append(f"- {rid} — {r['status']}, 코드 연결 {len(r['code'])}건, 평가 문서 인용 {len(r['evals'])}건")
    L.append("")
    L.append("## 역방향: 테스트 → REQ")
    L.append("")
    L.append("| 테스트 함수 | 변형 수 | REQ | 추적표 비-REQ 행 | 고아 범주 |")
    L.append("|---|---:|---|---|---|")
    for t in d["tests"]:
        L.append(f"| `{t['test']}` | {t['variants']} | {', '.join(t['reqs']) or '—'} | "
                 f"{esc('; '.join(t['nonreq_rows'])) or '—'} | {t.get('category', '')} |")
    L.append("")
    L.append("## 역방향: 코드(함수) → REQ")
    L.append("")
    L.append("| 위치(파일:정의) | 인용 REQ | 정의 없는 REQ |")
    L.append("|---|---|---|")
    for e in d["code"]:
        L.append(f"| `{e['location']}` | {', '.join(e['reqs'])} | {', '.join(e['undefined']) or '—'} |")
    L.append("")
    L.append("## TRACEABILITY.md 비-REQ 행")
    L.append("")
    for e in d["nonreq_trace_rows"]:
        L.append(f"- `{e['where']}` {esc(e['label'])} — 테스트 {len(e['tests'])}개")
    L.append("")
    L.append("## TRACEABILITY.md에서 해석하지 못한 표기")
    L.append("")
    for e in d["unresolved_trace_tokens"] or ["(없음)"]:
        L.append(f"- {esc(e)}")
    L.append("")
    L.append("## 이상탐지 확장: DESIGN 절 → 스크립트 → 결과 폴더 (REQ 체계 밖, 별도 표)")
    L.append("")
    L.append("항목 목록은 사람이 고른 것이다(`ANOMALY_CHAIN`). 절 제목·경로 존재와, 스크립트 소스의 폴더 태그 문자열·폴더 이름 일치는 생성 때마다 자동 확인한다.")
    L.append("")
    L.append("| 항목 | DESIGN.md 절 | 스크립트 | 결과 폴더 | 태그 확인 |")
    L.append("|---|---|---|---|---|")
    for e in d["anomaly_chain"]:
        L.append(f"| {e['item']} | {', '.join(e['design'])} | `{e['script']}` | `{e['result']}` | "
                 f"{'예' if e['tag_checked'] else '— (로그 폴더)'} |")
    L.append("")
    return "\n".join(L)


def render_json(d) -> str:
    return json.dumps(d, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    d = build()
    md, js = render_md(d), render_json(d)
    if a.check:
        bad = [p.name for p, s in ((OUT_MD, md), (OUT_JSON, js))
               if not p.exists() or p.read_bytes() != s.encode("utf-8")]
        if bad:
            print(f"[make_trace_matrix --check] 불일치: {', '.join(bad)} — 다시 생성해 차이를 확인할 것")
            print(f"[make_trace_matrix --check] 재생성 명령(저장소 루트): {REGEN_CMD}")
            sys.exit(1)
        print(f"[make_trace_matrix --check] 일치: {OUT_MD.name}, {OUT_JSON.name} "
              f"(REQ {d['counts']['req_total']}, 테스트 없는 REQ {d['counts']['req_without_tests']}, "
              f"REQ 없는 테스트 {d['counts']['tests_without_req']})")
        return
    for p, s in ((OUT_MD, md), (OUT_JSON, js)):
        with open(p, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(s)
    print(json.dumps(d["counts"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
