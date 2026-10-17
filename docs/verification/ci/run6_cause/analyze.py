"""run6_cause 실험 결과 집계(PLAN.md §4의 사전 선언 정의를 그대로 구현). 원자료는 읽기만 한다.

사용: python analyze.py --exp-dir <out_dir> [--json summary.json] [--md summary.md] [--noload-threshold 10]
"""
import argparse
import datetime
import gzip
import json
from collections import Counter, defaultdict
from pathlib import Path

from scipy.stats import beta, fisher_exact

TARGETS = ("i5", "i4_rec", "i4_cl100", "i4_cl101", "base")
CPU_KEYS = ("total_pct", "exp_pct", "load_pct", "other_pct", "ide_pct", "other_excl_ide_pct", "other_adj_pct")


def ts(s):
    """ISO 시각 → epoch 초. sysmon(.NET)은 소수 7자리라 6자리로 자른다."""
    if s is None:
        return None
    if "." in s:
        head, rest = s.split(".", 1)
        i = 0
        while i < len(rest) and rest[i].isdigit():
            i += 1
        s = head + "." + rest[:min(i, 6)] + rest[i:]
    return datetime.datetime.fromisoformat(s).timestamp()


def cp_interval(k, n, alpha=0.05):
    """Clopper-Pearson 양측 95% 구간."""
    if n == 0:
        return (None, None)
    lo = 0.0 if k == 0 else beta.ppf(alpha / 2, k, n - k + 1)
    hi = 1.0 if k == n else beta.ppf(1 - alpha / 2, k + 1, n - k)
    return (float(lo), float(hi))


def upper95_zero(n):
    """불일치 0회일 때 단측 95% 상한(= 1 - 0.05^(1/n))."""
    return 1 - 0.05 ** (1 / n) if n else None


