"""직접 만든 AST 변이기 + 층별 실행기 (docs/verification/mutation/PREREGISTRATION.md).

- 표준 라이브러리만 쓴다(Python 3.9: ast의 end_lineno/end_col_offset, tokenize).
- 변이는 원본 **문자열의 해당 구간만** 바꿔 만든다(ast.unparse를 쓰지 않음) → 주석·서식·줄 번호가 유지된다.
- 실행은 저장소 밖 임시 사본(thesis_v2, results 제외)에서만 한다. 원본 작업 트리는 읽기만 한다.
- 바이트코드 캐시 때문에 같은 길이의 변이가 이전 코드로 실행되는 일을 막으려고 PYTHONDONTWRITEBYTECODE=1로 실행하고
  사본의 __pycache__를 지운다.

사용(저장소 루트):
  python docs/verification/mutation/mutate.py list                    # 변이 목록·수만 출력(실행 안 함)
  python docs/verification/mutation/mutate.py run --out <raw.json>    # 전체 실행(약 1시간 안팎)
  python docs/verification/mutation/mutate.py run --out <raw.json> --only fsm   # 모듈 하나만
"""
import argparse
import ast
import io
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import tokenize
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[3]
TOOL_VERSION = "1"

# ------------------------------------------------------------------ 사전 선언된 범위(PREREGISTRATION.md §2)
TARGETS = {
    "fsm": dict(path="thesis_v2/baseline/fsm.py", ranges=[(33, 75)],
                l1=["thesis_v2/tests/test_fsm.py", "thesis_v2/tests/test_fsm_mcdc.py"], l3=True),
    "detector_a": dict(path="thesis_v2/anomaly/detector_a.py", ranges=[(86, 215)],
                       l1=["thesis_v2/anomaly/tests/test_detector_a.py"], l3=False),
    "closed_loop": dict(path="thesis_v2/anomaly/closed_loop.py", ranges=[(169, 216), (344, 362)],
                        l1=["thesis_v2/anomaly/tests/test_closed_loop.py"], l3=False),
    "baseline_mpc": dict(path="thesis_v2/baseline/mpc.py", ranges=[(1, 264)],
                         l1=["thesis_v2/tests/test_mpc.py"], l3=True),
}
L2_CMD = ["thesis_v2/tests", "thesis_v2/anomaly/tests", "--ignore=thesis_v2/tests/test_check_golden.py"]
GOLDEN_TOL = 1e-3   # thesis_v2/tests/check_golden.py:21
OPERATORS = ["rel", "bool", "operand_drop", "not_rm", "const", "arith", "return_none", "assign_del"]

REL_MAP = {ast.Lt: ("<", "<="), ast.LtE: ("<=", "<"), ast.Gt: (">", ">="), ast.GtE: (">=", ">"),
           ast.Eq: ("==", "!="), ast.NotEq: ("!=", "=="), ast.Is: ("is", "is not"), ast.IsNot: ("is not", "is"),
           ast.In: ("in", "not in"), ast.NotIn: ("not in", "in")}
ARITH_MAP = {ast.Add: ("+", "-"), ast.Sub: ("-", "+"), ast.Mult: ("*", "/"), ast.Div: ("/", "*")}


@dataclass
class Edit:
    start: Tuple[int, int]   # (line 1-based, col 0-based)
    end: Tuple[int, int]
    new: str


@dataclass
class Mutant:
    id: str
    module: str
    path: str
    line: int
    operator: str
    original: str
    replacement: str
    description: str
    edits: List[Edit] = field(default_factory=list)


