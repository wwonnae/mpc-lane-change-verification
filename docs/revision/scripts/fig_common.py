"""
기술보고서 그림 공통 설정(DESIGN_REVISION §8-4). 모든 그림은 docs/revision/figures/에 PNG로 저장하고, 그림 하단에 데이터 출처·조건 코드를
한 줄로 박아 넣는다(캡션 전문은 figures/CAPTIONS.md). 조건 코드: 부록 B(E1/E2/E3 데이터, D dev, T0 계산시간 seed 0~99, H1 공식 호스트).
"""
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FIG_DIR = ROOT / "docs/revision/figures"
DATA_DIR = ROOT / "docs/revision/data"
META = FIG_DIR / "figures_meta.json"

plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 110

C_BASE = "#6e7781"   # baseline v1.1
C_V1 = "#bf8700"     # improved v1
C_V2 = "#1f6feb"     # improved v2 (교사)
C_S10 = "#d1242f"    # Student S10
C_S9 = "#8250df"     # Student 9입력
C_ONNX = "#2da44e"
STATE_ORDER = ["KEEP_L2", "EVADE_L", "KEEP_L1", "RETURN_TO_L2"]


def save(fig, fid, title, source, cond, selection, replaces, script):
    """그림 저장 + 하단 조건 태그 + 메타(캡션 생성용) 기록."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.text(0.01, 0.005, f"[데이터: {cond}]  출처: {source}  |  생성: docs/revision/scripts/{script}",
             fontsize=7, color="#57606a", ha="left", va="bottom")
    path = FIG_DIR / f"{fid}.png"
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    meta = json.load(open(META, encoding="utf-8")) if META.exists() else {}
    meta[fid] = dict(title=title, source=source, cond=cond, selection=selection, replaces=replaces, script=script,
                     file=f"figures/{fid}.png")
    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print("saved", path)
