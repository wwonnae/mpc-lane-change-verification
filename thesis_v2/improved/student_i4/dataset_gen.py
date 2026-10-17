"""
I4 데이터 생성(DESIGN_I4 §1, 개정 1). 교사 = v2 MPC. dev 전용(paper seed 100~199 + S3 dev 격자
900), eval seed/격자는 쓰지 않는다. 옛 데이터셋과 섞지 않는다.

표본 부족 규칙(§1-4 개정 1): MPC 호출 4개 상태 중 최소 스텝 수 < 최대/3이면 paper dev seed를
200개 단위(300~499, 500~699, 700~899 순서 고정)로 늘려 재생성. 확대 후 (최소/최대) 비율이
개선되지 않으면 더 늘리지 않고 멈춘다([공백] 멈춤 조건, 사용자 확인 대기 항목).

split(§1-5 개정 1): 소스별 에피소드 단위 계층 분할, SPLIT_SEED 고정 1개, 재추첨 없음.

사용(저장소 루트): python -m thesis_v2.improved.student_i4.dataset_gen --out-dir <run>/dataset
"""
import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List

import numpy as np

from thesis_v2.baseline.world import generate_scenario, generate_grid_scenario
from thesis_v2.improved.mpc import ImprovedMPC
from thesis_v2.improved.runner import run_episode as improved_run_episode

from . import config as i4_config
from .features import SolveRecorder, pair_calls_with_log, MPC_STATES


def _run_source(scenarios, source: str) -> List[Dict]:
    """한 소스(paper/S3)를 MPC 인스턴스 1개로 순서대로 실행(dev/eval 관례와 같게 인스턴스 재사용)."""
    mpc = ImprovedMPC(**i4_config.TEACHER_FLAGS)
    rec = SolveRecorder(mpc)
    episodes = []
    for key, sc in scenarios:
        res = improved_run_episode(sc, mpc=mpc)
        samples = pair_calls_with_log(rec.pop(), res.logger.rows)
        episodes.append(dict(source=source, key=key, outcome=res.outcome, samples=samples))
    return episodes


def paper_scenarios(seeds):
    return [(int(s), generate_scenario(int(s))) for s in seeds]


def s3_scenarios():
    out = []
    for i, fg in enumerate(i4_config.DEV_S3_FRONT_GAPS):
        for j, y0 in enumerate(i4_config.DEV_S3_Y0S):
            out.append((i * len(i4_config.DEV_S3_Y0S) + j, generate_grid_scenario(float(fg), float(y0))))
    return out


def state_counts(episodes) -> Dict[str, int]:
    c = Counter(s["state"] for ep in episodes for s in ep["samples"])
    return {st: int(c.get(st, 0)) for st in MPC_STATES}


def min_max_ratio(counts: Dict[str, int]) -> float:
    vals = [counts[s] for s in MPC_STATES]
    return (min(vals) / max(vals)) if max(vals) > 0 else 0.0


def stratified_episode_split(episodes: List[Dict], seed: int, val_fraction: float):
    """에피소드 단위 계층 분할(DESIGN_I4 §1-5 개정 1). 정렬 후 블록별 1개 계통 추출."""
    n = len(episodes)
    n_val = int(round(val_fraction * n))
    counts = state_counts(episodes)
    # 이 소스에서 전체 스텝이 적은 상태부터 정렬 키로 사용(데이터에서 계산, 미리 지목 안 함)
    order_states = sorted(MPC_STATES, key=lambda s: (counts[s], MPC_STATES.index(s)))

    def comp(ep):
        c = Counter(s["state"] for s in ep["samples"])
        tot = max(1, len(ep["samples"]))
        return tuple(c.get(s, 0) / tot for s in order_states) + (ep["key"],)

    idx_sorted = sorted(range(n), key=lambda i: comp(episodes[i]))
    rng = np.random.default_rng(seed)
    val_idx = set()
    for block in np.array_split(np.array(idx_sorted), n_val):
        val_idx.add(int(block[rng.integers(len(block))]))
    return val_idx, order_states


