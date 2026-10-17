"""FMEA·FTTI 분석 수치 생성기 — 이미 있는 이상탐지 평가 결과 CSV만 읽는다(평가 재실행 없음, 결과 폴더 무수정).

출력: docs/verification/safety/SAFETY_TABLES.md, safety_numbers.json (POSIX 경로·LF·정렬 고정)
사용(저장소 루트):
  python docs/verification/safety/make_safety_tables.py           # 생성
  python docs/verification/safety/make_safety_tables.py --check   # 다시 계산해 저장본과 바이트 비교(다르면 exit 1)

입력(모두 git 추적 파일):
- 폐루프 평가 CL_DIR/episodes_{P0,P1_A,P1_B1,P1_B2,P1_HYBRID,P2_A}.csv
  열: run, seed, outcome, total_steps, finish_step, onset, duration, first_alarm_step, first_alarm_channel,
      policy_action, unnecessary_stop
- CL_DIR/diag_timing.csv (combo, run, seed, time_limit_hits, max_solve_ms), CL_DIR/meta.json, CL_DIR/summary.json(교차 대조)
- 오프라인 평가 OFF_DIR/episodes_{A,B1,B2,HYBRID}.csv
  열: run, seed, outcome, total_steps, onset, first_alarm, detected, delay_steps, alarm_before_onset, alarm_before_failure
- OFF_DIR/summary.json(교차 대조)
- 코드 근거(읽기만): baseline/config.py의 DT, anomaly/closed_loop.py의 FAILURE_OUTCOMES·HARMFUL_KINDS·HARMLESS_KINDS

유도 규칙(코드 근거):
- 위험 사건 = outcome ∈ FAILURE_OUTCOMES({충돌, 이탈}). 사건 스텝 = total_steps
  (closed_loop.py에서 충돌·이탈이면 그 step_idx에서 break하고 total_steps=step_idx로 기록).
- 고장 시작 스텝 = onset(faults.py: 1부터, runner step_idx 기준, k ≥ onset이면 활성).
- 시간 = 스텝 × DT.
"""
import argparse
import ast
import csv
import json
import math
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT_DIR = Path(__file__).resolve().parent
OUT_MD = OUT_DIR / "SAFETY_TABLES.md"
OUT_JSON = OUT_DIR / "safety_numbers.json"
REGEN_CMD = ("python docs/verification/safety/make_safety_tables.py && git diff -- "
             "docs/verification/safety/SAFETY_TABLES.md docs/verification/safety/safety_numbers.json")

CL_DIR = "thesis_v2/results/anomaly/20261012_142758_3층PC109_it3_closed_loop_eval"
OFF_DIR = "thesis_v2/results/anomaly/20261002_145638_3층PC108_it3_eval_offline_eval"
CONFIG_PY = "thesis_v2/baseline/config.py"
CLOSED_LOOP_PY = "thesis_v2/anomaly/closed_loop.py"
COMBOS = ["P0", "P1_A", "P1_B1", "P1_B2", "P1_HYBRID", "P2_A"]
DETECTORS = ["A", "B2", "HYBRID", "B1"]          # 표 순서(A 주 대상, 나머지 참고)
BACKLOG = "repro/docs/IMPROVEMENT_BACKLOG.md"

# 결과 심각도(시뮬레이션) — 결과(outcome) 문자열에 묶인 순서 척도. ISO 26262 S0~S3(부상 정도)와 다르다.
SEVERITY = [
    (4, "충돌", {"충돌"}),
    (3, "이탈", {"이탈"}),
    (2, "미완료(타임아웃·미정착·관찰 중 상태 이탈)", {"타임아웃", "미정착", "관찰 중 상태 이탈"}),
    (1, "정지(SAFE_STOP·탐지 정지 — 안전 상태이나 임무 미완료)", {"SAFE_STOP", "탐지 정지"}),
    (0, "성공", {"성공"}),
]
INTENDED_SAFE_STOP_RUNS = {"none_leftobs"}  # 좌측 장애물 정상 시나리오: SAFE_STOP이 기대 결과(MEASURE_PLAN.md P트랙)