# ------------------------------------------------------------------ 소스 위치 도우미
class Source:
    def __init__(self, text: str):
        self.text = text
        self.lines = text.splitlines(keepends=True)
        self.offsets = [0]
        for ln in self.lines:
            self.offsets.append(self.offsets[-1] + len(ln))
        self.tokens = [t for t in tokenize.generate_tokens(io.StringIO(text).readline)
                       if t.type in (tokenize.OP, tokenize.NAME)]

    def off(self, pos):
        return self.offsets[pos[0] - 1] + pos[1]

    def cpos(self, line: int, byte_col: int):
        """AST의 (줄, UTF-8 바이트 열) → (줄, 문자 열). tokenize 위치는 문자 열이라 둘을 맞춘다."""
        raw = self.lines[line - 1].encode("utf-8")
        return (line, len(raw[:byte_col].decode("utf-8")))

    def seg(self, a, b):
        return self.text[self.off(a):self.off(b)]

    def tokens_between(self, a, b):
        return [t for t in self.tokens if a <= t.start and t.end <= b]

    def apply(self, edits: List[Edit]) -> str:
        out, last = [], 0
        for e in sorted(edits, key=lambda e: e.start):
            s, t = self.off(e.start), self.off(e.end)
            assert s >= last, "겹치는 편집"
            new = e.new
            lost = self.text[s:t].count("\n") - new.count("\n")
            if lost > 0:  # 지운 구간의 줄바꿈 수만큼 줄 연속으로 채워 이후 줄 번호를 유지한다
                new = new + " \\\n" * lost
            out.append(self.text[last:s]); out.append(new); last = t
        out.append(self.text[last:])
        return "".join(out)


_SRC: Optional["Source"] = None  # generate_from_text 실행 중인 소스(바이트 열 → 문자 열 변환용)


def _start(n):
    return _SRC.cpos(n.lineno, n.col_offset)


def _end(n):
    return _SRC.cpos(n.end_lineno, n.end_col_offset)


def _op_tokens(src: Source, a, b, words: str):
    """구간 [a, b) 안에서 연산자(한 단어 또는 'is not'/'not in' 두 단어)의 시작·끝 위치."""
    toks = src.tokens_between(a, b)
    parts = words.split()
    for i in range(len(toks) - len(parts) + 1):
        if [t.string for t in toks[i:i + len(parts)]] == parts:
            return toks[i].start, toks[i + len(parts) - 1].end
    return None


def _paren_wrapped(src: Source, node):
    """노드가 괄호로 감싸여 있으면 괄호까지 포함한 (start, end), 아니면 노드 구간."""
    s, e = _start(node), _end(node)
    before = [t for t in src.tokens if t.end <= s]
    after = [t for t in src.tokens if t.start >= e]
    if before and after and before[-1].string == "(" and after[0].string == ")":
        return before[-1].start, after[0].end
    return s, e


# ------------------------------------------------------------------ 변이 생성
def in_ranges(node, ranges):
    ln = getattr(node, "lineno", None)
    return ln is not None and any(a <= ln <= b for a, b in ranges)


def generate(module: str, text: Optional[str] = None) -> List[Mutant]:
    cfg = TARGETS[module]
    text = text if text is not None else (ROOT / cfg["path"]).read_text(encoding="utf-8")
    return generate_from_text(module, cfg["path"], text, cfg["ranges"])