def _to_arrays(episodes, val_idx_by_source):
    X, Y, states, split, source, key, fallback, iters, status = [], [], [], [], [], [], [], [], []
    psi, dprev = [], []
    for ep_i, ep in episodes:
        is_val = ep_i in val_idx_by_source[ep["source"]]
        for s in ep["samples"]:
            X.append(s["x"])
            Y.append([s["delta_deg"], s["v_target"]])
            states.append(s["state"])
            split.append("val" if is_val else "train")
            source.append(ep["source"])
            key.append(ep["key"])
            fallback.append(s["ey_is_fallback"])
            iters.append(s["iterations"])
            status.append(s["solver_status"])
            psi.append(s["psi_deg"])
            dprev.append(s["delta_prev_deg"])
    return dict(X=np.array(X, dtype=np.float32), Y=np.array(Y, dtype=np.float32),
                state=np.array(states), split=np.array(split), source=np.array(source),
                episode_key=np.array(key, dtype=np.int64), ey_is_fallback=np.array(fallback),
                teacher_iterations=np.array(iters, dtype=np.int64),
                teacher_solver_status=np.array(status),
                # Student v2(DESIGN_I4 §6): ψ(deg)·δ_prev(deg, MPC에 들어간 직전 최종 조향) -- 9차원 X와 별도 저장
                psi_deg=np.array(psi, dtype=np.float32), delta_prev_deg=np.array(dprev, dtype=np.float32))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=str, required=True)
    ap.add_argument("--expansion-rounds", type=int, default=None,
                    help="지정하면 §1-4 자동 규칙 대신 정확히 K번 확대한 데이터로 고정(사용자 결정 기록용)")
    args = ap.parse_args()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    s3_eps = _run_source(s3_scenarios(), "S3_dev")
    paper_seeds = list(i4_config.DEV_PAPER_SEEDS)
    paper_eps = _run_source(paper_scenarios(paper_seeds), "paper_dev")

    rounds = []
    counts = state_counts(paper_eps + s3_eps)
    ratio = min_max_ratio(counts)
    rounds.append(dict(paper_seeds=f"{paper_seeds[0]}~{paper_seeds[-1]} ({len(paper_seeds)})",
                       counts=counts, min_max_ratio=ratio,
                       below_threshold=ratio < i4_config.MIN_MAX_RATIO_THRESHOLD))
    print(f"[round 0] counts={counts} ratio={ratio:.4f}", flush=True)
    stop_reason = "threshold_met" if ratio >= i4_config.MIN_MAX_RATIO_THRESHOLD else None
    if args.expansion_rounds is not None:
        stop_reason = None
    for bi, block in enumerate(i4_config.EXPANSION_BLOCKS):
        if args.expansion_rounds is not None:
            if bi >= args.expansion_rounds:
                stop_reason = f"user_fixed_expansion_rounds={args.expansion_rounds}"
                break
        elif stop_reason is not None:
            break
        paper_seeds = paper_seeds + block
        paper_eps = _run_source(paper_scenarios(paper_seeds), "paper_dev")  # 재생성
        new_counts = state_counts(paper_eps + s3_eps)
        new_ratio = min_max_ratio(new_counts)
        rounds.append(dict(paper_seeds=f"100~199 + {paper_seeds[100]}~{paper_seeds[-1]} ({len(paper_seeds)})",
                           counts=new_counts, min_max_ratio=new_ratio,
                           below_threshold=new_ratio < i4_config.MIN_MAX_RATIO_THRESHOLD))
        print(f"[round {len(rounds)-1}] counts={new_counts} ratio={new_ratio:.4f}", flush=True)
        if args.expansion_rounds is not None:
            counts, ratio = new_counts, new_ratio
            continue
        if new_ratio >= i4_config.MIN_MAX_RATIO_THRESHOLD:
            stop_reason = "threshold_met"
        elif new_ratio <= ratio:
            stop_reason = "no_improvement_after_expansion(stop_and_report)"
        counts, ratio = new_counts, new_ratio
    if stop_reason is None:
        stop_reason = (f"user_fixed_expansion_rounds={args.expansion_rounds}"
                       if args.expansion_rounds is not None
                       else "expansion_blocks_exhausted(stop_and_report)")

    episodes = list(enumerate(paper_eps)) + [(i, ep) for i, ep in enumerate(s3_eps)]
    val_paper, order_paper = stratified_episode_split(paper_eps, i4_config.SPLIT_SEED,
                                                      i4_config.VAL_FRACTION)
    val_s3, order_s3 = stratified_episode_split(s3_eps, i4_config.SPLIT_SEED, i4_config.VAL_FRACTION)
    arrays = _to_arrays(episodes, {"paper_dev": val_paper, "S3_dev": val_s3})
    np.savez_compressed(out / "dataset.npz", **arrays)

    def split_counts(src):
        m = arrays["source"] == src if src else np.ones(len(arrays["state"]), bool)
        res = {}
        for sp in ("train", "val"):
            mm = m & (arrays["split"] == sp)
            c = Counter(arrays["state"][mm])
            tot = int(mm.sum())
            res[sp] = {"n": tot, **{st: {"n": int(c.get(st, 0)),
                                         "frac": (c.get(st, 0) / tot) if tot else None}
                                    for st in MPC_STATES}}
        return res

    summary = dict(
        teacher="v2 MPC " + json.dumps(i4_config.TEACHER_FLAGS),
        rounds=rounds, stop_reason=stop_reason,
        final_paper_seeds=[int(s) for s in paper_seeds],
        n_episodes={"paper_dev": len(paper_eps), "S3_dev": len(s3_eps)},
        outcomes={"paper_dev": dict(Counter(e["outcome"] for e in paper_eps)),
                  "S3_dev": dict(Counter(e["outcome"] for e in s3_eps))},
        state_counts_by_source={"paper_dev": state_counts(paper_eps), "S3_dev": state_counts(s3_eps)},
        state_counts_total=state_counts(paper_eps + s3_eps),
        ey_fallback_rate=float(arrays["ey_is_fallback"].mean()),
        split=dict(seed=i4_config.SPLIT_SEED, val_fraction=i4_config.VAL_FRACTION,
                   sort_state_order={"paper_dev": order_paper, "S3_dev": order_s3},
                   n_val_episodes={"paper_dev": len(val_paper), "S3_dev": len(val_s3)},
                   val_episode_keys={"paper_dev": sorted(int(paper_eps[i]["key"]) for i in val_paper),
                                     "S3_dev": sorted(int(s3_eps[i]["key"]) for i in val_s3)},
                   by_source={"paper_dev": split_counts("paper_dev"), "S3_dev": split_counts("S3_dev")},
                   total=split_counts(None)),
        n_samples=int(len(arrays["state"])),
        wall_time_sec=time.perf_counter() - t0,
    )
    with open(out / "dataset_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: summary[k] for k in ("rounds", "stop_reason", "n_samples")},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
