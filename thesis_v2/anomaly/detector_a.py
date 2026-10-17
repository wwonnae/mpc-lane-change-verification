"""
탐지기 A — 모델 잔차 + CUSUM (DESIGN.md §4, §13-2·§13-3, 2026-10-01 승인).

입력은 runner의 `DetectorObs`뿐이다(주입 후 센서값 + 차량 자기 상태 + 직전 조향 명령 + 탐지기 전용 자이로).
시뮬레이터 내부(장애물 좌표·고장 라벨·정상값)는 받지 않는다. 출력은 관찰 전용이며 제어에 쓰이지 않는다(2단계).

채널(잔차) — 모두 정상 주행에서는 센서 노이즈만 남도록 플랜트와 같은 식(Euler)으로 예측한다:
  fg  : front_gap 정지 장애물 예측 잔차 (연속, σ = √2·σ_fg_meas)                       → F1·F2
  ey  : 측정 ey − ey(ir_pattern(y)) (연속, σ = σ_ey; y는 참값 상태 — 낙관성 한계)        → F3
  psi : 자이로 − (v_{k−1}/L)·tan(δcmd_{k−1}) (연속, σ = σ_gyro)                           → F6·F6b
  trk : 추적 장애물이 전방 통로에 있어야 하는데 무반사 (이산)                              → F2b
  rc  : 추적 장애물이 L2 윈도우에 확실히 있는데 right_clear=True (이산)                    → F5
  lc  : 추적 장애물이 L1 윈도우에 확실히 있는데 left_clear=True (이산, rc와 대칭)          → left_clear 고착
  ir_miss : 참값 y로 예상한 IR 패턴이 검출인데 측정 ey_line이 None (이산, rc/lc와 같은
            베르누이 LLR) — iteration 3(DESIGN.md §18) 추가. 사유: B2가 ir_dropout을 잡은
            결과를 보고, A가 관측 가능한 정보를 쓰지 않고 있었음을 확인.                  → F4(ir_dropout)

점수: 연속 채널은 z 단위 양측 CUSUM(κ=0.5 — N(0,1) 대 N(±1,1)의 로그우도비 증분 z−0.5와 같음),
이산 채널은 베르누이 로그우도비 CUSUM(p0=S4-low flip_p, p1=0.5). 둘 다 nats 척도라 채널 최대를 점수로 쓴다.
마스크된 step은 해당 채널 CUSUM을 갱신하지 않는다(유지). 경보 후 리셋하지 않는다.

추적기(§13-3 A3 추가 승인): 장애물을 y 범위로 구분해 여러 개 보관한다. 새 측정은 추적 예측과 맞을 때
(|z_fg| ≤ TRACK_GATE_Z)만 그 추적을 갱신하고, 아니면 자차 이동량으로만 예측을 이어간다 — 고장 측정값으로
추적기가 오염되면 trk·rc가 고장을 놓친다.
"""
import math
from dataclasses import dataclass
from typing import Dict, List, Optional

from thesis_v2.baseline import config as base_config
from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.baseline.vehicle import VehicleState

from . import config as an_config
from .runner import DetectorObs, DetectorOutput

_NOISE = base_sensors.NOISE_PROFILES[an_config.NORMAL_NOISE_PROFILE]

# ---- A1: 해석적 정규화(데이터에서 추정하지 않음) ----
SIGMA_FG_MEAS = _NOISE.sigma_front_gap               # 단일 front_gap 측정 노이즈 (m)
SIGMA_FG = math.sqrt(2.0) * SIGMA_FG_MEAS            # fg 잔차 = n_k − n_{k−1}
SIGMA_EY = _NOISE.sigma_ey                           # ey 잔차 = n_k (패턴은 참값 y의 결정적 함수)

# ---- A2: CUSUM ----
CUSUM_KAPPA = 0.5
BERN_P0 = _NOISE.flip_p                              # 정상 불일치 확률 = S4-low 오판정 확률
BERN_P1 = 0.5
LLR_MISMATCH = math.log(BERN_P1 / BERN_P0)           # +3.91 nats
LLR_MATCH = math.log((1.0 - BERN_P1) / (1.0 - BERN_P0))  # −0.68 nats
assert BERN_P0 == 0.01

