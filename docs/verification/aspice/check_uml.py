"""UML.md의 Mermaid 그림 3개를 코드와 대조한다(불일치 시 exit 1). 새 패키지 없이 ast·re만 쓴다.

1. 상태도 ↔ thesis_v2/baseline/fsm.py
   - 상태 집합 = FSMState 멤버
   - 전이 집합 (출발, 도착, 행) = step()의 if/elif 구조에서 추출한 것
     (상태 조건 없는 첫 if → SAFE_STOP이 아닌 모든 상태에서 그 목적 상태로, 초기 전이 = initial_fsm 반환 행)
   - 결정 Dk(코드 등장 순서 D0, D1, …)의 가드에 쓰인 config.* 상수·sensors.* 필드·지역 변수가 그림에서 'Dk'가 적힌 행들에 모두 있음
2. 시퀀스도 ↔ 호출 위치
   - '이름() · 파일:행' 표기마다 그 행에 '이름'이 있음
   - anomaly/closed_loop.py 행 번호가 그림 순서대로 증가
3. 컴포넌트도 ↔ 패키지 단위 import 그래프(thesis_v2, tests 제외, improved/student_i4는 별도 패키지)
   - 실선(-->) 집합 = 내부 패키지 의존, 점선(-.->) 집합 = 외부 라이브러리 의존(EXTERNAL 중 실제 import)

사용(저장소 루트): python docs/verification/aspice/check_uml.py
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
UML = Path(__file__).resolve().parent / "UML.md"
FSM = ROOT / "thesis_v2/baseline/fsm.py"
PKG_ROOT = ROOT / "thesis_v2"
EXTERNAL = {"numpy", "scipy", "osqp", "sklearn", "torch", "pandas", "onnx", "onnxruntime", "matplotlib", "joblib"}
# 그림은 손으로 쓴 문서라 자동 재생성 명령이 없다 — 위 불일치 목록대로 UML.md를 고친 뒤 같은 명령으로 다시 확인한다.
FIX_HINT = "docs/verification/aspice/UML.md의 해당 그림을 위 목록대로 코드에 맞게 고친 뒤 재확인: python docs/verification/aspice/check_uml.py"
SKIP_NAMES = {"abs", "config", "sensors", "fsm", "y", "psi_deg", "t", "FSMState"}


def mermaid_block(text, marker):
    i = text.index(f"<!-- uml:{marker} -->")
    s = text.index("```mermaid", i) + len("```mermaid")
    e = text.index("```", s)
    return text[s:e].splitlines()


# ------------------------------------------------------------------ 1. 상태도
def fsm_from_code():
    tree = ast.parse(FSM.read_text(encoding="utf-8"))
    enum = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "FSMState")
    states = {t.id for st in enum.body if isinstance(st, ast.Assign) for t in st.targets}
    step = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "step")
    init = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "initial_fsm")

    def target_of(body):
        for st in body:
            if isinstance(st, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "new_state" for t in st.targets):
                v = st.value
                if isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and v.value.id == "FSMState":
                    return v.attr
        return None

    def guard_tokens(test):
        toks = set()
        for n in ast.walk(test):
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id in ("config", "sensors"):
                toks.add(n.attr)
            elif isinstance(n, ast.Name) and n.id not in SKIP_NAMES:
                toks.add(n.id)
        return toks

    transitions, guards = set(), {}
    top = next(n for n in step.body if isinstance(n, ast.If))
    node, k = top, 0
    while node is not None:
        t = node.test
        is_state = (isinstance(t, ast.Compare) and isinstance(t.left, ast.Attribute) and t.left.attr == "state")
        if not is_state:  # 상태 조건 없는 결정(D0)
            dst = target_of(node.body)
            if dst:
                for s in states - {dst}:
                    transitions.add((s, dst, node.lineno))
                guards[f"D{k}"] = guard_tokens(t)
                k += 1
        else:
            src = t.comparators[0].attr
            for inner in node.body:
                if isinstance(inner, ast.If):
                    dst = target_of(inner.body)
                    if dst:
                        transitions.add((src, dst, inner.lineno))
                        toks = guard_tokens(inner.test)
                        # 가드에 쓰인 지역 변수(예: elapsed)는 그대로 요구한다
                        guards[f"D{k}"] = toks
                        k += 1
        nxt = node.orelse
        node = nxt[0] if len(nxt) == 1 and isinstance(nxt[0], ast.If) else None
    ret = next(n for n in ast.walk(init) if isinstance(n, ast.Return))
    init_state = next(kw.value.attr for kw in ret.value.keywords if kw.arg == "state")
    transitions.add(("[*]", init_state, ret.lineno))
    return states, transitions, guards


def check_state(text, errors):
    states, code_tr, guards = fsm_from_code()
    lines = mermaid_block(text, "state")
    fig_tr, fig_states = set(), set()
    for ln in lines:
        m = re.match(r"^\s*(\[\*\]|\w+)\s*-->\s*(\w+)\s*:(.*)$", ln)
        if not m:
            continue
        ref = re.search(r"\[fsm\.py:(\d+)\]", m.group(3))
        if not ref:
            errors.append(f"상태도: 행 번호 없는 전이 '{ln.strip()}'")
            continue
        fig_tr.add((m.group(1), m.group(2), int(ref.group(1))))
        fig_states |= {m.group(1), m.group(2)} - {"[*]"}
    if fig_states != states:
        errors.append(f"상태도: 상태 불일치 그림={sorted(fig_states)} 코드={sorted(states)}")
    for x in sorted(code_tr - fig_tr):
        errors.append(f"상태도: 코드에 있고 그림에 없는 전이 {x}")
    for x in sorted(fig_tr - code_tr):
        errors.append(f"상태도: 그림에 있고 코드에 없는 전이 {x}")
    for d, toks in sorted(guards.items()):
        text_d = " ".join(ln for ln in lines if re.search(rf"\b{d}\b", ln))
        missing = [tk for tk in sorted(toks) if not re.search(rf"\b{re.escape(tk)}\b", text_d)]
        if missing:
            errors.append(f"상태도: {d} 가드 토큰 누락 {missing}")
    return len(code_tr), len(states), len(guards)


# ------------------------------------------------------------------ 2. 시퀀스도
def check_sequence(text, errors):
    refs = []
    for ln in mermaid_block(text, "sequence"):
        for m in re.finditer(r"([\w.]+)\(\) · ([\w/]+\.py):(\d+)", ln):
            refs.append((m.group(1), m.group(2), int(m.group(3))))
    for name, path, line in refs:
        src = (PKG_ROOT / path).read_text(encoding="utf-8").splitlines()
        if not (1 <= line <= len(src)) or name not in src[line - 1]:
            errors.append(f"시퀀스도: {path}:{line}에 '{name}' 없음")
    main = [line for _, path, line in refs if path == "anomaly/closed_loop.py"]
    if main != sorted(main) or len(set(main)) != len(main):
        errors.append(f"시퀀스도: anomaly/closed_loop.py 행 순서가 증가하지 않음 {main}")
    return len(refs)


# ------------------------------------------------------------------ 3. 컴포넌트도
def package_of(parts):
    if parts[0] == "improved" and len(parts) > 1 and parts[1] == "student_i4":
        return "student_i4"
    return parts[0]


def import_graph():
    internal, external = set(), set()
    for f in sorted(PKG_ROOT.rglob("*.py")):
        parts = f.relative_to(PKG_ROOT).parts
        if len(parts) == 1 or parts[0] in ("tests", "results") or "tests" in parts:
            continue
        src = package_of(parts)
        modparts = list(f.relative_to(PKG_ROOT).with_suffix("").parts)
        for n in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom):
                if n.level:
                    base = modparts[:-n.level]
                    mods = [".".join(["thesis_v2"] + base + ([n.module] if n.module else []))]
                elif n.module:
                    mods = [n.module]
            for m in mods:
                head = m.split(".")[0]
                if m.startswith("thesis_v2."):
                    dst = package_of(m.split(".")[1:])
                    if dst != src:
                        internal.add((src, dst))
                elif head in EXTERNAL:
                    external.add((src, head))
    return internal, external


def check_component(text, errors):
    internal, external = import_graph()
    fig_int, fig_ext = set(), set()
    for ln in mermaid_block(text, "component"):
        m = re.match(r"^\s*(\w+)\s*(-->|-\.->)\s*(\w+)\s*$", ln)
        if m:
            (fig_int if m.group(2) == "-->" else fig_ext).add((m.group(1), m.group(3)))
    for name, code, fig in (("내부 의존(실선)", internal, fig_int), ("외부 의존(점선)", external, fig_ext)):
        for x in sorted(code - fig):
            errors.append(f"컴포넌트도: {name} 코드에 있고 그림에 없음 {x}")
        for x in sorted(fig - code):
            errors.append(f"컴포넌트도: {name} 그림에 있고 코드에 없음 {x}")
    return len(internal), len(external)


def main():
    text = UML.read_text(encoding="utf-8")
    errors = []
    n_tr, n_st, n_dec = check_state(text, errors)
    n_ref = check_sequence(text, errors)
    n_int, n_ext = check_component(text, errors)
    if errors:
        for e in errors:
            print(f"[check_uml] 불일치: {e}")
        print(f"[check_uml] 수정 방법: {FIX_HINT}")
        sys.exit(1)
    print(f"[check_uml] 일치: 상태도(상태 {n_st}, 전이 {n_tr}, 가드 결정 {n_dec}), "
          f"시퀀스도(호출 위치 {n_ref}), 컴포넌트도(내부 의존 {n_int}, 외부 의존 {n_ext})")


if __name__ == "__main__":
    main()
