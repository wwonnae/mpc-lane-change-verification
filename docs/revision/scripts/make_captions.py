"""figures/figures_meta.json → figures/CAPTIONS.md (그림 캡션 전문: 제목·데이터 출처·조건 코드·선택 규칙·대체 대상·생성 스크립트·비고)."""
import json

from fig_common import FIG_DIR

NOTES = {
    "F1_baseline_trajectories": "궤적은 후륜 중심. 충돌 패널(b)만 가로·세로 같은 축척으로 충돌 스텝의 차체(L×B, 헤딩 회전 반영)를 그림 — "
                                "충돌 판정은 차체 전단 기준(회전 사각형 겹침). 배경색은 FSM 상태.",
    "F2_baseline_summary": "제출본 그림 2의 9개 패널 중 속도 분포는 규칙 기반 속도(0.5 m/s 상수, 첫 스텝만 v0)라 정보가 없어 제외하고 수치는 표 7로. "
                           "제약 만족 허용오차는 SETTINGS_DECISION §19 정정값.",
    "F3_student9_failure": "재사용 그림(생성 당시 캡션 없음). v2 MPC δ는 Student 궤적 위에서 같은 입력으로 그림자 호출한 값(조향에 쓰지 않음).",
    "F4_s3_boundary": "기존 분석 그림(repro/2c_analysis/out/s3_with_physical_limit.png)은 구 격자·다른 호스트(3층PC104) 데이터이고 범례 색상표가 "
                      "10색으로 잘못 표시돼 재사용하지 않고 E2 데이터로 다시 그림. 물리 한계 = 조향 최대 노력(bang-bang) 회피가 충돌하지 않는 최소 front_gap0.",
    "F5_improvement_ablation": "(c)는 세 버전을 같은 날 같은 조건으로 잰 timing_v3 공식 측정. R2(표 8·18의 출처)는 baseline 0.184 / v2 1.405 ms — "
                               "1ms 미만 양의 p99는 실행 간 변동이 큼(RESULT_I4 §12-1).",
    "F6_input_observability": "칸 크기: ey 0.01 m, front_gap 0.05 m, left_clear, 상태, ψ 1°, δ_prev 1°. 위약 = 같은 상태 안에서 섞은 ψ(δ_prev) — "
                              "칸을 잘게 나누는 것만의 효과를 분리.",
    "F7_v2_vs_s10_trajectories": "원출력 점 = MPC(교사) 또는 Student가 호출된 스텝의 후처리 전 δ. 라인추종·SAFE_STOP 스텝은 두 제어기가 같은 규칙.",
    "F8_v2_vs_s10_control": "제출본 그림 3의 속도 패널은 제외(두 제어기 모두 규칙 기반 속도라 동일). (d)의 jerk는 조향각 2차 차분(제출본 표 17 라벨대로) — "
                            "S10이 v2보다 16% 큼(불리한 방향 그대로 표시).",
    "F9_timing_quantiles": "원시 시간 배열이 저장되지 않아 분포 대신 분위수 막대. Student 시간은 정규화+추론+역정규화(e2e).",
}


def main():
    meta = json.load(open(FIG_DIR / "figures_meta.json", encoding="utf-8"))
    order = sorted(meta, key=lambda k: int(k.split("_")[0][1:]))
    lines = ["# 기술보고서 그림 캡션 (S3, 2026-09-25)", "",
             "생성: `docs/revision/scripts/fig_f1_f2_baseline.py`, `fig_f3_to_f9.py`, 캡션: `make_captions.py`. 조건 코드는 부록 B "
             "(E2 = paper seed 200~299·S3 1/4칸 격자, E3 = paper seed 2000~2099·S3 3/4칸 격자, D = dev, T0-H1 = 계산시간 seed 0~99·공식 호스트).",
             "재생 기반 그림(F1·F2·F7·F8)은 저장 결과와 일치 검증을 통과한 데이터만 사용(D9).", "",
             "| 번호 | 제목 | 데이터 출처 | 조건 | 대표 에피소드 선택 규칙 | 대체 대상 |", "|---|---|---|---|---|---|"]
    for k in order:
        m = meta[k]
        lines.append(f"| {k.split('_')[0]} | {m['title']} | `{m['source']}` | {m['cond']} | {m['selection']} | {m['replaces']} |")
    lines += ["", "## 그림별 캡션 전문", ""]
    for k in order:
        m = meta[k]
        lines += [f"### {k.split('_')[0]}. {m['title']}", "",
                  f"![{k}]({k}.png)", "",
                  f"- 데이터 출처: `{m['source']}`",
                  f"- 조건 코드: {m['cond']}",
                  f"- 대표 에피소드 선택 규칙: {m['selection']}",
                  f"- 대체 대상: {m['replaces']}",
                  f"- 생성: `{m['script']}`",
                  f"- 비고: {NOTES.get(k, m.get('note', ''))}", ""]
    (FIG_DIR / "CAPTIONS.md").write_text("\n".join(lines), encoding="utf-8")
    print("CAPTIONS.md", len(order))


if __name__ == "__main__":
    main()