def generate_from_text(module, path, text, ranges) -> List[Mutant]:
    global _SRC
    src = Source(text)
    _SRC = src
    tree = ast.parse(text)
    out: List[Mutant] = []

    def add(op, node, edits, original, replacement, desc):
        out.append(Mutant(id="", module=module, path=path, line=node.lineno, operator=op,
                          original=original, replacement=replacement, description=desc, edits=edits))

    for node in ast.walk(tree):
        if not in_ranges(node, ranges):
            continue
        if isinstance(node, ast.Compare):
            prev = node.left
            for op, comp in zip(node.ops, node.comparators):
                a, b = REL_MAP[type(op)]
                pos = _op_tokens(src, _end(prev), _start(comp), a)
                if pos:
                    add("rel", node, [Edit(pos[0], pos[1], b)], a, b, f"관계 {a} → {b}")
                prev = comp
        elif isinstance(node, ast.BoolOp):
            word, other = ("and", "or") if isinstance(node.op, ast.And) else ("or", "and")
            edits = []
            for v1, v2 in zip(node.values, node.values[1:]):
                pos = _op_tokens(src, _end(v1), _start(v2), word)
                if pos:
                    edits.append(Edit(pos[0], pos[1], other))
            if len(edits) == len(node.values) - 1:
                add("bool", node, edits, word, other, f"논리 {word} → {other}")
            spans = [_paren_wrapped(src, v) for v in node.values]
            for i, v in enumerate(node.values):
                if i < len(node.values) - 1:
                    e = Edit(spans[i][0], spans[i + 1][0], "")
                else:
                    e = Edit(spans[i - 1][1], spans[i][1], "")
                add("operand_drop", v, [e], src.seg(e.start, e.end).strip(), "",
                    f"피연산자 제거 #{i + 1}/{len(node.values)}")
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            s = _start(node)
            o = _paren_wrapped(src, node.operand)[0]
            add("not_rm", node, [Edit(s, o, "")], src.seg(s, o).strip(), "", "not 제거")
        elif isinstance(node, ast.Constant) and type(node.value) in (int, float):
            orig = src.seg(_start(node), _end(node))
            if isinstance(node.value, int):
                new = "1" if node.value == 0 else "0"
            else:
                new = "1.0" if node.value == 0 else "0.0"
            add("const", node, [Edit(_start(node), _end(node), new)], orig, new, f"상수 {orig} → {new}")
        elif isinstance(node, ast.BinOp) and type(node.op) in ARITH_MAP:
            a, b = ARITH_MAP[type(node.op)]
            pos = _op_tokens(src, _end(node.left), _start(node.right), a)
            if pos:
                add("arith", node, [Edit(pos[0], pos[1], b)], a, b, f"산술 {a} → {b}")
        elif isinstance(node, ast.AugAssign) and type(node.op) in ARITH_MAP:
            a, b = ARITH_MAP[type(node.op)]
            pos = _op_tokens(src, _end(node.target), _start(node.value), a + "=")
            if pos:
                add("arith", node, [Edit(pos[0], pos[1], b + "=")], a + "=", b + "=", f"산술 {a}= → {b}=")
        if isinstance(node, ast.Return) and node.value is not None and \
                not (isinstance(node.value, ast.Constant) and node.value.value is None):
            s, e = _start(node.value), _end(node.value)
            add("return_none", node, [Edit(s, e, "None")], src.seg(s, e)[:60], "None", "return 값 → None")
        if isinstance(node, (ast.Assign, ast.AugAssign)) or (isinstance(node, ast.AnnAssign) and node.value is not None):
            s, e = _start(node), _end(node)
            nl = src.seg(s, e).count("\n")
            add("assign_del", node, [Edit(s, e, "pass" + "\n" * nl)], src.seg(s, e).split("\n")[0][:60], "pass",
                "대입문 삭제")

    out.sort(key=lambda m: (m.line, m.edits[0].start[1], OPERATORS.index(m.operator), m.description))
    for i, m in enumerate(out, 1):
        m.id = f"{module}:{i:03d}"
    return out


def mutated_text(text: str, m: Mutant) -> str:
    return Source(text).apply(m.edits)


def validate(text: str, m: Mutant) -> Optional[str]:
    """무효 사유(없으면 None): 원본과 같음 / 파싱 실패 / 줄 수 변경."""
    new = mutated_text(text, m)
    if new == text:
        return "원본과 같음"
    if new.count("\n") != text.count("\n"):
        return "줄 수 변경"
    try:
        ast.parse(new)
    except SyntaxError as ex:
        return f"파싱 실패: {ex.msg}"
    return None


# ------------------------------------------------------------------ 실행기
def make_copy(dst: Path) -> None:
    shutil.copytree(ROOT / "thesis_v2", dst / "thesis_v2",
                    ignore=shutil.ignore_patterns("results", "__pycache__", "*.pyc"))


def _env():
    e = dict(os.environ)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e["PYTHONUTF8"] = "1"
    e.pop("PYTHONPATH", None)
    return e


def _clear_pycache(copy: Path):
    for d in copy.rglob("__pycache__"):
        shutil.rmtree(d, ignore_errors=True)


