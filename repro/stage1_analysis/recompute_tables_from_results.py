"""
논문 제출 이후 작성.
기준 원본: legacy_2025/results/teacher/metrics.npz, legacy_2025/results/student/metrics.npz (읽기 전용, 수정 안 함)
목적: 저장소에 이미 있는 results/*/metrics.npz로 논문 Table 6,7,8,9,10,11,14 수치를 재계산해서
      논문 값과 대조한다. 새 시뮬레이션을 실행하지 않는다 (기존 로그만 읽는다).
"""
import numpy as np
import json

def analyze(path, label):
    d = np.load(path, allow_pickle=True)
    out = {"path": path, "label": label, "keys": d.files}
    y, psi, delta, v = d['y'], d['psi'], d['delta'], d['v']
    state = d['state']
    front_gap = d['front_gap']
    episode = d['episode']
    n = len(state)
    out['n_samples'] = int(n)
    out['n_episodes'] = int(len(np.unique(episode)))

    # per-episode sample counts
    _, counts = np.unique(episode, return_counts=True)
    out['episode_len_mean'] = float(np.mean(counts))
    out['episode_len_min'] = int(np.min(counts))
    out['episode_len_max'] = int(np.max(counts))

    # Table 10 state sample dist
    vals, cnts = np.unique(state, return_counts=True)
    dist = {v_: int(c) for v_, c in zip(vals.tolist(), cnts.tolist())}
    out['state_counts'] = dist
    out['state_pct'] = {k: round(100*c/n, 4) for k, c in dist.items()}

    # Table 6: per-state y error, heading, steering
    table6 = {}
    for s in vals:
        mask = state == s
        table6[s] = {
            'y_mean': float(np.mean(np.abs(y[mask]))),
            'y_std': float(np.std(np.abs(y[mask]))),
            'psi_abs_mean': float(np.mean(np.abs(psi[mask]))),
            'psi_abs_std': float(np.std(np.abs(psi[mask]))),
            'delta_mean': float(np.mean(delta[mask])),
            'delta_std': float(np.std(delta[mask])),
            'occupancy_pct': round(100*np.sum(mask)/n, 4),
        }
    out['table6_by_state'] = table6

    # Table 7: longitudinal
    valid_gap = front_gap[~np.isnan(front_gap)] if np.issubdtype(front_gap.dtype, np.floating) else front_gap
    out['table7'] = {
        'v_mean': float(np.mean(v)),
        'v_std': float(np.std(v)),
        'v_min': float(np.min(v)),
        'v_max': float(np.max(v)),
        'front_gap_min': float(np.nanmin(front_gap)) if np.issubdtype(front_gap.dtype, np.floating) else None,
        'front_gap_na_ratio': float(np.mean(np.isnan(front_gap))) if np.issubdtype(front_gap.dtype, np.floating) else None,
    }

    # Table 11: control command stats
    out['table11'] = {
        'delta_mean': float(np.mean(delta)), 'delta_std': float(np.std(delta)),
        'delta_min': float(np.min(delta)), 'delta_max': float(np.max(delta)),
        'v_mean': float(np.mean(v)), 'v_std': float(np.std(v)),
        'v_min': float(np.min(v)), 'v_max': float(np.max(v)),
    }

    # compute_time (Table 8) if present
    if 'compute_time' in d.files:
        ct = d['compute_time']
        active = ct[ct > 0.01]
        out['compute_time_all'] = {
            'mean': float(np.mean(ct)), 'median': float(np.median(ct)),
            'std': float(np.std(ct)), 'min': float(np.min(ct)), 'max': float(np.max(ct)),
            'p95': float(np.percentile(ct, 95)), 'p99': float(np.percentile(ct, 99)),
            'n_nonzero': int(np.sum(ct > 0.01)), 'n_total': int(len(ct)),
        }
        if len(active) > 0:
            out['compute_time_active_only'] = {
                'mean': float(np.mean(active)), 'median': float(np.median(active)),
                'std': float(np.std(active)), 'min': float(np.min(active)), 'max': float(np.max(active)),
                'p95': float(np.percentile(active, 95)), 'p99': float(np.percentile(active, 99)),
            }
        # per-state compute time
        ct_by_state = {}
        for s in vals:
            mask = state == s
            c = ct[mask]
            c_active = c[c > 0.01]
            ct_by_state[s] = {
                'mean_all': float(np.mean(c)) if len(c) else None,
                'mean_active': float(np.mean(c_active)) if len(c_active) else None,
                'max_active': float(np.max(c_active)) if len(c_active) else None,
                'n_active': int(len(c_active)),
            }
        out['compute_time_by_state'] = ct_by_state

        lane_change_mask = np.isin(state, ['EVADE_L', 'KEEP_L1', 'RETURN_TO_L2'])
        lc = ct[lane_change_mask]
        lc_active = lc[lc > 0.01]
        out['compute_time_lane_change_active'] = {
            'mean': float(np.mean(lc_active)) if len(lc_active) else None,
            'max': float(np.max(lc_active)) if len(lc_active) else None,
            'n': int(len(lc_active)),
        }

    return out

results = {}
for path, label in [('legacy_2025/results/teacher/metrics.npz', 'teacher'), ('legacy_2025/results/student/metrics.npz', 'student')]:
    results[label] = analyze(path, label)

with open('repro/stage1_analysis/recompute_tables.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(json.dumps(results, ensure_ascii=False, indent=2))