def p(path):
    return ROOT / path


def read_csv(path):
    with open(p(path), encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def ival(s):
    return int(s) if s not in ("", None) else None


def code_constant(path, name):
    tree = ast.parse(p(path).read_text(encoding="utf-8"))
    for n in tree.body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets):
            return ast.literal_eval(n.value), n.lineno
    raise SystemExit(f"{path}에 {name} 없음")


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    ph = k / n
    den = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / den
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return [round(max(0.0, c - h) * 100, 1), round(min(1.0, c + h) * 100, 1)]


def dist(vals):
    if not vals:
        return None
    v = sorted(vals)
    return dict(n=len(v), min=v[0], p50=statistics.median(v), max=v[-1])


def severity_of(outcome, run):
    if outcome == "SAFE_STOP" and run in INTENDED_SAFE_STOP_RUNS:
        return 0
    for lv, _, outs in SEVERITY:
        if outcome in outs:
            return lv
    raise SystemExit(f"척도에 없는 outcome: {outcome!r} (run={run})")


def backlog_heading(num):
    for i, ln in enumerate(p(BACKLOG).read_text(encoding="utf-8").splitlines(), 1):
        if ln.startswith(f"## 후보 {num} "):
            return f"{BACKLOG}:{i}"
    raise SystemExit(f"backlog 후보 {num} 없음")


