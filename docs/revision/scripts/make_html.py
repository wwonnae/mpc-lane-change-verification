"""조립된 보고서(Markdown) → 인쇄용 단일 HTML.

외부 패키지 없이 보고서가 쓰는 Markdown 부분집합만 변환한다: 제목, 문단, 목록(중첩), 표, 그림, 굵게/기울임, 코드, 링크, 수평선.
- 한글 글꼴: 이 PC의 Noto Sans KR(C:/Windows/Fonts/NotoSansKR-VF.ttf)
- 그림: 보고서와 같은 폴더 기준 상대경로 그대로(figures/…)
- 페이지 나눔: 장(# 제목) 단위
- 표: 페이지 폭에 맞춤(열이 많거나 행이 많은 표는 글자를 줄임)

사용: python docs/revision/scripts/build_report.py --check  (먼저 조립)
      python docs/revision/scripts/make_html.py
출력: docs/revision/재구현검증보고서_2026.html → Chrome에서 열어 인쇄 → PDF로 저장
"""
import html
import re
from pathlib import Path

REV = Path(__file__).resolve().parents[1]
SRC = REV / "재구현검증보고서_2026.md"
OUT = REV / "재구현검증보고서_2026.html"

CSS = """
@font-face { font-family: 'NotoKR'; src: local('Noto Sans KR'), url('file:///C:/Windows/Fonts/NotoSansKR-VF.ttf') format('truetype');
             font-weight: 100 900; }
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
:root { --text: #111; --muted: #555; --rule: #999; --head: #eee; }
html, body { background: #fff; color: var(--text); }
body { font-family: 'NotoKR', 'Noto Sans KR', 'Malgun Gothic', sans-serif; font-size: 10pt; line-height: 1.6;
       max-width: 178mm; margin: 0 auto; padding: 0 4mm; word-break: keep-all; overflow-wrap: anywhere; }
h1 { font-size: 16pt; margin: 0 0 8pt; padding-bottom: 4pt; border-bottom: 1.5pt solid var(--text); break-before: page; }
h1.first { break-before: auto; font-size: 18pt; }
h2 { font-size: 13pt; margin: 14pt 0 6pt; break-after: avoid; }
h3 { font-size: 11pt; margin: 12pt 0 4pt; break-after: avoid; }
h4 { font-size: 10pt; margin: 10pt 0 4pt; break-after: avoid; }
p { margin: 4pt 0 6pt; text-align: justify; }
ul, ol { margin: 4pt 0 6pt; padding-left: 16pt; }
li { margin: 2pt 0; }
code { font-family: 'Consolas', monospace; font-size: 8.5pt; background: #f3f3f3; padding: 0 2pt; overflow-wrap: anywhere; word-break: break-all; }
a { color: inherit; }
hr { border: 0; border-top: 0.75pt solid var(--rule); margin: 10pt 0; }
table { width: 100%; border-collapse: collapse; margin: 4pt 0 10pt; font-size: 8.5pt; line-height: 1.35; table-layout: auto; }
table.dense { font-size: 7.5pt; }
table.xdense { font-size: 6.8pt; }
th, td { border: 0.5pt solid var(--rule); padding: 2pt 3pt; vertical-align: top; text-align: left; }
th { background: var(--head); }
thead { display: table-header-group; }
tr { break-inside: avoid; }
p.caption { font-size: 9pt; margin-bottom: 2pt; break-after: avoid; }
figure { margin: 8pt 0 10pt; break-inside: avoid; }
figure img { display: block; max-width: 100%; max-height: 190mm; margin: 0 auto 4pt; }
figure figcaption { font-size: 8.5pt; color: var(--muted); }
@media screen { body { padding: 10mm 6mm; } h1 { margin-top: 24pt; } }
"""


def inline(t):
    codes = []

    def keep(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"

    t = re.sub(r"`([^`]*)`", keep, t)
    t = html.escape(t, quote=False).replace("\\|", "|")
    t = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![*\w])\*(?![\s*])(.+?)(?<![\s*])\*(?![*\w])", r"<em>\1</em>", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], t)


def split_row(line):
    s = line.strip().replace("\\|", "\x01")
    cells = s.strip("|").split("|")
    return [c.strip().replace("\x01", "\\|") for c in cells]


