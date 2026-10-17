"""
Teacher Data Generation with Original Parameters
"""
import sys
import argparse

# Import from final.py and simulator.py
from final import *
from simulator import run_simulation_episodes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--num_episodes", type=int, default=100)
    parser.add_argument("--steps_per_episode", type=int, default=300)
    parser.add_argument("--dataset_dir", type=str, default="./dataset_teacher")
    args = parser.parse_args()
    
    # 원본 파라미터 사용
    vp = VehicleParams(L=0.20, B=0.15, V_MAX=0.5,
                       DELTA_MAX_DEG=25.0, DELTA_RATE_MAX_DEGPS=200.0,
                       A_MAX=2.0, A_MIN=-3.0, WHEEL_RATE_MAX=3.0)
    
    rp = RoadParams(W=0.30, MAX_Y_DEVIATION=3.0)
    
    bp = BehaviorParams(G_TRIG=1.0, G_SAFE_MIN=0.15, T_KEEP_L1_MIN=0.5)
    
    cp = ControllerParams(k_ey_keep=1.5, k_ey_evade=2.0,
                         k_ey_return=1.8, k_delta_rate=0.05)
    
    # App config
    cfg = AppConfig(
        hz=20.0, run_mode=RunMode.TEACHER,
        assume_straight_nominal=1,
        comm="dummy", hb_period=0.5,
        log_dir="./runs", export_dataset=1,
        dataset_dir=args.dataset_dir,
        merge_shards=0,
        merged_out="./dataset_all.npz",
        tau_ms=0.0, tau_jitter_ms=0.0,
        policy_onnx=None, policy_ts=None, yaml_path=None,
        debug_print=1,  # Enable debug output
        lidar_port=0, ir_sensor_spacing=0.04
    )
    
    # App 인스턴스 생성
    app = App(cfg, vp, rp, bp, cp)
    
    print("=" * 60)
    print("[TEACHER] Starting with ORIGINAL parameters:")
    print(f"  G_TRIG: {bp.G_TRIG}m")
    print(f"  EVADE MPC qy: 100.0")
    print(f"  RETURN MPC qy: 40.0")
    print(f"  Obstacle distance: 1.5-2.5m (original)")
    print("=" * 60)
    
    # Teacher 데이터 생성
    run_simulation_episodes(
        app=app,
        num_episodes=args.num_episodes,
        steps_per_episode=args.steps_per_episode,
        dataset_dir=args.dataset_dir,
        randomize=True
    )
    
    print("\n[TEACHER] Completed!")

if __name__ == "__main__":
    main()
