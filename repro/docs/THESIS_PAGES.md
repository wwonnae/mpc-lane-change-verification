# 논문 페이지별 핵심 수치/서술 (이미지 직접 판독)

`docs/졸업논문.pdf`를 PyMuPDF로 200dpi PNG 렌더링(`repro/docs/pdf_pages/page_NN.png`)한 뒤
제가 직접 읽었습니다(tesseract 등 OCR 소프트웨어 미사용). 아래 인용은 전부 이미지 판독
기준입니다. 인용 안 한 페이지(3,4,5,7,9,10,12,20–22)는 이번 라운드에서 이미지로 재확인하지
않았고, 숫자만 `repro/docs/thesis_pdftotext.txt`(`pdftotext -layout`, 한글 깨짐/숫자는 정상) 참고했습니다.

| 페이지 | 절 | 핵심 내용 (이미지 확인) |
|---|---|---|
| 1 | 표지 | "2025학년도 학사학위논문", 제목 "MPC 기반 모방학습을 이용한 자율주행 차선변경 시스템", 중앙대 전자전기공학부, 이원회(20226115), **2025.12.04** |
| 6 | III.2 시뮬레이션 환경 | 차선 폭 0.30m, L2 y=0m/L1 y=0.30m. **"장애물의 위치는 0.5m에서 2.0m 사이의 균등 분포를 따른다. 차량의 초기 속도는 0.3m/s에서 0.5m/s 사이의 균등 분포를 따른다."** Table 1: L=0.20m, B=0.15m |
| 8 | IV.1 FSM | 5상태 정의, SAFE_STOP "가능한 한 빠르게 감속". **Table 2**: KEEP_L2→EVADE_L(front_gap<1.2 AND left_clear=True), **모든 상태→SAFE_STOP**(front_gap<0.20 AND left_clear=False), EVADE_L→KEEP_L1(\|y-0.30\|≤0.08), KEEP_L1→RETURN_TO_L2(t>0.6s), RETURN_TO_L2→KEEP_L2(\|y\|≤0.20 AND \|ψ\|≤20°). (3) 쿨다운 0.3초 "연속적인 상태 전이를 방지", Δδ_max=10deg/step |
| 11 | V.1 학습 데이터 생성 | **"장애물 위치(0.5–2.0m), 초기 속도(0.3–0.5 m/s), 초기 횡방향 위치(±0.05m Gaussian)를 무작위로 설정"**. **"각 시나리오는 최대 10초(200 step at 20Hz)까지 실행되며, 차량이 안전하게 회피 및 복귀를 완료하거나 SAFE_STOP 상태에 도달하면 종료"**. 9차원 입력/2차원 출력 정의. 100 에피소드, 평균 191 step, 총 19,129 샘플 |
| 13 | V.3 학습 설정 / VI.1-2 | Adam, lr=1e-3, batch=256, epoch=50, 85/15 split. VI.1: 100개 무작위 시나리오. **Table 6** FSM 상태별 제어 성능(횡방향오차/헤딩/조향각/체류비율): KEEP_L2 0.035±0.028 / 27.3±22.1 / -0.82±3.45 / 56.3%, EVADE_L 0.110±0.065 / 29.5±18.4 / 5.23±7.12 / 2.1%, KEEP_L1 0.289±0.041 / 35.4±14.2 / -1.45±4.89 / 6.6%, RETURN_TO_L2 0.255±0.096 / 15.8±12.7 / -8.91±6.34 / 35.0% |
| 14 | VI.2 | **Table 7** 종방향: 평균속도 0.458±0.048 m/s, 최소 0.301, 최대 0.500, 최소front_gap 0.648m, 충돌 0회, 회피성공률 100%. **그림1 "Teacher 정책의 차선변경 궤적 예시"**(matplotlib title "Trajectory Comparison (Sample Episode)", Teacher/Student/L2 Center/L1 Center 범례, Lateral Position + Steering Angle vs Time Step) |
| 15 | VI.2(2), VI.3(1) | **Table 8** 계산시간(3,000회): 평균1.091 / 중앙값1.035 / 표준편차0.152 / 최소0.823 / 최대5.747 / p95 1.312 / p99 1.524 ms. 본문: "전체 제어 주기 평균 3.23ms", "차선변경 구간 평균 3.71ms", "EVADE_L 최대 5.64ms". **Table 9** 총 에피소드100/총샘플19,129/평균191.3/최소142/최대267. **Table 10 시작**: KEEP_L2 10,770(56.3%) |
| 16 | VI.3(1)-(3) | Table 10 계속: RETURN_TO_L2 6,694(35.0%), SAFE_STOP 0(0.0%) "모든 에피소드가 성공적으로 완료". **Table 11** 조향각평균-2.73/std6.79/min-12.44/max24.99, 속도평균0.458/std0.048/min0.301/max0.500. **Table 12** 제약만족률: 조향각·속도·헤딩각 100%, 횡방향 위치 위반율 **0.2143%**(19,129 중 **41** 스텝), 만족률99.7857% |
| 17 | VI.3(3)-(4) | **Table 13** 조향각변화율 평균1.483/std1.827/최대10.000 deg/step, 속도변화율 평균0.001/최대0.015, 충돌0. **Table 14** FSM별 목표추종오차: KEEP_L2(목표y=0, 평균0.029/RMS0.037), EVADE_L(0.30, 0.104/0.128), KEEP_L1(0.30, 0.026/0.032), RETURN_TO_L2(0, 0.245/0.263) |
| 18 | VI.3(4)-(5), VI.4(1)-(2) | **그림2 "MPC 성능 종합 분석"**: 9개 서브플롯 제목 확인 - State Distribution / Steering Angle Distribution / Velocity Distribution / Front Gap Distribution / Lateral Position Distribution / Avg Steering by State / Steering Angle Constraint Violations / Velocity Constraint Violations / Heading Angle Distribution. Student: 16,360 train / 2,769 val. **Table 15** MSE/MAE(조향,속도): Train 0.082/1.15/0.014, Val 0.095/1.24/0.016, Test 0.091/**1.20**/0.015 |
| 19 | VI.4(2)-(3) | **Table 16** 추론시간(6,000회): 평균0.206(5.30배)/중앙값0.189/표준편차0.055(2.76배)/최소0.152/최대1.557(3.69배)/p95 0.287/p99 0.354. **Table 17** 부드러움 비교: 조향각변화율 Teacher1.483/Student1.484(-0.1%), 속도변화율 둘다0.004(0.0%), Jerk Teacher0.935/Student0.905(+3.2%). **그림3 "Teacher와 Student 제어 비교"**: 4개 서브플롯 - Steering Angle Comparison / Velocity Comparison(그래프상 **Teacher는 0.50m/s에 뾰족한 단일 스파이크**, Student는 넓게 분포) / Lateral Position Comparison / State-wise RMSE Comparison |

