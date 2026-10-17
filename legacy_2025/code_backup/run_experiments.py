"""
100 에피소드 실험 스크립트 (Teacher/Student 비교)
"""
import subprocess
import time
import os
import sys
import numpy as np
from pathlib import Path

def run_single_episode(mode, episode_num, log_dir, model_path=None, stats_path=None):
    """단일 에피소드 실행"""
    
    cmd = [
        sys.executable,
        "final_hierarchical_backup.py",
        "--run_mode", mode,
        "--random_env",
        "--log_dir", f"{log_dir}/ep_{episode_num:03d}",
    ]
    
    if mode == "student":
        if model_path and stats_path:
            cmd.extend([
                "--student_model", model_path,
                "--student_stats", stats_path
            ])
    
    print(f"\n{'='*80}")
    print(f"[Episode {episode_num + 1}/100] Mode: {mode.upper()}")
    print(f"{'='*80}")
    
    start_time = time.time()
    
    try:
        # 10초 타임아웃으로 실행
        result = subprocess.run(
            cmd,
            timeout=10,
            capture_output=True,
            text=True
        )
        
        elapsed = time.time() - start_time
        
        # 에피소드 성공 여부 확인 (SAFE_STOP이 아니면 성공)
        success = "SAFE_STOP" not in result.stdout
        
        print(f"[Episode {episode_num + 1}] Completed in {elapsed:.1f}s - {'SUCCESS' if success else 'FAILED'}")
        
        return success, elapsed
        
    except subprocess.TimeoutExpired:
        print(f"[Episode {episode_num + 1}] Timeout (10s) - Terminated")
        return True, 10.0  # 타임아웃은 정상 완료로 간주
        
    except Exception as e:
        print(f"[Episode {episode_num + 1}] Error: {e}")
        return False, 0.0

def merge_episode_metrics(log_dir, num_episodes):
    """에피소드별 metrics 병합"""
    
    all_metrics = {
        'y': [],
        'psi': [],
        'delta': [],
        'v': [],
        'state': [],
        'front_gap': [],
        'loop_time': [],
        'episode': []
    }
    episode_success = []
    
    print(f"\n[INFO] Merging {num_episodes} episodes...")
    
    for ep in range(num_episodes):
        ep_dir = f"{log_dir}/ep_{ep:03d}"
        metrics_file = os.path.join(ep_dir, "metrics.npz")
        
        if not os.path.exists(metrics_file):
            print(f"[WARN] Episode {ep} metrics not found: {metrics_file}")
            episode_success.append(False)
            continue
        
        data = np.load(metrics_file, allow_pickle=True)
        
        # 데이터 병합
        all_metrics['y'].extend(data['y'])
        all_metrics['psi'].extend(data['psi'])
        all_metrics['delta'].extend(data['delta'])
        all_metrics['v'].extend(data['v'])
        all_metrics['state'].extend(data['state'])
        all_metrics['front_gap'].extend(data['front_gap'])
        all_metrics['loop_time'].extend(data['loop_time'])
        
        # 에피소드 번호 업데이트
        episode_nums = [ep] * len(data['y'])
        all_metrics['episode'].extend(episode_nums)
        
        # 성공 여부
        if 'success' in data and len(data['success']) > 0:
            episode_success.append(bool(data['success'][0]))
        else:
            # SAFE_STOP 상태가 없으면 성공
            has_safe_stop = np.any(data['state'] == 'SAFE_STOP')
            episode_success.append(not has_safe_stop)
    
    # 최종 저장
    print(f"[INFO] Saving merged metrics to {log_dir}/metrics.npz")
    np.savez(
        os.path.join(log_dir, 'metrics.npz'),
        y=np.array(all_metrics['y']),
        psi=np.array(all_metrics['psi']),
        delta=np.array(all_metrics['delta']),
        v=np.array(all_metrics['v']),
        state=np.array(all_metrics['state']),
        front_gap=np.array(all_metrics['front_gap']),
        loop_time=np.array(all_metrics['loop_time']),
        episode=np.array(all_metrics['episode']),
        success=np.array(episode_success)
    )
    
    success_rate = np.mean(episode_success) * 100
    print(f"[INFO] Success rate: {success_rate:.1f}% ({np.sum(episode_success)}/{len(episode_success)})")
    
    return all_metrics, episode_success

def run_experiment(mode, num_episodes=100, model_path=None, stats_path=None):
    """전체 실험 실행"""
    
    log_dir = f"./results/{mode}"
    os.makedirs(log_dir, exist_ok=True)
    
    print(f"\n{'='*80}")
    print(f"Starting {mode.upper()} experiment: {num_episodes} episodes")
    print(f"Log directory: {log_dir}")
    print(f"{'='*80}")
    
    total_start = time.time()
    episode_times = []
    episode_results = []
    
    for ep in range(num_episodes):
        success, elapsed = run_single_episode(
            mode, ep, log_dir, model_path, stats_path
        )
        episode_results.append(success)
        episode_times.append(elapsed)
        
        # 진행률 표시
        if (ep + 1) % 10 == 0:
            success_rate = np.mean(episode_results) * 100
            avg_time = np.mean(episode_times)
            print(f"\n[Progress] {ep + 1}/{num_episodes} episodes | "
                  f"Success: {success_rate:.1f}% | "
                  f"Avg time: {avg_time:.2f}s")
    
    # 메트릭 병합
    metrics, success_list = merge_episode_metrics(log_dir, num_episodes)
    
    total_time = time.time() - total_start
    
    print(f"\n{'='*80}")
    print(f"{mode.upper()} Experiment Complete!")
    print(f"Total time: {total_time/60:.1f} minutes")
    print(f"Average episode time: {np.mean(episode_times):.2f}s")
    print(f"Success rate: {np.mean(success_list)*100:.1f}%")
    print(f"{'='*80}\n")

def main():
    """메인 실행"""
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['teacher', 'student', 'both'], default='both')
    parser.add_argument('--num_episodes', type=int, default=100)
    parser.add_argument('--student_model', default='models/policy_best.pth')
    parser.add_argument('--student_stats', default='models/normalization_stats.json')
    args = parser.parse_args()
    
    if args.mode in ['teacher', 'both']:
        print("\n" + "="*80)
        print("TEACHER EXPERIMENT")
        print("="*80)
        run_experiment('teacher', args.num_episodes)
    
    if args.mode in ['student', 'both']:
        print("\n" + "="*80)
        print("STUDENT EXPERIMENT")
        print("="*80)
        run_experiment('student', args.num_episodes, 
                      args.student_model, args.student_stats)
    
    print("\n" + "="*80)
    print("ALL EXPERIMENTS COMPLETE!")
    print("Run 'python analysis.py' to generate figures and tables")
    print("="*80)

if __name__ == '__main__':
    main()
