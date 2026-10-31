"""
validate_report.py - Mechanical integrity checks for the Phase 1~3 pipeline (v4.3.x)

SCOPE (read this before trusting a green result)
  VERIFIES   : internal consistency of 2_Translated_DB/valuation_metrics.json (SSOT), HTML-tag <-> JSON
               agreement, the price / safety-pin / multiplier-cap inequalities from GEMINI.md, required
               section headings, leftover placeholders, and that SSOT numbers appear in Phase3_DCF.md.
  DOES NOT   : judge whether the reasoning is sound, whether qualitative claims (bottleneck lead time,
               governance, theme selection) are true, or whether cited facts are real.
               A PASS means "numbers are consistent", NOT "the analysis is correct".

Usage
  python validate_report.py <company_folder>            # SSOT + report files
  python validate_report.py --json <valuation_metrics.json>
  python validate_report.py --all [Stock_Research_dir]  # every company folder
  python validate_report.py --diff old.json new.json    # numeric diff, ignores generated_at (regression aid)
Exit code: 1 if any ERROR, else 0. WARN never fails the run.
"""
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ssot_common import STOCK_RESEARCH_ROOT  # noqa: E402

EPS = 1e-6
CAP_BASE_A = 1.38
CAP_BULL_A = 1.45
FLOOR_MULT_A = 0.80

PHASE1_REQUIRED = ["Step 1.2", "Step 1.5", "Step 1.8", "Step 2.0", "Step 3.5"]
PHASE3_REQUIRED = ["레드팀", "안전핀"]
PLACEHOLDER_PATTERNS = [r"\{\{.*?\}\}", r"\[기업명\]", r"XX,XXX", r"TODO", r"data-[a-z-]+=\"\s*\"", r"\bNaN\b"]


class Result:
    def __init__(self, name):
        self.name = name
        self.errors = []
        self.warns = []

    def err(self, msg):
        self.errors.append(msg)

    def warn(self, msg):
        self.warns.append(msg)


