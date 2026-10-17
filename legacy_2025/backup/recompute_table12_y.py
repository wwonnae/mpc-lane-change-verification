import numpy as np

# 1) metrics.npz 불러오기 (경로는 네 프로젝트에 맞게 수정)
data = np.load("runs/metrics.npz", allow_pickle=True)

# 2) y값과 FSM 상태 배열 가져오기
#   - 실제 키 이름이 다를 수도 있으니, npz 안에 어떤 키가 있는지는
#     print(data.files) 로 한번 찍어보고 맞춰줘.
print("keys:", data.files)

y = data["y"]          # shape: (N,)
state_arr = data["state"]  # shape: (N,)

# 3) 상태별 y 허용 범위(방식 B)
def bounds_for_state(s: str):
    if s in ("KEEP_L2", "SAFE_STOP"):
        return -0.15, 0.15       # L2 구간
    elif s == "KEEP_L1":
        return 0.15, 0.45        # L1 구간
    elif s in ("EVADE_L", "RETURN_TO_L2"):
        return -0.15, 0.45       # 차선 변경 중 전체 도로
    else:
        # 혹시 모르는 상태는 도로 전체 범위로 본다
        return -0.15, 0.45

# 4) 위반 횟수 세기
under = 0
over = 0
total = len(y)

for yi, si in zip(y, state_arr):
    # npz에 들어간 문자열 타입이 np.bytes_일 수 있어서 한 번 정규화
    if isinstance(si, bytes):
        s = si.decode()
    else:
        s = str(si)

    lo, hi = bounds_for_state(s)

    if yi < lo:
        under += 1
    elif yi > hi:
        over += 1
    # else: valid

valid = total - under - over

# 5) 결과 출력
print("Total samples    :", total)
print("Under violations :", under, f"({under/total*100:.4f}%)")
print("Over  violations :", over, f"({over/total*100:.4f}%)")
print("Valid (in range) :", valid, f"({valid/total*100:.4f}%)")
