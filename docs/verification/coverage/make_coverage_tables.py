"""coverage json -> 모듈별 구문·분기 커버리지 표 + 미커버 분기 목록(markdown).

사용(저장소 루트):
  python -m coverage json --rcfile=docs/verification/coverage/.coveragerc -o <임시폴더>/coverage.json
  python docs/verification/coverage/make_coverage_tables.py <임시폴더>/coverage.json \
      docs/verification/coverage/COVERAGE_TABLES.md

값은 전부 coverage.json에서 읽는다(상수 없음). 모듈 분류:
- "실행 스크립트": 파일에 `if __name__ == "__main__"`이 있는 모듈(측정·평가·학습 CLI). 단위 테스트 대상이 아니라
  사용자가 직접 실행해 결과 폴더를 만드는 코드다.
- "라이브러리": 그 밖의 모듈(제어기·시뮬레이터·탐지기 본체, 집계 함수).
"""
import json
import sys
from pathlib import Path

PACKAGES = ("baseline", "improved", "anomaly")


def _pkg(path: str) -> str:
    parts = Path(path).parts
    for p in PACKAGES:
        if p in parts:
            sub = parts[parts.index(p) + 1:-1]
            return p + ("/" + "/".join(sub) if sub else "")
    return "(기타)"


def _is_script(path: str) -> bool:
    try:
        return '__name__ == "__main__"' in Path(path).read_text(encoding="utf-8")
    except OSError:
        return False


def _pct(num, den):
    return "—" if den == 0 else f"{100.0 * num / den:.1f}%"


def _branch_str(src, dst):
    return f"{src}→{'exit' if dst < 0 else dst}"


def main(cov_json: str, out_md: str):
    d = json.loads(Path(cov_json).read_text(encoding="utf-8"))
    rows = []
    for f, v in d["files"].items():
        s = v["summary"]
        if s["num_statements"] == 0:  # 빈 __init__.py 등(report의 skip_empty와 같은 처리)
            continue
        rows.append(dict(
            file=f.replace("\\", "/"), pkg=_pkg(f), script=_is_script(f),
            st=s["num_statements"], st_cov=s["covered_lines"],
            br=s["num_branches"], br_cov=s["covered_branches"],
            missing_branches=v.get("missing_branches", []),
        ))
    rows.sort(key=lambda r: (r["pkg"], r["script"], r["file"]))

    def agg(sel):
        return (sum(r["st_cov"] for r in sel), sum(r["st"] for r in sel),
                sum(r["br_cov"] for r in sel), sum(r["br"] for r in sel))

    out = []
    meta = d.get("meta", {})
    out.append(f"<!-- 자동 생성: make_coverage_tables.py, coverage {meta.get('version')}, "
               f"branch={meta.get('branch_coverage')}, 측정 시각 {meta.get('timestamp')} -->\n")
    out.append("## 패키지 × 분류 요약\n")
    out.append("| 패키지 | 분류 | 모듈 수 | 구문 (커버/전체) | 구문 % | 분기 (커버/전체) | 분기 % |")
    out.append("|---|---|---:|---:|---:|---:|---:|")
    groups = {}
    for r in rows:
        groups.setdefault((r["pkg"].split("/")[0], r["script"]), []).append(r)
    for (pkg, script), sel in sorted(groups.items()):
        sc, st, bc, bt = agg(sel)
        out.append(f"| {pkg} | {'실행 스크립트' if script else '라이브러리'} | {len(sel)} | {sc}/{st} | {_pct(sc, st)} "
                   f"| {bc}/{bt} | {_pct(bc, bt)} |")
    for label, sel in (("라이브러리 합계", [r for r in rows if not r["script"]]),
                       ("실행 스크립트 합계", [r for r in rows if r["script"]]), ("전체", rows)):
        sc, st, bc, bt = agg(sel)
        out.append(f"| **{label}** | | {len(sel)} | {sc}/{st} | {_pct(sc, st)} | {bc}/{bt} | {_pct(bc, bt)} |")

    out.append("\n## 모듈별\n")
    out.append("| 모듈 | 분류 | 구문 (커버/전체) | 구문 % | 분기 (커버/전체) | 분기 % | 미커버 분기 수 |")
    out.append("|---|---|---:|---:|---:|---:|---:|")
    for r in rows:
        out.append(f"| `{r['file']}` | {'스크립트' if r['script'] else '라이브러리'} | {r['st_cov']}/{r['st']} "
                   f"| {_pct(r['st_cov'], r['st'])} | {r['br_cov']}/{r['br']} | {_pct(r['br_cov'], r['br'])} "
                   f"| {len(r['missing_branches'])} |")

    out.append("\n## 미커버 분기 목록 — 라이브러리 모듈\n")
    out.append("`행A→행B`: 행A의 판단에서 행B로 가는 경로가 테스트 중 한 번도 실행되지 않음(`exit` = 함수 종료).\n")
    for r in rows:
        if r["script"] or not r["missing_branches"]:
            continue
        brs = ", ".join(_branch_str(a, b) for a, b in r["missing_branches"])
        out.append(f"- `{r['file']}` ({len(r['missing_branches'])}): {brs}")
    out.append("\n## 미커버 분기 수 — 실행 스크립트\n")
    out.append("행 단위 목록은 coverage.json에 있다(약 1.4 MB라 저장소에 넣지 않음 — COVERAGE.md의 재생성 명령으로 다시 만든다).\n")
    for r in rows:
        if r["script"] and r["missing_branches"]:
            out.append(f"- `{r['file']}`: {len(r['missing_branches'])}/{r['br']}")
    Path(out_md).write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
