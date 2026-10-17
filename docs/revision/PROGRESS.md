# 기술보고서 집필 진행 체크리스트

설계: `repro/docs/DESIGN_REVISION.md` §8. 재개할 때는 아래에서 첫 번째 미완료 항목부터 진행합니다. 세션이 끝날 때마다 커밋합니다.

- [x] S1 설계 확정(D1–D9), `REVISION_NUMBERS.csv` 생성(256행, 산출대기 95)
- [x] S2 CSV 전사 검증(판독 오류 0, 쪽 정정 2, 확인필요 24) — DESIGN_REVISION §3-4
- [x] S2 제출본 내부 불일치·근거 불명 6건 → THESIS_REVISION_LOG, CSV 서술위치 열
- [x] S2 R1(baseline v1.1 E2 재생 통계, 집계 9개 일치) → CSV 반영
- [x] S2 R3(eval3 v2·S10 재생 통계, 4조합 outcome 일치) → CSV 반영
- [x] S2 R2 스크립트 작성(스모크 확인)
- [x] S2 R2 사용자 실행(공식 조건 True) → CSV 256행 확정, 계산시간 표를 R2 단일 실행으로 통일, 확인필요 24행 처리 방침 명시
- [x] S3 그림 F1–F9 생성·점검, CAPTIONS.md(출처·조건·선택 규칙·대체 대상)
장 완료 조건: `python docs/revision/scripts/build_report.py --check` 통과(본문 수치 = CSV, 그림·표 파일 참조, 캡션 조건 태그 4종).

- [x] S4-0 build_report.py(조립 + --check), 신규 수치 행(new_numbers.py), 캡션 태그 4종
- [x] S4-1 부록 B `chapters/91_appB.md`
- [x] S4-2 III `chapters/30_ch3_system.md`
- [x] S4-3 IV `chapters/40_ch4_decision.md`
- [x] S4-4 V `chapters/50_ch5_learning.md`
- [x] S5-1 VI.1 `chapters/61_vi1.md`
- [x] S5-2 VI.2 `chapters/62_vi2.md`
- [x] S5-3 VI.3 `chapters/63_vi3.md`
- [x] S5-4 VI.5 `chapters/65_vi5.md`
- [x] S6-1 VI.6 `chapters/66_vi6.md`
- [x] S6-2 VI.4 `chapters/64_vi4.md`
- [x] S6-3 VI.7 `chapters/67_vi7.md`
- [x] S7-1 VI.8 `chapters/68_vi8.md`
- [x] S7-2 VII `chapters/70_ch7.md`
- [x] S7-3 I `chapters/10_ch1.md`
- [x] S7-4 II `chapters/20_ch2.md` + 참고문헌 `chapters/80_refs.md`
- [x] S7-5 서문 `chapters/05_preface.md`
- [x] S7-6 부록 A `chapters/90_appA.md`(CSV 256행 전체 대조표 + 그림 1–3 폐기 단락)
- [x] S7-7 표지 `chapters/00_cover.md`
- [x] S7-8 전체 조립·--check 통과·분량(본문 약 30.4쪽 + 부록 약 11.4쪽, 추정)·OPEN_ITEMS 8건·부록 A 256행 전부 확인·커밋·푸시
- [x] (사용자) OPEN_ITEMS.md 8건 결정 → 반영(판정 라벨, 부록 A 축약, 속도 배수 범위화 + CSV_CHANGELOG, 문헌 [3] 초록 확인·축소, 표 6 미확립 유지,
  RESULT 소수점 정정 4건, CSV 111·112 비고) → --check 통과, OPEN 0건, 분량 본문 30.2쪽 + 부록 6.9쪽(부록 A 5.0쪽, 추정)
- [ ] PDF 생성(wkhtmltopdf + NotoSansCJK) — 실패(2026-09-25): wkhtmltopdf 미설치(PATH·Program Files·chocolatey에 없음), 저장소에 해당 변환 스크립트 없음, NotoSansCJK 폰트 없음(Windows Fonts에 NotoSansKR·NotoSerifKR만)
- [x] 문체 평서체(–하였다/–이다) 일괄 변환(수치·인용·자리표시자 불변 확인) → --check 통과
- [x] 인쇄용 HTML `make_html.py`(설치 없이, NotoSansKR, 장 단위 페이지 나눔, 표 폭 맞춤; 인쇄 폭 178mm에서 넘침 0건 확인) → PDF는 사용자가 Chrome 인쇄로 저장