def load_batches(exp_dir):
    out = []
    for p in sorted((Path(exp_dir) / "batches").glob("*.json.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            d = json.load(f)
        out.append(d)
    return out


def load_sysmon(exp_dir):
    p = Path(exp_dir) / "sysmon.jsonl"
    rows = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                d = json.loads(line)
                if d.get("tag") == "periodic":
                    d["_a"], d["_b"] = ts(d["t_start"]), ts(d["t_end"])
                    rows.append(d)
    return rows


def cpu_for_window(sysmon, a, b):
    """[a,b] 구간과 겹치는 sysmon 구간들을 겹친 길이로 가중 평균. 겹치는 표본이 없으면 None."""
    w = 0.0
    acc = defaultdict(float)
    names = defaultdict(float)
    for r in sysmon:
        ov = min(b, r["_b"]) - max(a, r["_a"])
        if ov > 0:
            w += ov
            for k in CPU_KEYS:
                v = r.get(k)
                if v is None:  # ide 분리 이전 형식의 표본: ide=0, other_excl_ide=other로 본다
                    v = r.get("other_pct", 0.0) if k in ("other_excl_ide_pct", "other_adj_pct") else 0.0
                acc[k] += ov * v
            for x in r.get("top_other") or []:
                names[_base_name(x["name"])] += ov * x["pct"]
    if w == 0:
        return None
    out = {k: v / w for k, v in acc.items()}
    out["covered_s"] = w
    out["top_other"] = sorted(((n, v / w) for n, v in names.items()), key=lambda x: -x[1])[:5]
    return out


def _base_name(n):
    return n.split("#", 1)[0]


def _rho_profile(rows, t):
    """에피소드 위치별 rho 갱신 총수의 분포. 회차 사이에 값이 하나뿐이면 rho 갱신이 실행마다 같다는 뜻."""
    prof = defaultdict(Counter)
    for tr in rows:
        for j, e in enumerate(tr[t]["eps"]):
            s = e.get("solves")
            if s:
                prof[j][s["rho_updates_total"]] += 1
    return {str(j): dict(c) for j, c in sorted(prof.items())}


def _hash_sig(sig):
    import hashlib
    return hashlib.sha256(repr(sig).encode()).hexdigest()[:16]


def trial_sig(tr, t):
    return tuple((e["delta_hash"], e["full_hash"]) for e in tr[t]["eps"])


def analyze(exp_dir, noload_threshold):
    batches = load_batches(exp_dir)
    sysmon = load_sysmon(exp_dir)
    # 보조 재분류(S2_RESULT.md): sysmon은 표본 시점의 pid 파일로 실험·부하를 가르므로, 표본 도중 끝난 batch 프로세스와
    # 부하 전환 순간의 부하 프로세스가 "other"에 들어간다. trial 기록의 pid와 load_set 이벤트의 pid를 top_other(최대 8개)에서
    # 빼 other_adj_pct를 만든다. 위반 판정 원값(other_pct)은 그대로 두고 이 값은 따로 보고한다.
    own = {tr["pid"] for b in batches for tr in b["trials"] if tr.get("pid")}
    evp = Path(exp_dir) / "events.jsonl"
    if evp.exists():
        for line in evp.read_text(encoding="utf-8").splitlines():
            e = json.loads(line) if line.strip() else {}
            if e.get("event") == "load_set":
                own.update(e.get("pids") or [])
    for r in sysmon:
        r["own_in_other_pct"] = sum(x["pct"] for x in r.get("top_other") or [] if x.get("pid") in own)
        r["other_adj_pct"] = r.get("other_pct", 0.0) - r["own_in_other_pct"]
    arms = defaultdict(list)
    for b in batches:
        for tr in b["trials"]:
            tr["_batch"] = b["meta"]["batch_id"]
            tr["_load_k"] = b["meta"]["load_k"]
            tr["_probe"] = b["meta"]["probe"]
            tr["_cond"] = (b["meta"].get("condition") or {}).get("cond")
            arms[b["meta"]["arm"]].append(tr)
    res = dict(exp_dir=str(exp_dir), arms={})
    for arm, trs in arms.items():
        a = dict(n_trials=len(trs), load_k=sorted({t["_load_k"] for t in trs}), probe=sorted({t["_probe"] for t in trs}),
                 cond=sorted({str(t["_cond"]) for t in trs}), targets={})
        # CPU(회차별)
        viol = 0
        viol_ide_only = 0
        cov = 0
        cpu_rows = []
        viol_names = defaultdict(float)
        viol_adj = 0
        for tr in trs:
            c = cpu_for_window(sysmon, ts(tr["t_start"]), ts(tr["t_end"]))
            tr["_cpu"] = c
            if c is not None:
                cov += 1
                cpu_rows.append(c)
                if c["other_pct"] > noload_threshold:
                    viol += 1
                    # 사용자 결정: 위반 기준은 그대로, VS Code·claude(ide) 기여로만 위반된 회차를 따로 표시
                    if c["other_excl_ide_pct"] <= noload_threshold:
                        viol_ide_only += 1
                    for n, v in c["top_other"]:
                        viol_names[n] += v
                    if c["other_adj_pct"] > noload_threshold:
                        viol_adj += 1
        a["cpu"] = dict(trials_with_cpu=cov, other_gt_threshold=viol, violation_ide_only=viol_ide_only,
                        violation_even_excl_ide=viol - viol_ide_only, threshold=noload_threshold,
                        violation_after_own_pid_reclass=viol_adj,
                        violation_top_processes_mean_pct=sorted(((n, v / viol) for n, v in viol_names.items()),
                                                                key=lambda x: -x[1])[:8] if viol else [],
                        mean={k: (sum(r[k] for r in cpu_rows) / len(cpu_rows) if cpu_rows else None)
                              for k in CPU_KEYS},
                        max_other=max((r["other_pct"] for r in cpu_rows), default=None))
        for t in TARGETS:
            rows = [tr for tr in trs if t in tr]
            if not rows:
                continue
            n = len(rows)
            mism = [tr for tr in rows if tr[t]["mismatch"]]
            fail = [tr for tr in rows if not tr[t]["passed"]]
            k = len(mism)
            # 회차 간 기준(최빈 서명)과 다른 회차 — 3회가 서로 같아도 다른 회차와 다른 경우를 잡는다
            sigs = Counter(trial_sig(tr, t) for tr in rows)
            modal, modal_n = sigs.most_common(1)[0]
            tl_any = [tr for tr in rows if any((e.get("solves") or {}).get("n_tl_fp", 0) for e in tr[t]["eps"])]
            tl_status = sum(sum((e.get("solves") or {}).get("n_tl_status", 0) for e in tr[t]["eps"]) for tr in rows)
            tl_fp = sum(sum((e.get("solves") or {}).get("n_tl_fp", 0) for e in tr[t]["eps"]) for tr in rows)
            co = Counter((tr[t]["mismatch"], tr in tl_any) for tr in rows)
            firsts = []
            for tr in mism:
                for c in tr[t]["cmp"]:
                    if not c["delta_equal"]:
                        firsts.append(dict(batch=tr["_batch"], trial=tr["trial"], pair=c["pair"],
                                           first_delta_row=c["first_delta_row"],
                                           max_abs_delta_diff_deg=c.get("max_abs_delta_diff_deg"),
                                           first_solve_diff=c.get("first_solve_diff"),
                                           first_solve_row=c.get("first_solve_row"),
                                           in_equal=c.get("first_solve_in_equal"),
                                           in_parts_diff=c.get("first_solve_in_parts_diff"),
                                           tl_fp=c.get("first_solve_tl_fp"),
                                           window_a=[(s["k"], s["status"], s["iter"], round(s["run_time"] * 1e3, 3),
                                                      s["tl_fp"]) for s in c.get("window_a", [])],
                                           window_b=[(s["k"], s["status"], s["iter"], round(s["run_time"] * 1e3, 3),
                                                      s["tl_fp"]) for s in c.get("window_b", [])],
                                           other_cpu=(tr["_cpu"] or {}).get("other_pct")))
            # "불일치는 항상 time_limit 지문과 함께 나오는가" — 첫 불일치 solve 기준
            with_fp = [f for f in firsts if f["tl_fp"] and any(f["tl_fp"])]
            in_eq = [f for f in firsts if f["in_equal"] is True]
            maxw = max(((e.get("solves") or {}).get("max_wall_ms") or 0) for tr in rows for e in tr[t]["eps"])
            maxrt = max(((e.get("solves") or {}).get("max_run_time_ms") or 0) for tr in rows for e in tr[t]["eps"])
            a["targets"][t] = dict(
                n=n, mismatch=k, test_failed=len(fail), rate=k / n, ci95=cp_interval(k, n),
                upper95_if_zero=upper95_zero(n) if k == 0 else None,
                deviate_from_modal=n - modal_n, distinct_signatures=len(sigs),
                signature_set=sorted(_hash_sig(s) for s in sigs),
                trials_with_tl_fp=len(tl_any), tl_fp_solves=tl_fp, tl_status_solves=tl_status,
                cooccur={f"mismatch={m},tl_fp_in_trial={f}": v for (m, f), v in sorted(co.items())},
                first_diff_pairs=len(firsts), first_diff_with_tl_fp=len(with_fp), first_diff_inputs_equal=len(in_eq),
                max_wall_ms=maxw, max_run_time_ms=maxrt,
                mismatches_noviol=sum(1 for tr in mism if (tr["_cpu"] or {}).get("other_pct", 0) <= noload_threshold),
                n_noviol=sum(1 for tr in rows if (tr["_cpu"] or {}).get("other_pct", 0) <= noload_threshold),
                mismatch_other_adj_pct=[round((tr["_cpu"] or {}).get("other_adj_pct", float("nan")), 2) for tr in mism],
                rho_updates_by_episode=_rho_profile(rows, t),
                first_diffs=firsts[:200])
        res["arms"][arm] = a
    # 조건 간 비교(같은 대상, Fisher 정확검정)
    names = list(arms)
    comp = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            for t in TARGETS:
                ai, aj = res["arms"][names[i]]["targets"].get(t), res["arms"][names[j]]["targets"].get(t)
                if ai and aj:
                    table = [[ai["mismatch"], ai["n"] - ai["mismatch"]], [aj["mismatch"], aj["n"] - aj["mismatch"]]]
                    comp.append(dict(a=names[i], b=names[j], target=t, table=table,
                                     fisher_p=float(fisher_exact(table)[1])))
    res["comparisons"] = comp
    # arm 사이 서명 비교(S1: probe_off vs probe_on). 대상마다 모든 arm의 서명 집합이 같고 원소가 1개면 "동일".
    res["signature_across_arms"] = {
        t: dict(per_arm={arm: res["arms"][arm]["targets"][t]["signature_set"] for arm in names
                         if t in res["arms"][arm]["targets"]})
        for t in TARGETS}
    for t, d in res["signature_across_arms"].items():
        sets = list(d["per_arm"].values())
        d["identical_single"] = bool(sets) and all(s == sets[0] for s in sets) and len(sets[0]) == 1
    ev = Path(exp_dir) / "events.jsonl"
    if ev.exists():
        res["events"] = [json.loads(x) for x in ev.read_text(encoding="utf-8").splitlines()
                         if x.strip() and json.loads(x)["event"] not in ("batch_start", "batch_end")]
    return res


def to_md(res):
    L = [f"# 집계: {res['exp_dir']}", ""]
    for arm, a in res["arms"].items():
        c = a["cpu"]
        L.append(f"## arm {arm} (회차 {a['n_trials']}, load_k {a['load_k']}, probe {a['probe']}, cond {a['cond']})")
        m = c["mean"]
        fmt = lambda v: "—" if v is None else f"{v:.2f}"  # noqa: E731
        L.append(f"- CPU 평균(%): total {fmt(m['total_pct'])}, exp {fmt(m['exp_pct'])}, load {fmt(m['load_pct'])}, "
                 f"other {fmt(m['other_pct'])} (그중 VS Code·claude {fmt(m['ide_pct'])}), other 최대 {fmt(c['max_other'])}")
        L.append(f"- 위반(other>{c['threshold']}%) 회차 {c['other_gt_threshold']} / CPU 기록 있는 회차 {c['trials_with_cpu']}"
                 f" — VS Code·claude 기여로만 위반 {c['violation_ide_only']}, 그것을 빼도 위반 {c['violation_even_excl_ide']}"
                 f"; 보조: 우리 batch·부하 pid를 other에서 뺀 재분류 후 위반 {c.get('violation_after_own_pid_reclass', '—')}")
        if c["violation_top_processes_mean_pct"]:
            L.append("- 위반 회차의 other 기여 프로세스(회차 평균 %): " + ", ".join(
                f"{n} {v:.2f}" for n, v in c["violation_top_processes_mean_pct"]))
        L.append("")
        L.append("| 대상 | n | 불일치 | 테스트 실패 | 비율 | 95% CI | 0회 시 상한 | 최빈과 다른 회차 | 지문 있는 회차 | 지문 solve | "
                 "'run time limit reached' | 첫 불일치 중 지문 동반 | 첫 불일치 중 입력 동일 | 최대 wall ms | 최대 run_time ms |")
        L.append("|" + "---|" * 16)
        for t, d in a["targets"].items():
            ci = d["ci95"]
            up = "" if d["upper95_if_zero"] is None else f"{d['upper95_if_zero']:.4f}"
            L.append(f"| {t} | {d['n']} | {d['mismatch']} | {d['test_failed']} | {d['rate']:.4f} | "
                     f"[{ci[0]:.4f}, {ci[1]:.4f}] | {up} | "
                     f"{d['deviate_from_modal']} | {d['trials_with_tl_fp']} | {d['tl_fp_solves']} | {d['tl_status_solves']} | "
                     f"{d['first_diff_with_tl_fp']}/{d['first_diff_pairs']} | {d['first_diff_inputs_equal']}/{d['first_diff_pairs']} | "
                     f"{d['max_wall_ms']:.2f} | {d['max_run_time_ms']:.2f} |")
        L.append("")
        L.append("- 위반 아닌 회차만: " + ", ".join(
            f"{t} {d['mismatches_noviol']}/{d['n_noviol']}" for t, d in a["targets"].items()))
        L.append("- rho 갱신 총수(에피소드 위치별 {값: 회차 수}): " + "; ".join(
            f"{t} {d['rho_updates_by_episode']}" for t, d in a["targets"].items()))
        L.append("")
    L.append("## arm 사이 회차 서명 비교 (에피소드별 delta·전체 행 해시)")
    for t, d in res["signature_across_arms"].items():
        L.append(f"- {t}: 모든 arm에서 서명 1개로 동일 = {d['identical_single']} / " + ", ".join(
            f"{arm} {s}" for arm, s in d["per_arm"].items()))
    L.append("")
    if res.get("comparisons"):
        L.append("## 조건 간 비교 (Fisher 정확검정, 양측)")
        L.append("| a | b | 대상 | [[a불일치,a일치],[b불일치,b일치]] | p |")
        L.append("|---|---|---|---|---|")
        for c in res["comparisons"]:
            L.append(f"| {c['a']} | {c['b']} | {c['target']} | {c['table']} | {c['fisher_p']:.3g} |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp-dir", required=True)
    ap.add_argument("--json")
    ap.add_argument("--md")
    ap.add_argument("--noload-threshold", type=float, default=10.0)
    args = ap.parse_args()
    res = analyze(args.exp_dir, args.noload_threshold)
    md = to_md(res)
    if args.json:
        Path(args.json).write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    if args.md:
        Path(args.md).write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
