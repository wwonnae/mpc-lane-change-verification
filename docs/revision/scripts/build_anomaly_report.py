"""
이상탐지 확장 보고서 조립·검증.

장 파일(docs/revision/anomaly/chapters/*.md, 파일명 순서)을 합쳐 docs/revision/확장_센서시계열이상탐지_2026.md를 만든다.
본문 수치는 **ANOMALY_NUMBERS.csv 참조로만** 쓴다:  {{a:KEY}} → key=KEY 행의 값.
--check:
  1) 참조 해석 실패, 2) 참조 밖 생 숫자가 CSV(값·항목·비고)에 없는지(구조 번호·식별자·날짜·코드 스팬 제외, 5 이하 정수 허용 —
     기존 build_report.py와 같은 규칙, 그 함수를 import해 재사용), 3) 모든 표·그림 캡션에 조건 태그[데이터·호스트·버전·커밋],
  4) 첫 장 첫 문단에 "확장"·"제출본"·"기존 개정 보고서" 명시, 5) "개선" 단어가 나온 줄 목록(WARN — 신뢰구간이 겹치는 차이를
     개선으로 단정하지 않았는지 사람이 확인).
기존 REVISION_NUMBERS.csv·build_report.py·기존 보고서는 읽기만 하고 수정하지 않는다.
사용(저장소 루트): python docs/revision/scripts/build_anomaly_report.py [--check]
"""
import argparse
import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from build_report import num_set, raw_numbers, estimate_pages, gfm_safe_tildes  # noqa: E402  (기존 규칙 재사용)

ROOT = HERE.parents[2]
REV = ROOT / "docs/revision"
CH = REV / "anomaly/chapters"
OUT = REV / "확장_센서시계열이상탐지_2026.md"
CSV = REV / "ANOMALY_NUMBERS.csv"
TAGS = ("[데이터:", "호스트:", "버전:", "커밋:")


def load_csv():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    return rows, {r["key"]: r for r in rows}


def render(src, by, errors, where):
    def rep(m):
        r = by.get(m.group(1))
        if r is None:
            errors.append(f"{where}: CSV 행 {m.group(1)} 없음")
            return f"[?{m.group(1)}]"
        return r["값"]
    return re.sub(r"\{\{a:([^}]+)\}\}", rep, src)


def check(path, src, rendered, allowed, errors, warns):
    where = path.name
    for tok, ctx in raw_numbers(src):
        try:
            v = round(abs(float(tok.replace(",", ""))), 6)
        except ValueError:
            continue
        if v <= 5 and float(v).is_integer():
            continue
        if v not in allowed:
            errors.append(f"{where}: CSV에 없는 생 숫자 {tok} — «{ctx}»")
    rl = rendered.splitlines()
    for i, line in enumerate(rl):
        if line.startswith("|") and (i == 0 or not rl[i - 1].startswith("|")):
            j = i - 1
            while j >= 0 and not rl[j].strip():
                j -= 1
            cap = rl[j] if j >= 0 else ""
            if not all(t in cap for t in TAGS):
                errors.append(f"{where}: 표(줄 {i + 1}) 캡션에 조건 태그 누락 — «{cap[:60]}»")
    for i, line in enumerate(src.splitlines()):
        if "개선" in line:
            warns.append(f"{where}:{i + 1}: «{line.strip()[:90]}»")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows, by = load_csv()
    allowed = num_set([r["값"] for r in rows] + [r["항목"] for r in rows] + [r["비고"] for r in rows])
    errors, warns, parts = [], [], []
    files = sorted(CH.glob("*.md"))
    for path in files:
        src = path.read_text(encoding="utf-8")
        rendered = render(src, by, errors, path.name)
        parts.append(rendered)
        if args.check:
            check(path, src, rendered, allowed, errors, warns)
    if args.check and files:
        first = files[0].read_text(encoding="utf-8")
        para = next((p for p in first.split("\n\n") if p.strip() and not p.lstrip().startswith(("#", "**기술", "이원회"))), "")
        for need in ("확장", "제출본", "기존 개정 보고서"):
            if need not in para:
                errors.append(f"{files[0].name}: 첫 문단에 '{need}' 명시 없음")
    OUT.write_text(gfm_safe_tildes("\n\n".join(parts) + "\n"), encoding="utf-8")
    pages, chars, trows, figs = estimate_pages("\n".join(parts))
    print(f"조립: {OUT.name} ({len(parts)}개 장 파일), 분량 추정 {pages:.1f}쪽(글자 {chars:,}, 표 행 {trows})")
    if args.check:
        print(f"WARN '개선' 사용 {len(warns)}줄(신뢰구간 겹침 단정 여부 수동 확인):")
        for w in warns:
            print("  ", w)
        for e in errors:
            print("ERROR", e)
        print("--check:", "통과" if not errors else f"실패 {len(errors)}건")
        sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