# ------------------------------------------------------------------ 계산
def build():
    dt, dt_line = code_constant(CONFIG_PY, "DT")
    failure, fl = code_constant(CLOSED_LOOP_PY, "FAILURE_OUTCOMES")
    harmful, hl = code_constant(CLOSED_LOOP_PY, "HARMFUL_KINDS")
    harmless, hsl = code_constant(CLOSED_LOOP_PY, "HARMLESS_KINDS")
    faults = sorted(harmful) + sorted(harmless)
    meta = json.loads(p(f"{CL_DIR}/meta.json").read_text(encoding="utf-8"))

    cl = {c: {(r["run"], int(r["seed"])): r for r in read_csv(f"{CL_DIR}/episodes_{c}.csv")} for c in COMBOS}
    keys = sorted(cl["P0"])
    for c in COMBOS:
        assert sorted(cl[c]) == keys, f"{c} 키가 P0와 다름"
    runs = sorted({k[0] for k in keys}, key=lambda r: (r not in faults, faults.index(r) if r in faults else 0, r))
    p0 = cl["P0"]

    def hazard(r):
        return r["outcome"] in failure

    # 교차 대조: 폐루프 summary.json outcome 집계
    cl_sum = json.loads(p(f"{CL_DIR}/summary.json").read_text(encoding="utf-8"))
    for c in COMBOS:
        for kind, v in cl_sum[c].get("per_kind", {}).items():
            for out, n in v["outcome_counts"].items():
                got = sum(1 for (run, _), r in cl[c].items() if run == kind and r["outcome"] == out)
                if got != n:
                    raise SystemExit(f"교차 대조 실패: {c} {kind} {out} summary={n} csv={got}")

    # ---- 전제 확인: P1_X 경보 없는 행 = P0
    premise = {}
    for c in ["P1_A", "P1_B1", "P1_B2", "P1_HYBRID"]:
        no_alarm = [k for k in keys if cl[c][k]["first_alarm_step"] == ""]
        mism = [k for k in no_alarm if any(cl[c][k][f] != p0[k][f] for f in ("outcome", "total_steps", "finish_step"))]
        premise[c] = dict(no_alarm_rows=len(no_alarm), match=len(no_alarm) - len(mism),
                          mismatch=[f"{r}:{s}" for r, s in mism])

    # ---- P0 영향
    effects = {}
    for run in runs:
        rs = [p0[k] for k in keys if k[0] == run]
        cnt = {}
        for r in rs:
            cnt[r["outcome"]] = cnt.get(r["outcome"], 0) + 1
        sev = [severity_of(r["outcome"], run) for r in rs]
        effects[run] = dict(n=len(rs), outcome_counts=dict(sorted(cnt.items())),
                            collision=cnt.get("충돌", 0), departure=cnt.get("이탈", 0),
                            not_completed=sum(1 for r in rs if r["outcome"] != "성공"),
                            worst_severity=max(sev), severity_hist={str(lv): sev.count(lv) for lv in range(4, -1, -1)},
                            hazard_seeds=[int(r["seed"]) for r in rs if hazard(r)] if run not in faults else None)

    # ---- 검출도: 오프라인
    off_sum = json.loads(p(f"{OFF_DIR}/summary.json").read_text(encoding="utf-8"))
    offline = {}
    for det in DETECTORS:
        rows = read_csv(f"{OFF_DIR}/episodes_{det}.csv")
        per = {}
        for run in sorted({r["run"] for r in rows}, key=lambda x: (x not in faults, x)):
            rs = [r for r in rows if r["run"] == run]
            if run in faults:
                started = [r for r in rs if r["onset"] != "" and int(r["onset"]) <= int(r["total_steps"])]
                k = sum(r["detected"] == "1" for r in started)
                fails = [r for r in rs if r["outcome"] in failure]
                delays = [int(r["delay_steps"]) for r in started if r["detected"] == "1"]
                ref = off_sum[det]["per_kind"][run]
                if (k, len(started)) != (ref["detected"], ref["fault_started"]):
                    raise SystemExit(f"교차 대조 실패: 오프라인 {det} {run} csv={k}/{len(started)} "
                                     f"summary={ref['detected']}/{ref['fault_started']}")
                per[run] = dict(started=len(started), detected=k, ci95=wilson(k, len(started)),
                                delay_steps=dist(delays),
                                alarm_before_onset=sum(r["alarm_before_onset"] == "1" for r in rs),
                                failures=len(fails), alarm_before_failure=sum(r["alarm_before_failure"] == "1" for r in fails))
            else:
                k = sum(r["first_alarm"] != "" for r in rs)
                per[run] = dict(n=len(rs), false_alarm_episodes=k, ci95=wilson(k, len(rs)))
        offline[det] = per

    # ---- 검출도: 폐루프 (P1_X vs P0, 같은 seed 쌍)
    closed = {}
    for det in DETECTORS:
        c = f"P1_{det}"
        per = {}
        for run in runs:
            ks = [k for k in keys if k[0] == run]
            h0 = [k for k in ks if hazard(p0[k])]
            per[run] = dict(p0_hazard=len(h0), p1_hazard=sum(hazard(cl[c][k]) for k in ks),
                            prevented=sum(not hazard(cl[c][k]) for k in h0),
                            new_hazard=sum(hazard(cl[c][k]) and not hazard(p0[k]) for k in ks),
                            detect_stop=sum(cl[c][k]["outcome"] == "탐지 정지" for k in ks),
                            unnecessary_stop=sum(cl[c][k]["unnecessary_stop"] != "" for k in ks))
        closed[det] = per

    # ---- FTTI / FDTI / FRTI
    ftti, fdti, cond = {}, {}, {}
    for run in faults:
        ks = [k for k in keys if k[0] == run]
        h0 = [k for k in ks if hazard(p0[k])]
        before = [k for k in h0 if ival(p0[k]["onset"]) is None or int(p0[k]["total_steps"]) < int(p0[k]["onset"])]
        steps = [int(p0[k]["total_steps"]) - int(p0[k]["onset"]) for k in h0 if k not in before]
        ftti[run] = dict(p0_hazard=len(h0), hazard_before_onset=len(before), steps=dist(steps),
                         first_hazard=(min(h0, key=lambda k: int(p0[k]["total_steps"]) - int(p0[k]["onset"]))[1]
                                       if steps else None))
        fdti[run], cond[run] = {}, {}
        for det in DETECTORS:
            for c in ([f"P1_{det}", "P2_A"] if det == "A" else [f"P1_{det}"]):
                rows = {k: cl[c][k] for k in ks}
                after = [k for k in ks if rows[k]["first_alarm_step"] != ""
                         and ival(rows[k]["onset"]) is not None and int(rows[k]["first_alarm_step"]) >= int(rows[k]["onset"])]
                pre = [k for k in ks if rows[k]["first_alarm_step"] != ""
                       and (ival(rows[k]["onset"]) is None or int(rows[k]["first_alarm_step"]) < int(rows[k]["onset"]))]
                fd = [int(rows[k]["first_alarm_step"]) - int(rows[k]["onset"]) for k in after]
                # FRTI: 경보 → 정지(탐지 정지 또는 SAFE_STOP) 스텝, policy_action별
                frti = {}
                for k in after:
                    r = rows[k]
                    act = r["policy_action"] or "(없음)"
                    stopped = r["outcome"] in ("탐지 정지", "SAFE_STOP")
                    e = frti.setdefault(act, dict(n=0, stopped=0, steps=[], other_outcomes={}))
                    e["n"] += 1
                    if stopped:
                        e["stopped"] += 1
                        e["steps"].append(int(r["finish_step"]) - int(r["first_alarm_step"]))
                    else:
                        e["other_outcomes"][r["outcome"]] = e["other_outcomes"].get(r["outcome"], 0) + 1
                for e in frti.values():
                    e["steps"] = dist(e["steps"])
                    e["other_outcomes"] = dict(sorted(e["other_outcomes"].items()))
                fdti[run][c] = dict(alarm_after_onset=len(after), alarm_before_onset=len(pre),
                                    no_alarm=len(ks) - len(after) - len(pre), steps=dist(fd),
                                    frti=dict(sorted(frti.items())))
                # 조건 판정(P0 위험 사건 N회, 고장 시작 후 사건만): 세 범주
                #  만족 = 경보가 onset 이후 ∧ 정지 스텝 s < P0 사건 스텝 e
                #  저하 운행으로 회피 = 경보가 onset 이후 ∧ 정지 안 함(P2 override_ey/rc 등) ∧ 그 조합에서 위험 사건 없음
                #  미달 = 경보 없음 ∨ s ≥ e ∨ (경보 후 정지 안 함 ∧ 위험 사건 발생)
                #  판정 제외(고장 전 오경보) = 경보가 onset 이전
                sat, degraded, miss_no_alarm, miss_late, miss_no_stop, excl = 0, 0, 0, 0, 0, 0
                eligible = [k for k in h0 if k not in before]
                for k in eligible:
                    r, e_step = rows[k], int(p0[k]["total_steps"])
                    if r["first_alarm_step"] == "":
                        miss_no_alarm += 1
                        continue
                    a = int(r["first_alarm_step"])
                    if a < int(r["onset"]):
                        excl += 1
                        continue
                    if r["outcome"] not in ("탐지 정지", "SAFE_STOP"):
                        if hazard(r):
                            miss_no_stop += 1
                        else:
                            degraded += 1
                        continue
                    if int(r["finish_step"]) < e_step:
                        sat += 1
                    else:
                        miss_late += 1
                miss = miss_no_alarm + miss_late + miss_no_stop
                assert sat + degraded + miss + excl == len(eligible)
                cond[run][c] = dict(n=len(eligible), satisfied=sat, degraded_avoided=degraded, shortfall=miss,
                                    excluded_alarm_before_onset=excl,
                                    shortfall_detail=dict(no_alarm=miss_no_alarm, stop_not_before_event=miss_late,
                                                          alarm_but_no_stop=miss_no_stop),
                                    actually_not_hazard=sum(not hazard(rows[k]) for k in eligible))

    # ---- 비주입 이상
    diag = read_csv(f"{CL_DIR}/diag_timing.csv")
    tl = dict(rows=len(diag), hits=sum(int(r["time_limit_hits"]) for r in diag),
              by_combo={c: sum(int(r["time_limit_hits"]) for r in diag if r["combo"] == c) for c in COMBOS},
              max_solve_ms=max(float(r["max_solve_ms"]) for r in diag))
    normal_hazard = {}
    for run in [r for r in runs if r not in faults]:
        for k in keys:
            if k[0] == run and hazard(p0[k]):
                normal_hazard[f"{run}:{k[1]}"] = dict(
                    outcome=p0[k]["outcome"], event_step=int(p0[k]["total_steps"]),
                    by_combo={c: cl[c][k]["outcome"] for c in COMBOS})

    p2_avail = {run: dict(sorted({o: sum(1 for k in keys if k[0] == run and cl["P2_A"][k]["outcome"] == o)
                                   for o in {cl["P2_A"][k]["outcome"] for k in keys if k[0] == run}}.items()))
                for run in runs}

    return dict(
        sources=dict(closed_loop=CL_DIR, offline=OFF_DIR, dt=f"{CONFIG_PY}:{dt_line}",
                     failure_outcomes=f"{CLOSED_LOOP_PY}:{fl}", harmful_kinds=f"{CLOSED_LOOP_PY}:{hl}",
                     harmless_kinds=f"{CLOSED_LOOP_PY}:{hsl}", backlog_13=backlog_heading(13),
                     backlog_14=backlog_heading(14), seeds=meta["seeds"], thresholds=meta["h_by_detector"]),
        dt=dt, failure_outcomes=sorted(failure), harmful=sorted(harmful), harmless=sorted(harmless),
        severity_scale=[dict(level=lv, name=nm, outcomes=sorted(o)) for lv, nm, o in SEVERITY],
        premise=premise, effects=effects, offline=offline, closed=closed, ftti=ftti, fdti=fdti, condition=cond,
        time_limit=tl, normal_hazard=normal_hazard, p2_a_outcomes=p2_avail,
    )


