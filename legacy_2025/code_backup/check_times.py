import numpy as np

t = np.load('results/teacher/metrics.npz')
s = np.load('results/student/metrics.npz')

print('Teacher 상태별:')
for state in ['KEEP_L2', 'EVADE_L', 'KEEP_L1', 'RETURN_TO_L2']:
    if (t['state'] == state).any():
        times = t['compute_time'][t['state'] == state]
        print(f"  {state}: 평균 {times.mean():.2f}ms")

print('\nStudent 상태별:')
for state in ['KEEP_L2', 'EVADE_L', 'KEEP_L1', 'RETURN_TO_L2']:
    if (s['state'] == state).any():
        times = s['compute_time'][s['state'] == state]
        print(f"  {state}: 평균 {times.mean():.2f}ms")