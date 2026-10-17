# 부록 C. 재현 방법

저장소 루트에서 Python 가상환경을 켠 뒤 실행한다(소프트웨어 버전은 부록 B). 평가를 다시 실행하지 않고 **이 문서만 다시 만드는** 경우는
3번만 하면 된다.

1. **평가 결과 재현**(평가 데이터는 확정된 코드에 한 번씩만 실행한 기록이 이미 저장소에 있음 — 다시 돌리면 같은 결과가 나와야 함):
   - baseline·개선판 E2: `python -m thesis_v2.improved.run_eval_v2 --out-root <폴더>` (커밋 C2)
   - Student 폐루프 E3: `python -m thesis_v2.improved.student_i4.closed_loop --run-dir <run> --track eval3_paper --model-dir <S10>` (커밋 C5)
2. **보고서용 통계·그림**(저장된 결과와 일치를 확인한 뒤에만 저장):
   - `python docs/revision/scripts/r1_baseline_e2_stats.py`, `python docs/revision/scripts/r3_eval3_replay_stats.py`
   - 계산 시간 보충(공식 조건에서): `python docs/revision/scripts/r2_timing_supplement.py --power-mode-confirmed --cooldown-before-sec 60`
   - 그림: `docs/revision/scripts/` 폴더에서 `python fig_f1_f2_baseline.py`, `python fig_f3_to_f9.py`, `python make_captions.py`
3. **수치표와 문서 조립**:
   - `python docs/revision/scripts/make_revision_numbers.py` — 제출본 수치 대조 행과 신규 수치 행을 저장된 결과에서 다시 만듦
   - `python docs/revision/scripts/build_report.py --check` — 장 파일을 합쳐 이 문서를 만들고, 본문 수치가 CSV와 일치하는지·표와 그림 캡션에
     조건 태그가 있는지·그림 파일이 있는지 검사. 보류 항목은 `docs/revision/OPEN_ITEMS.md`로 모음
   - `python docs/revision/scripts/make_html.py` — 인쇄용 단일 HTML(`docs/revision/재구현검증보고서_2026.html`) 생성. Chrome에서 인쇄 → PDF로 저장

단위 테스트: `python -m pytest thesis_v2/tests -q`.