# ---- 구현 상수(해석값, 2026-10-01 — DESIGN.md §13-3에 기록) ----
# 무반사 판정: S4 노이즈가 front_gap을 [0, MAX]로 clip하므로 장애물이 없을 때도 MAX−|n|이 나온다 → 5σ 여유.
NO_RETURN_MARGIN = 5.0 * SIGMA_FG_MEAS               # 0.05 m
# 추적 갱신 게이트: |측정 근거리 − 추적 예측| ≤ 4·σ_fg (정상에서 벗어날 확률 ≈ 6e−5/step)
TRACK_GATE_Z = 4.0
# 종방향 경계 불확실 구간: 추적 x는 노이즈 있는 측정의 평균이므로 경계 ±5σ 안에서는 판정하지 않는다.
BOUNDARY_MARGIN = 5.0 * SIGMA_FG_MEAS                # 0.05 m
# 같은 장애물로 볼 y 중심 차이(차로 폭의 절반 미만이면 같은 차로)
TRACK_Y_ASSOC = base_config.W / 2.0

CHANNELS = ("fg", "ey", "psi", "trk", "rc", "lc", "ir_miss")
CONTINUOUS = ("fg", "ey", "psi")
L2_RANGE = (-0.15, 0.15)   # baseline sensors.right_clear (REQ-SEN-04)
L1_RANGE = (0.15, 0.45)    # baseline sensors.left_clear (REQ-SEN-02)


@dataclass
class Track:
    """정지 장애물 하나(자차 dead-reckoning 좌표계 x̂, y는 세계 좌표 — LiDAR 스캔의 y_lo/y_hi)."""
    x_near: float      # 수용된 측정들의 평균
    length: float      # gap_far − gap_near (첫 측정)
    y_lo: float
    y_hi: float
    n: int = 1

    @property
    def x_far(self) -> float:
        return self.x_near + self.length

    @property
    def y_center(self) -> float:
        return 0.5 * (self.y_lo + self.y_hi)


def _lat_overlap(a_lo, a_hi, b_lo, b_hi) -> bool:
    return not (a_hi < b_lo or a_lo > b_hi)


def _no_return(fg: float) -> bool:
    return fg >= base_config.LIDAR_MAX_RANGE - NO_RETURN_MARGIN