def table(lines):
    head = split_row(lines[0])
    body = [split_row(l) for l in lines[2:]]
    ncol, nrow = len(head), len(body)
    cls = "xdense" if ncol >= 9 or nrow > 40 else ("dense" if ncol >= 7 or nrow > 20 else "")
    out = [f'<table class="{cls}">' if cls else "<table>", "<thead><tr>"]
    out += [f"<th>{inline(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for r in body:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "\n".join(out)


LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def lists(lines):
    """들여쓰기 기반 중첩 목록. 항목 뒤의 더 깊게 들여쓴 비목록 줄은 이어지는 문장."""
    out, stack = [], []  # stack: (들여쓰기, 태그, 부모 항목 안의 하위 목록 여부)
    for line in lines:
        m = LIST_RE.match(line)
        if not m:
            if out and out[-1].endswith("</li>"):
                out[-1] = out[-1][:-5] + " " + inline(line.strip()) + "</li>"
            else:
                out.append(inline(line.strip()))
            continue
        ind, mk, text = len(m.group(1)), m.group(2), m.group(3)
        tag = "ol" if mk[0].isdigit() else "ul"
        while stack and ind < stack[-1][0]:
            _, t, nested = stack.pop()
            out.append(f"</{t}>" + ("</li>" if nested else ""))
        if not stack or ind > stack[-1][0]:
            if stack and out[-1].endswith("</li>"):
                out[-1] = out[-1][:-5]  # 하위 목록을 부모 항목 안에 넣음
                stack.append((ind, tag, True))
            else:
                stack.append((ind, tag, False))
            start = f' start="{mk[:-1]}"' if tag == "ol" and mk[:-1] != "1" else ""
            out.append(f"<{tag}{start}>")
        out.append(f"<li>{inline(text)}</li>")
    while stack:
        ind, tag, nested = stack.pop()
        out.append(f"</{tag}>" + ("</li>" if nested else ""))
    return "\n".join(out)


def convert(md):
    md = re.sub(r"<!--.*?-->", "", md, flags=re.S)
    lines = md.splitlines()
    out, i, first_h1 = [], 0, True
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            lv = len(m.group(1))
            cls = ' class="first"' if lv == 1 and first_h1 else ""
            if lv == 1:
                first_h1 = False
            out.append(f"<h{lv}{cls}>{inline(m.group(2))}</h{lv}>")
            i += 1
            continue
        if line.strip() == "---":
            out.append("<hr>")
            i += 1
            continue
        if line.startswith("|"):
            j = i
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            out.append(table(lines[i:j]))
            i = j
            continue
        if line.startswith("!["):
            img = inline(line.strip())
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            cap = ""
            if j < len(lines) and lines[j].startswith("*그림"):
                k = j
                while k < len(lines) and lines[k].strip():
                    k += 1
                cap = f"<figcaption>{inline(' '.join(l.strip() for l in lines[j:k]))}</figcaption>"
                j = k
            else:
                j = i + 1
            out.append(f"<figure>{img}{cap}</figure>")
            i = j
            continue
        if LIST_RE.match(line):
            j = i
            while j < len(lines) and lines[j].strip() and (LIST_RE.match(lines[j]) or lines[j].startswith(" ")):
                j += 1
            out.append(lists(lines[i:j]))
            i = j
            continue
        j = i
        while (j < len(lines) and lines[j].strip() and not lines[j].startswith(("|", "#", "![")) and lines[j].strip() != "---"
               and not (j > i and LIST_RE.match(lines[j]))):
            j += 1
        text = " ".join(l.strip() for l in lines[i:j])
        cls = ' class="caption"' if re.match(r"^\*\*(표|그림) ", text) else ""
        out.append(f"<p{cls}>{inline(text)}</p>")
        i = j
    return "\n".join(out)


def main():
    md = SRC.read_text(encoding="utf-8")
    title = re.search(r"^# (.+)$", md, re.M).group(1)
    body = convert(md)
    doc = (f'<!DOCTYPE html>\n<html lang="ko"><head><meta charset="utf-8">\n<title>{html.escape(title)}</title>\n'
           f"<style>{CSS}</style></head>\n<body>\n{body}\n</body></html>\n")
    OUT.write_text(doc, encoding="utf-8")
    print(f"{OUT} ({len(doc):,} bytes, 표 {body.count('<table')}, 그림 {body.count('<figure')}, 장 {body.count('<h1')})")


if __name__ == "__main__":
    main()