# ------------------------------------------------------------------ 표 출력
def sec(steps, dt):
    return f"{steps * dt:.2f}"


def fmt_dist(d, dt):
    if not d:
        return "데이터 없음"
    p50 = d["p50"]
    p50s = f"{p50:g}"
    return (f"n={d['n']}: 최소 {d['min']}({sec(d['min'], dt)} s) / p50 {p50s}({sec(p50, dt)} s) / "
            f"최대 {d['max']}({sec(d['max'], dt)} s)")


def ci(c):
    return f"[{c[0]}, {c[1]}]%" if c else "—"


def render(d):
    dt, L = d["dt"], []
    s = d["sources"]
    L += ["# 안전 분석 수치표 (자동 생성)", "",
          "<!-- make_safety_tables.py가 생성. 손으로 고치지 않는다. 확인: python docs/verification/safety/make_safety_tables.py --check -->", "",
          "ISO 26262·AIAG-VDA FMEA의 용어와 틀을 빌려 시뮬레이션 결과를 정리한 수치이며, 표준 준수나 안전 인증이 아니다.", "",
          f"- 폐루프 평가: `{s['closed_loop']}` (seed {s['seeds'][0]}~{s['seeds'][1]}), 오프라인 평가: `{s['offline']}`",
          f"- dt = {dt} s (`{s['dt']}`). 스텝 차이에 dt를 곱해 초로 바꾼다.",
          f"- 위험 사건 = outcome ∈ {d['failure_outcomes']} (`{s['failure_outcomes']}`), 사건 스텝 = `total_steps`.",
          f"- 유해 고장 {d['harmful']} (`{s['harmful_kinds']}`), 무해 고장 {d['harmless']} (`{s['harmless_kinds']}`).", ""]

    L += ["## T0. FDTI 근사의 전제 확인 — P1_X에서 경보가 없는 행이 P0와 같은가", "",
          "탐지기는 경보 전까지 관찰만 하므로 경보가 없는 에피소드는 P0와 같아야 한다(열: outcome, total_steps, finish_step).", "",
          "| 조합 | 경보 없는 행 | P0와 일치 | 불일치 seed |", "|---|---:|---:|---|"]
    for c, v in d["premise"].items():
        L.append(f"| {c} | {v['no_alarm_rows']} | {v['match']} | {', '.join(v['mismatch']) or '없음'} |")

    L += ["", "## T1. 결과 심각도(시뮬레이션) 척도", "",
          "| 수준 | 이름 | outcome |", "|---:|---|---|"]
    for e in d["severity_scale"]:
        L.append(f"| {e['level']} | {e['name']} | {', '.join(e['outcomes'])} |")
    L.append(f"| 0 | 의도된 SAFE_STOP | {', '.join(sorted(INTENDED_SAFE_STOP_RUNS))}의 SAFE_STOP |")

    L += ["", "## T2. 영향 — P0(탐지 없음) 폐루프, run별 100회 중 N회", "",
          "열 출처: `episodes_P0.csv`의 run, outcome.", "",
          "| run | 충돌 | 이탈 | 미완료(성공 아님) | outcome 분포 | 결과 심각도 최댓값 | 수준별 횟수(4/3/2/1/0) |",
          "|---|---|---|---|---|---:|---|"]
    for run, e in d["effects"].items():
        dist_txt = ", ".join(f"{o} {n}" for o, n in e["outcome_counts"].items())
        hist = "/".join(str(e["severity_hist"][str(lv)]) for lv in range(4, -1, -1))
        L.append(f"| {run} | {e['n']}회 중 {e['collision']}회 | {e['n']}회 중 {e['departure']}회 | "
                 f"{e['n']}회 중 {e['not_completed']}회 | {dist_txt} | {e['worst_severity']} | {hist} |")

    L += ["", "## T3. 검출도 — 오프라인 탐지율 (고장 시작된 에피소드 중 탐지, Wilson 95% CI)", "",
          "열 출처: `episodes_<탐지기>.csv`의 onset, total_steps, detected, delay_steps, alarm_before_onset, alarm_before_failure. "
          "고장 시작 = onset ≤ total_steps(eval_offline.py와 같은 정의). summary.json과 교차 대조함. B1·HYBRID는 IF 시간 문제(backlog 후보 14) 대상.", "",
          "| run | " + " | ".join(f"{det} 탐지 k/n [CI]" for det in DETECTORS) + " | A 탐지 지연(스텝) | A 사건 전 경보 / 위험 사건 |",
          "|---|" + "---|" * (len(DETECTORS) + 2)]
    for run in d["offline"]["A"]:
        cells = []
        for det in DETECTORS:
            v = d["offline"][det][run]
            if "detected" in v:
                cells.append(f"{v['detected']}/{v['started']} {ci(v['ci95'])}")
            else:
                cells.append(f"오경보 {v['false_alarm_episodes']}/{v['n']} {ci(v['ci95'])}")
        a = d["offline"]["A"][run]
        delay = fmt_dist(a.get("delay_steps"), dt) if "detected" in a else "—"
        abf = f"{a['alarm_before_failure']}/{a['failures']}" if "detected" in a else "—"
        L.append(f"| {run} | " + " | ".join(cells) + f" | {delay} | {abf} |")

    L += ["", "## T4. 검출도 — 폐루프 P1(첫 경보 즉시 정지) vs P0, 같은 seed 쌍", "",
          "열 출처: `episodes_P0.csv`, `episodes_P1_<탐지기>.csv`의 outcome, unnecessary_stop.", "",
          "| run | P0 위험 사건 | " + " | ".join(f"{det}: P1 위험 / 막음 / 새 위험 / 불필요 정지" for det in DETECTORS) + " |",
          "|---|---:|" + "---|" * len(DETECTORS)]
    for run in d["closed"]["A"]:
        cells = []
        for det in DETECTORS:
            v = d["closed"][det][run]
            cells.append(f"{v['p1_hazard']} / {v['prevented']} / {v['new_hazard']} / {v['unnecessary_stop']}")
        L.append(f"| {run} | {d['closed']['A'][run]['p0_hazard']} | " + " | ".join(cells) + " |")

    L += ["", "## T5. FTTI 근사 — P0에서 고장 시작 → 위험 사건(충돌·이탈)", "",
          "FTTI 근사 = (사건 스텝 `total_steps` − `onset`) × dt. **대표값 = 최솟값**(가장 빠른 위험 사건). 분포도 함께 보인다.", "",
          "| run | P0 위험 사건 | 고장 시작 전 사건 | FTTI 근사 대표값(최소) | 분포(스텝, 초) |", "|---|---:|---:|---|---|"]
    for run, v in d["ftti"].items():
        rep = f"{v['steps']['min']} 스텝 = {sec(v['steps']['min'], dt)} s (seed {v['first_hazard']})" if v["steps"] else \
            "데이터 없음 — P0 위험 사건 0회"
        L.append(f"| {run} | {v['p0_hazard']} | {v['hazard_before_onset']} | {rep} | {fmt_dist(v['steps'], dt) if v['steps'] else '데이터 없음 — P0 위험 사건 0회'} |")

    L += ["", "## T6. FDTI 근사 — 고장 시작 → 첫 경보 (A 주 대상, B2·HYBRID·B1 참고)", "",
          "FDTI 근사 = (`first_alarm_step` − `onset`) × dt, 해당 조합 CSV. 고장 시작 전 경보는 FDTI에서 빼고 따로 센다. "
          "B1·HYBRID는 backlog 후보 14(IF 단일 샘플 시간) 연결.", "",
          "| run | 조합 | 경보(고장 후) | 고장 전 경보 | 경보 없음 | FDTI 분포(스텝, 초) |", "|---|---|---:|---:|---:|---|"]
    for run, per in d["fdti"].items():
        for c, v in per.items():
            tag = "" if c in ("P1_A", "P2_A") else " (참고)"
            L.append(f"| {run} | {c}{tag} | {v['alarm_after_onset']} | {v['alarm_before_onset']} | {v['no_alarm']} | "
                     f"{fmt_dist(v['steps'], dt) if v['steps'] else '데이터 없음 — 고장 후 경보 0회'} |")

    L += ["", "## T7. FRTI 근사 — 첫 경보 → 정지(탐지 정지·SAFE_STOP), 탐지기 A", "",
          "FRTI 근사 = (`finish_step` − `first_alarm_step`) × dt, outcome이 탐지 정지 또는 SAFE_STOP인 행. `policy_action`별.", "",
          "| run | 조합 | policy_action | 경보 | 정지 도달 | FRTI 분포(스텝, 초) | 정지 못 한 행의 outcome |", "|---|---|---|---:|---:|---|---|"]
    for run, per in d["fdti"].items():
        for c in ("P1_A", "P2_A"):
            for act, e in per[c]["frti"].items():
                oth = ", ".join(f"{o} {n}" for o, n in e["other_outcomes"].items()) or "—"
                L.append(f"| {run} | {c} | {act} | {e['n']} | {e['stopped']} | "
                         f"{fmt_dist(e['steps'], dt) if e['steps'] else '데이터 없음 — 정지 도달 0회'} | {oth} |")

    L += ["", "## T8. FDTI + FRTI < FTTI 판정 — P0 위험 사건 N회 중 만족 M, 저하 운행 회피 G, 미달 K, 제외 J", "",
          "N = P0에서 고장 시작 후 일어난 위험 사건(충돌·이탈) 수(같은 seed의 해당 조합 행으로 판정). 네 범주(M + G + K + J = N):", "",
          "- **만족**: 경보가 onset 이후이고, 정지 스텝(`finish_step`, 해당 조합) < P0 사건 스텝(`total_steps`).",
          "- **저하 운행으로 회피(정지 없음, 위험 사건 없음)**: 경보가 onset 이후, 정지하지 않았고(P2_A의 ey·rc 덮어쓰기 등), 해당 조합에서 그 seed에 위험 사건이 없음.",
          "- **미달**: 경보가 없거나, 정지 스텝 ≥ P0 사건 스텝(같은 스텝 포함 — 보수적), 또는 경보 후 정지하지 않았는데 위험 사건이 일어남.",
          "- **판정 제외(고장 전 오경보)**: 경보가 onset 이전. FDTI가 정의되지 않는다.", "",
          "'실제로 위험 사건 아님'은 해당 조합에서 그 seed의 outcome이 충돌·이탈이 아닌 수(조건 판정과 실제 결과의 교차 확인).", "",
          "| run | 조합 | 판정 (N회 중) | 미달 내역: 경보 없음 / 정지 ≥ 사건 / 경보 후 정지 안 함·위험 사건 발생 | 실제로 위험 사건 아님 |",
          "|---|---|---|---|---:|"]
    for run, per in d["condition"].items():
        for c, v in per.items():
            tag = "" if c in ("P1_A", "P2_A") else " (참고)"
            if v["n"] == 0:
                L.append(f"| {run} | {c}{tag} | 데이터 없음 — P0 위험 사건 0회 | — | — |")
            else:
                sd = v["shortfall_detail"]
                L.append(f"| {run} | {c}{tag} | {v['n']}회 중 만족 {v['satisfied']}, 저하 운행 회피 {v['degraded_avoided']}, "
                         f"미달 {v['shortfall']}, "
                         f"제외 {v['excluded_alarm_before_onset']} | {sd['no_alarm']} / {sd['stop_not_before_event']} / "
                         f"{sd['alarm_but_no_stop']} | {v['actually_not_hazard']} |")

    tl = d["time_limit"]
    L += ["", "## T9. 비주입 이상", "",
          f"- MPC time_limit 발동(`diag_timing.csv`의 time_limit_hits): {tl['rows']}행 중 합계 {tl['hits']}회 "
          f"(조합별 {', '.join(f'{c} {n}' for c, n in tl['by_combo'].items())}), 에피소드별 최대 solve 시간의 최댓값 {tl['max_solve_ms']} ms.",
          "- 고장 없는 정상 run의 P0 위험 사건(`episodes_P0.csv`), 같은 seed의 조합별 outcome:"]
    for k, v in d["normal_hazard"].items():
        L.append(f"  - {k}: {v['outcome']}, 사건 스텝 {v['event_step']} — "
                 + ", ".join(f"{c} {o}" for c, o in v["by_combo"].items()))
    L += ["", "## T10. P2_A run별 outcome (가용성 손실 분리용)", "",
          "| run | outcome 분포 |", "|---|---|"]
    for run, v in d["p2_a_outcomes"].items():
        L.append(f"| {run} | {', '.join(f'{o} {n}' for o, n in v.items())} |")
    L.append("")
    return "\n".join(L)


