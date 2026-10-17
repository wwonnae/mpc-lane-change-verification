"""
이상탐지 실행 공통 설정 — 임계값 결정·dev·평가가 **같은 조건**으로 에피소드를 만들도록 한 곳에 둔다.

조건(DESIGN.md §10·§13): improved v2 제어기, 원거리 시나리오(좌측 장애물 선택), S4-low 정상 노이즈
(rng (seed, 7001)), 탐지기 전용 자이로(rng (seed, 7002)), 에피소드 상한 300 step, 이탈(중심 기준) 시 종료.
"""
import csv
import json
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from thesis_v2.baseline import sensors as base_sensors
from thesis_v2.baseline.envinfo import collect_env_info
from thesis_v2.improved.mpc import ImprovedMPC

from . import config as an_config
from .faults import sample_fault
from .runner import run_episode, AnomalyEpisodeResult
from .scenarios import generate_anomaly_scenario


def run_anomaly_episode(seed: int, kind: Optional[str] = None, left_obstacle: bool = False,
                        detector=None, sigma_gyro_deg: float = an_config.SIGMA_GYRO_DEG,
                        record_alog: bool = True) -> AnomalyEpisodeResult:
    """kind=None이면 정상(고장 없음). 고장 파라미터는 sample_fault(dev에서 확정한 범위)."""
    sc = generate_anomaly_scenario(seed, left_obstacle=left_obstacle)
    spec = None if kind is None else sample_fault(kind, sc)
    profile = base_sensors.NOISE_PROFILES[an_config.NORMAL_NOISE_PROFILE]
    return run_episode(
        sc, mpc=ImprovedMPC(**an_config.V2_MPC_FLAGS), fault=spec, detector=detector,
        noise_profile=profile, noise_rng=np.random.default_rng((seed, an_config.NOISE_STREAM_ID)),
        gyro_rng=np.random.default_rng((seed, an_config.GYRO_STREAM_ID)), sigma_gyro_deg=sigma_gyro_deg,
        max_steps=an_config.ANOMALY_MAX_STEPS, terminate_on_departure=True, record_alog=record_alog)


def threshold_from_episode_max(values) -> float:
    """§4·§13-4 공통 절차: 정상 에피소드 최대 점수의 98% 분위수(method="higher"). 경보는 score > h."""
    return float(np.quantile(np.asarray(values, dtype=float), an_config.THRESHOLD_QUANTILE, method="higher"))


def new_out_dir(out_root: str, stage: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path(out_root) / f"{stamp}_{socket.gethostname()}_{stage}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def git_info() -> dict:
    """실행 시점 커밋 해시 + 작업 트리 상태(2026-10-02 지시: 평가 결과 폴더에 커밋 해시 기록).
    직접 호출하면 **호출 시점**의 git 상태를 매번 다시 읽는다 — 결과 파일을 쓴 뒤 호출하면 그 결과 파일
    자신이 untracked로 잡혀 dirty=True가 될 수 있다(2026-10-02 it3_eval_offline_eval에서 실제로 발생, DESIGN.md
    §23 기록). `write_env()`는 이 함수를 직접 쓰지 않고 아래 `_GIT_SNAPSHOT`(모듈 임포트 시점 1회 캡처)을 쓴다."""
    def _run(args):
        try:
            r = subprocess.run(["git"] + args, capture_output=True, text=True, timeout=10)
            return r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            return None
    commit = _run(["rev-parse", "HEAD"])
    status = _run(["status", "--porcelain"])
    tag = _run(["describe", "--tags", "--exact-match"])
    return dict(commit=commit, dirty=bool(status), tag=tag)


# 2026-10-02(지시) 수정: 각 anomaly 스크립트는 이 모듈을 가장 먼저 import하고(결과 파일을 쓰기 전),
# write_env()는 스크립트 끝에서 호출된다 — git_info()를 write_env() 안에서 호출하면 그 사이에 쓴
# episodes.csv·meta.json 등 자신의 결과 파일이 이미 untracked로 잡혀 dirty가 왜곡된다. 모듈 임포트
# 시점(=스크립트 시작, 결과 파일 쓰기 전) 1회만 스냅샷해 모든 write_env() 호출이 이 값을 공유한다.
_GIT_SNAPSHOT = git_info()


def write_env(out: Path, extra: Optional[dict] = None) -> None:
    env = collect_env_info()
    import platform
    pk = {}
    for name in ("sklearn", "pandas", "torch"):
        try:
            pk[name] = __import__(name).__version__
        except ImportError:
            pk[name] = None
    env["anomaly_packages"] = pk
    env["cpu"] = dict(processor=platform.processor(), machine=platform.machine())
    env["git"] = _GIT_SNAPSHOT
    if extra:
        env = dict(env, **extra)
    (out / "env.json").write_text(json.dumps(env, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def fmt(v) -> str:
    """CSV 값 표기: float는 repr(정확한 왕복), None은 빈 칸. --check는 이 문자열을 그대로 비교한다."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(int(v))
    if isinstance(v, float):
        return repr(v)
    return str(v)


def write_csv(path: Path, header, rows) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([fmt(r[h]) for h in header])


def read_csv_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def is_leftobs(scenario: str) -> bool:
    assert scenario in ("far", "leftobs"), scenario
    return scenario == "leftobs"


def normal_runs(seeds, scenarios):
    """정상 데이터 실행 목록 [(scenario, seed)] — 시나리오 순서대로, 각 시나리오 안에서 seed 순."""
    return [(sc, s) for sc in scenarios for s in seeds]
