"""thesis_v2 테스트 공통 fixture.

i5_time_limit_off — 결정론 비교 테스트 전용(run #6 조사 대응, 선택지 2).
  improved v2 MPC(I5 on)는 OSQP time_limit(벽시계 안전망, improved/config.py I5_TIME_LIMIT_SEC=0.045)을 쓴다.
  실행 환경이 한 solve 안에서 45 ms 넘게 멈추면 그 solve가 시간으로 끊겨 같은 입력의 결과가 달라진다
  (docs/verification/ci/run6_cause/README.md §1). 결정론 검증과 실시간 마감 보장은 별개 요구사항이므로,
  두 실행을 비트 단위로 비교하는 테스트에서만 이 값을 1e10(OSQP 기본값, 사실상 무제한)으로 바꾼다.
  - 제품 코드는 바꾸지 않는다. ImprovedMPC는 생성 시점에 improved_config.I5_TIME_LIMIT_SEC를 읽어 OSQP setup에
    넘기므로(improved/mpc.py), 테스트 안에서 MPC를 만들기 전에 값을 바꾸면 그 인스턴스에만 적용된다.
  - 자동 적용하지 않는다. 대상 테스트에 @pytest.mark.usefixtures("i5_time_limit_off")를 명시한다.
  - time_limit 발동 경로는 test_improved_i5.py::test_i5_time_limit_safety_net_reachable 등이 계속 검증한다.
  - 이 fixture가 실제로 OSQP 설정에 반영되는지는 test_improved_i5.py의 보호 테스트 2개가 확인한다.
"""
import pytest

I5_TIME_LIMIT_OFF_SEC = 1e10  # run6_cause 실험 조건 A와 같은 값


@pytest.fixture
def i5_time_limit_off(monkeypatch):
    from thesis_v2.improved import config as improved_config
    monkeypatch.setattr(improved_config, "I5_TIME_LIMIT_SEC", I5_TIME_LIMIT_OFF_SEC)
    yield I5_TIME_LIMIT_OFF_SEC