def _g(d, *path, default=None):
    cur = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def _tag_attrs(tag):
    return dict(re.findall(r'data-([a-z0-9-]+)="([^"]*)"', tag or ""))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def check_ssot(d, res):
    for key in ["stock_code", "anchor_price", "bench", "sotp", "section2", "section3", "section4",
                "step1_2_bottleneck", "step1_8_k_return", "canonical_html_tag"]:
        if key not in d or d[key] in (None, {}, ""):
            res.err(f"missing/empty key: {key}")
    if res.errors:
        return

    anchor = _num(d["anchor_price"])
    s3, s4 = d["section3"], d["section4"]

    # --- Single Price Anchor (principle 1) ---
    dcf = d.get("reverse_dcf") or {}
    if dcf.get("status") == "success" and _num(dcf.get("price")) not in (None, anchor):
        res.err(f"price anchor mismatch: anchor_price={anchor} vs reverse_dcf.price={dcf.get('price')}")
    if not dcf or dcf.get("status") != "success":
        res.warn("reverse_dcf missing or not 'success' (run calc_reverse_dcf.py)")
    for label, val in (("bench.close", _g(d, "bench", "close")), ("section4.d_close", s4.get("d_close"))):
        v = _num(val)
        if v and anchor and abs(v / anchor - 1) > 0.10:
            res.warn(f"{label}={v:,.0f} deviates >10% from anchor_price={anchor:,.0f} (intentional anchor override?)")

    # --- canonical HTML tag <-> JSON ---
    attrs = _tag_attrs(d["canonical_html_tag"])
    expect = {
        "price": anchor,
        "bear": s3.get("bear_auto"), "base": s3.get("base_auto"), "bull": s3.get("bull_auto"),
        "base-a": s3.get("base_auto_a"), "bull-a": s3.get("bull_auto_a"),
        "tp1": s3.get("tp1_price"), "tp1-a": s3.get("tp1_price_a"),
        "buy1": s4.get("buy1"), "buy2": s4.get("buy2"), "buy3": s4.get("buy3"),
        "stop-pin": s4.get("init_stop_pin"), "poc-low": s4.get("poc_low"),
    }
    if dcf.get("status") == "success":
        expect.update({"shares": dcf.get("distb_shares"), "total-shares": dcf.get("total_shares"),
                       "net-debt": dcf.get("net_debt_eok")})
    for k, v in expect.items():
        a = _num(attrs.get(k))
        if v is None:
            continue
        if a is None:
            res.err(f"html tag missing data-{k}")
        elif abs(a - float(v)) > 0.5:
            res.err(f"html tag data-{k}={a} != JSON {v}")

    # --- Safety-pin & price hierarchy (principle 6) ---
    buys = [_num(s4.get(k)) for k in ("buy1", "buy2", "buy3")]
    avg = _num(s4.get("avg_buy_price"))
    pin = _num(s4.get("init_stop_pin"))
    tp1 = _num(s3.get("tp1_price"))
    if None not in buys and pin is not None and avg is not None:
        if not pin < min(buys[0], buys[1], avg):
            res.err(f"safety pin {pin} must be < min(buy1,buy2,avg)={min(buys[0], buys[1], avg)}")
        if tp1 is not None and not max(buys + [avg]) < tp1:
            if s4.get("is_overvalued") or s4.get("is_track2"):
                res.warn(f"max(buys,avg)={max(buys + [avg])} >= tp1={tp1} (overvalued/track2 flag set)")
            else:
                res.err(f"max(buy1..3,avg)={max(buys + [avg])} must be < tp1_price={tp1}")
        if not (buys[0] <= buys[1] <= buys[2]):
            res.warn(f"buy ladder not ascending: {buys}")

    # --- Multiplier caps & de-rating floor (v4.3 / v5.1 dual hard cap & floor) ---
    if _num(s3.get("base_mult_a")) is not None:
        if s3["base_mult_a"] > CAP_BASE_A + EPS:
            res.err(f"base_mult_a={s3['base_mult_a']} exceeds cap {CAP_BASE_A}")
        if s3["base_mult_a"] < FLOOR_MULT_A - EPS:
            res.err(f"base_mult_a={s3['base_mult_a']} below floor {FLOOR_MULT_A}")
    if _num(s3.get("bull_mult_a")) is not None:
        if s3["bull_mult_a"] > CAP_BULL_A + EPS:
            res.err(f"bull_mult_a={s3['bull_mult_a']} exceeds cap {CAP_BULL_A}")
        if s3["bull_mult_a"] < FLOOR_MULT_A - EPS:
            res.err(f"bull_mult_a={s3['bull_mult_a']} below floor {FLOOR_MULT_A}")

    # --- Scenario ordering ---
    for lo, hi in (("bear_auto", "base_auto"), ("base_auto", "bull_auto"), ("base_auto_a", "bull_auto_a")):
        if _num(s3.get(lo)) is not None and _num(s3.get(hi)) is not None and s3[lo] > s3[hi]:
            res.err(f"scenario order violated: {lo}={s3[lo]} > {hi}={s3[hi]}")

    # --- Share counts ---
    if dcf.get("status") == "success" and dcf.get("distb_shares") and dcf.get("total_shares"):
        if dcf["distb_shares"] > dcf["total_shares"]:
            res.err("distb_shares > total_shares")
        ratio = _num(dcf.get("non_op_ratio_book_pct"))
        if ratio is not None and ratio > 100:
            res.warn(f"reverse_dcf.non_op_ratio_book_pct={ratio} > 100% (check --ctrl-equity input / unit)")

    # --- SOTP 20% gate (principle 8) ---
    sotp = d["sotp"]
    mx = _num(sotp.get("non_op_max_ratio_pct"))
    if mx is not None and bool(sotp.get("sotp_triggered")) != (mx >= 20.0):
        res.err(f"sotp_triggered={sotp.get('sotp_triggered')} inconsistent with non_op_max_ratio_pct={mx}")

    # --- Bottleneck grade vs lead time (s_curve_spec: S>=24, A 12~23, B<12) ---
    b = d["step1_2_bottleneck"]
    grade, months = b.get("bottleneck_grade"), _num(b.get("bottleneck_lead_time_months"))
    if grade and months is not None:
        exp = "S" if months >= 24 else "A" if months >= 12 else "B"
        if grade in ("S", "A", "B") and grade != exp:
            res.warn(f"bottleneck grade {grade} vs lead time {months:.0f}m (spec implies {exp}); "
                     f"fine only if grade was deliberately overridden")
    pen1, pen2 = _num(b.get("penetration_pct")), _num(b.get("second_penetration_pct"))
    zone = str(b.get("penetration_zone", ""))
    # 2nd S-Curve only counts when the 1st curve is already mature (spec 2.3: 1st >= 18%)
    near = [p for p in (pen1,) if p is not None and 8.0 <= p <= 18.0]
    if pen2 is not None and 8.0 <= pen2 <= 18.0 and pen1 is not None and pen1 >= 18.0:
        near.append(pen2)
    if near and "Zone A" not in zone:
        res.warn(f"penetration {pen1}/{pen2} in 8~18% but zone is '{zone[:20]}' (spec: Zone A)")
    if not near and "Zone A" in zone:
        res.warn(f"zone says Zone A but penetration {pen1}/{pen2} not in 8~18%")

    # --- Falsification fields (principle 12) ---
    for k in ("qoq_summary_str", "kill_switch_guide"):
        if not d["section2"].get(k):
            res.err(f"section2.{k} empty (QoQ + Kill-Switch are mandatory)")

    # --- data quality (new) ---
    dq = d.get("data_quality")
    if dq is None:
        res.warn("no data_quality block (generated before validator era; re-run backtest_valuation.py)")
    elif dq.get("status") == "degraded":
        res.warn(f"data_quality degraded: {[w['stage'] for w in dq.get('warnings', [])]}")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def check_reports(folder, d, res):
    rpt = os.path.join(folder, "3_Final_Reports")
    p1, p2, p3 = (os.path.join(rpt, n) for n in ("Phase1_Report.md", "Phase2_Story.md", "Phase3_DCF.md"))
    texts = {}
    for p in (p1, p2, p3):
        if not os.path.exists(p):
            res.warn(f"missing report: {os.path.basename(p)}")
        else:
            texts[os.path.basename(p)] = _read(p)

    t1 = texts.get("Phase1_Report.md")
    if t1:
        for s in PHASE1_REQUIRED:
            if s not in t1:
                res.err(f"Phase1 missing required gate: {s} (legacy report -> clean rebuild)")
    t3 = texts.get("Phase3_DCF.md")
    if t3:
        for s in PHASE3_REQUIRED:
            if s not in t3:
                res.err(f"Phase3 missing required element: {s}")
        if d:
            s3, s4 = d.get("section3", {}), d.get("section4", {})
            probes = {"anchor_price": d.get("anchor_price"), "buy1": s4.get("buy1"), "buy2": s4.get("buy2"),
                      "buy3": s4.get("buy3"), "stop_pin": s4.get("init_stop_pin"),
                      "base_auto_a": s3.get("base_auto_a"), "tp1_price": s3.get("tp1_price")}
            for k, v in probes.items():
                if v and f"{int(round(v)):,}" not in t3 and str(int(round(v))) not in t3:
                    res.warn(f"Phase3 does not contain SSOT {k}={int(round(v)):,} (stale report or different format)")
    for name, t in texts.items():
        for pat in PLACEHOLDER_PATTERNS:
            m = re.search(pat, t)
            if m:
                res.err(f"{name}: leftover placeholder '{m.group(0)[:30]}'")

    thesis = os.path.join(folder, "Weekly_Trend", "thesis_log.md")
    if os.path.exists(thesis):
        tt = _read(thesis)
        hdr = [l for l in tt.splitlines() if l.strip().startswith("|") and ("가설" in l)]
        if hdr and hdr[0].count("|") - 1 != 6:
            res.warn(f"thesis_log.md header has {hdr[0].count('|') - 1} columns (6-column Popper format required)")
        if "Kill" not in tt and "반증" not in tt:
            res.err("thesis_log.md has no Kill-Switch / 반증 condition")
    else:
        res.warn("Weekly_Trend/thesis_log.md missing")


