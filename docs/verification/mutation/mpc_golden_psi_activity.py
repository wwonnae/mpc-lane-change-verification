"""golden 시나리오(check_golden과 같은 6개)에서 baseline MPC의 ψ 제약(±PSI_LIMIT_DEG)이 활성되는지 확인한다.

- 제품 코드는 고치지 않는다. OSQPMPC 인스턴스의 OSQP solve 호출만 감싸서, 매 solve 해의 ψ_1..ψ_N 최대 |값|과
  δ_0..δ_{N−1} 최대 |값|을 기록한다.
- 결과: 저장소 루트에서 `python docs/verification/mutation/mpc_golden_psi_activity.py --out <json>`.
  RESULTS.md 발견 사항(ψ 제약 행 제거 변이 baseline_mpc:133의 golden 차이가 작은 이유)의 근거.
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from thesis_v2.baseline import config, mpc as mpc_mod  # noqa: E402
from thesis_v2.tests.check_golden import SCENARIOS, SEEDS  # noqa: E402
from thesis_v2.baseline.runner import run_episode  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
a = ap.parse_args()

rec = dict(n_solves=0, max_abs_psi_rad=0.0, max_abs_delta_rad=0.0, statuses={})
_orig_init = mpc_mod.OSQPMPC.__init__


def _init(self):
    _orig_init(self)
    inner = self.prob.solve

    def solve(*args, **kwargs):
        res = inner(*args, **kwargs)
        rec["n_solves"] += 1
        st = res.info.status
        rec["statuses"][st] = rec["statuses"].get(st, 0) + 1
        if res.x is not None and st in ("solved", "solved inaccurate"):
            psi = [abs(float(res.x[mpc_mod._idx_psi(i)])) for i in range(1, self.N + 1)]
            dl = [abs(float(res.x[mpc_mod._idx_delta(k)])) for k in range(self.N)]
            rec["max_abs_psi_rad"] = max(rec["max_abs_psi_rad"], max(psi))
            rec["max_abs_delta_rad"] = max(rec["max_abs_delta_rad"], max(dl))
        return res
    self.prob.solve = solve


mpc_mod.OSQPMPC.__init__ = _init
for name, gen in SCENARIOS.items():
    for seed in SEEDS:
        run_episode(gen(seed))

psi_lim = math.radians(config.PSI_LIMIT_DEG)
d_lim = math.radians(config.DELTA_MAX_DEG)
out = dict(scenarios=list(SCENARIOS), seeds=SEEDS, **rec,
           psi_limit_rad=psi_lim, psi_ratio=rec["max_abs_psi_rad"] / psi_lim,
           delta_limit_rad=d_lim, delta_ratio=rec["max_abs_delta_rad"] / d_lim)
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(out, ensure_ascii=False))
