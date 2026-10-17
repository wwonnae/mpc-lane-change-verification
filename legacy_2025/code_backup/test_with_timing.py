#!/usr/bin/env python3
"""
Loop time 측정을 위한 수정된 테스트 래퍼
기존 TestHarness를 확장해서 loop time을 수집
"""
import sys
import time
import numpy as np

# 원본 코드 임포트
from lane_change_mpc import *

# TestHarness 확장
class TestHarnessWithTiming(TestHarness):
    def __init__(self, app):
        super().__init__(app)
        self.loop_times = []
        self.state_loop_times = {}
        
    def run_scenario(self, name: str, timeline: List[Tuple[int, dict]], expected_states: List[Tuple[int, str]]):
        print(f"\n{'=' * 60}")
        print(f"{Colors.CYAN}🧪 Testing: {name}{Colors.RESET}")
        print(f"{'=' * 60}")
        
        sim = SensorSimulator()
        sim.add_timeline(timeline)
        self.reset_app_state()
        expected_dict = {step: state for step, state in expected_states}
        max_step = max(step for step, _ in expected_states)
        base_time = time.time()
        
        for step in range(max_step + 1):
            step_time = base_time + (step * self.app.dt)
            self.app._test_time = step_time
            sensor_data = sim.get_values(step)
            self.inject_sensors(sensor_data)
            
            # ⏱️ Loop time 측정 시작
            t_start = time.time()
            
            try:
                self.app.step_once()
            except Exception as e:
                print(f"{Colors.RED}❌ Step {step}: ERROR - {e}{Colors.RESET}")
                import traceback
                traceback.print_exc()
                self.results.append({
                    'scenario': name,
                    'step': step,
                    'expected': expected_dict.get(step, 'N/A'),
                    'actual': 'ERROR',
                    'passed': False
                })
                continue
            
            # ⏱️ Loop time 측정 종료
            loop_ms = (time.time() - t_start) * 1000.0
            self.loop_times.append(loop_ms)
            
            # 상태별 loop time 수집
            state_name = self.app.state.name
            if state_name not in self.state_loop_times:
                self.state_loop_times[state_name] = []
            self.state_loop_times[state_name].append(loop_ms)
            
            if step in expected_dict:
                actual = self.app.state.name
                expected = expected_dict[step]
                passed = (actual == expected)
                status = f"{Colors.GREEN}✅{Colors.RESET}" if passed else f"{Colors.RED}❌{Colors.RESET}"
                roi = sensor_data.get('roi', InfraROI())
                fg = roi.front_gap
                fg_str = f"{fg:.1f}" if fg else "N/A"
                lc = "Clear" if sensor_data.get('left_clear', True) else "Block"
                print(f"{status} Step {step:3d}: Exp {expected:15s} | Got {actual:15s} | "
                      f"y={self.app.pose.y:5.2f} | fg={fg_str:>5s} | L={lc:5s} | "
                      f"loop={loop_ms:4.1f}ms")
                self.results.append({
                    'scenario': name,
                    'step': step,
                    'expected': expected,
                    'actual': actual,
                    'passed': passed
                })
        
        self.app._test_time = None
        print()
    
    def print_summary(self):
        # 기존 summary 출력
        super().print_summary()
        
        # Loop time 통계 출력
        if not self.loop_times:
            return
            
        print("\n" + "=" * 60)
        print(f"{Colors.BOLD}⏱️  LOOP TIME 분석{Colors.RESET}")
        print("=" * 60)
        
        loop_array = np.array(self.loop_times)
        target_ms = 1000.0 / 20.0  # 20Hz = 50ms
        
        print(f"샘플 수:     {len(loop_array):,}")
        print(f"평균:        {loop_array.mean():.2f} ms")
        print(f"중앙값:      {np.median(loop_array):.2f} ms")
        print(f"최소:        {loop_array.min():.2f} ms")
        print(f"최대:        {loop_array.max():.2f} ms")
        print(f"표준편차:    {loop_array.std():.2f} ms")
        print(f"Target:      {target_ms:.2f} ms (20Hz)")
        print()
        
        # Percentile
        print("📈 Percentile:")
        for p in [50, 75, 90, 95, 99]:
            val = np.percentile(loop_array, p)
            print(f"  {p:2d}%: {val:6.2f} ms")
        print()
        
        # Target 대비
        within_target = (loop_array <= target_ms).sum()
        pct = (within_target / len(loop_array)) * 100
        print(f"✅ Target 이내: {within_target:,} / {len(loop_array):,} ({pct:.1f}%)")
        
        if loop_array.max() > target_ms:
            exceeds = (loop_array > target_ms).sum()
            pct_exceeds = (exceeds / len(loop_array)) * 100
            print(f"⚠️  Target 초과: {exceeds:,} / {len(loop_array):,} ({pct_exceeds:.1f}%)")
            print(f"   최대 초과량: {loop_array.max() - target_ms:.2f} ms")
        
        # 상태별 통계
        if self.state_loop_times:
            print("\n" + "=" * 60)
            print("📋 상태별 Loop Time:")
            print("-" * 60)
            
            state_stats = []
            for state, times in self.state_loop_times.items():
                times_array = np.array(times)
                state_stats.append({
                    'state': state,
                    'count': len(times),
                    'mean': times_array.mean(),
                    'max': times_array.max(),
                    'median': np.median(times_array)
                })
            
            # 평균 시간으로 정렬
            state_stats.sort(key=lambda x: x['mean'], reverse=True)
            
            print(f"{'State':<15} {'Count':>6} {'Mean':>8} {'Median':>8} {'Max':>8}")
            print("-" * 60)
            for s in state_stats:
                print(f"{s['state']:<15} {s['count']:>6} {s['mean']:>7.2f}ms {s['median']:>7.2f}ms {s['max']:>7.2f}ms")
            
            # MPC 집중 구간 분석
            mpc_states = ['EVADE_L', 'KEEP_L1', 'RETURN_TO_L2']
            mpc_times = []
            for state in mpc_states:
                if state in self.state_loop_times:
                    mpc_times.extend(self.state_loop_times[state])
            
            if mpc_times:
                mpc_array = np.array(mpc_times)
                print("\n" + "-" * 60)
                print(f"{Colors.CYAN}🔍 MPC 집중 사용 구간 (차선 변경){Colors.RESET}")
                print("-" * 60)
                print(f"평균:        {mpc_array.mean():.2f} ms")
                print(f"중앙값:      {np.median(mpc_array):.2f} ms")
                print(f"최대:        {mpc_array.max():.2f} ms")
                mpc_exceeds = (mpc_array > target_ms).sum()
                mpc_pct = (mpc_exceeds / len(mpc_array)) * 100
                print(f"Target 초과: {mpc_exceeds} / {len(mpc_array)} ({mpc_pct:.1f}%)")
        
        print()
        print("💡 해석:")
        if loop_array.mean() < target_ms * 0.8:
            print("✅ 평균 loop time이 충분히 여유있습니다.")
        elif loop_array.mean() < target_ms:
            print("✅ 평균적으로 실시간 제약을 만족합니다.")
        else:
            print("⚠️  평균 loop time이 target을 초과합니다. 최적화 필요.")
        
        if loop_array.max() > target_ms * 1.5:
            print("⚠️  일부 구간에서 심각한 지연이 발생합니다.")
        
        print("=" * 60 + "\n")


