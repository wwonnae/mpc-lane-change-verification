#!/usr/bin/env python3
"""
final_hierarchical_backup.py 파일이 올바르게 수정되었는지 확인
"""

def verify_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 체크포인트 1: metrics 초기화에 compute_time 있는지
    if "'compute_time': []" in content:
        print("✅ metrics 초기화에 'compute_time' 키 존재")
    else:
        print("❌ metrics 초기화에 'compute_time' 키 없음!")
        return False
    
    # 체크포인트 2: 방어적 코딩 있는지
    if "if 'compute_time' not in self.metrics:" in content:
        print("✅ 방어적 코딩 존재 (키 체크)")
    else:
        print("⚠️  방어적 코딩 없음 (선택사항)")
    
    # 체크포인트 3: compute_time 측정 코드 있는지
    count = content.count('t_compute_start = time.perf_counter()')
    if count >= 4:  # 최소 4개 상태에서 측정
        print(f"✅ compute_time 측정 코드 {count}개 발견")
    else:
        print(f"❌ compute_time 측정 코드가 부족함 ({count}개)")
        return False
    
    # 체크포인트 4: compute_time = 0.0 코드 있는지
    count = content.count('compute_time = 0.0')
    if count >= 3:  # line following, SAFE_STOP, else
        print(f"✅ compute_time = 0.0 초기화 {count}개 발견")
    else:
        print(f"❌ compute_time = 0.0 초기화가 부족함 ({count}개)")
        return False
    
    # 체크포인트 5: metrics 저장에 compute_time 있는지
    if "compute_time=np.array(self.metrics['compute_time'])" in content:
        print("✅ metrics 저장에 compute_time 포함")
    else:
        print("❌ metrics 저장에 compute_time 없음!")
        return False
    
    print("\n🎉 모든 체크포인트 통과! 파일이 올바르게 수정되었습니다.")
    return True

if __name__ == '__main__':
    import sys
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'final_hierarchical_backup.py'
    print(f"검증 대상: {filepath}\n")
    success = verify_file(filepath)
    sys.exit(0 if success else 1)
