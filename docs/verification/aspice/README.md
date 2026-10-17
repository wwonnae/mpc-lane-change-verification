# ASPICE V-모델 관점 추적성 + UML (검증 산출물 보강 2단계)

> **ASPICE 준수·평가가 아니다.** 기존 산출물(명세, 결정표, 코드, 테스트, 평가 결과)을 **Automotive SPICE 4.0의 SWE 프로세스 관점으로
> 매핑**한 것이다. 모두 코드와 테스트에서 **역으로** 문서화했다. 기준 버전과 프로세스 이름의 출처는 `SWE_MAPPING.md` 첫 절에 있다.

작업 2026-10-13, 3층PC109. 제어·탐지 코드, 기존 테스트, `thesis_v2/tests/TRACEABILITY.md`는 읽기만 했다.

| 파일 | 내용 | 자동 대조 |
|---|---|---|
| [SWE_MAPPING.md](SWE_MAPPING.md) | SWE.1~6 프로세스별 대응 산출물, 근거 파일:행, 갭 | — (손으로 쓴 문서) |
| [TRACE_MATRIX.md](TRACE_MATRIX.md), [trace_matrix.json](trace_matrix.json) | 양방향 추적: REQ → 설계 → 코드 → 테스트 → 평가 문서, 그리고 테스트 → REQ, 코드 → REQ. 고아 집계·범주. 이상탐지 별도 표 | `make_trace_matrix.py --check` |
| [UML.md](UML.md) | Mermaid 상태도(FSM), 시퀀스도(폐루프 1스텝), 컴포넌트도(패키지 import 그래프) | `check_uml.py` |
| `make_trace_matrix.py` | 매트릭스 생성기(연결 규칙은 머리말) | — |
| `check_uml.py` | 그림 ↔ 코드 대조 | — |

## 핵심 수치 (자동 생성 결과, `TRACE_MATRIX.md` 요약)

- REQ 대상 **59개**: SPEC 정의 57, SETTINGS_DECISION에만 정의 1(REQ-FSM-03b), **정의 없음 1(REQ-SIM-07)**.
- **테스트 없는 REQ 15개**, 코드 연결 없는 REQ 5개. (2026-10-13 mutation 보강으로 REQ-EVAL-03에 테스트가 생겨 16 → 15)
- 테스트 함수 241개(파라미터 변형 포함 359개 수집 항목) 중 REQ가 연결된 것은 69개, **REQ 없는 것은 172개**.
  - 범주: 이상탐지(REQ 체계 밖) 94(mutation 보강 20개 포함 — DESIGN 절을 근거로 들고 REQ는 없음), improved(SPEC에 REQ 없음) 39(2026-10-14 run #6 대응 테스트 6개 함수 추가로 33 → 39), 인프라·도구 34, 기타 5
  - 0으로 만들려고 연결을 만들지 않았다.
- `TRACEABILITY.md`에서 해석하지 못한 표기 0건, 비-REQ 행 12개(스텝 순서, 로거 스키마, golden 등).

## REQ-SIM-07 이력 (확인됨, git)

- `git log -S "REQ-SIM-07" --all` 결과는 2개 커밋이다. 27d8973(2026-09-17, `MEASURE_PLAN.md`·`IMPROVEMENT_BACKLOG.md`에 인용 추가)과
  00d47e5(2026-09-17, 코드 주석 추가)다.
- `git log -S "REQ-SIM-07" --all -- repro/docs/SPEC.md`는 결과가 없다. 따라서 **정의되었다가 삭제된 것이 아니라 처음부터 정의된 적이 없다.**
- 참고: REQ-SIM-06·REQ-SIM-09는 `repro/docs`의 `THESIS_REVISION_LOG.md`, `DESIGN_REVISION.md`, `SETTINGS_DECISION.md`, `IMPROVEMENT_BACKLOG.md`에만 나온다.
  SPEC 표에 없고 thesis_v2 코드·테스트에서도 인용되지 않아 대상 규칙(SPEC 표 행 ∪ 코드·테스트 직접 인용)에 들지 않는다.

## 실행 (저장소 루트, 테스트 의존성 설치 환경)

```
python docs/verification/aspice/make_trace_matrix.py           # 생성(내부에서 pytest --collect-only 호출)
python docs/verification/aspice/make_trace_matrix.py --check   # 저장본과 바이트 비교, 다르면 exit 1
python docs/verification/aspice/check_uml.py                   # 그림 ↔ 코드 대조, 다르면 exit 1
```

- 생성물은 POSIX 경로·LF 줄바꿈·정렬 순서가 고정이다. 그래서 OS가 달라도 같은 바이트가 나와야 한다. CI(ubuntu·windows)에서 두 검사를 모두 돌린다(`.github/workflows/ci.yml`).
- 테스트를 추가하거나 `TRACEABILITY.md`·SPEC·코드 주석의 REQ 인용을 바꾸면 `--check`가 실패한다. 이것은 의도된 동작이다. 생성기를 다시 돌려 차이를 확인한 뒤 함께 커밋한다.

## 검증 확인 (확인됨, 실행, 2026-10-13, 3층PC109)

- `check_uml.py`가 불일치를 잡는지, 그림을 일부러 틀린 사본 5종(스크래치)으로 확인했다. 5종 모두 exit 1이었다.
  - 전이 행 번호 변경
  - D3 가드 토큰 삭제
  - 시퀀스 순서 뒤바꿈
  - 내부 의존 화살표 추가
  - 외부 의존 삭제
- `make_trace_matrix.py --check`는 저장본 끝에 한 줄을 덧붙이자 exit 1이었고, 원래대로 되돌리자 exit 0이었다.
