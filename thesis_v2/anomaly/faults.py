"""
고장 주입기 + 스텝 단위 정답 라벨 (DESIGN.md §2, 결정 D4).

**모든 고장은 시뮬레이션에서 인위적으로 주입한 것**이다(실제 센서 고장 데이터 아님).

주입 위치: 센서 함수 출력(정상 변동=S4 노이즈 포함) → [여기서 고장 주입] → 탐지기 → 제어기.
액추에이터 고장(조향 지연·고착)만 후처리 출력 → [주입] → 차량 모델.
제어기 코드(FSM·MPC·lateral·postprocess·longitudinal)는 이 모듈을 모르며 수정하지 않는다.

라벨 정의: step k(1부터)에서 `spec.active(k)` = onset_step <= k < onset_step + duration_steps
(duration_steps=None이면 에피소드 끝까지 영구). 주입값이 우연히 정상값과 같아 겉으로 안 보이는
스텝도 라벨은 1이다 — 별도로 `effective`(주입값 != 정상값)를 함께 기록한다.
"""
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

import numpy as np

from thesis_v2.baseline import config as base_config
from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.baseline.world import Scenario
from thesis_v2.improved.sensors import FrontObstacleInfo

from . import config as an_config
from .scenarios import estimated_trigger_step

Pattern = Tuple[int, int, int]

# 고장 종류 ID(고장 파라미터 난수 스트림 분리용 — 값 자체를 바꾸면 재현성이 깨지므로 고정)
FAULT_IDS: Dict[str, int] = {
    "lidar_freeze": 1,       # F1
    "lidar_spike": 2,        # F2
    "lidar_dropout": 3,      # F2b
    "ir_stuck": 4,           # F3
    "ir_dropout": 5,         # F4 (무해 대조군)
    "right_clear_stuck": 6,  # F5
    "steer_delay": 7,        # F6
    "steer_stuck": 8,        # F6b (선택)
    "left_clear_stuck": 9,   # 2순위(선택)
}
SENSOR_KINDS = {"lidar_freeze", "lidar_spike", "lidar_dropout", "ir_stuck", "ir_dropout",
                "right_clear_stuck", "left_clear_stuck"}
ACTUATOR_KINDS = {"steer_delay", "steer_stuck"}
assert SENSOR_KINDS | ACTUATOR_KINDS == set(FAULT_IDS)


@dataclass(frozen=True)
class FaultSpec:
    kind: str
    onset_step: int                    # 첫 고장 step (1-based, runner의 step_idx와 같은 기준)
    duration_steps: Optional[int]      # None = 영구
    magnitude: float = 0.0             # spike: 주입 거리(m) / steer_delay: 지연 step 수
    pattern: Optional[Pattern] = None  # ir_stuck: 고정 패턴
    value: Optional[bool] = None       # *_clear_stuck: 고정 값
    meta: Dict[str, float] = field(default_factory=dict)  # 기록용(t_trig 추정치 등), 주입에 안 씀

    def __post_init__(self):
        assert self.kind in FAULT_IDS, self.kind
        assert self.onset_step >= 1
        assert self.duration_steps is None or self.duration_steps >= 1

    def active(self, k: int) -> bool:
        if k < self.onset_step:
            return False
        return self.duration_steps is None or k < self.onset_step + self.duration_steps

    def to_dict(self) -> dict:
        return dict(kind=self.kind, onset_step=self.onset_step, duration_steps=self.duration_steps,
                    magnitude=self.magnitude, pattern=list(self.pattern) if self.pattern else None,
                    value=self.value, meta=dict(self.meta))


@dataclass(frozen=True)
class SensorFrame:
    """제어기가 한 step에 받는 센서 출력 묶음(runner가 baseline/improved 센서 함수로 만든 값)."""
    front_gap: float
    left_clear: bool
    right_clear: bool
    ir_pattern: Pattern
    ey_line: Optional[float]
    obstacle_info: Optional[FrontObstacleInfo]


def _shift_obstacle_info(info: Optional[FrontObstacleInfo], new_near: float) -> Optional[FrontObstacleInfo]:
    """front_gap 주입값과 같은 스캔의 front_obstacle_info를 일관되게 이동(DESIGN.md §1-2)."""
    if info is None:
        return None  # 실제 장애물이 없는 곳의 허위 반사는 front_gap에만 반영(I2 미발동) — 단순화
    if new_near >= base_config.LIDAR_MAX_RANGE:
        return None
    length = info.gap_far - info.gap_near
    return replace(info, gap_near=new_near, gap_far=new_near + length)