def validate_company(folder):
    res = Result(os.path.basename(folder.rstrip("\\/")))
    jp = os.path.join(folder, "2_Translated_DB", "valuation_metrics.json")
    d = None
    if not os.path.exists(jp):
        res.err("2_Translated_DB/valuation_metrics.json missing (run backtest_valuation.py)")
    else:
        d = json.loads(_read(jp))
        check_ssot(d, res)
    check_reports(folder, d, res)
    return res


def validate_json(path):
    res = Result(os.path.basename(path))
    check_ssot(json.loads(_read(path)), res)
    return res


def _flatten(o, prefix=""):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(_flatten(v, f"{prefix}{k}."))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            out.update(_flatten(v, f"{prefix}{i}."))
    else:
        out[prefix.rstrip(".")] = o
    return out


def diff_json(a_path, b_path, rel_tol=1e-9):
    a, b = _flatten(json.loads(_read(a_path))), _flatten(json.loads(_read(b_path)))
    diffs = []
    for k in sorted(set(a) | set(b)):
        if k in ("generated_at", "data_quality.status") or k.startswith("data_quality."):
            continue
        va, vb = a.get(k, "<absent>"), b.get(k, "<absent>")
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            if abs(va - vb) > rel_tol * max(1.0, abs(va)):
                diffs.append((k, va, vb))
        elif va != vb:
            diffs.append((k, va, vb))
    return diffs


def _print(res):
    status = "FAIL" if res.errors else ("WARN" if res.warns else "PASS")
    print(f"[{status}] {res.name}")
    for e in res.errors:
        print(f"   ERROR: {e}")
    for w in res.warns:
        print(f"   warn : {w}")


def main(argv):
    if len(argv) >= 2 and argv[0] == "--diff":
        diffs = diff_json(argv[1], argv[2])
        for k, va, vb in diffs:
            print(f"{k}: {va} -> {vb}")
        print(f"{len(diffs)} differing field(s)")
        return 1 if diffs else 0
    if argv and argv[0] == "--json":
        results = [validate_json(argv[1])]
    elif argv and argv[0] == "--all":
        root = argv[1] if len(argv) > 1 else STOCK_RESEARCH_ROOT
        results = [validate_company(os.path.join(root, n)) for n in sorted(os.listdir(root))
                   if os.path.exists(os.path.join(root, n, "2_Translated_DB"))]
    elif argv:
        results = [validate_company(argv[0])]
    else:
        print(__doc__)
        return 2
    for r in results:
        _print(r)
    return 1 if any(r.errors for r in results) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