if __name__ == "__main__":
    # 원본 main과 동일하게 설정
    args = build_args()
    
    if int(args.merge_shards) == 1:
        merge_shards(args.dataset_dir, args.merged_out)
        sys.exit(0)
    
    cfg = AppConfig(
        hz=args.hz, run_mode=RunMode[args.run_mode.upper()],
        assume_straight_nominal=args.assume_straight_nominal,
        comm=args.comm, cmd_mode=args.cmd_mode, hb_period=args.hb_period,
        log_dir=args.log_dir, export_dataset=int(args.export_dataset),
        dataset_dir=args.dataset_dir, merge_shards=int(args.merge_shards),
        merged_out=args.merged_out, tau_ms=args.tau_ms, tau_jitter_ms=args.tau_jitter_ms,
        policy_onnx=args.policy_onnx, policy_ts=args.policy_ts, yaml_path=args.yaml,
        debug_print=1 if args.debug else 0
    )
    
    vp = VehicleParams(L=args.L, B=args.B, V_MAX=args.v_max,
                       DELTA_MAX_DEG=args.delta_max, DELTA_RATE_MAX_DEGPS=args.delta_rate,
                       A_MAX=args.a_max, A_MIN=args.a_min, WHEEL_RATE_MAX=args.wheel_rate)
    
    rp = RoadParams(W=args.lane_width, MAX_Y_DEVIATION=args.max_y_deviation)
    
    bp = BehaviorParams(G_TRIG=args.g_trig, TTC_TRIG=args.ttc_trig, TTC_MIN=args.ttc_min,
                        TTC_EVADE_MIN=args.ttc_evade_min, T_KEEP_L1_MIN=args.t_keep_l1_min,
                        G_RETURN_SAFE=args.g_return_safe, K_TTC=args.k_ttc)
    
    cp = ControllerParams(k_ey_keep=args.k_ey_keep, k_ey_evade=args.k_ey_evade,
                         k_ey_return=args.k_ey_return, k_delta_rate=args.k_delta_rate)
    
    app = App(cfg, vp, rp, bp, cp)
    
    if args.test:
        print("\n" + "=" * 60)
        print(f"{Colors.CYAN}{Colors.BOLD}🧪 RUNNING TEST MODE (With Loop Time Measurement){Colors.RESET}")
        print("=" * 60 + "\n")
        
        # 수정된 TestHarness 사용
        harness = TestHarnessWithTiming(app)
        scenarios = create_test_scenarios()
        
        for scenario_name, timeline, expected_states in scenarios:
            harness.run_scenario(scenario_name, timeline, expected_states)
        
        harness.print_summary()
    else:
        app.run()