## 추가 이미지 확인 (2026-09-17, 2차 보완)

페이지 9(Table 3 MPC 가중치 + 제약식), 10(속도제어 규칙, K_ey=1.5, "G_SAFE_MIN 비상정지 —
**회피 기동 중** 장애물과의 거리가 이 값 이하로 감소하면 즉시 SAFE_STOP" 문구 확인), 12(Table 4
Student 신경망 구조), 20(Table 18 계산시간 비교, VI.5 논의 시작)을 이미지로 추가 확인했습니다.
**결과: `repro/docs/thesis_pdftotext.txt`(pdftotext 텍스트 추출) 수치와 이번 이미지 판독 수치 사이에
불일치가 발견된 곳은 없습니다.** 표 1–18 전부(값, 단위, 설명 텍스트까지) 완전히 일치합니다.

특히 페이지 10의 "G_SAFE_MIN = 0.20m는 비상 정지 거리이다. **회피 기동 중** 장애물과의 거리가
이 값 이하로 감소하면, 즉시 SAFE_STOP 상태로 전이하여 차량을 정지한다."는 문장은 Table 2의
"모든 상태" 표현보다 더 구체적으로 "EVADE_L 중에도 SAFE_STOP이 발동해야 한다"는 것을 명시하고
있어, `PDF_VS_CODE.md`의 SAFE_STOP 행 근거를 보강합니다.

## 여전히 이미지로 확인 안 한 페이지

3,4,5(I·II장 서론/관련연구), 7(III.3 소프트웨어 구조), 21(VII 결론 계속), 22(참고문헌) —
전부 목차상 표가 없는 순수 서술/참고문헌 페이지입니다. `repro/docs/thesis_pdftotext.txt`로 훑어본 결과 숫자가
거의 없거나(참고문헌은 연도·페이지 번호뿐) 이미 인용한 수치의 반복이라, 이번 보완에서는
우선순위를 낮췄습니다. 표·수치가 필요해지면 그때 이미지로 확인하겠습니다.
