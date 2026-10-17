"""
논문 제출 이후 작성.
기준 원본: legacy_2025/results/teacher/metrics.npz, legacy_2025/results/student/metrics.npz (읽기 전용)
목적: 에피소드별 FSM 상태 전이 간격을 계산해 쿨다운(0.3s) 적용 여부를 판정한다.
"""
import numpy as np
import json

DT = 0.05  # 논문/코드 고정 파라미터

def analyze(path, label):
    d = np.load(path, allow_pickle=True)
    state = d['state']
    episode = d['episode']
    front_gap = d['front_gap'] if 'front_gap' in d.files else None

    transitions = []  # (from, to, interval_since_prev_change_in_this_episode)
    safe_stop_count = 0
    evade_would_trigger_safestop = 0  # EVADE_L rows where front_gap<0.20 (left_clear unknown, npz has no left_clear key)
    has_left_clear = 'left_clear' in d.files

    for ep in np.unique(episode):
        mask = episode == ep
        ep_states = state[mask]
        ep_fg = front_gap[mask] if front_gap is not None else None
        last_change_idx = 0
        for i in range(1, len(ep_states)):
            if ep_states[i] != ep_states[i-1]:
                interval = (i - last_change_idx) * DT
                transitions.append((str(ep_states[i-1]), str(ep_states[i]), interval))
                last_change_idx = i
        safe_stop_count += int(np.sum(ep_states == 'SAFE_STOP'))
        if ep_fg is not None:
            evade_mask = (ep_states == 'EVADE_L')
            evade_would_trigger_safestop += int(np.sum(evade_mask & (ep_fg < 0.20)))

    # summarize by transition type
    by_type = {}
    for f, t, interval in transitions:
        key = f"{f}->{t}"
        by_type.setdefault(key, []).append(interval)

    summary = {}
    for key, intervals in by_type.items():
        arr = np.array(intervals)
        summary[key] = {
            'n': int(len(arr)),
            'min_interval_s': float(np.min(arr)),
            'mean_interval_s': float(np.mean(arr)),
            'n_under_0.3s': int(np.sum(arr < 0.3 - 1e-9)),
        }

    return {
        'path': path,
        'label': label,
        'has_left_clear_key': has_left_clear,
        'n_transitions_total': len(transitions),
        'transition_summary': summary,
        'safe_stop_sample_count': safe_stop_count,
        'evade_L_rows_with_front_gap_lt_0.20': evade_would_trigger_safestop,
    }

out = {}
for path, label in [('legacy_2025/results/teacher/metrics.npz', 'teacher'), ('legacy_2025/results/student/metrics.npz', 'student')]:
    out[label] = analyze(path, label)

with open('repro/stage1_analysis/fsm_transition_analysis.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(json.dumps(out, ensure_ascii=False, indent=2))
