"""run #6 조사용 실험 조건을 **임시 사본**에 적용한다(원본 저장소에는 적용을 거부한다).

사용
  python apply_condition.py make  --dest <폴더> [--commit 4c0c503]   # git archive로 thesis_v2만 풀어 사본 생성
  python apply_condition.py apply --root <사본> --cond A [--interval 50] [--time-limit 0.0003]

조건(PLAN.md)
  orig : 변경 없음
  A    : improved/config.py I5_TIME_LIMIT_SEC = 1e10 (OSQP 기본값과 같음 = time_limit 사실상 비활성)
  B    : improved/mpc.py I5 분기에 setup_kwargs["adaptive_rho_interval"] = <--interval> 추가
  C    : A + B
  T    : I5_TIME_LIMIT_SEC = <--time-limit> (지문 규칙 검증용 양성 대조 — 일부러 끊기게 함)
  D    : improved/mpc.py I5 분기에 setup_kwargs["adaptive_rho"] = 0 추가(adaptive rho 비활성, 0단계 보고 대안)

원본 보호: --root가 이 저장소 경로 안이면 거부한다. 단 GitHub Actions(환경변수 GITHUB_ACTIONS=true)에서
--ci를 주면 작업 공간 사본(체크아웃)에 적용한다 — 그 변경은 커밋하지 않는다.
적용 내용은 <root>/_run6_condition.json에 기록한다(파일별 변경 전후 sha256).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

CFG = "thesis_v2/improved/config.py"
MPC = "thesis_v2/improved/mpc.py"
TL_LINE = "I5_TIME_LIMIT_SEC = 0.045"
I5_ANCHOR = '            setup_kwargs["time_limit"] = improved_config.I5_TIME_LIMIT_SEC\n'


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


REPO = Path(__file__).resolve().parents[4]


def _inside_repo(root):
    """이 저장소(MPC_LINETRACING) 작업 트리 안인지. (홈 폴더 자체가 git 저장소인 PC가 있어 git 여부로는 판정하지 않는다.)"""
    try:
        Path(root).resolve().relative_to(REPO)
        return True
    except ValueError:
        return False


def _replace_once(path, old, new):
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        sys.exit(f"[apply_condition] {path}: 기준 문자열이 정확히 1번 있어야 함 (발견 {text.count(old)}회): {old!r}")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text.replace(old, new))


def apply(root, cond, interval=None, time_limit=None, ci=False):
    root = Path(root).resolve()
    if _inside_repo(root) and not (ci and os.environ.get("GITHUB_ACTIONS") == "true"):
        sys.exit(f"[apply_condition] 거부: {root} 는 저장소({REPO}) 안이다(원본 보호). 임시 사본에만 적용한다.")
    marker = root / "_run6_condition.json"
    if marker.exists():
        sys.exit(f"[apply_condition] 거부: 이미 조건이 적용된 사본이다 ({json.loads(marker.read_text())['cond']}).")
    cfg, mpc = root / CFG, root / MPC
    before = {CFG: _sha(cfg), MPC: _sha(mpc)}
    if cond in ("A", "C"):
        _replace_once(cfg, TL_LINE, "I5_TIME_LIMIT_SEC = 1e10  # run6_cause 조건 A")
    if cond == "T":
        if time_limit is None:
            sys.exit("[apply_condition] 조건 T는 --time-limit 필요")
        _replace_once(cfg, TL_LINE, f"I5_TIME_LIMIT_SEC = {time_limit!r}  # run6_cause 조건 T")
    if cond in ("B", "C"):
        if interval is None:
            sys.exit("[apply_condition] 조건 B/C는 --interval 필요")
        _replace_once(mpc, I5_ANCHOR,
                      I5_ANCHOR + f'            setup_kwargs["adaptive_rho_interval"] = {int(interval)}  # run6_cause 조건 B\n')
    if cond == "D":
        _replace_once(mpc, I5_ANCHOR, I5_ANCHOR + '            setup_kwargs["adaptive_rho"] = 0  # run6_cause 조건 D\n')
    if cond not in ("orig", "A", "B", "C", "T", "D"):
        sys.exit(f"[apply_condition] 알 수 없는 조건 {cond}")
    after = {CFG: _sha(cfg), MPC: _sha(mpc)}
    info = dict(cond=cond, interval=interval, time_limit=time_limit, before=before, after=after)
    marker.write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False))
    return info


def make(dest, commit):
    dest = Path(dest).resolve()
    repo = REPO
    if dest.exists() and any(dest.iterdir()):
        sys.exit(f"[apply_condition] 거부: {dest} 가 비어 있지 않다.")
    if _inside_repo(dest):
        sys.exit(f"[apply_condition] 거부: 사본은 저장소 밖에 만든다 ({dest}).")
    dest.mkdir(parents=True, exist_ok=True)
    full = subprocess.run(["git", "-C", str(repo), "rev-parse", commit], capture_output=True, text=True,
                          check=True).stdout.strip()
    arc = subprocess.run(["git", "-C", str(repo), "archive", "--format=tar", full, "thesis_v2",
                          ":(exclude)thesis_v2/results"], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dest)], input=arc, check=True)
    (dest / "_run6_copy.json").write_text(json.dumps(dict(commit=full, source=str(repo)), indent=1), encoding="utf-8")
    print(f"[apply_condition] 사본 생성: {dest} (commit {full})")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("--dest", required=True)
    m.add_argument("--commit", default="4c0c503")
    a = sub.add_parser("apply")
    a.add_argument("--root", required=True)
    a.add_argument("--cond", required=True)
    a.add_argument("--interval", type=int)
    a.add_argument("--time-limit", type=float)
    a.add_argument("--ci", action="store_true")
    args = ap.parse_args()
    if args.cmd == "make":
        make(args.dest, args.commit)
    else:
        apply(args.root, args.cond, args.interval, args.time_limit, args.ci)


if __name__ == "__main__":
    main()
