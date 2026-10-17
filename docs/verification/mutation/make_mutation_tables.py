"""mutation 원자료 → MUTATION_TABLES.md (PREREGISTRATION §9, RESULTS.md의 수치 근거).

입력(읽기 전용):
- raw/run_before.json (1차, 보강 전), raw/run_after.json (2차, 보강 후) — mutate.py run 출력
- equivalence.json — 1차 생존 변이 분류(확정)
- raw/run_after_tl_recheck.json — RESULTS.md 사전 선언 변경 5번 kill 재확인(있을 때만)

출력: MUTATION_TABLES.md (LF, 결정적 — 같은 입력이면 바이트 단위로 같다)

사용(저장소 루트):
  python docs/verification/mutation/make_mutation_tables.py           # 생성
  python docs/verification/mutation/make_mutation_tables.py --check   # 저장본과 바이트 비교(CI)
"""
import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "MUTATION_TABLES.md"
MODULES = ("fsm", "detector_a", "closed_loop", "baseline_mpc")
CAUGHT = ("killed", "killed_exception", "timeout")
CLASS_KO = collections.OrderedDict([
    ("equivalent_judgement", "등가(판단)"),
    ("boundary_unverified_low_risk", "경계 동치 미검증(저위험)"),
    ("differs_only_on_unreachable_input", "도달 불가 입력에서만 차이"),
    ("pending_external_library", "보류(외부 라이브러리)"),
    ("test_gap", "테스트 공백"),
    ("within_tolerance_measured_zero", "MPC 측정: 허용오차 내, max|diff|=0"),
    ("within_tolerance_measured_nonzero", "MPC 측정: 허용오차 내, max|diff|>0"),
])
SOURCES = ("raw/run_before.json", "raw/run_after.json", "equivalence.json", "raw/run_after_tl_recheck.json")


def load(rel):
    p = HERE / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def sha(rel):
    p = HERE / rel
    # 체크아웃 줄바꿈(core.autocrlf)과 무관하게 같은 값이 나오도록 CRLF를 LF로 바꿔 해시한다
    return hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:16] if p.exists() else "(없음)"


def pct(a, b):
    return f"{100.0 * a / b:.1f}%" if b else "—"


def table(header, rows):
    esc = lambda c: str(c).replace("|", r"\|")  # noqa: E731  셀 안의 |(예: max|diff|)가 표를 깨지 않게
    out = ["| " + " | ".join(esc(h) for h in header) + " |",
           "|" + "|".join("---" if i == 0 else "---:" for i in range(len(header))) + "|"]
    out += ["| " + " | ".join(esc(c) for c in r) + " |" for r in rows]
    return out


