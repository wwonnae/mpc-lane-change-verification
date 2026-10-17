"""
기술보고서 조립·검증(DESIGN_REVISION §8-1).

장 파일(docs/revision/chapters/*.md, 파일명 순서)을 하나로 합쳐 docs/revision/재구현검증보고서_2026.md를 만든다.
본문 수치는 **CSV 참조로만** 쓴다:
  {{c:N}}   REVISION_NUMBERS.csv no=N 행의 개정판_값
  {{s:N}}   no=N 행의 제출본_값 — "제출본" 문구가 있는 줄 또는 "제출본" 열이 있는 표 안에서만 허용
  {{n:KEY}} 신규 행(no=N:KEY)의 개정판_값
  {{fig:F1}} 그림 삽입 + 캡션(figures_meta.json: 제목·데이터·조건·선택 규칙·대체 대상·생성 스크립트)
  {{appendixA_summary}} 분류별 요약표, {{appendixA_table}} 개정·재현불가_대체·라벨불일치_대체 행 대조표(나머지는 CSV)
--check:
  1) 참조 해석 실패, 2) 참조 밖의 생 숫자가 CSV에 없는 값인지(구조 번호·식별자·날짜 제외), 3) {{s:}} 위치 규칙,
  4) 그림 파일·참조 존재, 5) 모든 표 캡션에 조건 태그([데이터: …]), 6) OPEN 주석 수집 → OPEN_ITEMS.md, 7) 분량 추정.
사용: python docs/revision/scripts/build_report.py [--check]
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
REV = ROOT / "docs/revision"
CH = REV / "chapters"
OUT = REV / "재구현검증보고서_2026.md"
CSV = REV / "REVISION_NUMBERS.csv"
META = REV / "figures/figures_meta.json"
OPEN_OUT = REV / "OPEN_ITEMS.md"

NUM = re.compile(r"(?<![\w.])[-−]?\d+(?:[.,]\d+)*")



def gfm_safe_tildes(text):
    """GitHub(GFM)는 단일 ~ 두 개를 취소선으로 렌더링한다. 범위 표기 ~를 –로 바꾼다(코드 블록·코드 스팬·~~ 제외).
    본문 수치 검사(--check)는 바꾸기 전 원고로 하므로 검사 결과에는 영향이 없다."""
    def seg(s):
        return re.sub(r"(?<!~)~(?!~)(?=\S)|(?<=\S)(?<!~)~(?!~)", "–", s)
    parts = re.split(r"(```.*?```)", text, flags=re.S)
    for k in range(0, len(parts), 2):
        sub = re.split(r"(`[^`\n]*`)", parts[k])
        for j in range(0, len(sub), 2):
            sub[j] = seg(sub[j])
        parts[k] = "".join(sub)
    return "".join(parts)

def load_csv():
    rows = list(csv.DictReader(open(CSV, encoding="utf-8-sig")))
    by = {r["no"]: r for r in rows}
    return rows, by


def num_set(texts):
    s = set()
    for t in texts:
        for m in NUM.findall(t.replace("−", "-")):
            m = m.replace(",", "")
            try:
                s.add(round(abs(float(m)), 6))
            except ValueError:
                pass
    return s


# 그림별 호스트·버전·커밋 태그(커밋 코드는 부록 B 표). 데이터 코드는 figures_meta의 cond.
FIG_TAGS = {
    "F1": ("H1(재생)", "baseline v1.1", "C2 평가 · C7 재생"),
    "F2": ("H1(재생)", "baseline v1.1", "C2 평가 · C7 재생"),
    "F3": ("H1", "Student 9입력 · v2 MPC", "C4"),
    "F4": ("H1", "baseline v1.1 · improved v2", "C2"),
    "F5": ("H1", "baseline v1.1 · improved v1 · improved v2", "C2 · C3"),
    "F6": ("H1", "교사 baseline v1.1 · v2 MPC", "C5"),
    "F7": ("H1(재생)", "v2 MPC · Student S10", "C5 평가 · C7 재생"),
    "F8": ("H1(재생)", "v2 MPC · Student S10", "C5 평가 · C7 재생"),
    "F9": ("H1(공식 조건)", "baseline v1.1 · v2 MPC · Student S10", "C7"),
}


# 그림별 호스트·버전·커밋 태그(커밋 코드는 부록 B 표 B-3). 데이터 코드는 figures_meta의 cond.
FIG_TAGS = {
    "F1": ("H1(재생)", "baseline v1.1", "C2 평가 · C7 재생"),
    "F2": ("H1(재생)", "baseline v1.1", "C2 평가 · C7 재생"),
    "F3": ("H1", "Student 9입력 · v2 MPC", "C4"),
    "F4": ("H1", "baseline v1.1 · improved v2", "C2"),
    "F5": ("H1", "baseline v1.1 · improved v1 · improved v2", "C2 · C3"),
    "F6": ("H1", "교사 baseline v1.1 · v2 MPC", "C5"),
    "F7": ("H1(재생)", "v2 MPC · Student S10", "C5 평가 · C7 재생"),
    "F8": ("H1(재생)", "v2 MPC · Student S10", "C5 평가 · C7 재생"),
    "F9": ("H1(공식 조건)", "baseline v1.1 · v2 MPC · Student S10", "C7"),
}


def fig_block(fid_short, meta):
    key = next((k for k in meta if k.split("_")[0] == fid_short), None)
    if key is None:
        return None
    m = meta[key]
    h, v, c = FIG_TAGS[fid_short]
    return (f"![{m['title']}](figures/{key}.png)\n\n"
            f"*그림 {fid_short}. {m['title']}.* [데이터: {m['cond']} | 호스트: {h} | 버전: {v} | 커밋: {c}] 출처: `{m['source']}`. "
            f"대표 에피소드 선택: {m['selection']}. 대체 대상: {m['replaces']}. 생성: `{m['script']}`.")


# 부록 A.5(사용자 결정 2026-09-25, OPEN #2): 카테고리 요약표 + 전문은 개정·재현불가_대체·라벨불일치_대체만, 나머지는 CSV 참조
FULL_CATS = ("개정", "재현불가_대체", "라벨불일치_대체")
CAT_DESC = {
    "설정유지": "제출본 설정·파라미터를 그대로 사용",
    "개정": "계산으로 실현 불가가 증명된 명세 값 수정(A.1, [개정] 3건이 여러 위치에 표기)",
    "재측정": "같은 정의로 새로 측정한 값으로 교체(삭제는 직접 비교가 불가능한 행)",
    "재현불가_대체": "근거 파일·생성 기록이 없어 재현하지 못해 새 측정값으로 대체(A.3)",
    "라벨불일치_대체": "표 라벨과 제출본 스크립트의 실제 계산이 달라 라벨대로 다시 측정(A.3)",
    "정의변경_대체": "표본·데이터 정의가 달라진 값(예: 전체 스텝 → MPC 호출 스텝)",
    "내부불일치_정정": "제출본 안의 두 위치가 서로 맞지 않아 한 정의로 정정(A.3)",
    "미적용": "제출본 방법 중 이 보고서가 적용하지 않은 항목(V장 3절)",
}


def _cell(x):
    return x.replace("|", "／").replace("\n", " ")


def appendix_a_summary(rows):
    from collections import Counter
    sub = [r for r in rows if not r["no"].startswith("N:")]
    cnt = Counter((r["분류"], r["처리"]) for r in sub)
    order = list(CAT_DESC)
    out = ["| 분류 | 처리 | 행 수 | 뜻 | 표 A-2 전문 수록 |", "|---|---|---|---|---|"]
    for (cat, how), n in sorted(cnt.items(), key=lambda x: (order.index(x[0][0]) if x[0][0] in order else 99, x[0][1])):
        out.append(f"| {cat} | {how} | {n} | {CAT_DESC.get(cat, '—')} | {'수록' if cat in FULL_CATS else 'CSV 참조'} |")
    out.append(f"| **합계** | | **{len(sub)}** | | 수록 {sum(1 for r in sub if r['분류'] in FULL_CATS)}행 |")
    return "\n".join(out)


def appendix_a_table(rows):
    out = ["| no | 쪽 | 제출본 위치 | 항목 | 제출본 값 | 개정판 값 | 분류 | 조건 | 전사검증 |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["no"].startswith("N:") or r["분류"] not in FULL_CATS:
            continue
        chk = "확인필요" if r["전사검증"].startswith("확인필요") else r["전사검증"]
        out.append(f"| {r['no']} | {r['쪽']} | {_cell(r['위치'])} | {_cell(r['항목'])} | {_cell(r['제출본_값'])} | "
                   f"{_cell(r['개정판_값'])} | {r['분류']} | {r['조건_코드']} | {_cell(chk)} |")
    return "\n".join(out)


def render(text, by, meta, rows, errors, where):
    def rep(m):
        kind, key = m.group(1), m.group(2)
        if kind == "fig":
            b = fig_block(key, meta)
            if b is None:
                errors.append(f"{where}: 그림 {key} 없음")
                return f"[그림 {key} 없음]"
            return b
        rid = f"N:{key}" if kind == "n" else key
        r = by.get(rid)
        if r is None:
            errors.append(f"{where}: CSV 행 {rid} 없음")
            return f"[?{rid}]"
        return r["제출본_값"] if kind == "s" else r["개정판_값"]
    text = re.sub(r"\{\{appendixA_table\}\}", lambda m: appendix_a_table(rows), text)
    text = re.sub(r"\{\{appendixA_summary\}\}", lambda m: appendix_a_summary(rows), text)
    return re.sub(r"\{\{(c|s|n|fig):([^}]+)\}\}", rep, text)


STRIP = [
    (re.compile(r"<!--.*?-->", re.S), " "),
    (re.compile(r"\{\{[^}]+\}\}"), " "),
    (re.compile(r"`[^`]*`"), " "),
    (re.compile(r"\]\([^)]*\)"), "] "),
    (re.compile(r"20\d\d[-.]\d\d(?:[-.]\d\d)?"), " "),
    (re.compile(r"(?<!\d)20(?:25|26)(?=년|\b|[.\s)])"), " "),
    (re.compile(r"\[\d+\]"), " "),   # 문헌 인용 번호 [1]~[6]
    (re.compile(r"[A-Za-z§ψδΔ_][A-Za-z0-9_.'\-]*\d[A-Za-z0-9_.'\-]*"), " "),   # F1, S10, E2, v1.1, REQ-FSM-02e, §20, p99, KEEP_L2
    (re.compile(r"(표|그림|부록)\s*[A-Z]?\d*(?:-\d+)?"), " "),
    (re.compile(r"(식|장|절|단계|세션|후보|결정|개정|항목|조건 코드)\s*\(?\d+\)?(?:~\(?\d+\)?)?"), " "),
    (re.compile(r"^\s*\d+\.\s", re.M), " "),
    (re.compile(r"^#+.*$", re.M), " "),
    (re.compile(r"\[[^\]]*\]\("), " "),
]


def raw_numbers(src):
    t = src
    for rx, r in STRIP:
        t = rx.sub(r, t)
    out = []
    for line in t.splitlines():
        for m in NUM.findall(line.replace("−", "-")):
            out.append((m, line.strip()[:80]))
    return out


def check_chapter(path, src, rendered, csv_new, csv_old_only, errors, warns):
    where = path.name
    # 2) 생 숫자(참고문헌 파일은 서지 번호·연도·쪽수라 제외)
    for tok, ctx in ([] if path.name.startswith("80_") else raw_numbers(src)):
        try:
            v = round(abs(float(tok.replace(",", ""))), 6)
        except ValueError:
            continue
        if v <= 5 and float(v).is_integer():
            continue  # 구조용 작은 정수(단계·개수 표현)
        if v in csv_new:
            continue
        if v in csv_old_only:
            if "제출본" not in ctx:
                errors.append(f"{where}: 제출본 전용 값 {tok}가 '제출본' 문맥 밖에 생으로 쓰임 — «{ctx}»")
            continue
        errors.append(f"{where}: CSV에 없는 생 숫자 {tok} — «{ctx}»")
    # 3) {{s:}} 위치
    lines = src.splitlines()
    table_has_sub = False
    for i, line in enumerate(lines):
        if line.startswith("|") and ("제출본" in line) and (i == 0 or not lines[i - 1].startswith("|")):
            table_has_sub = True
        if not line.startswith("|"):
            table_has_sub = False
        if "{{s:" in line and "제출본" not in line and not (line.startswith("|") and table_has_sub):
            errors.append(f"{where}:{i + 1}: 제출본 값 참조가 '제출본' 문맥 밖")
    # 4) 그림 파일
    for m in re.finditer(r"!\[[^\]]*\]\((figures/[^)]+)\)", rendered):
        if not (REV / m.group(1)).exists():
            errors.append(f"{where}: 그림 파일 없음 {m.group(1)}")
    for m in re.finditer(r"그림 (F\d)", src):
        if not list((REV / "figures").glob(f"{m.group(1)}_*.png")):
            errors.append(f"{where}: 본문이 참조한 그림 {m.group(1)} 파일 없음")
    # 5) 표 캡션 조건 태그: 표 블록 바로 위(빈 줄 건너뜀) 캡션 줄에 [데이터: …] 필수
    rl = rendered.splitlines()
    for i, line in enumerate(rl):
        if line.startswith("|") and (i == 0 or not rl[i - 1].startswith("|")):
            j = i - 1
            while j >= 0 and not rl[j].strip():
                j -= 1
            cap = rl[j] if j >= 0 else ""
            if not all(t in cap for t in ("[데이터:", "호스트:", "버전:", "커밋:")):
                errors.append(f"{where}: 표(줄 {i + 1})의 캡션에 조건 태그[데이터·호스트·버전·커밋] 누락 — «{cap[:60]}»")
    # 그림 캡션(삽입된 이미지 다음 줄)
    for i, line in enumerate(rl):
        if line.startswith("!["):
            nxt = next((x for x in rl[i + 1:] if x.strip()), "")
            if not all(t in nxt for t in ("[데이터:", "호스트:", "버전:", "커밋:")):
                errors.append(f"{where}: 그림(줄 {i + 1}) 캡션에 조건 태그[데이터·호스트·버전·커밋] 누락")


def estimate_pages(text):
    lines = text.splitlines()
    table_rows = sum(1 for l in lines if l.startswith("|"))
    figs = sum(1 for l in lines if l.startswith("!["))
    prose = "\n".join(l for l in lines if not l.startswith("|") and not l.startswith("!["))
    chars = len(re.sub(r"\s+", " ", prose))
    return chars / 1700 + table_rows / 38 + figs * 0.45, chars, table_rows, figs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows, by = load_csv()
    meta = json.load(open(META, encoding="utf-8"))
    csv_new = num_set([r["개정판_값"] for r in rows] + [r["비고"] for r in rows] + [r["조건_코드"] for r in rows]
                      + [r["항목"] for r in rows if r["no"].startswith("N:")])
    csv_old = num_set([r["제출본_값"] for r in rows])
    csv_old_only = csv_old - csv_new
    errors, warns, opens = [], [], []
    parts = []
    body_text, app_text, app_files = [], [], []
    for path in sorted(CH.glob("*.md")):
        src = path.read_text(encoding="utf-8")
        rendered = render(src, by, meta, rows, errors, path.name)
        parts.append(rendered)
        (app_text if path.name.startswith("9") else body_text).append(rendered)
        if path.name.startswith("9"):
            app_files.append((path.name, rendered))
        for m in re.finditer(r"<!--\s*OPEN:(.*?)-->", src, re.S):
            line = src[:m.start()].count("\n") + 1
            opens.append((path.name, line, " ".join(m.group(1).split())))
        if args.check:
            check_chapter(path, src, rendered, csv_new, csv_old_only, errors, warns)
    OUT.write_text(gfm_safe_tildes("\n\n".join(parts) + "\n"), encoding="utf-8")
    # OPEN_ITEMS.md
    lines = ["# OPEN 항목 (집필 중 판단 보류·결정 필요)", "",
             "`build_report.py`가 장 파일의 `<!-- OPEN: … -->` 주석을 모아 자동 생성합니다. 형식: `[우선순위] 내용 | 필요한 결정`.",
             "우선순위: **결정** = 사용자 결정 필요, **확인** = 사실 확인 필요, **참고** = 기록만.", "",
             "| # | 우선순위 | 위치 | 내용 | 필요한 결정 |", "|---|---|---|---|---|"]
    def prio(t):
        return 0 if t.startswith("[결정]") else (1 if t.startswith("[확인]") else 2)
    for k, (fn, ln, t) in enumerate(sorted(opens, key=lambda x: (prio(x[2]), x[0], x[1])), 1):
        p = re.match(r"\[(결정|확인|참고)\]\s*", t)
        pr = p.group(1) if p else "참고"
        body = t[p.end():] if p else t
        what, _, need = body.partition("|")
        lines.append(f"| {k} | {pr} | `chapters/{fn}:{ln}` | {what.strip()} | {need.strip() or '—'} |")
    OPEN_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    bp, bc, bt, bf = estimate_pages("\n".join(body_text))
    ap_, ac, at, af = estimate_pages("\n".join(app_text))
    print(f"조립: {OUT.name} ({len(parts)}개 장 파일)")
    print(f"분량 추정: 본문 {bp:.1f}쪽(글자 {bc:,}, 표 행 {bt}, 그림 {bf}) + 부록 {ap_:.1f}쪽(표 행 {at})")
    for fn, t in app_files:
        print(f"  부록 {fn}: {estimate_pages(t)[0]:.1f}쪽")
    print(f"OPEN 항목 {len(opens)}개 → {OPEN_OUT.name}")
    if args.check:
        for w in warns:
            print("WARN", w)
        for e in errors:
            print("ERROR", e)
        print("--check:", "통과" if not errors else f"실패 {len(errors)}건")
        sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
