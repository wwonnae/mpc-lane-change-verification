"""mpc_setup_experiment.py가 임시 사본 루트에서 실행하는 탐침. 저장소에서 직접 실행하지 않는다.

baseline OSQPMPC의 생성 결과(A, l, u)와 입력 격자·연속 호출의 출력(delta_deg 비트, solver_status, fallback_used)을
JSON으로 표준 출력에 낸다.
"""
import itertools
import json
import os
import sys

sys.path.insert(0, os.getcwd())
from thesis_v2.baseline.mpc import OSQPMPC  # noqa: E402
from thesis_v2.baseline import config  # noqa: E402

m = OSQPMPC()
A = m.A
out = dict(A=dict(indptr=A.indptr.tolist(), indices=A.indices.tolist(), data=[float(x).hex() for x in A.data]),
           l=[float(x).hex() for x in m.l], u=[float(x).hex() for x in m.u], solves=[])
states = list(config.POSITION_CONSTRAINTS)
grid = itertools.product([-0.2, -0.05, 0.0, 0.07, 0.3, 0.45], [-0.3, 0.0, 0.2], [0.0, 0.3, 0.5], [0.0, 0.3], states)
for y0, p0, v0, tgt, st in grid:            # 한 인스턴스로 연속 호출(웜스타트 경로 포함)
    r = m.solve(y0, p0, v0, tgt, st)
    out["solves"].append([float(r.delta_deg).hex(), r.solver_status, r.fallback_used])
m2 = OSQPMPC()                               # 새 인스턴스 첫 호출들(셋업 직후 상태)
for y0, st in itertools.product([-0.2, 0.0, 0.3], states):
    r = m2.solve(y0, 0.1, 0.4, 0.3, st)
    out["solves"].append([float(r.delta_deg).hex(), r.solver_status, r.fallback_used])
print(json.dumps(out))