FMEA_MD = OUT_DIR / "FMEA.md"


def check_fmea_text(d):
    """FMEA.md에 직접 쓴 유일한 수치(지시된 표기 '평가 발동 k/n')가 재계산 값과 같은지 확인한다."""
    tl = d["time_limit"]
    want = f"평가 발동 {tl['hits']}/{tl['rows']:,}"
    if want not in FMEA_MD.read_text(encoding="utf-8"):
        raise SystemExit(f"[make_safety_tables] FMEA.md의 time_limit 표기가 재계산 값 '{want}'과 다름 — FMEA.md 10행을 고칠 것")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    d = build()
    check_fmea_text(d)
    md = render(d)
    js = json.dumps(d, ensure_ascii=False, indent=1) + "\n"
    if a.check:
        bad = [q.name for q, s in ((OUT_MD, md), (OUT_JSON, js)) if not q.exists() or q.read_bytes() != s.encode("utf-8")]
        if bad:
            print(f"[make_safety_tables --check] 불일치: {', '.join(bad)}")
            print(f"[make_safety_tables --check] 재생성 명령(저장소 루트): {REGEN_CMD}")
            sys.exit(1)
        print(f"[make_safety_tables --check] 일치: {OUT_MD.name}, {OUT_JSON.name}")
        return
    for q, s in ((OUT_MD, md), (OUT_JSON, js)):
        with open(q, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(s)
    print(f"생성: {OUT_MD.name}, {OUT_JSON.name}")


if __name__ == "__main__":
    main()
