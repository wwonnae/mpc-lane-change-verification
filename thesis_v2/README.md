# thesis_v2 — 실행 환경

2단계-B에서 교차 환경(SSAFY PC / 노트북) 재현성을 확보하기 위해 실행 환경 정보를 기록한
문서입니다. 프로젝트 전체 개요는 저장소 루트의 `README.md`에 있습니다. 이후 CI(GitHub Actions)는
ubuntu·windows × Python 3.9로 같은 테스트를 실행합니다(`docs/verification/CI.md`).

## 지원 Python 버전

- **최소 3.9** (osqp>=1.0 API 기준 — 코드에 3.10+ 전용 문법 없음, 2단계-B에서 확인).
- 확인 완료된 조합 2가지:
  - **노트북**(공식 측정 환경, 2026-09-17 지정 — `repro/docs/MEASURE_PLAN.md` 공통 원칙):
    Python 3.9.12, `thesis_v2/requirements-py39.txt`
  - **SSAFY PC**(참고): Python 3.12.9, `thesis_v2/requirements-py312.txt`
- 이 두 조합 밖의 Python 버전(예: 3.10, 3.11, 3.13)은 시도하지 않았습니다 — 될 수도 있지만
  확인된 사실이 아닙니다.

## 설치

```powershell
# 노트북
python -m venv .venv
.\.venv\Scripts\pip install -r thesis_v2\requirements-py39.txt

# SSAFY PC
python -m venv .venv
.\.venv\Scripts\pip install -r thesis_v2\requirements-py312.txt
```

프로젝트 공용 `thesis_v2/requirements.txt`(범위 지정)는 두 파일의 상위 호환 기준이며, 이미
설치된 환경과의 충돌을 피하려는 목적입니다 — 새로 설치할 때는 위 두 파일 중 해당 PC에 맞는
것을 쓰십시오.

## OSQP 버전 차이 (osqp>=1.0 API)

`requirements.txt`가 `osqp<2.0`으로 0.6.x 이하 구버전을 배제하므로, 이 프로젝트는 osqp 0.6.x
API(`polish`, `warm_start` 설정명)를 지원하지 않습니다. `thesis_v2/baseline/config.py`의
`OSQP_*` 상수(`eps_abs`, `eps_rel`, `max_iter`, `polishing`, `warm_starting`, `raise_error`)가
osqp 1.x 설정명 기준으로 명시 고정되어 있습니다 — 근거: `repro/docs/SETTINGS_DECISION.md` §18.

## 실행 결과 재현성 확인

같은 코드가 두 PC에서 같은 결과를 내는지는 `thesis_v2/tests/check_golden.py`로 확인합니다.
사용법은 `thesis_v2/tests/golden/README.md` 참고.