class DetectorA:
    """threshold=inf이면 점수만 계산(임계값 결정용)."""

    def __init__(self, threshold: float = math.inf, sigma_gyro_deg: float = an_config.SIGMA_GYRO_DEG):
        self.threshold = threshold
        self.sigma_psi = math.radians(sigma_gyro_deg)
        self.reset()

    def reset(self) -> None:
        self.prev: Optional[DetectorObs] = None
        self.x_hat = 0.0  # 자차 후륜 x (dead-reckoning, 시작점 0)
        self.tracks: List[Track] = []
        self.s_pos = {c: 0.0 for c in CONTINUOUS}
        self.s_neg = {c: 0.0 for c in CONTINUOUS}
        self.s_bin = {c: 0.0 for c in CHANNELS if c not in CONTINUOUS}

    # ---------- 추적기 ----------
    def _front_x(self, obs: DetectorObs) -> float:
        return self.x_hat + base_config.L * math.cos(obs.psi)

    def _update_tracks(self, obs: DetectorObs) -> None:
        info = obs.frame.obstacle_info
        fg = obs.frame.front_gap
        if info is None or _no_return(fg):
            return
        fx = self._front_x(obs)
        x_near_m = fx + fg                       # 근거리는 노이즈 있는 front_gap으로
        length = max(0.0, info.gap_far - info.gap_near)
        yc = 0.5 * (info.y_lo + info.y_hi)
        for tr in self.tracks:
            if abs(tr.y_center - yc) < TRACK_Y_ASSOC:
                if abs(x_near_m - tr.x_near) <= TRACK_GATE_Z * SIGMA_FG:
                    tr.x_near += (x_near_m - tr.x_near) / (tr.n + 1)
                    tr.n += 1
                return  # 같은 차로 장애물: 게이트 밖이면 갱신하지 않고 예측만 유지
        self.tracks.append(Track(x_near=x_near_m, length=length, y_lo=info.y_lo, y_hi=info.y_hi))

    def _window_state(self, obs: DetectorObs, lane: tuple) -> Optional[bool]:
        """추적 장애물이 lane 윈도우에 확실히 있으면 True, 확실히 없으면 False, 경계 근처면 None."""
        rx = self.x_hat
        fx = self._front_x(obs)
        lo, hi = rx - base_config.G_SAFE_MIN, fx + base_config.G_TRIG
        any_ambiguous = False
        for tr in self.tracks:
            if not _lat_overlap(tr.y_lo, tr.y_hi, *lane):
                continue
            # 종방향 겹침: x_far >= lo and x_near <= hi
            if tr.x_far >= lo + BOUNDARY_MARGIN and tr.x_near <= hi - BOUNDARY_MARGIN:
                return True
            if tr.x_far >= lo - BOUNDARY_MARGIN and tr.x_near <= hi + BOUNDARY_MARGIN:
                any_ambiguous = True
        return None if any_ambiguous else False

    def _corridor_state(self, obs: DetectorObs) -> Optional[bool]:
        """추적 장애물이 전방 통로(front_gap 대상)에 확실히 있으면 True, 없으면 False, 경계면 None."""
        fx = self._front_x(obs)
        c_lo, c_hi = obs.y - base_config.B / 2, obs.y + base_config.B / 2
        any_ambiguous = False
        for tr in self.tracks:
            if not _lat_overlap(tr.y_lo, tr.y_hi, c_lo, c_hi):
                continue
            if tr.x_far >= fx + BOUNDARY_MARGIN and tr.x_near - fx < base_config.LIDAR_MAX_RANGE - NO_RETURN_MARGIN:
                return True
            if tr.x_far >= fx - BOUNDARY_MARGIN:
                any_ambiguous = True
        return None if any_ambiguous else False

    # ---------- 잔차 ----------
    def _residuals(self, obs: DetectorObs) -> Dict[str, Optional[float]]:
        r: Dict[str, Optional[float]] = {c: None for c in CHANNELS}
        p = self.prev
        fr = obs.frame
        # fg: 정지 장애물 가정 front_gap 예측(전단 기준점 x+L cosψ, Euler)
        if p is not None and not _no_return(fr.front_gap) and not _no_return(p.frame.front_gap) \
                and p.frame.front_gap > 0.0:
            pred = p.frame.front_gap - p.v * math.cos(p.psi) * base_config.DT \
                - base_config.L * (math.cos(obs.psi) - math.cos(p.psi))
            r["fg"] = (fr.front_gap - pred) / SIGMA_FG
        # ey: 참값 y로 예상한 IR 패턴의 ey와 비교(둘 다 검출일 때만 정의됨)
        # ir_miss: 예상은 검출인데 측정이 미검출(None) — iteration 3(§18), F4(ir_dropout) 탐지용
        ey_exp = base_sensors.ey_line(base_sensors.ir_pattern(VehicleState(0.0, obs.y, 0.0, 0.0)))
        if ey_exp is not None:
            if fr.ey_line is not None:
                r["ey"] = (fr.ey_line - ey_exp) / SIGMA_EY
            r["ir_miss"] = 1.0 if fr.ey_line is None else 0.0
        # psi: 자이로 vs 명령 조향으로 예측한 요레이트 (v_{k−1}=0이면 마스크)
        if p is not None and obs.yaw_rate_meas is not None and p.v > 0.0:
            pred_rate = (p.v / base_config.L) * math.tan(math.radians(obs.delta_prev_cmd_deg))
            r["psi"] = (obs.yaw_rate_meas - pred_rate) / self.sigma_psi
        # 이산 채널(추적 예측은 이번 step 측정으로 갱신하기 전 값으로 비교)
        corr = self._corridor_state(obs)
        if corr is True:
            r["trk"] = 1.0 if _no_return(fr.front_gap) else 0.0
        if self._window_state(obs, L2_RANGE) is True:
            r["rc"] = 1.0 if fr.right_clear else 0.0
        if self._window_state(obs, L1_RANGE) is True:
            r["lc"] = 1.0 if fr.left_clear else 0.0
        return r

    # ---------- 갱신 ----------
    def update(self, obs: DetectorObs) -> DetectorOutput:
        p = self.prev
        if p is not None:  # 자차 이동량(플랜트와 같은 Euler: x_k = x_{k−1} + v_{k−1} cosψ_{k−1} dt)
            self.x_hat += p.v * math.cos(p.psi) * base_config.DT
        res = self._residuals(obs)
        for c in CONTINUOUS:
            z = res[c]
            if z is not None:
                self.s_pos[c] = max(0.0, self.s_pos[c] + z - CUSUM_KAPPA)
                self.s_neg[c] = max(0.0, self.s_neg[c] - z - CUSUM_KAPPA)
        for c in self.s_bin:
            m = res[c]
            if m is not None:
                self.s_bin[c] = max(0.0, self.s_bin[c] + (LLR_MISMATCH if m > 0.5 else LLR_MATCH))
        self._update_tracks(obs)
        self.prev = obs
        scores = {c: max(self.s_pos[c], self.s_neg[c]) for c in CONTINUOUS}
        scores.update(self.s_bin)
        ch = max(CHANNELS, key=lambda c: scores[c])  # 동점이면 CHANNELS 순서 앞쪽
        score = scores[ch]
        return DetectorOutput(score=score, alarm=score > self.threshold, channel=ch,
                              channel_scores=scores, residuals=res)
