"""
합성 데이터 생성 시스템 통합 테스트

단일 시나리오로 전체 파이프라인 검증:
1. Front gap 프로파일 생성
2. MPC 시뮬레이터 실행
3. Feature/Label 수집
4. 데이터 형식 검증
"""

import numpy as np
import sys
import os

# 현재 디렉토리를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_synthetic_data import FrontGapGenerator, SyntheticConfig, MPCSimulator


def test_single_scenario():
    """단일 시나리오 테스트"""
    print("=" * 70)
    print("  Single Scenario Test")
    print("=" * 70 + "\n")
    
    # 설정
    config = SyntheticConfig(
        initial_gap_min=100.0,
        initial_gap_max=150.0,
        sim_length=100  # 짧게 테스트
    )
    
    # 1. 시나리오 생성
    print("[1/4] Generating front_gap profile...")
    generator = FrontGapGenerator(config, seed=42)
    scenario = generator.generate_scenario('normal')
    
    print(f"  - Type: {scenario['type']}")
    print(f"  - Length: {scenario['length']} steps ({scenario['length']/20.0:.1f}s)")
    print(f"  - Initial gap: {scenario['front_gap'][0]:.1f} cm")
    print(f"  - Final gap: {scenario['front_gap'][-1]:.1f} cm")
    
    # 2. MPC 시뮬레이터 초기화
    print("\n[2/4] Initializing MPC Simulator...")
    try:
        simulator = MPCSimulator()
        print("  ✓ Simulator initialized")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 3. 시뮬레이션 실행
    print("\n[3/4] Running MPC simulation...")
    try:
        result = simulator.run_scenario(scenario['front_gap'])
        print("  ✓ Simulation completed")
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 4. 결과 검증
    print("\n[4/4] Validating results...")
    
    success = result.get('success', False)
    features = result.get('features', np.array([]))
    labels = result.get('labels', np.array([]))
    states = result.get('states', [])
    
    print(f"  - Success: {success}")
    print(f"  - Features shape: {features.shape}")
    print(f"  - Labels shape: {labels.shape}")
    print(f"  - Num states: {len(states)}")
    
    if len(features) > 0:
        print(f"\n  Feature statistics (first 5 dims):")
        for i, name in enumerate(['v_cmd', 'ey', 'fg', 'ttc', 'left_clear']):
            print(f"    - {name:12s}: mean={features[:, i].mean():.3f}, std={features[:, i].std():.3f}")
        
        print(f"\n  Label statistics:")
        print(f"    - delta_deg: mean={labels[:, 0].mean():.3f}, std={labels[:, 0].std():.3f}, range=[{labels[:, 0].min():.1f}, {labels[:, 0].max():.1f}]")
        print(f"    - v_cmd:     mean={labels[:, 1].mean():.3f}, std={labels[:, 1].std():.3f}")
        
        print(f"\n  State distribution:")
        from collections import Counter
        state_counts = Counter(states)
        for state, count in state_counts.most_common():
            print(f"    - {state:15s}: {count:4d} ({count/len(states)*100:.1f}%)")
    
    # 검증
    checks = [
        ("Success flag", success),
        ("Features shape", features.shape == (len(scenario['front_gap']), 10)),
        ("Labels shape", labels.shape == (len(scenario['front_gap']), 2)),
        ("Num samples", len(features) == len(labels)),
        ("State history", len(states) > 0)
    ]
    
    print("\n" + "=" * 70)
    print("  Validation Results:")
    print("=" * 70)
    
    all_passed = True
    for check_name, check_result in checks:
        status = "✓ PASS" if check_result else "✗ FAIL"
        print(f"  {status:8s} {check_name}")
        if not check_result:
            all_passed = False
    
    return all_passed


if __name__ == '__main__':
    success = test_single_scenario()
    
    print("\n" + "=" * 70)
    if success:
        print("  ✅ ALL TESTS PASSED!")
        print("  Ready to generate full dataset.")
    else:
        print("  ❌ TESTS FAILED!")
        print("  Please fix the issues above.")
    print("=" * 70 + "\n")
    
    sys.exit(0 if success else 1)
