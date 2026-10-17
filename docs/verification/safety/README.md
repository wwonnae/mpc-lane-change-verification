# 안전 분석 (검증 산출물 보강 3단계): FMEA · FTTI 근사

> **ISO 26262·AIAG-VDA FMEA의 용어와 틀을 빌려 시뮬레이션 결과를 정리한 것이며, 표준 준수나 안전 인증이 아니다.**
> **대상은 시뮬레이션에서 주입한 고장 9종이다**(`thesis_v2/anomaly/faults.py:30-40`). 여기에 비주입 이상 2가지(가설 고장 모드 MPC time_limit, 정상 seed 5011 충돌)를 더했다.

작업 2026-10-13, 3층PC109. 새 평가는 실행하지 않았다. 평가 seed(4000~4099, 5000~5099)를 다시 실행하지 않았고, 이미 저장된 결과 CSV만 읽었다.
제어·탐지 코드, 기존 테스트, 평가 결과 폴더는 수정하지 않았다.

| 파일 | 내용 |
|---|---|
| [FMEA.md](FMEA.md) | 척도 정의(결과 심각도(시뮬레이션), O 해당 없음, D는 탐지율과 폐루프 결과, RPN·AP 미계산 이유), FMEA 표 11행, 권고 조치(backlog 후보 13·14) |
| [FTTI.md](FTTI.md) | 필요한 스텝이 결과 파일에 있는지 확인, FTTI·FDTI·FRTI 근사 정의, 데이터 없음 항목, 한계 |
| [SAFETY_TABLES.md](SAFETY_TABLES.md), [safety_numbers.json](safety_numbers.json) | 모든 수치(T0~T10). 자동 생성이며 손으로 고치지 않는다 |
| `make_safety_tables.py` | 결과 CSV → 수치표. `--check`로 다시 계산해 바이트 비교한다. summary.json과도 교차 대조한다 |

## 실행 (저장소 루트)

```
python docs/verification/safety/make_safety_tables.py          # 생성
python docs/verification/safety/make_safety_tables.py --check  # 재계산 대조, 다르면 exit 1 + 재생성 명령 출력
```

- 입력 CSV 12개와 `meta.json` 2개는 모두 git 추적 파일이다(`git ls-files`로 확인, 2026-10-13). 그래서 CI(ubuntu·windows)에서도 같은 입력으로 `--check`를 돌린다.
- 생성물은 LF 줄바꿈·정렬 고정이다. `.gitattributes`로 LF 체크아웃을 지정했다.
- 생성기는 pytest나 thesis_v2 import 없이 CSV·JSON과 코드 상수(ast로 읽음)만 읽는다.