class FaultInjector:
    """에피소드 하나에 대한 고장 상태(멈춤값·조향 이력)를 가진다. spec=None이면 항등."""

    def __init__(self, spec: Optional[FaultSpec]):
        self.spec = spec
        self._last_good: Optional[SensorFrame] = None
        self._frozen: Optional[SensorFrame] = None
        self._delta_hist: List[float] = []
        self._stuck_delta: Optional[float] = None

    # ---- 라벨 ----
    def label(self, k: int) -> int:
        return int(self.spec is not None and self.spec.active(k))

    # ---- 센서 ----
    def apply_sensors(self, k: int, frame: SensorFrame) -> SensorFrame:
        spec = self.spec
        if spec is None or spec.kind not in SENSOR_KINDS or not spec.active(k):
            if spec is not None and spec.kind == "lidar_freeze":
                self._last_good = frame
            return frame
        kind = spec.kind
        if kind == "lidar_freeze":
            if self._frozen is None:
                self._frozen = self._last_good if self._last_good is not None else frame
            return replace(frame, front_gap=self._frozen.front_gap,
                           obstacle_info=self._frozen.obstacle_info)
        if kind == "lidar_spike":
            g = float(np.clip(spec.magnitude, 0.0, base_config.LIDAR_MAX_RANGE))
            return replace(frame, front_gap=g, obstacle_info=_shift_obstacle_info(frame.obstacle_info, g))
        if kind == "lidar_dropout":
            return replace(frame, front_gap=base_config.LIDAR_MAX_RANGE, obstacle_info=None)
        if kind == "ir_stuck":
            p = tuple(spec.pattern)
            return replace(frame, ir_pattern=p, ey_line=base_sensors.ey_line(p))
        if kind == "ir_dropout":
            return replace(frame, ir_pattern=(0, 0, 0), ey_line=None)
        if kind == "right_clear_stuck":
            return replace(frame, right_clear=bool(spec.value))
        if kind == "left_clear_stuck":
            return replace(frame, left_clear=bool(spec.value))
        raise AssertionError(kind)

    # ---- 액추에이터 ----
    def apply_actuator(self, k: int, delta_cmd_deg: float) -> float:
        """후처리 이후 최종 조향 명령 → 차량에 실제로 들어가는 조향각."""
        self._delta_hist.append(delta_cmd_deg)
        spec = self.spec
        if spec is None or spec.kind not in ACTUATOR_KINDS or not spec.active(k):
            return delta_cmd_deg
        if spec.kind == "steer_delay":
            d = int(spec.magnitude)
            idx = len(self._delta_hist) - 1 - d
            return self._delta_hist[idx] if idx >= 0 else 0.0  # S5와 같은 관례(이력 전 0.0)
        if spec.kind == "steer_stuck":
            if self._stuck_delta is None:
                # onset 직전 step에 실제로 들어간 값으로 고착(onset=1이면 0.0)
                self._stuck_delta = self._delta_hist[-2] if len(self._delta_hist) >= 2 else 0.0
            return self._stuck_delta
        raise AssertionError(spec.kind)


# ===== 고장 파라미터 샘플링 =====
# 범위는 dev seed(3200~3229, 탐지기 없음, S4-low)에서만 정했다(DESIGN.md §2 결정 규칙: 탐지기가
# 없을 때 영향이 나타나는 범위 + 무해 범위를 함께 포함). 근거 수치는 DESIGN.md §12.
# t_trig = 정상 주행 시 front_gap이 G_TRIG(1.2 m)에 닿는 step 추정치.

def fault_rng(seed: int, kind: str) -> np.random.Generator:
    """world 생성 rng·S4 노이즈 rng와 분리된 스트림(S4의 (seed, profile_id) 관례와 같은 방식)."""
    return np.random.default_rng((seed, 1000 + FAULT_IDS[kind]))


def _randint(rng: np.random.Generator, lo: int, hi: int) -> int:
    """[lo, hi] 정수 균등. hi<lo이면 lo."""
    return int(lo if hi <= lo else rng.integers(lo, hi + 1))


def sample_fault(kind: str, scenario: Scenario) -> FaultSpec:
    rng = fault_rng(scenario.seed, kind)
    t_trig = estimated_trigger_step(scenario)
    w = an_config.WARMUP_STEPS
    pre_hi = max(w, t_trig - 5)          # 회피 시작 전 구간
    meta = {"t_trig_est": float(t_trig)}
    if kind == "lidar_freeze":
        # 회피 전 영구 멈춤 (dev: 30/30 충돌)
        return FaultSpec(kind, _randint(rng, w, pre_hi), None, meta=meta)
    if kind == "lidar_dropout":
        # 회피 시점을 덮는 누락. dev: 20 step 무해, 40 step 대부분 이탈, 60 step 대부분 충돌
        return FaultSpec(kind, _randint(rng, max(w, t_trig - 10), pre_hi), _randint(rng, 20, 60), meta=meta)
    if kind == "lidar_spike":
        # 1~3 step 튐, 위(최대거리)/아래(0.05~0.5 m) 반반 — 대체로 무해 예상(오경보 비용 비교용)
        onset = _randint(rng, w, t_trig + 20)
        dur = _randint(rng, 1, 3)
        up = bool(rng.uniform() < 0.5)
        mag = base_config.LIDAR_MAX_RANGE if up else float(rng.uniform(0.05, 0.5))
        return FaultSpec(kind, onset, dur, magnitude=mag, meta=dict(meta, up=float(up)))
    if kind == "ir_stuck":
        pat = [(1, 0, 0), (0, 0, 1)][int(rng.integers(0, 2))]
        return FaultSpec(kind, _randint(rng, w, pre_hi), None, pattern=pat, meta=meta)
    if kind == "ir_dropout":
        # 무해 대조군(None → 기존 MPC 경로)
        return FaultSpec(kind, _randint(rng, w, pre_hi), None, meta=meta)
    if kind == "right_clear_stuck":
        # dev: onset t_trig+0/20/40 모두 정상과 결과 동일(v2 I2 제약이 흡수한 것으로 추정)
        return FaultSpec(kind, _randint(rng, t_trig, t_trig + 10), None, value=True, meta=meta)
    if kind == "left_clear_stuck":
        return FaultSpec(kind, _randint(rng, w, pre_hi), None, value=True, meta=meta)
    if kind == "steer_delay":
        # dev: 3~4 step 무해, 6 일부 이탈, 8 대부분 충돌 → 4~8 step
        return FaultSpec(kind, _randint(rng, w, pre_hi), None, magnitude=float(_randint(rng, 4, 8)),
                         meta=meta)
    if kind == "steer_stuck":
        # 회피 직후 고착. dev: 10 step 무해, 20 step 일부 이탈, 30 step 대부분 이탈
        return FaultSpec(kind, _randint(rng, t_trig, t_trig + 10), _randint(rng, 10, 30), meta=meta)
    raise AssertionError(kind)
