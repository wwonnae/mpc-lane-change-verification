#!/usr/bin/env python
import time
import argparse
import numpy as np

from final_hierarchical_backup import (
    VehicleParams,
    RoadParams,
    OSQPMPC,
    StudentPolicyWrapper,
    Colors,
)

def benchmark_mpc(num_iters: int = 2000) -> np.ndarray:
    """Teacher(MPC) 한 스텝 계산 시간 벤치마크"""
    vp = VehicleParams()
    rp = RoadParams()
    dt = 1.0 / 20.0  # 20 Hz

    mpc = OSQPMPC(
        vp, rp,
        N=15,
        dt=dt,
        qy=100.0,
        qpsi=25.0,
        rdelta=2.0,
        rddelta=5.0,
    )

    # 고정된 “대표 상황” 하나 정해서 계속 돌림
    y0 = 0.15       # 2차로에서 약간 치우친 상황
    psi0 = 0.0      # 헤딩 0
    v0 = 0.5        # 0.5 m/s
    target_y = 0.30 # 1차선 중심 근처

    # 워밍업 (JIT / 캐시 안정화용)
    for _ in range(200):
        _ = mpc.solve(y0, psi0, v0, target_y)

    times = []
    for _ in range(num_iters):
        t0 = time.perf_counter()
        _ = mpc.solve(y0, psi0, v0, target_y)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        times.append(dt_ms)

    return np.array(times, dtype=np.float64)


def benchmark_student(model_path: str, stats_path: str, num_iters: int = 5000) -> np.ndarray:
    """Student NN 한 스텝 계산 시간 벤치마크"""
    if StudentPolicyWrapper is None:
        raise RuntimeError("StudentPolicyWrapper가 None입니다. PyTorch 설치 및 import를 확인하세요.")

    policy = StudentPolicyWrapper(model_path, stats_path)

    # 특징 벡터: [v, ey, gap, left_clear, state_one_hot(5)]  = 총 9차원
    # 대표 상황 하나 정해서 고정
    v_now = 0.5
    ey = 0.0
    gap = 2.0
    left_clear = 1.0
    state_one_hot = np.array([1, 0, 0, 0, 0], dtype=np.float32)  # KEEP_L2
    feats = np.concatenate([
        np.array([v_now, ey, gap, left_clear], dtype=np.float32),
        state_one_hot
    ])

    # 워밍업
    for _ in range(200):
        _ = policy.predict(feats)

    times = []
    for _ in range(num_iters):
        t0 = time.perf_counter()
        _ = policy.predict(feats)
        dt_ms = (time.perf_counter() - t0) * 1000.0
        times.append(dt_ms)

    return np.array(times, dtype=np.float64)


def summarize(name: str, arr: np.ndarray):
    mean = float(arr.mean())
    std = float(arr.std())
    min_v = float(arr.min())
    max_v = float(arr.max())

    print()
    print("=" * 72)
    print(f"{name}")
    print("-" * 72)
    print(f"샘플 수         : {len(arr)}")
    print(f"평균            : {mean:.3f} ms")
    print(f"표준편차        : {std:.3f} ms")
    print(f"최소            : {min_v:.3f} ms")
    print(f"최대            : {max_v:.3f} ms")
    print("=" * 72)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--iters", type=int, default=3000, help="반복 횟수(기본 3000)")
    parser.add_argument("--student_model", type=str,
                        default="models/policy_best.pth",
                        help="Student 모델 경로(.pth)")
    parser.add_argument("--student_stats", type=str,
                        default="models/normalization_stats.json",
                        help="정규화 통계 경로(.json)")
    args = parser.parse_args()

    print("=" * 80)
    print(f"{Colors.CYAN}Teacher(MPC) vs Student(NN) 제어 계산 시간 벤치마크{Colors.RESET}")
    print("=" * 80)

    # Teacher(MPC)
    print(f"\n{Colors.YELLOW}[BENCH] Teacher(MPC) 벤치마크 중...{Colors.RESET}")
    mpc_times = benchmark_mpc(num_iters=args.iters)
    summarize("Teacher (MPC) 계산 시간 분포", mpc_times)

    # Student(NN)
    print(f"\n{Colors.YELLOW}[BENCH] Student(NN) 벤치마크 중...{Colors.RESET}")
    student_times = benchmark_student(
        model_path=args.student_model,
        stats_path=args.student_stats,
        num_iters=args.iters * 2,  # NN은 빠르니까 샘플을 더 많이
    )
    summarize("Student (NN) 계산 시간 분포", student_times)

    # 논문 표용 숫자 요약
    print("\n" + "#" * 80)
    print("# 논문 표에 바로 쓸 수 있는 요약 (평균/최대 기준)")
    print("#")
    print(f"# Teacher 평균: {mpc_times.mean():.3f} ms, 최대: {mpc_times.max():.3f} ms")
    print(f"# Student 평균: {student_times.mean():.3f} ms, 최대: {student_times.max():.3f} ms")
    ratio_mean = mpc_times.mean() / student_times.mean()
    ratio_max = mpc_times.max() / student_times.max()
    print(f"# 평균 기준 속도 비율 (Teacher / Student): {ratio_mean:.1f}x")
    print(f"# 최대 기준 속도 비율 (Teacher / Student): {ratio_max:.1f}x")
    print("#" * 80)

if __name__ == "__main__":
    main()

