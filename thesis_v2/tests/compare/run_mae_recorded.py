"""
SSAFY PC 마지막 실행, MAE 측정 조건 보완: legacy_2025/results/teacher/metrics.npz, legacy_2025/results/student/
metrics.npz(실제 12-04 코드(legacy_2025/final_hierarchical_backup_thesis_1204.py) 실행이 남긴 원자료, 논문 Table 8/9/10/15 등의 출처로
추정 -- 100 에피소드, teacher는 v=0.5 고정 등 특징이 root shard_00000.npz와 일치)에서
Student 9차원 입력을 구성해, 이전 세션(RESULT_STUDENT.md §4, baseline 궤적 기반, ey_line
fallback 74.8%)보다 학습 분포에 가까운 입력으로 MAE를 다시 잰다.

metrics.npz에는 ey_line/left_clear가 저장되어 있지 않다(self.metrics 딕셔너리 정의,
legacy_2025/final_hierarchical_backup_thesis_1204.py:1687에 그 두 필드가 없음 -- 확인됨). 따라서:
- ey: get_student_features()의 fallback 공식 y - target_line_y(state)로 근사(이전 세션과
  동일 관례, 코드 근거 있음).
- left_clear: 저장 안 됨 -> True로 근사(근거: normalization_stats.json X_mean[3]≈0.996,
  root shard_00000.npz에서도 거의 항상 True -- 이 파이프라인 자체가 left_clear=False를
  거의 만들지 않음). 이 두 근사는 "임의 가정"이 아니라 각각 근거를 문서화했지만, 완전한
  원본 입력 재현은 아니라는 한계가 있다(RESULT_STUDENT.md에 명시).

teacher 세트: 실제 옛 MPC가 그 순간 실제로 낸 delta(`metrics.delta`)와 Student 예측을 비교
-> "학습 분포에 가장 가까운" MAE.
student 세트: Student 자신이 실제로 낸 delta와, 지금 다시 로드한 동일 가중치 Student의
예측을 비교 -> 파이프라인 자기 일관성 점검(입력 근사 오차가 얼마나 되는지 상한을 보여줌).
"""
import json
from pathlib import Path
from typing import Any, Dict

import numpy as np

from thesis_v2.baseline.fsm import FSMState, target_line_y
from thesis_v2.tests.compare.student_model import StudentPredictor, build_feature_vector

REPO_ROOT = Path(__file__).resolve().parents[3]
TEACHER_METRICS = REPO_ROOT / "legacy_2025" / "results" / "teacher" / "metrics.npz"
STUDENT_METRICS = REPO_ROOT / "legacy_2025" / "results" / "student" / "metrics.npz"


def _analyze(metrics_path: Path, predictor: StudentPredictor, label: str) -> Dict[str, Any]:
    d = np.load(metrics_path, allow_pickle=True)
    n = len(d["y"])
    abs_err = []
    z_flags = []
    per_state: Dict[str, Dict[str, Any]] = {}
    for i in range(n):
        state = str(d["state"][i])
        try:
            fsm_state = FSMState(state)
        except ValueError:
            continue  # 미지 상태 문자열(방어적, 실제로는 4개 상태만 존재 확인됨)
        target_y = target_line_y(fsm_state)
        ey = float(d["y"][i]) - target_y  # 근사(§ 위 docstring)
        feat = build_feature_vector(v=float(d["v"][i]), ey=ey, front_gap=float(d["front_gap"][i]),
                                     left_clear=True, state=state)
        pred = predictor.predict(feat)
        delta_pred = float(pred[0])
        delta_recorded = float(d["delta"][i])
        err = abs(delta_pred - delta_recorded)
        abs_err.append(err)

        z = predictor.z_scores(feat)
        z_flags.append(bool(np.any(np.abs(z[:4]) > 3.0)))

        if state not in per_state:
            per_state[state] = {"n": 0, "err_sum": 0.0, "ood_count": 0}
        ps = per_state[state]
        ps["n"] += 1
        ps["err_sum"] += err
        ps["ood_count"] += int(z_flags[-1])

    per_state_out = {s: {"n": ps["n"], "mae_deg": ps["err_sum"] / ps["n"],
                          "ood_fraction": ps["ood_count"] / ps["n"]}
                      for s, ps in per_state.items()}

    return {
        "label": label, "source": str(metrics_path), "n_total": len(abs_err),
        "mae_deg": float(np.mean(abs_err)),
        "ood_fraction_overall": float(np.mean(z_flags)),
        "per_state": per_state_out,
        "approximations": {
            "ey_line": "y - target_line_y(state) (fallback 공식, ey_line 미저장)",
            "left_clear": "True 고정(근사, 근거: normalization_stats X_mean[3]~=0.996)",
        },
    }


def main():
    predictor = StudentPredictor()
    result = {}

    if TEACHER_METRICS.exists():
        result["teacher"] = _analyze(TEACHER_METRICS, predictor,
                                      "legacy_2025/results/teacher (옛 MPC 실제 실행, 학습 분포에 가까움)")
    else:
        result["teacher"] = {"skipped": True, "reason": f"파일 없음: {TEACHER_METRICS}"}

    if STUDENT_METRICS.exists():
        result["student_self_consistency"] = _analyze(
            STUDENT_METRICS, predictor,
            "legacy_2025/results/student (Student 자신의 실제 실행, 파이프라인 자기 일관성 점검용)")
    else:
        result["student_self_consistency"] = {"skipped": True, "reason": f"파일 없음: {STUDENT_METRICS}"}

    print(json.dumps(result, ensure_ascii=False, indent=2))

    out_path = REPO_ROOT / "thesis_v2" / "results" / "mae_recorded_result.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {out_path}")


if __name__ == "__main__":
    main()
