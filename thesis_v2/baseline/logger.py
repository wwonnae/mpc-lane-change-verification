"""
스텝 기록. 논문 제출 이후 작성. 기록 스키마: repro/docs/DESIGN_BASELINE.md §3.
"""
import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

STEP_FIELDS = [
    "t", "x", "y", "psi", "v",
    "delta_mpc_raw", "delta_after_rate", "delta_final", "v_cmd",
    "state", "front_gap", "left_clear", "right_clear",
    "ir_pattern", "ey_line", "solver_status", "fallback_used",
    "t_mpc_solve_ms", "t_step_ms", "rate_limit_active", "clip_active",
]


class StepLogger:
    def __init__(self):
        self.rows: List[Dict[str, Any]] = []

    def log(self, **kwargs):
        row = {f: kwargs.get(f, None) for f in STEP_FIELDS}
        self.rows.append(row)

    def has_all_fields(self) -> bool:
        if not self.rows:
            return True
        return all(f in self.rows[0] for f in STEP_FIELDS)

    def save_npz(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        arrays = {}
        for f in STEP_FIELDS:
            vals = [r[f] for r in self.rows]
            if f in ("state", "solver_status"):
                arrays[f] = np.array(vals, dtype=object)
            elif f == "ir_pattern":
                arrays[f] = np.array(["".join(map(str, v)) if v is not None else "" for v in vals],
                                      dtype=object)
            elif f == "ey_line":
                arrays[f] = np.array([np.nan if v is None else v for v in vals], dtype=float)
            elif f in ("left_clear", "right_clear", "fallback_used", "rate_limit_active", "clip_active"):
                arrays[f] = np.array(vals, dtype=bool)
            else:
                arrays[f] = np.array(vals, dtype=float)
        np.savez(path, **arrays)


def save_json(obj: Any, path: Path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, default=str)
