"""S6: time_limit 지문 규칙 검토 (2026-10-14, 커밋 2 준비).

질문(사용자 보완 요청): 지문 규칙(status+반복 수)에 "OSQP info.run_time >= time_limit" 조건을 OR로 넣으면
(1) 기존 지문 대비 새로 잡히는 solve가 몇 개인지, (2) 절단이 아닌데 참이 되는 과대 집계가 몇 개인지.
덧붙여, 채택한 안 B(기존 지문 + "solved" & iter == 0)가 기존 판정을 바꾸는지와,
제품 함수 improved.mpc.time_limit_fingerprint가 osqp_probe.tl_fingerprint와 같은 판정을 내는지 확인한다.

자료:
- 실측: run6_cause/raw/{S1_identity,S2_noload,S2_load,S3,S4_runner/run1,run2} — solve 전수 기록(solves_full)과
  에피소드별 최대 run_time·지문 solve 목록.
- 양성 대조: 이 폴더 pc_rt/ — 저장소 밖 임시 사본(커밋 4c0c503, I5_TIME_LIMIT_SEC만 0.2/0.5/1 ms로 바꿈)에서
  harness.py로 i5+i4 대상 10회차씩, 전 solve 기록(keep_full_first=10). 스펙: pc_rt/spec.json.

판정 기준: OSQP 소스(osqp_api.c v1.0.0)상 안 B 지문은 절단과 정확히 일치한다(STATIC_ANALYSIS.md §3-3 정정).
따라서 run_time 조건만 참인 solve는 "과대 집계"로 센다(정상 종료 뒤 마무리 시간으로 제한을 넘긴 경우).

사용(저장소 루트): python docs/verification/ci/run6_cause/raw/S6_fingerprint_check/check_fingerprint.py
출력: 같은 폴더 result.json
"""
import collections
import glob
import gzip
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE.parent
REPO = HERE.parents[5]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(RAW.parent))
from thesis_v2.improved.mpc import time_limit_fingerprint  # noqa: E402  제품 함수(안 B)
from osqp_probe import tl_fingerprint  # noqa: E402  조사 도구(안 B로 맞춤)

T = ("i5", "i4_rec", "i4_cl100", "i4_cl101", "base")


def rule_a(s, i, mx, ct):  # 커밋 2 이전 지문(안 A)
    return (s == "run time limit reached" or (s == "solved inaccurate" and i < mx)
            or (s == "solved" and bool(ct) and i % ct != 0 and i != mx))


def scan(name, batch_dir):
    c = collections.Counter()
    for f in sorted(glob.glob(str(Path(batch_dir) / "batches" / "*.json.gz"))):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            b = json.load(fh)
        arm = b["meta"]["arm"]
        for tr in b["trials"]:
            for t in T:
                x = tr.get(t)
                if not x:
                    continue
                for sf in x.get("solves_full") or []:
                    for s in (sf if isinstance(sf, list) else [sf]):
                        if not isinstance(s, dict) or "run_time" not in s:
                            continue
                        tl, mx, ct = s["time_limit"], s["max_iter"], s["check_termination"]
                        a = rule_a(s["status"], s["iter"], mx, ct)
                        bb = time_limit_fingerprint(s["status"], s["iter"], mx, ct)
                        p = tl_fingerprint(s["status"], s["iter"], mx, ct)
                        rt = s["run_time"] >= tl
                        c["solves"] += 1
                        c["solves_with_time_limit"] += tl < 1
                        c["A"] += a
                        c["B"] += bb
                        c["run_time_rule"] += rt
                        c["B_or_run_time"] += bb or rt
                        c["new_by_run_time_vs_B"] += rt and not bb
                        c["new_by_B_vs_A"] += bb and not a
                        c["B_but_run_time_below_limit"] += bb and not rt
                        c["product_vs_probe_disagree"] += bb != p
                        c["solved_iter0"] += s["status"] == "solved" and s["iter"] == 0
                for e in x["eps"]:
                    sv = e.get("solves")
                    for s in e.get("tl_fp_solves") or []:
                        c["fp_list_solves"] += 1
                        c["fp_list_run_time_below_limit"] += s["run_time"] < s["time_limit"]
                        c["fp_list_B_false"] += not time_limit_fingerprint(s["status"], s["iter"], s["max_iter"],
                                                                           s["check_termination"])
                    if not sv or sv.get("max_run_time_ms") is None or arm == "A" or t == "base":
                        continue
                    c["episodes_time_limit_045"] += 1
                    if sv["max_run_time_ms"] >= 45.0 and sv["n_tl_fp"] == 0:
                        c["episodes_run_time_ge_45_without_fp"] += 1
    return {k: int(v) for k, v in c.items()}


def main():
    sets = {"S1_identity": RAW / "S1_identity", "S2_noload": RAW / "S2_noload", "S2_load": RAW / "S2_load",
            "S3": RAW / "S3"}
    for r in ("run1", "run2"):
        for j in ("ubuntu-24.04-orig", "ubuntu-24.04-A", "windows-2025-orig", "windows-2025-A"):
            sets[f"S4_{r}_{j}"] = RAW / "S4_runner" / r / j / "probe-out" / "run"
    real = {k: scan(k, v) for k, v in sets.items()}
    tot = collections.Counter()
    for v in real.values():
        tot.update(v)
    # 양성 대조는 arm(time_limit)별로 따로 센다
    pc = {}
    for f in sorted(glob.glob(str(HERE / "pc_rt" / "batches" / "*.json.gz"))):
        tmp = HERE / "_one"
        arm = Path(f).name.split("_")[0]
        (tmp / "batches").mkdir(parents=True, exist_ok=True)
        dst = tmp / "batches" / Path(f).name
        dst.write_bytes(Path(f).read_bytes())
        pc[arm] = scan(arm, tmp)
        dst.unlink()
        (tmp / "batches").rmdir()
        tmp.rmdir()
    out = dict(real_by_set=real, real_total=dict(tot), positive_control=pc)
    (HERE / "result.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dict(real_total=dict(tot), positive_control=pc), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