def build():
    runs = collections.OrderedDict([("1차(보강 전)", load("raw/run_before.json")), ("2차(보강 후)", load("raw/run_after.json"))])
    eqf = load("equivalence.json")
    eq = {m["id"]: m for m in eqf["mutants"]}
    equiv = {k for k, v in eq.items() if v["classification"].startswith("equivalent")}
    reinforce = sorted(k for k, v in eq.items() if v.get("reinforce"))
    L = ["# Mutation 표 (자동 생성)", "",
         "> `make_mutation_tables.py`가 원자료에서 만든다. 손으로 고치지 않는다. CI는 `--check`로 바이트 비교한다.",
         "> 점수 규칙은 PREREGISTRATION.md §5: 원점수 = 잡힘 / (전체 − 무효), 등가 제외 점수 = 잡힘 / (전체 − 무효 − 등가(판단)).",
         "> 잡힘 = killed + killed_exception + timeout. 등가(판단)는 1차 생존 변이 분류(equivalence.json, 확정)를 두 실행 모두에 쓴다.", ""]

    L += ["## 1. 실행 조건", ""]
    rows = []
    for name, r in runs.items():
        cr = r["clean_run"]
        l1 = ", ".join(f"{m} {cr['per_module_l1'][m]['seconds']}" for m in MODULES)
        to = r["timeouts"]
        rows.append([name, r["git"]["commit"][:7], str(r["git"]["dirty"]).lower(), f"{r['started']} ~ {r['finished']}",
                     r["python"], f"{r['pc_load_before'].get('cpu_load_percent')} / {r['pc_load_after'].get('cpu_load_percent')}",
                     l1, cr["l2"]["seconds"], cr["l3"]["seconds"],
                     f"L1 {'/'.join(str(to[m]['l1']) for m in MODULES)}, L2 {to['fsm']['l2']}, L3 {to['fsm']['l3']}"])
    L += table(["실행", "커밋", "git dirty", "시각", "Python", "CPU % 전/후", "깨끗한 사본 L1 s (모듈별)", "L2 s", "L3 s",
                "타임아웃 s (L1 fsm/detector_a/closed_loop/baseline_mpc)"], rows)
    L += [""]

    L += ["## 2. 점수(모듈별)", ""]
    rows = []
    for name, r in runs.items():
        ms = r["mutants"]
        tot = collections.Counter()
        for mod in MODULES + ("합계",):
            sel = ms if mod == "합계" else [m for m in ms if m["module"] == mod]
            n = len(sel)
            inv = sum(m["status"] == "invalid" for m in sel)
            k = sum(m["status"] == "killed" for m in sel)
            ke = sum(m["status"] == "killed_exception" for m in sel)
            to = sum(m["status"] == "timeout" for m in sel)
            c = k + ke + to
            e = sum(m["id"] in equiv for m in sel)
            rows.append([name, mod, n, inv, c, k, ke, to, pct(c, n - inv), e, f"{pct(c, n - inv - e)} ({c}/{n - inv - e})"])
    L += table(["실행", "모듈", "전체", "무효", "잡힘", "killed", "killed_exception", "timeout", "원점수", "등가(판단)", "등가 제외 점수"], rows)
    L += [""]

    L += ["## 3. 처음 잡힌 층", ""]
    rows = []
    for name, r in runs.items():
        for mod in MODULES:
            c = collections.Counter(m.get("first_layer") for m in r["mutants"] if m["module"] == mod and m["status"] in CAUGHT)
            rows.append([name, mod, c.get("L1", 0), c.get("L2", 0), c.get("L3", 0)])
    L += table(["실행", "모듈", "L1", "L2", "L3"], rows)
    L += [""]

    b = {m["id"]: m for m in runs["1차(보강 전)"]["mutants"]}
    a = {m["id"]: m for m in runs["2차(보강 후)"]["mutants"]}
    L += ["## 4. 1차 → 2차 변화", ""]
    same = sorted(b) == sorted(a) and all((b[i]["line"], b[i]["original"], b[i]["replacement"]) ==
                                          (a[i]["line"], a[i]["original"], a[i]["replacement"]) for i in b)
    L += [f"- 두 실행의 변이 정의(ID·행·원본·치환) 동일: {'예' if same else '아니오'} ({len(b)}개)"]
    tr = collections.Counter((b[i]["status"], a[i]["status"]) for i in b if b[i]["status"] != a[i]["status"])
    for (s0, s1), n in sorted(tr.items()):
        L += [f"- {s0} → {s1}: {n}"]
    lost = sorted(i for i in b if b[i]["status"] in CAUGHT and a[i]["status"] not in CAUGHT)
    L += [f"- 1차에서 잡혔는데 2차에서 잡히지 않은 변이: {len(lost)}" + (f" — {', '.join(lost)}" if lost else "")]
    rc = sum(a[i]["status"] in CAUGHT for i in reinforce)
    miss = [i for i in reinforce if a[i]["status"] not in CAUGHT]
    L += [f"- 보강 대상(equivalence.json `reinforce`) {len(reinforce)}개 중 2차에서 잡힘: {rc}" + (f" (안 잡힘: {', '.join(miss)})" if miss else "")]
    newly = sorted(i for i in b if b[i]["status"] not in CAUGHT and a[i]["status"] in CAUGHT)
    L += [f"- 2차에서 새로 잡힌 변이: {len(newly)} (그중 보강 대상 {sum(i in reinforce for i in newly)})"]
    lay = collections.Counter((b[i].get("first_layer"), a[i].get("first_layer")) for i in b
                              if b[i]["status"] in CAUGHT and a[i]["status"] in CAUGHT and b[i].get("first_layer") != a[i].get("first_layer"))
    for (l0, l1), n in sorted(lay.items()):
        ids = sorted(i for i in b if b[i]["status"] in CAUGHT and a[i]["status"] in CAUGHT
                     and (b[i].get("first_layer"), a[i].get("first_layer")) == (l0, l1))
        L += [f"- 두 실행 모두 잡혔고 처음 잡힌 층이 바뀐 변이 {l0} → {l1}: {n} ({', '.join(ids)})"]
    L += [""]

    L += ["## 5. 생존 변이 분류 (equivalence.json 기준)", ""]
    rows = []
    for name, r in runs.items():
        surv = [m for m in r["mutants"] if m["status"] == "survived"]
        for mod in MODULES:
            c = collections.Counter(eq[m["id"]]["classification"] if m["id"] in eq else "unclassified"
                                    for m in surv if m["module"] == mod)
            rows.append([name, mod, sum(c.values())] + [c.get(k, 0) for k in CLASS_KO] + [c.get("unclassified", 0)])
    L += table(["실행", "모듈", "생존"] + list(CLASS_KO.values()) + ["분류 없음"], rows)
    L += ["", "- 2차 생존 변이 목록:"]
    for m in sorted((m for m in a.values() if m["status"] == "survived"), key=lambda m: (MODULES.index(m["module"]), m["id"])):
        l3 = (m["layers"].get("L3") or {}).get("max_diff_rad")
        L += [f"  - `{m['id']}` L{m['line']} {m['operator']}: {CLASS_KO.get(eq.get(m['id'], {}).get('classification'), '분류 없음')}"
              + (f", L3 max|diff| {l3}" if l3 not in (None, 0.0) else "")]
    L += [""]

    L += ["## 6. 커버리지 대조 (깨끗한 사본에서 L2+L3 범위로 실행된 줄)", ""]
    rows = []
    for name, r in runs.items():
        cov = {k: set(v) for k, v in r["coverage_executed_lines"].items()}
        for mod in MODULES:
            path = r["modules"][mod]["path"]
            surv = [m for m in r["mutants"] if m["module"] == mod and m["status"] == "survived"]
            on = [m for m in surv if m["line"] in cov.get(path, set())]
            rows.append([name, mod, len(surv), len(on), len(surv) - len(on),
                         ", ".join(sorted(m["id"] for m in surv if m["line"] not in cov.get(path, set()))) or "—"])
    L += table(["실행", "모듈", "생존", "실행된 줄에서 생존", "실행되지 않은 줄에서 생존", "실행되지 않은 줄의 생존 변이"], rows)
    L += [""]

    rc_ = load("raw/run_after_tl_recheck.json")
    if rc_:
        L += ["## 7. time_limit kill 재확인 (RESULTS.md 사전 선언 변경 5)", ""]
        v = rc_["verdict"]
        cnt = collections.Counter(x["verdict"] for x in v.values())
        bym = collections.Counter(c["first_failure"].split("::")[0] for c in rc_["candidates"])
        L += [f"- 대상 실행: `{rc_['run']}` (커밋 {rc_['run_git']['commit'][:7]}), 반복 {rc_['repeats']}회, 시각 {rc_['started']} ~ {rc_['finished']}",
              f"- kill {rc_['n_kills']}개 중 대상(첫 실패 테스트가 time_limit 켠 I5 MPC 사용) {rc_['n_targets_all']}개, 재확인 {len(v)}개",
              f"- 판정: " + ", ".join(f"{k} {n}" for k, n in sorted(cnt.items())),
              f"- 대상의 첫 실패 테스트 모듈: " + ", ".join(f"`{k}` {n}" for k, n in sorted(bym.items())),
              f"- timeout 등 first_failure 없음으로 제외: {len(rc_['skipped_timeouts'])}"]
        rev = sorted(k for k, x in v.items() if x["verdict"] != "kill 유지")
        L += [f"- 재검토: {', '.join(rev) if rev else '없음'}", ""]

    L += ["## 원자료", ""]
    L += [f"- `{s}` sha256 앞 16자리 `{sha(s)}`" for s in SOURCES]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = build()
    if a.check:
        cur = OUT.read_bytes().decode("utf-8") if OUT.exists() else None
        if cur != text:
            print("[make_mutation_tables --check] 불일치: MUTATION_TABLES.md — 다시 생성해 차이를 확인할 것")
            print("[make_mutation_tables --check] 재생성 명령(저장소 루트): python docs/verification/mutation/make_mutation_tables.py"
                  " && git diff -- docs/verification/mutation/MUTATION_TABLES.md")
            sys.exit(1)
        print("[make_mutation_tables --check] 일치: MUTATION_TABLES.md")
        return
    OUT.write_bytes(text.encode("utf-8"))
    print(f"[make_mutation_tables] 생성: {OUT.name} ({len(text.splitlines())}줄)")


if __name__ == "__main__":
    main()
