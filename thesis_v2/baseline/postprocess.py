"""
후처리: rate limit -> clip. 논문 제출 이후 작성.
REQ-VEH-03(rate limit 공식), §15(순서 확정: rate limit 먼저, 그다음 ±25 clip).
"""
from dataclasses import dataclass

from . import config


@dataclass
class PostprocessResult:
    delta_final_deg: float
    rate_limit_active: bool
    clip_active: bool
    after_rate_deg: float  # rate limit 적용 후, clip 적용 전 값(측정용 -- MEASURE_PLAN.md
    # clip_numerical/clip_violation 분류에 필요, §18). delta_final_deg와 별개로 계산 결과에는
    # 영향 없음(순수 노출용 필드).


def apply(delta_desired_deg: float, delta_prev_deg: float) -> PostprocessResult:
    rate = config.DELTA_RATE_MAX_PER_STEP_DEG
    lo, hi = delta_prev_deg - rate, delta_prev_deg + rate
    after_rate = max(lo, min(hi, delta_desired_deg))
    rate_active = after_rate != delta_desired_deg

    clip_lo, clip_hi = -config.DELTA_MAX_DEG, config.DELTA_MAX_DEG
    after_clip = max(clip_lo, min(clip_hi, after_rate))
    clip_active = after_clip != after_rate

    return PostprocessResult(delta_final_deg=after_clip,
                              rate_limit_active=rate_active,
                              clip_active=clip_active,
                              after_rate_deg=after_rate)
