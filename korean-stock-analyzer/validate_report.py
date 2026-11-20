"""
validate_report.py - Mechanical integrity checks for the Phase 1~3 pipeline (v5.0)

SCOPE (read this before trusting a green result)
  VERIFIES   : internal consistency of 2_Translated_DB/valuation_metrics.json (SSOT), HTML-tag <-> JSON
               agreement, the price / safety-pin / multiplier-cap inequalities from GEMINI.md, required
               section headings, top `분석완료일` header, Mermaid v10.9.8 diagram syntax (MD + HTML),
               leftover placeholders, and that SSOT numbers appear in Phase3_DCF.md.
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
import html
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_html import sanitize_mermaid_code  # noqa: E402
from ssot_common import STOCK_RESEARCH_ROOT  # noqa: E402

EPS = 1e-6
CAP_BASE_A = 1.38
CAP_BULL_A = 1.45
FLOOR_MULT_A = 0.80

PHASE1_REQUIRED = ["Step 1.2", "Step 1.5", "Step 1.8", "Step 2.0", "Step 3.5"]
PHASE3_REQUIRED = ["레드팀", "안전핀"]
PLACEHOLDER_PATTERNS = [
    r"\{\{.*?\}\}",
    r"\[기업명\]",
    r"XX,XXX",
    r"TODO",
    r"data-[a-z-]+=\"\s*\"",
    r"\bNaN\b",
    r"\[AI(?:가|\s*작성)[^\]]*\]",
]
_GENERIC_DRIVER_STUB_RE = re.compile(
    r"^(?:AI가\s*)?(?:(?:전방\s*(?:호황|둔화)/)?가동률\s*(?:상단|하락)\s*서술|컨센서스/본업\s*유지\s*서술)$"
)


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
    has_valid_dcf = dcf.get("status") == "success" or bool(dcf.get("norm_fcf_eok") and float(dcf.get("norm_fcf_eok") or 0) > 0)
    if has_valid_dcf and _num(dcf.get("price")) not in (None, anchor):
        res.err(f"price anchor mismatch: anchor_price={anchor} vs reverse_dcf.price={dcf.get('price')}")
    if not dcf or not has_valid_dcf:
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
    is_p2_b = b.get("is_phase2", True)
    # 2nd S-Curve only counts when the 1st curve is already mature (spec 2.3: 1st >= 18%)
    near = [p for p in (pen1,) if p is not None and 8.0 <= p <= 18.0]
    if pen2 is not None and 8.0 <= pen2 <= 18.0 and pen1 is not None and pen1 >= 18.0:
        near.append(pen2)
    if near and is_p2_b and "Zone A" not in zone:
        res.warn(f"penetration {pen1}/{pen2} in 8~18% but zone is '{zone[:20]}' (spec: Zone A)")
    if (not near or not is_p2_b) and "Zone A" in zone:
        res.warn(f"zone says Zone A but penetration {pen1}/{pen2} not in 8~18% or is_phase2=False")

    # --- Step 1.3 BM Core Driver & Forward OP Slope (v5.2, Model A exclusive + Track 2 block) ---
    s13 = d.get("step1_3_bm_slope")
    if isinstance(s13, dict) and s13:
        sb_m = _num(s13.get("op_slope_base_mult"))
        su_m = _num(s13.get("op_slope_bull_mult"))
        if sb_m is not None and not (0.88 - EPS <= sb_m <= 1.12 + EPS):
            res.err(f"step1_3_bm_slope.op_slope_base_mult={sb_m} out of bounds [0.88, 1.12]")
        if su_m is not None and not (0.85 - EPS <= su_m <= 1.15 + EPS):
            res.err(f"step1_3_bm_slope.op_slope_bull_mult={su_m} out of bounds [0.85, 1.15]")
        if bool(s3.get("op_slope_decel_warn") or s13.get("op_slope_decel_warn")) and bool(s4.get("is_track2")):
            res.err("section4.is_track2 must be False when Step 1.3 op_slope_decel_warn is True")
        ds_v = _num(s13.get("dol_scale"))
        if ds_v is not None and not (0.6 - EPS <= ds_v <= 1.4 + EPS):
            res.err(f"step1_3_bm_slope.dol_scale={ds_v} out of bounds [0.60, 1.40]")
        ca_v = _num(s13.get("consensus_absorb_ratio"))
        if ca_v is not None and not (0.0 - EPS <= ca_v <= 1.0 + EPS):
            res.err(f"step1_3_bm_slope.consensus_absorb_ratio={ca_v} out of bounds [0.0, 1.0]")

    # --- Section 2 Value Trap Mode Consistency (v5.2.2 Dual-Split / User Switches) ---
    s2 = d.get("section2") or {}
    vtm = s2.get("value_trap_mode")
    if vtm == "confirmed_type_b":
        if not bool(s2.get("is_type_b")):
            res.err("section2.value_trap_mode='confirmed_type_b' requires section2.is_type_b=True")
        if not bool(s4.get("is_value_trap_hold")):
            res.err("section2.value_trap_mode='confirmed_type_b' requires section4.is_value_trap_hold=True")
    elif vtm == "confirmed_non_trap":
        if bool(s2.get("is_type_b")):
            res.err("section2.value_trap_mode='confirmed_non_trap' requires section2.is_type_b=False")
        if bool(s4.get("is_value_trap_hold")):
            res.err("section2.value_trap_mode='confirmed_non_trap' requires section4.is_value_trap_hold=False")
    elif vtm == "dual_split_review":
        if not bool(s2.get("is_dual_split")):
            res.err("section2.value_trap_mode='dual_split_review' requires section2.is_dual_split=True")
        if not bool(s4.get("is_value_trap_hold")):
            res.err("section2.value_trap_mode='dual_split_review' requires section4.is_value_trap_hold=True")

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


_ANCHOR_DECL_LINE_RE = re.compile(
    r"(?:(?:파이프라인\s*SSOT\s*)?단일\s*기준\s*주가|Single\s*Price\s*Anchor|단일\s*기준가|Anchor\s*Price)"
    r"(?:\s*\([^)\n0-9]*\))?"
    r"(?:[*\]`\s])*[:：(]\s*(?:[*`'\"]|\s)*(?P<num>[\d,]+)원"
)
_ANCHOR_TABLE_ROW_RE = re.compile(
    r"^\s*\|\s*(?:[*`'\"]|\s)*(?:단일\s*기준\s*주가|Anchor\s*Price)[^|\n]*\|\s*(?:[*`'\"]|\s)*(?P<num>[\d,]+)원"
)


def _extract_declared_anchors(text):
    """Returns list of (line_no, val) for explicit Single Price Anchor declarations."""
    hits = []
    for idx, ln in enumerate(text.splitlines(), 1):
        m = _ANCHOR_DECL_LINE_RE.search(ln) or _ANCHOR_TABLE_ROW_RE.search(ln)
        if m:
            try:
                hits.append((idx, int(m.group("num").replace(",", ""))))
            except ValueError:
                pass
    return hits


_MERMAID_MD_RE = re.compile(r"```mermaid[ \t]*\r?\n(.*?)```", re.DOTALL)
_MERMAID_HTML_RE = re.compile(
    r'<pre>\s*<code[^>]*class="[^"]*language-mermaid[^"]*"[^>]*>(.*?)</code>\s*</pre>',
    re.DOTALL | re.IGNORECASE,
)
_MERMAID_KNOWN_HEADERS = (
    "graph",
    "flowchart",
    "sequencediagram",
    "classdiagram",
    "statediagram",
    "erdiagram",
    "gantt",
    "pie",
    "journey",
    "gitgraph",
    "mindmap",
    "timeline",
    "quadrantchart",
    "requirementdiagram",
    "c4context",
    "sankey",
    "xychart",
    "block-beta",
)
_NON_NODE_KEYWORDS = (
    "subgraph ",
    "subgraph\t",
    "style ",
    "classdef ",
    "class ",
    "linkstyle ",
    "click ",
    "direction ",
    "acctitle",
    "accdescr",
)
_BARE_END_NODE_RE = re.compile(r"(?<![A-Za-z0-9_-])end(?![A-Za-z0-9_-])")
_COMPLETION_DATE_RE = re.compile(r"분석\s*완료일\s*[*`]*\s*[:：]\s*[*`]*\s*\d{4}[-.]\d{2}[-.]\d{2}")


def check_mermaid_syntax(code):
    """Lightweight structural validator targeting Mermaid v10.9.8 parser failure modes."""
    errors = []
    if not code or not code.strip():
        return ["empty mermaid block"]

    raw_lines = code.splitlines()
    header = ""
    i = 0
    while i < len(raw_lines):
        s = raw_lines[i].strip()
        if not s:
            i += 1
            continue
        if s.startswith("%%{"):
            while i < len(raw_lines) and "}%%" not in raw_lines[i]:
                i += 1
            i += 1
            continue
        if s.startswith("%%"):
            i += 1
            continue
        header = s.lower()
        break

    if not header:
        return ["missing mermaid diagram header"]
    first_tok = header.split()[0]
    if not any(first_tok.startswith(k) for k in _MERMAID_KNOWN_HEADERS):
        errors.append(f"unrecognized mermaid header '{raw_lines[i].strip()[:40]}'")
        return errors

    is_flowchart = first_tok.startswith("flowchart") or first_tok.startswith("graph")
    if not is_flowchart:
        return errors

    subgraph_depth = 0
    in_init = False
    for ln_no, raw in enumerate(raw_lines, 1):
        s = raw.strip()
        if not s:
            continue
        if in_init:
            if "}%%" in s:
                in_init = False
            continue
        if s.startswith("%%{"):
            if "}%%" not in s:
                in_init = True
            continue
        if s.startswith("%%"):
            continue
        low = s.lower()
        if ln_no == i + 1 and (low.startswith("flowchart") or low.startswith("graph")):
            continue

        if low == "subgraph" or low.startswith("subgraph ") or low.startswith("subgraph\t"):
            subgraph_depth += 1
        elif low == "end":
            subgraph_depth -= 1
            if subgraph_depth < 0:
                errors.append(f"line {ln_no}: unmatched 'end' without open subgraph")
                subgraph_depth = 0
            continue

        # Character-level scan for balanced quotes and node brackets outside quotes
        in_quote = False
        stack = []
        pipe_count = 0
        no_quote_chars = []
        j = 0
        n = len(raw)
        while j < n:
            ch = raw[j]
            if ch == '"':
                in_quote = not in_quote
                no_quote_chars.append(" ")
                j += 1
                continue
            if in_quote:
                j += 1
                continue
            if ch == "%" and j + 1 < n and raw[j + 1] == "%":
                break
            no_quote_chars.append(ch)
            if ch in "[({":
                stack.append(ch)
            elif ch in "])}":
                expected = {"]": "[", ")": "(", "}": "{"}[ch]
                # Allow asymmetric flag `id>label]` when `>` opened it without `[`
                if not stack and ch == "]" and ">" in raw[:j]:
                    pass
                elif not stack or stack[-1] != expected:
                    errors.append(f"line {ln_no}: unmatched '{ch}' outside quotes in '{s[:60]}'")
                    break
                else:
                    stack.pop()
            elif ch == "|":
                pipe_count += 1
            j += 1

        if in_quote:
            errors.append(f"line {ln_no}: unclosed double quote in '{s[:60]}'")
        elif stack:
            errors.append(f"line {ln_no}: unclosed '{stack[-1]}' in '{s[:60]}'")
        if pipe_count % 2 != 0:
            errors.append(f"line {ln_no}: unclosed '|' edge label in '{s[:60]}'")

        if not any(low.startswith(kw) for kw in _NON_NODE_KEYWORDS):
            nq = "".join(no_quote_chars)
            if _BARE_END_NODE_RE.search(nq):
                errors.append(f"line {ln_no}: reserved keyword 'end' used as node ID in '{s[:60]}'")

    if subgraph_depth > 0:
        errors.append(f"unclosed subgraph block(s): missing {subgraph_depth} 'end'")
    return errors


def check_reports(folder, d, res):
    # --- Guardrail: Detect stray/misplaced Phase1~3 reports outside 3_Final_Reports/ ---
    allowed_dirs = {"1_Raw_Data", "2_Translated_DB", "2_Context_Cache", "3_Final_Reports", "Weekly_Trend"}
    if os.path.isdir(folder):
        for entry in sorted(os.listdir(folder)):
            ep = os.path.join(folder, entry)
            if os.path.isfile(ep) and re.match(r"^Phase[123]_.*\.(?:md|html)$", entry, re.IGNORECASE):
                res.err(
                    f"misplaced report in company root: {entry} "
                    f"(must be written to 3_Final_Reports/{entry}; merge and remove stray file)"
                )
            elif os.path.isdir(ep) and entry not in allowed_dirs:
                for sub in sorted(os.listdir(ep)):
                    if re.match(r"^Phase[123]_.*\.(?:md|html)$", sub, re.IGNORECASE):
                        res.err(
                            f"misplaced report in non-standard folder: {entry}/{sub} "
                            f"(must be written to 3_Final_Reports/{sub}; merge and remove {entry}/)"
                        )

    rpt = os.path.join(folder, "3_Final_Reports")
    p1, p2, p3 = (os.path.join(rpt, n) for n in ("Phase1_Report.md", "Phase2_Story.md", "Phase3_DCF.md"))
    texts = {}
    for p in (p1, p2, p3):
        if not os.path.exists(p):
            res.warn(f"missing report: {os.path.basename(p)}")
        else:
            texts[os.path.basename(p)] = _read(p)

    ssot_ver = str((d or {}).get("version", ""))
    t1 = texts.get("Phase1_Report.md")
    if t1:
        for s in PHASE1_REQUIRED:
            if s not in t1:
                res.err(f"Phase1 missing required gate: {s} (legacy report -> clean rebuild)")
        t1_h1 = next((ln for ln in t1.splitlines()[:10] if ln.lstrip().startswith("# ")), "")
        is_v52_doc = bool(re.search(r"\bv5\.[2-9]", t1_h1, re.IGNORECASE))
        is_v52_ssot = bool(re.match(r"^5\.[2-9]", ssot_ver))
        if "Step 1.3" not in t1:
            if is_v52_doc or (is_v52_ssot and not re.search(r"\bv5\.[01]\b", t1_h1, re.IGNORECASE)):
                res.err("Phase1 missing required v5.2 gate: Step 1.3 (BM 핵심인자 · DOL · 선행 OP 기울기 진단)")
            elif is_v52_ssot:
                res.warn("Phase1 (v5.0/v5.1) does not include v5.2 Step 1.3 yet (will be added on next Track A rebuild)")
        missing_secs = [
            str(n) for n in range(1, 9)
            if not re.search(rf"^##\s+(?:Section\s+)?{n}\.", t1, re.MULTILINE)
        ]
        if missing_secs:
            msg = f"Phase1_Report.md missing canonical section heading(s): ## {', '.join(missing_secs)}."
            if ssot_ver.startswith("5."):
                res.err(msg + " (follow static_cache_prefix PART D standard ## 1.~## 8. skeleton)")
            else:
                res.warn(msg)
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

    # --- Top `분석완료일`, stale v4.x H1 check & Mermaid v10.9.8 syntax checks (Markdown + compiled HTML) ---
    for name, t in texts.items():
        top_zone = "\n".join(t.splitlines()[:30])
        h1_line = next((ln for ln in t.splitlines()[:10] if ln.lstrip().startswith("# ")), "")
        is_v5 = ssot_ver.startswith("5.") or bool(re.search(r"\bv5\.[0-9]", "\n".join(t.splitlines()[:10])))
        if ssot_ver.startswith("5.") and re.search(r"\bv4\.[0-9]", h1_line, re.IGNORECASE):
            res.err(
                f"{name}: H1 title still declares legacy v4.x ('{h1_line[:70]}') while SSOT is v{ssot_ver} "
                f"(Track A clean rebuild into 3_Final_Reports/{name} required)"
            )
        if not _COMPLETION_DATE_RE.search(top_zone):
            msg = f"{name}: missing top '분석완료일: YYYY-MM-DD' header"
            if is_v5:
                res.err(msg)
            else:
                res.warn(msg)

        for m_idx, m in enumerate(_MERMAID_MD_RE.finditer(t), 1):
            sanitized = sanitize_mermaid_code(m.group(1))
            for err in check_mermaid_syntax(sanitized):
                res.err(f"{name}: Mermaid #{m_idx} syntax error: {err}")

        html_name = os.path.splitext(name)[0] + ".html"
        html_path = os.path.join(rpt, html_name)
        if os.path.exists(html_path):
            htxt = _read(html_path)
            for h_idx, hm in enumerate(_MERMAID_HTML_RE.finditer(htxt), 1):
                raw_code = html.unescape(hm.group(1))
                for err in check_mermaid_syntax(raw_code):
                    res.err(f"{html_name}: Mermaid #{h_idx} HTML syntax error: {err}")
            if is_v5:
                title_m = re.search(r"<title>(.*?)</title>", htxt, re.IGNORECASE)
                if title_m and re.search(r"\(v4\.[0-9.]*\)", title_m.group(1)):
                    res.warn(f"{html_name}: HTML <title> shows stale version '{title_m.group(1)}' (rebuild HTML for v5.0)")

    # --- Cross-report SSOT anchor_price & calculator tag verification across Phase 1~3 ---
    if d and d.get("anchor_price"):
        ssot_anchor = _num(d.get("anchor_price"))
        s3_d, s4_d = d.get("section3", {}), d.get("section4", {})
        md_tag_expect = {
            "price": ssot_anchor,
            "bear": s3_d.get("bear_auto"), "base": s3_d.get("base_auto"), "bull": s3_d.get("bull_auto"),
            "base-a": s3_d.get("base_auto_a"), "bull-a": s3_d.get("bull_auto_a"),
            "buy1": s4_d.get("buy1"), "buy2": s4_d.get("buy2"), "buy3": s4_d.get("buy3"),
            "stop-pin": s4_d.get("init_stop_pin"),
        }
        for name, t in texts.items():
            for ln_no, found_p in _extract_declared_anchors(t):
                if ssot_anchor and 0.25 * ssot_anchor <= found_p <= 4.0 * ssot_anchor:
                    if abs(found_p - ssot_anchor) > 0.5:
                        res.err(
                            f"{name}:{ln_no}: declared anchor price {found_p:,}원 != SSOT anchor_price {int(round(ssot_anchor)):,}원"
                        )
            for m in re.finditer(r'<div\s+id="dcf-calculator-root"[^>]*>', t):
                attrs = _tag_attrs(m.group(0))
                for ak, av in md_tag_expect.items():
                    if av is None or ak not in attrs:
                        continue
                    parsed_av = _num(attrs.get(ak))
                    if parsed_av is None or abs(parsed_av - float(av)) > 0.5:
                        res.err(f"{name}: markdown <div id=\"dcf-calculator-root\"> data-{ak}={attrs.get(ak)} != SSOT {av}")

    for name, t in texts.items():
        for pat in PLACEHOLDER_PATTERNS:
            m = re.search(pat, t)
            if m:
                res.err(f"{name}: leftover placeholder '{m.group(0)[:45]}'")

        m_auto2 = re.search(
            r"#{2,3}\s*📌\s*\[코드 자동 생성 2\].*?(?=\n#{1,3}\s|\n---|\Z)",
            t,
            flags=re.DOTALL,
        )
        if m_auto2:
            for ln in m_auto2.group(0).splitlines():
                s = ln.strip()
                if not (s.startswith("|") and s.endswith("|")):
                    continue
                cells = [c.strip() for c in re.split(r"(?<!\\)\|", s[1:-1])]
                if len(cells) < 6:
                    continue
                c0_low = cells[0].lower()
                if any(k in c0_low for k in ("bull", "base", "bear")):
                    drv = cells[2].strip()
                    if not drv or len(drv) < 15 or _GENERIC_DRIVER_STUB_RE.match(drv):
                        res.err(
                            f"{name}: [코드 자동 생성 2] '{cells[0]}' 핵심 드라이버 가정이 미작성/일반문구입니다 "
                            f"('{drv[:30]}') — 기업별 제품·고객사·가동률·OPM·촉매 수치로 구체 서술 필수"
                        )

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