def run_pytest(copy: Path, args: List[str], timeout: float) -> Dict:
    junit = copy / "_junit.xml"
    if junit.exists():
        junit.unlink()
    cmd = [sys.executable, "-m", "pytest", *args, "-x", "-q", "-p", "no:cacheprovider", f"--junitxml={junit}"]
    t = time.perf_counter()
    try:
        r = subprocess.run(cmd, cwd=copy, env=_env(), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return dict(status="timeout", seconds=round(time.perf_counter() - t, 2))
    sec = round(time.perf_counter() - t, 2)
    if r.returncode == 0:
        return dict(status="pass", seconds=sec)
    kind, first = "killed_exception", None
    if junit.exists():
        try:
            root = ET.parse(junit).getroot()
            for tc in root.iter("testcase"):
                for tag in ("failure", "error"):
                    el = tc.find(tag)
                    if el is not None and first is None:
                        first = f"{tc.get('classname')}::{tc.get('name')}"
                        msg = (el.get("message") or "") + " " + (el.text or "")[:400]
                        ftype = el.get("type") or ""
                        if tag == "failure" and ("AssertionError" in ftype or msg.lstrip().startswith("assert")
                                                 or "AssertionError" in msg):
                            kind = "killed"
        except ET.ParseError:
            pass
    return dict(status=kind, seconds=sec, returncode=r.returncode, first_failure=first,
                tail=r.stdout[-300:] if first is None else None)


DIFF_RE = re.compile(r"max\|diff\|=([0-9.eE+-]+)")


def run_golden(copy: Path, timeout: float) -> Dict:
    t = time.perf_counter()
    try:
        r = subprocess.run([sys.executable, "-m", "thesis_v2.tests.check_golden"], cwd=copy, env=_env(),
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return dict(status="timeout", seconds=round(time.perf_counter() - t, 2))
    diffs = [float(x) for x in DIFF_RE.findall(r.stdout)]
    n_fail = r.stdout.count("[FAIL]")
    st = "pass" if r.returncode == 0 else ("killed" if n_fail else "killed_exception")
    return dict(status=st, seconds=round(time.perf_counter() - t, 2), max_diff_rad=(max(diffs) if diffs else None),
                n_scenarios_with_diff=len(diffs), n_fail=n_fail)


def pc_load() -> Dict:
    info = dict(host=socket.gethostname(), platform=platform.platform(), logical_cpus=os.cpu_count())
    if os.name == "nt":
        ps = ("$c=(Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average;"
              "$p=Get-Process | Sort-Object CPU -Descending | Select-Object -First 8 Name,"
              "@{n='cpu_s';e={[math]::Round($_.CPU,1)}},@{n='ws_mb';e={[math]::Round($_.WorkingSet64/1MB)}};"
              "[pscustomobject]@{cpu_load_percent=$c;top_by_cpu_time=$p} | ConvertTo-Json -Depth 3")
        try:
            r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=60)
            info.update(json.loads(r.stdout))
        except Exception as ex:  # 기록 실패도 사실대로 남긴다
            info["error"] = repr(ex)
    return info


def coverage_lines(copy: Path) -> Dict[str, List[int]]:
    """깨끗한 사본에서 L2+L3 범위를 coverage로 한 번 돌려, 대상 파일의 실행된 줄을 얻는다."""
    inc = ",".join(TARGETS[m]["path"] for m in TARGETS)
    data = copy / "_cov"
    env = _env(); env["COVERAGE_FILE"] = str(data)
    subprocess.run([sys.executable, "-m", "coverage", "run", f"--include={inc}", "-m", "pytest",
                    "thesis_v2/tests", "thesis_v2/anomaly/tests", "-q", "-p", "no:cacheprovider"],
                   cwd=copy, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = copy / "_cov.json"
    subprocess.run([sys.executable, "-m", "coverage", "json", "-o", str(out)], cwd=copy, env=env,
                   capture_output=True, text=True)
    d = json.loads(out.read_text(encoding="utf-8"))
    res = {}
    for f, v in d["files"].items():
        res[Path(f).as_posix()] = sorted(v["executed_lines"])
    return res


def git_state() -> Dict:
    def g(*a):
        return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return dict(commit=g("rev-parse", "HEAD"), dirty=bool(g("status", "--porcelain")))


def run_all(out_path: Path, only: Optional[List[str]] = None) -> None:
    modules = only or list(TARGETS)
    raw = dict(tool_version=TOOL_VERSION, started=time.strftime("%Y-%m-%dT%H:%M:%S"), git=git_state(),
               python=sys.version.split()[0], pc_load_before=pc_load(), modules={}, mutants=[])
    tmp = Path(tempfile.mkdtemp(prefix="mut_"))
    try:
        make_copy(tmp)
        _clear_pycache(tmp)
        # 깨끗한 사본 기준 실행(모든 층 통과해야 함) + 시간 측정 → 타임아웃
        base = {}
        for m in modules:
            l1 = run_pytest(tmp, TARGETS[m]["l1"], timeout=600)
            base[m] = dict(l1=l1)
        l2 = run_pytest(tmp, L2_CMD, timeout=1200)
        l3 = run_golden(tmp, timeout=600)
        for m in modules:
            if base[m]["l1"]["status"] != "pass" or l2["status"] != "pass" or l3["status"] != "pass":
                raise SystemExit(f"깨끗한 사본이 통과하지 않음: {m} {base[m]} L2={l2} L3={l3}")
        timeouts = {m: dict(l1=max(10.0, 5 * base[m]["l1"]["seconds"]), l2=max(10.0, 5 * l2["seconds"]),
                            l3=max(10.0, 5 * l3["seconds"])) for m in modules}
        raw["clean_run"] = dict(per_module_l1={m: base[m]["l1"] for m in modules}, l2=l2, l3=l3)
        raw["timeouts"] = timeouts
        raw["coverage_executed_lines"] = coverage_lines(tmp)

        for m in modules:
            cfg = TARGETS[m]
            target = tmp / cfg["path"]
            original = (ROOT / cfg["path"]).read_text(encoding="utf-8")
            assert target.read_text(encoding="utf-8") == original
            muts = generate(m, original)
            raw["modules"][m] = dict(path=cfg["path"], ranges=cfg["ranges"], l1=cfg["l1"], l3_applicable=cfg["l3"],
                                     n_generated=len(muts))
            for mu in muts:
                rec = dict(id=mu.id, module=m, path=mu.path, line=mu.line, operator=mu.operator,
                           original=mu.original, replacement=mu.replacement, description=mu.description)
                bad = validate(original, mu)
                if bad:
                    rec.update(status="invalid", invalid_reason=bad)
                    raw["mutants"].append(rec); continue
                target.write_text(mutated_text(original, mu), encoding="utf-8")
                _clear_pycache(tmp)
                layers = {}
                status, first = "survived", None
                r1 = run_pytest(tmp, cfg["l1"], timeouts[m]["l1"]); layers["L1"] = r1
                if r1["status"] != "pass":
                    status, first = r1["status"], "L1"
                else:
                    r2 = run_pytest(tmp, L2_CMD, timeouts[m]["l2"]); layers["L2"] = r2
                    if r2["status"] != "pass":
                        status, first = r2["status"], "L2"
                    elif cfg["l3"]:
                        r3 = run_golden(tmp, timeouts[m]["l3"]); layers["L3"] = r3
                        if r3["status"] != "pass":
                            status, first = r3["status"], "L3"
                    else:
                        layers["L3"] = dict(status="not_applicable")
                rec.update(status=status, first_layer=first, layers=layers)
                raw["mutants"].append(rec)
                target.write_text(original, encoding="utf-8")
                print(f"[{mu.id}] {mu.operator:12s} L{mu.line:<4d} {status:16s} {first or ''}", flush=True)
            assert target.read_text(encoding="utf-8") == original
        raw["pc_load_after"] = pc_load()
        raw["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        raw["git_after"] = git_state()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(raw, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    r = sub.add_parser("run")
    r.add_argument("--out", required=True)
    r.add_argument("--only", nargs="*")
    a = ap.parse_args()
    if a.cmd == "list":
        total = 0
        for m in TARGETS:
            text = (ROOT / TARGETS[m]["path"]).read_text(encoding="utf-8")
            muts = generate(m, text)
            inv = [x for x in muts if validate(text, x)]
            by = {}
            for x in muts:
                by[x.operator] = by.get(x.operator, 0) + 1
            print(f"{m:12s} 생성 {len(muts):4d} (무효 {len(inv)}) {by}")
            total += len(muts)
        print(f"합계 {total}")
    else:
        run_all(ROOT / a.out if not Path(a.out).is_absolute() else Path(a.out), a.only)


if __name__ == "__main__":
    main()
