"""
ksa_orchestrator.py - Unified One-Shot Pipeline Orchestrator for Korean Stock Analyzer (v5.0)

Eliminates multi-step tool-call snowballing (65 tool calls -> 4~6 tool calls) while preserving 100%
of the 18 core accounting/valuation integrity principles.

Subcommands:
  1) init       : Initialize 4 standard folders + 6-column thesis_log.md + company_timeline.md + report skeletons
  2) prep       : Inherit saved SSOT parameters + run backtest_valuation + run calc_reverse_dcf +
                  run 2-Tier lossless PDF verbatim extraction + generate single-read `ai_prep_digest.md`
  3) build      : Deterministically patch SSOT tables/tags/prices in Phase1 & Phase3 (--patch-ssot) +
                  compile Phase 1~3 HTML reports + run validate_report.py
  4) set-models : Customize Tier-1 (Flagship) and Tier-2 (High-Speed) Gemini model names in model_config.json
                  and regenerate 이용방법.md / 이용방법.html
"""

import argparse
import glob
import json
import os
import re
import subprocess
import sys
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.dirname(SKILL_DIR)
sys.path.insert(0, SKILL_DIR)

from ssot_common import (  # noqa: E402
    STOCK_RESEARCH_ROOT,
    S_CURVE_REGISTRY_PATH,
    get_model_config,
    update_model_config,
)
from backtest_valuation import run_valuation_backtest  # noqa: E402
from calc_reverse_dcf import (  # noqa: E402
    analyze_reverse_dcf,
    resolve_ctrl_equity,
    update_ssot_json,
)
from parse_pdf import batch_verbatim_extract  # noqa: E402
from validate_report import validate_company, _print as print_validation  # noqa: E402


def get_company_dir(corp_name):
    return os.path.join(STOCK_RESEARCH_ROOT, corp_name)


def lookup_scurve_keywords(stock_code, corp_name):
    """Finds primary & theme keywords from s_curve_registry.json if available."""
    primary = [corp_name]
    if stock_code:
        primary.append(str(stock_code).zfill(6))
    themes = []
    if os.path.exists(S_CURVE_REGISTRY_PATH):
        try:
            with open(S_CURVE_REGISTRY_PATH, "r", encoding="utf-8") as f:
                reg = json.load(f)
            stocks = reg.get("stocks", {})
            st = stocks.get(str(stock_code).zfill(6), {}) if stock_code else {}
            if not st:
                for k, v in stocks.items():
                    if v.get("name") == corp_name:
                        st = v
                        break
            if st:
                for kw in st.get("anchor_keywords", []):
                    if kw not in primary:
                        primary.append(kw)
                for kw in st.get("scurve_themes", []):
                    if kw not in themes:
                        themes.append(kw)
        except Exception:
            pass
    return primary, themes


def ensure_company_structure(corp_name, stock_code=None):
    """Creates 4 standard folders and initializes Weekly_Trend logs + 2_Translated_DB files."""
    comp_dir = get_company_dir(corp_name)
    subfolders = ["1_Raw_Data", "2_Translated_DB", "3_Final_Reports", "Weekly_Trend"]
    for sf in subfolders:
        os.makedirs(os.path.join(comp_dir, sf), exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    code_str = f"({str(stock_code).zfill(6)})" if stock_code else ""

    thesis_path = os.path.join(comp_dir, "Weekly_Trend", "thesis_log.md")
    if not os.path.exists(thesis_path):
        thesis_init = f"""# 🎯 {corp_name}{code_str} 포퍼식 반증 투자 가설 로그 (Popperian Falsification Thesis Log — v5.0)

> **최초 생성일**: {today} | **규격**: 6열 표준 포퍼식 반증(Kill-Switch) & 직전 분기(QoQ) 의무 병기

| 가설 ID (기록일) | 핵심 투자 가설 (Core Thesis) | 📊 직전 분기 대비 (QoQ) 실측 추이 | ✅ 확인 근거 (Bullish Fact) | 🚨 반증/약화 조건 ("이 숫자가 나오면 약화/폐기" Kill-Switch) | 판정 상태 |
| :---: | :--- | :--- | :--- | :--- | :---: |
| **H1**<br>({today[2:].replace('-', '.')}) | [신규 분석 시 본업/S-Curve 핵심 가설 입력] | [매출 QoQ / 영업익 QoQ 실측 입력] | [DART/리포트 실측 페이지 근거] | **차기 분기 영업이익 < [구체적 숫자]억 원(QoQ -15% 하회) 시 즉시 [약화] 강등** | `[신규 등록]` |
"""
        with open(thesis_path, "w", encoding="utf-8") as f:
            f.write(thesis_init)

    timeline_path = os.path.join(comp_dir, "Weekly_Trend", "company_timeline.md")
    if not os.path.exists(timeline_path):
        timeline_init = f"""# 📅 {corp_name}{code_str} 기업 미시 서사 & 이벤트 누적 타임라인 (`company_timeline.md` — v5.0)

| 기록일자 | 구분 (공시/IR/리포트/점검) | 핵심 이벤트 및 팩트 요약 (숫자·출처 명시) | 가설 영향 및 주가/멀티플 시사점 |
| :---: | :---: | :--- | :--- |
| **{today}** | `초기 세팅` | `{corp_name}{code_str}` 4대 표준 분석 폴더 및 v5.0 SSOT 파이프라인 초기화 완료 | Phase 1~3 최초 심층 분석 대기 |
"""
        with open(timeline_path, "w", encoding="utf-8") as f:
            f.write(timeline_init)

    return comp_dir


def find_latest_global_trend_dir():
    gt_root = os.path.join(STOCK_RESEARCH_ROOT, "Global_Trend")
    if not os.path.exists(gt_root):
        return None
    subdirs = [
        os.path.join(gt_root, d)
        for d in os.listdir(gt_root)
        if os.path.isdir(os.path.join(gt_root, d))
    ]
    if not subdirs:
        return None
    subdirs.sort(key=lambda p: os.path.basename(p), reverse=True)
    return subdirs[0]


def append_extended_ssot_tables(ssot_json_path):
    """
    Appends [코드 자동 생성 1-C: 역DCF 3단 요구성장률 표] and [코드 자동 생성 2-B: 마스터 SOP 매수가/안전핀 표]
    to 2_Translated_DB/auto_tables.md so all Phase 1 and Phase 3 numeric tables are 100% pre-built.
    """
    if not os.path.exists(ssot_json_path):
        return
    auto_md_path = os.path.join(os.path.dirname(ssot_json_path), "auto_tables.md")
    if not os.path.exists(auto_md_path):
        return

    with open(ssot_json_path, "r", encoding="utf-8") as f:
        d = json.load(f)
    with open(auto_md_path, "r", encoding="utf-8") as f:
        auto_md = f.read()

    dcf = d.get("reverse_dcf", {}) or {}
    s3 = d.get("section3", {}) or {}
    s4 = d.get("section4", {}) or {}
    anchor = d.get("anchor_price", 0)

    def fmt_pct(val):
        return f"`{val:+.2f}%`" if isinstance(val, (int, float)) else "`N/A (적자/미산출)`"

    dcf_table = f"""
### 📌 [코드 자동 생성 1-C] Phase 3 Section 1 역DCF 3단 요구성장률 요약표 (WACC `{dcf.get('wacc', 0.09)*100:.1f}%`, 영구성장률 `{dcf.get('terminal_g', 0.02)*100:.1f}%`)
| 평가 기준 (Valuation Basis) | 산출 가치 (억 원) | 보고 FCF (`{dcf.get('fcf_eok', 0.0):,.1f}억`) 내재 요구성장률 | 오너 정규화 FCF (`{dcf.get('norm_fcf_eok') or dcf.get('fcf_eok', 0.0):,.1f}억`) 내재 요구성장률 | 비고 및 해석 기준 |
| :--- | :---: | :---: | :---: | :--- |
| **① 유통시총 (Floating Equity)** | **`{dcf.get('market_cap_distb_eok', 0.0):,.1f}억`** | **{fmt_pct(dcf.get('implied_g_distb_pct'))}** | **{fmt_pct(dcf.get('norm_g_distb_pct') or dcf.get('implied_g_distb_pct'))}** | 자기주식(`{dcf.get('treasury_shares', 0):,}주`) 차감 실질 유통주식수(`{dcf.get('distb_shares', 0):,}주`) 기준 |
| **② 실질 기업가치 (EV)** | **`{dcf.get('ev_distb_eok', 0.0):,.1f}억`** | **{fmt_pct(dcf.get('implied_g_ev_pct'))}** | **{fmt_pct(dcf.get('norm_g_ev_pct') or dcf.get('implied_g_ev_pct'))}** | 순차입금(`{dcf.get('net_debt_eok', 0.0):+,.1f}억`) 및 우선주 반영 실질 EV 기준 |
| **③ 본업 기업가치 (Core EV, SOTP)** | **`{dcf.get('core_op_ev_eok', 0.0):,.1f}억`** | **{fmt_pct(dcf.get('implied_g_core_ev_pct'))}** | **{fmt_pct(dcf.get('norm_g_core_ev_pct') or dcf.get('implied_g_core_ev_pct'))}** | {'🚨 SOTP 20% 초과 발동 (비영업 안전가치 차감)' if dcf.get('sotp_triggered') else '🟢 비영업자산 20% 미만 (참고치)'} |
"""

    buy1 = s4.get("buy1", 0)
    buy2 = s4.get("buy2", 0)
    buy3 = s4.get("buy3", 0)
    avg_p = s4.get("avg_buy_price", 0)
    stop1 = s4.get("init_stop_pin", 0)
    stop2 = s4.get("breakout_trail_pin", 0)
    tp1_b = s3.get("tp1_price", 0)
    base_b = s3.get("base_auto", 0)
    base_a = s3.get("base_auto_a", 0)
    bull_a = s3.get("bull_auto_a", 0)

    sop_table = f"""
### 📌 [코드 자동 생성 2-B] Phase 3 Section 4 마스터 SOP 3분할 매수가 & 2단계 안전핀 실행표 (단일 기준 주가 `{anchor:,}원`)
| 실행 단계 (SOP Action Ladder) | 비중 / 구분 | 코드 확정 가격 (원) | 현재가(`{anchor:,}원`) 대비 | 완성 평단(`{avg_p:,}원`) 대비 | 실행 조건 및 기술적/밸류에이션 근거 |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **🚨 1단계 초입 고정 안전핀 (Hard Stop 1)** | **전량 손절선** | **`{stop1:,}원`** | `{(stop1/anchor - 1)*100 if anchor else 0:+.1f}%` | `{(stop1/avg_p - 1)*100 if avg_p else 0:+.1f}%` | `1단계 안전핀({stop1:,}원) < 1차 매수가({buy1:,}원)` 위계 100% 준수 |
| **🟢 1차 매수 (가치/눌림목 선취매)** | **30%** | **`{buy1:,}원`** | `{(buy1/anchor - 1)*100 if anchor else 0:+.1f}%` | `{(buy1/avg_p - 1)*100 if avg_p else 0:+.1f}%` | 하방 지지선(`{s3.get('bear_auto', 0):,}원`) 및 안전마진 확보 구간 |
| **🔵 2차 매수 (추세 확인 본대)** | **40%** | **`{buy2:,}원`** | `{(buy2/anchor - 1)*100 if anchor else 0:+.1f}%` | `{(buy2/avg_p - 1)*100 if avg_p else 0:+.1f}%` | 주봉/일봉 이동평균선(`20일선 {s4.get('d_ma20', 0):,}원 / 20주선 {s4.get('w_ma20', 0):,}원`) 지지 확인 |
| **🟣 3차 매수 (매물대 돌파/안착)** | **30%** | **`{buy3:,}원`** | `{(buy3/anchor - 1)*100 if anchor else 0:+.1f}%` | `{(buy3/avg_p - 1)*100 if avg_p else 0:+.1f}%` | 20일 POC 매물대(`{s4.get('poc_low', 0):,}~{s4.get('poc_high', 0):,}원`) 안착 확인 |
| **⭐ 3분할 완성 평균단가 (Avg Buy)** | **100%** | **`{avg_p:,}원`** | `{(avg_p/anchor - 1)*100 if anchor else 0:+.1f}%` | `0.0%` | **Gate 1 R:R `{s4.get('gate1_rr', 0):.2f}:1` / Gate 2 실전 R:R `{s4.get('exec_rr', 0):.2f}:1`** |
| **🔒 2단계 본절 보호핀 (Trailing Stop 2)** | **익절 보호선** | **`{stop2:,}원`** | `{(stop2/anchor - 1)*100 if anchor else 0:+.1f}%` | `{(stop2/avg_p - 1)*100 if avg_p else 0:+.1f}%` | 매물대 상단(`{s4.get('poc_high', 0):,}원`) 돌파 안착 성공 시 손절선 상향 |
| **🎯 1차 목표가 (TP1 / Base)** | **분할 익절 1** | **🛡️ `{tp1_b:,}원` / 🚀 `{base_a:,}원`** | `🛡️ {(tp1_b/anchor - 1)*100 if anchor else 0:+.1f}% / 🚀 {(base_a/anchor - 1)*100 if anchor else 0:+.1f}%` | `🛡️ {(tp1_b/avg_p - 1)*100 if avg_p else 0:+.1f}% / 🚀 {(base_a/avg_p - 1)*100 if avg_p else 0:+.1f}%` | 보수적 대안 B(`{base_b:,}원`) vs v4.3 병목·주주환원 반영 대안 A(`{base_a:,}원`) |
| **🚀 2차 목표가 (Bull 상단)** | **최종 익절 2** | **🛡️ `{s3.get('bull_auto', 0):,}원` / 🚀 `{bull_a:,}원`** | `🛡️ {(s3.get('bull_auto', 0)/anchor - 1)*100 if anchor else 0:+.1f}% / 🚀 {(bull_a/anchor - 1)*100 if anchor else 0:+.1f}%` | `🛡️ {(s3.get('bull_auto', 0)/avg_p - 1)*100 if avg_p else 0:+.1f}% / 🚀 {(bull_a/avg_p - 1)*100 if avg_p else 0:+.1f}%` | 주봉 MFI(14) 80 하향이탈 또는 RSI 과열 괴리 시 분할 차익실현 |
"""

    swing_table = f"""
### 📌 [코드 자동 생성 2-C] Argon 4.0 주봉 5·20·60·120주선 이격도 · 매물대(POC) · MFI/MACD · DART 실적 결합 중기 스윙 타점표
| 주봉 5·20·60·120주선 & 이격도(%) | 주봉 104주 최다 매물대(Volume Profile POC) | 주간 수급 (MFI 14W / RSI 14W) | 주봉 MACD (12, 26, 9) | 🏆 중기 스윙 결합 점수 & 타점 판정 |
| :--- | :--- | :--- | :--- | :--- |
| • **5주선**: `{s4.get('w_ma5', 0):,}원` (`{s4.get('w_disp5_pct', 0.0):+.1f}%`)<br>• **20주선**: `{s4.get('w_ma20', 0):,}원` (`{s4.get('w_disp20_pct', 0.0):+.1f}%`)<br>• **60주선**: `{s4.get('w_ma60', 0):,}원` (`{s4.get('w_disp60_pct', 0.0):+.1f}%`)<br>• **120주선**: `{s4.get('w_ma120', 0):,}원` (`{s4.get('w_disp120_pct', 0.0):+.1f}%`) | • **POC 구간**: `{s4.get('w_poc_low', 0):,}~{s4.get('w_poc_high', 0):,}원`<br>• **POC 중심가**: `{s4.get('w_poc_price', 0):,}원` (비중 `{s4.get('w_poc_pct', 0.0):.1f}%`)<br>• **현재가 이격**: `{s4.get('w_vp_dist_pct', 0.0):+.1f}%`<br>• **판정**: **`{s4.get('w_vp_status', 'N/A')}`** | • **주봉 MFI(14)**: **`{s4.get('w_mfi14', 50.0):.1f}`**<br>• **12주 최고 MFI**: `{s4.get('w_mfi14_12w_max', 50.0):.1f}`<br>• **주봉 RSI(14)**: `{s4.get('w_rsi14', 50.0):.1f}` | • **MACD**: `{s4.get('w_macd', 0.0):,.1f}`<br>• **Signal**: `{s4.get('w_macd_sig', 0.0):,.1f}`<br>• **Hist**: **`{s4.get('w_macd_hist', 0.0):+,.1f}`** | • **통합 점수**: **`{s4.get('w_swing_score', 50)}점 ({s4.get('w_swing_grade', 'B')}등급)`**<br>• **최종 시그널**: **{s4.get('w_swing_signal', 'N/A')}** |
"""

    if "[코드 자동 생성 1-C]" not in auto_md:
        auto_md = auto_md + "\n" + dcf_table.strip() + "\n\n" + sop_table.strip() + "\n\n" + swing_table.strip() + "\n"
        with open(auto_md_path, "w", encoding="utf-8") as f:
            f.write(auto_md)


def cmd_prep(args):
    comp_dir = ensure_company_structure(args.corp_name, args.code)
    ssot_path = os.path.join(comp_dir, "2_Translated_DB", "valuation_metrics.json")

    # 1. Load existing SSOT parameters if present for zero-friction inheritance
    old_ssot = {}
    if os.path.exists(ssot_path):
        try:
            with open(ssot_path, "r", encoding="utf-8") as f:
                old_ssot = json.load(f)
            # Save a backup snapshot before updating so `build --patch-ssot` knows what old numbers to replace
            prev_backup = os.path.join(comp_dir, "2_Translated_DB", "prev_valuation_metrics.json")
            with open(prev_backup, "w", encoding="utf-8") as bf:
                json.dump(old_ssot, bf, ensure_ascii=False, indent=2)
        except Exception:
            old_ssot = {}

    saved_params = old_ssot.get("input_params", {})
    old_dcf = old_ssot.get("reverse_dcf", {}) or {}
    old_sotp = old_ssot.get("sotp", {}) or {}
    old_s12 = old_ssot.get("step1_2_bottleneck", {}) or {}
    old_s18 = old_ssot.get("step1_8_k_return", {}) or {}

    code = args.code or old_ssot.get("stock_code") or saved_params.get("code")
    if not code:
        print(f"[Error] 종목코드(--code)가 필요합니다. ({args.corp_name})")
        return 1

    sector_type = args.sector_type or saved_params.get("sector_type") or "A"
    rerating_date = args.rerating_date or saved_params.get("rerating_date")
    distb_shares = args.distb_shares or old_dcf.get("distb_shares") or saved_params.get("distb_shares") or 0
    total_shares = args.total_shares or old_dcf.get("total_shares") or saved_params.get("total_shares") or distb_shares
    fcf = args.fcf if args.fcf is not None else (old_dcf.get("fcf_eok") or saved_params.get("fcf") or 0.0)
    norm_fcf = args.norm_fcf if args.norm_fcf is not None else (old_dcf.get("norm_fcf_eok") or saved_params.get("norm_fcf"))
    net_debt = args.net_debt if args.net_debt is not None else (old_dcf.get("net_debt_eok") or saved_params.get("net_debt") or 0.0)
    non_op_assets = (
        args.non_op_assets
        if args.non_op_assets is not None
        else (old_sotp.get("non_op_assets_eok") or old_dcf.get("non_op_assets_eok") or saved_params.get("non_op_assets"))
    )
    dart_exposure = args.dart_exposure if args.dart_exposure is not None else (old_s12.get("dart_exposure_pct") or saved_params.get("dart_exposure"))
    forward_eps = args.forward_eps if args.forward_eps is not None else saved_params.get("forward_eps")
    forward_eps_g = args.forward_eps_g if args.forward_eps_g is not None else saved_params.get("forward_eps_g")
    expected_dps = args.expected_dps if args.expected_dps is not None else (saved_params.get("expected_dps") or 0.0)
    penetration_pct = args.penetration_pct if args.penetration_pct is not None else old_s12.get("penetration_pct")
    second_penetration_pct = args.second_penetration_pct if args.second_penetration_pct is not None else old_s12.get("second_penetration_pct")
    bottleneck_grade = args.bottleneck_grade or old_s12.get("bottleneck_grade")
    bottleneck_months = args.bottleneck_months if args.bottleneck_months is not None else old_s12.get("bottleneck_lead_time_months")
    capa_util_pct = args.capa_util_pct if args.capa_util_pct is not None else old_s12.get("capa_util_pct")
    payout_ratio = args.payout_ratio if args.payout_ratio is not None else old_s18.get("payout_ratio_pct")
    buyback_cliff = True if args.buyback_cliff else old_s18.get("buyback_cliff_risk")
    related_party_eok = args.related_party_eok if args.related_party_eok is not None else old_s18.get("related_party_eok")
    governance_discount = args.governance_discount if args.governance_discount is not None else old_s18.get("gov_discount_pct")
    sc_override = True if args.s_curve_phase2 else (False if args.no_s_curve else saved_params.get("sc_override"))
    early_ignition = True if args.early_ignition else bool(saved_params.get("early_ignition", False))
    if getattr(args, "clear_sell_signals", False):
        shortage_easing = False
        slope_decel = False
        policy_headwind = False
    else:
        shortage_easing = True if getattr(args, "shortage_easing", False) else bool(old_s12.get("shortage_easing", False))
        slope_decel = True if getattr(args, "slope_decel", False) else bool(old_s12.get("slope_decel", False))
        policy_headwind = True if getattr(args, "policy_headwind", False) else bool(old_s12.get("policy_headwind", False))

    # 2. Run backtest_valuation
    run_valuation_backtest(
        code,
        years=args.years,
        rerating_date=rerating_date,
        corp_name=args.corp_name,
        base_target=args.base_target,
        bull_target=args.bull_target,
        scurve_override=sc_override,
        dart_exposure=dart_exposure,
        forward_eps=forward_eps,
        expected_dps=expected_dps,
        early_ignition=early_ignition,
        forward_eps_g=forward_eps_g,
        sector_type=sector_type,
        non_op_assets=non_op_assets,
        net_debt=net_debt,
        distb_shares=distb_shares,
        total_shares=total_shares,
        fcf=fcf,
        norm_fcf=norm_fcf,
        export_json=ssot_path,
        penetration_pct=penetration_pct,
        second_penetration_pct=second_penetration_pct,
        bottleneck_grade=bottleneck_grade,
        bottleneck_months=bottleneck_months,
        capa_util_pct=capa_util_pct,
        payout_ratio=payout_ratio,
        buyback_cliff=buyback_cliff,
        related_party_eok=related_party_eok,
        governance_discount=governance_discount,
        anchor_price=args.anchor_price,
        shortage_easing=shortage_easing,
        slope_decel=slope_decel,
        policy_headwind=policy_headwind,
    )

    # 3. Run calc_reverse_dcf and merge into valuation_metrics.json
    if os.path.exists(ssot_path):
        with open(ssot_path, "r", encoding="utf-8") as f:
            new_ssot = json.load(f)
        anchor_p = float(new_ssot.get("anchor_price", 0))
        sotp_block = new_ssot.get("sotp", {}) or {}
        if distb_shares <= 0 and new_ssot.get("bench", {}).get("bps"):
            # Fallback if distb_shares was not provided yet
            distb_shares = int(old_dcf.get("distb_shares") or 0)
            total_shares = int(old_dcf.get("total_shares") or distb_shares)

        if anchor_p > 0 and distb_shares > 0:
            ctrl_eq = resolve_ctrl_equity(ssot_path, sotp_block.get("controlling_equity_eok", 0.0))
            dcf_res = analyze_reverse_dcf(
                price=anchor_p,
                distb_shares=distb_shares,
                total_shares=total_shares or distb_shares,
                fcf_eok=fcf,
                wacc=args.wacc,
                terminal_g=args.terminal,
                years=5,
                net_debt_eok=net_debt,
                norm_fcf_eok=norm_fcf,
                non_op_assets_eok=float(non_op_assets or sotp_block.get("non_op_assets_eok") or 0.0),
                controlling_equity_eok=ctrl_eq,
            )
            update_ssot_json(ssot_path, dcf_res)

        # Persist input_params for future zero-arg `prep` runs
        with open(ssot_path, "r", encoding="utf-8") as f:
            final_ssot = json.load(f)
        final_ssot["input_params"] = {
            "code": str(code).zfill(6),
            "sector_type": sector_type,
            "rerating_date": rerating_date,
            "distb_shares": distb_shares,
            "total_shares": total_shares,
            "fcf": fcf,
            "norm_fcf": norm_fcf,
            "net_debt": net_debt,
            "non_op_assets": non_op_assets,
            "dart_exposure": dart_exposure,
            "forward_eps": forward_eps,
            "forward_eps_g": forward_eps_g,
            "expected_dps": expected_dps,
            "sc_override": sc_override,
            "early_ignition": early_ignition,
        }
        with open(ssot_path, "w", encoding="utf-8") as f:
            json.dump(final_ssot, f, ensure_ascii=False, indent=2)

        append_extended_ssot_tables(ssot_path)

    # 4. Run 2-Tier Lossless Verbatim PDF Extraction (if PDFs exist and not skipped)
    verbatim_path = os.path.join(comp_dir, "2_Translated_DB", "verbatim_extracts.md")
    if not args.skip_pdf:
        pdf_targets = []
        if args.pdf_dirs:
            pdf_targets.extend(args.pdf_dirs)
        else:
            latest_gt = find_latest_global_trend_dir()
            if latest_gt:
                pdf_targets.append(latest_gt)
            wt_dir = os.path.join(comp_dir, "Weekly_Trend")
            if os.path.exists(wt_dir):
                pdf_targets.append(wt_dir)
            if args.include_raw_pdfs:
                raw_dir = os.path.join(comp_dir, "1_Raw_Data")
                if os.path.exists(raw_dir):
                    pdf_targets.append(raw_dir)

        prim_kws, theme_kws = lookup_scurve_keywords(code, args.corp_name)
        if args.primary_keywords:
            for k in args.primary_keywords.split(","):
                if k.strip() and k.strip() not in prim_kws:
                    prim_kws.append(k.strip())
        if args.keywords:
            for k in args.keywords.split(","):
                if k.strip() and k.strip() not in theme_kws:
                    theme_kws.append(k.strip())
        all_kws = prim_kws + [t for t in theme_kws if t not in prim_kws]
        if pdf_targets and all_kws:
            batch_verbatim_extract(
                pdf_targets,
                all_kws,
                output_md=verbatim_path,
                max_chars_per_page=3200,
                primary_keywords=prim_kws,
                max_pages_total=args.max_pages,
            )

    # 5. Build Consolidated Single-Read Briefing (`2_Translated_DB/ai_prep_digest.md`)
    digest_path = build_ai_prep_digest(comp_dir, args.corp_name)
    print("\n======================================================================")
    print(f"🚀 [One-Shot Prep 완료] 단일 통합 브리핑 생성: {digest_path}")
    print("   👉 AI 에이전트는 이제 `ai_prep_digest.md` 파일 단 1개만 read_file 하십시오!")
    print("======================================================================\n")
    return 0


def build_ai_prep_digest(comp_dir, corp_name):
    """Combines Track Verdict + auto_tables.md + thesis_log.md + verbatim_extracts.md into one file."""
    rpt_dir = os.path.join(comp_dir, "3_Final_Reports")
    p1_path = os.path.join(rpt_dir, "Phase1_Report.md")
    p2_path = os.path.join(rpt_dir, "Phase2_Story.md")
    p3_path = os.path.join(rpt_dir, "Phase3_DCF.md")

    p1_exists = os.path.exists(p1_path)
    p2_exists = os.path.exists(p2_path)
    p3_exists = os.path.exists(p3_path)

    missing_gates = []
    if p1_exists:
        with open(p1_path, "r", encoding="utf-8") as f:
            t1 = f.read()
        for g in ["Step 1.2", "Step 1.5", "Step 1.8", "Step 2.0", "Step 3.5"]:
            if g not in t1:
                missing_gates.append(f"Phase1:{g}")
    else:
        missing_gates.append("Phase1_Report.md 없음")

    if p3_exists:
        with open(p3_path, "r", encoding="utf-8") as f:
            t3 = f.read()
        for g in ["레드팀", "안전핀"]:
            if g not in t3:
                missing_gates.append(f"Phase3:{g}")
    else:
        missing_gates.append("Phase3_DCF.md 없음")

    if not missing_gates and p1_exists and p2_exists and p3_exists:
        track_verdict = (
            "⚡ **[Track B 자격 충족 — 격주 핀셋 델타 점검 가능]**\n"
            "- 기존 `Phase1~3.md`가 모든 v4.3/v5.0 필수 게이트를 충족합니다.\n"
            "- **토큰 90% 절약 지침**: 정기 분기/사업보고서 공시나 전면 리빌드 지시가 아니라면 `Phase1~3.md` 전체를 다시 쓰지(`write_file`) 마십시오!\n"
            "- AI는 `Weekly_Trend/thesis_log.md` 및 `company_timeline.md`(필요 시 `Phase2_Story.md` / `Phase3_DCF.md` 서사 문단)만 `edit_file`로 갱신한 뒤, "
            "`python ksa_orchestrator.py build --corp-name " + corp_name + " --patch-ssot`를 실행하면 `Phase1/Phase3`의 모든 주가·목표가·역DCF·SOP 매수가·HTML 태그가 100% 코드로 자동 패치됩니다!"
        )
    else:
        track_verdict = (
            f"🏛️ **[Track A 필수 — 전면 클린 리빌드 대상]** (사유: `{', '.join(missing_gates)}`)\n"
            "- 신규 분석 기업이거나 기존 보고서에 필수 게이트가 누락된 구버전입니다.\n"
            "- 아래 `[2] SSOT 자동 생성 테이블`과 `[4] 무손실 원문 발췌본`을 바탕으로 `Phase1_Report.md`, `Phase2_Story.md`, `Phase3_DCF.md`, `thesis_log.md`를 작성한 후 `ksa_orchestrator.py build`를 실행하십시오."
        )

    auto_md_path = os.path.join(comp_dir, "2_Translated_DB", "auto_tables.md")
    auto_md_txt = open(auto_md_path, "r", encoding="utf-8").read() if os.path.exists(auto_md_path) else "(auto_tables.md 없음)"

    thesis_path = os.path.join(comp_dir, "Weekly_Trend", "thesis_log.md")
    thesis_txt = open(thesis_path, "r", encoding="utf-8").read() if os.path.exists(thesis_path) else "(thesis_log.md 없음)"

    timeline_path = os.path.join(comp_dir, "Weekly_Trend", "company_timeline.md")
    timeline_txt = open(timeline_path, "r", encoding="utf-8").read()[-4000:] if os.path.exists(timeline_path) else "(company_timeline.md 없음)"

    verbatim_path = os.path.join(comp_dir, "2_Translated_DB", "verbatim_extracts.md")
    verbatim_txt = open(verbatim_path, "r", encoding="utf-8").read() if os.path.exists(verbatim_path) else "(신규 PDF 발췌 없음)"

    static_prefix_path = os.path.join(SKILL_DIR, "static_cache_prefix.md")
    static_prefix_txt = (
        open(static_prefix_path, "r", encoding="utf-8").read().strip()
        if os.path.exists(static_prefix_path)
        else "# 🔒 [STATIC PROMPT CACHE PREFIX]"
    )

    digest_content = f"""{static_prefix_txt}

---

# 🧠 [{corp_name}] AI 원샷 통합 브리핑 문서 (`ai_prep_digest.md` — v5.1 Prompt-Cache Optimized)
> **생성 시각 (Dynamic Suffix Area)**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> **프롬프트 캐싱 구조**: 본 문서의 최상단(`[STATIC PROMPT CACHE PREFIX]`, 4,096+ 토큰 스키마·수식 정의서)은 전 종목 100% 고정되어 반복 호출 시 입력 토큰 비용 95% 할인($2.00 ➔ $0.10/1M) 및 캐시 히트를 보장하며, 기업별 가변 데이터는 모두 본 구분선 아래(Suffix)에 배치됩니다.

---

## [1] 🚦 실행 트랙 자동 판정 (Track A vs Track B)
{track_verdict}

---

## [2] 📊 코드 확정 SSOT 마크다운 테이블 (`auto_tables.md` 원본 — 숫자 임의 수정 절대 금지)
{auto_md_txt}

---

## [3] 🎯 기존 포퍼식 6열 가설 로그 (`thesis_log.md`) & 최근 타임라인 (`company_timeline.md`)
### 3-1. `Weekly_Trend/thesis_log.md`
{thesis_txt}

### 3-2. `Weekly_Trend/company_timeline.md` (최근 기록)
{timeline_txt}

---

## [4] 📄 2-Tier 스마트 무손실 원문 발췌본 (`verbatim_extracts.md`)
{verbatim_txt}
"""
    digest_path = os.path.join(comp_dir, "2_Translated_DB", "ai_prep_digest.md")
    with open(digest_path, "w", encoding="utf-8") as f:
        f.write(digest_content)
    return digest_path


def extract_section_from_auto_md(auto_md, header_prefix):
    """Extracts a specific `### 📌 [코드 자동 생성 ...]` block from auto_tables.md."""
    pattern = rf"(### 📌 \[{re.escape(header_prefix)}\].*?)(?=\n### 📌 \[|\Z)"
    m = re.search(pattern, auto_md, flags=re.DOTALL)
    return m.group(1).strip() if m else None


def patch_ssot_into_reports(comp_dir):
    """
    Deterministically patches SSOT tables, canonical HTML calculator tags, and updated price/SOP numbers
    into Phase1_Report.md and Phase3_DCF.md so Track B updates require ZERO manual number editing by the LLM.
    """
    ssot_path = os.path.join(comp_dir, "2_Translated_DB", "valuation_metrics.json")
    prev_path = os.path.join(comp_dir, "2_Translated_DB", "prev_valuation_metrics.json")
    auto_md_path = os.path.join(comp_dir, "2_Translated_DB", "auto_tables.md")

    if not os.path.exists(ssot_path) or not os.path.exists(auto_md_path):
        return

    with open(ssot_path, "r", encoding="utf-8") as f:
        curr_ssot = json.load(f)
    with open(auto_md_path, "r", encoding="utf-8") as f:
        auto_md = f.read()

    prev_ssot = {}
    if os.path.exists(prev_path):
        try:
            with open(prev_path, "r", encoding="utf-8") as f:
                prev_ssot = json.load(f)
        except Exception:
            prev_ssot = {}

    rpt_dir = os.path.join(comp_dir, "3_Final_Reports")
    p1_path = os.path.join(rpt_dir, "Phase1_Report.md")
    p3_path = os.path.join(rpt_dir, "Phase3_DCF.md")

    # Build numeric replacement pairs (old formatted -> new formatted) if prev_ssot exists
    num_replacements = []
    if prev_ssot:
        old_p = prev_ssot.get("anchor_price")
        new_p = curr_ssot.get("anchor_price")
        if old_p and new_p and old_p != new_p:
            num_replacements.append((f"{int(old_p):,}원", f"{int(new_p):,}원"))

        old_s3 = prev_ssot.get("section3", {}) or {}
        new_s3 = curr_ssot.get("section3", {}) or {}
        for k in ("bear_auto", "base_auto", "bull_auto", "base_auto_a", "bull_auto_a", "tp1_price", "tp1_price_a"):
            ov, nv = old_s3.get(k), new_s3.get(k)
            if ov and nv and ov != nv:
                num_replacements.append((f"{int(ov):,}원", f"{int(nv):,}원"))

        old_s4 = prev_ssot.get("section4", {}) or {}
        new_s4 = curr_ssot.get("section4", {}) or {}
        for k in ("buy1", "buy2", "buy3", "avg_buy_price", "init_stop_pin", "breakout_trail_pin"):
            ov, nv = old_s4.get(k), new_s4.get(k)
            if ov and nv and ov != nv:
                num_replacements.append((f"{int(ov):,}원", f"{int(nv):,}원"))

    # Patch Phase 1
    if os.path.exists(p1_path):
        with open(p1_path, "r", encoding="utf-8") as f:
            t1 = f.read()
        orig_t1 = t1

        for hdr in ("코드 자동 생성 1", "코드 자동 생성 1-B"):
            new_blk = extract_section_from_auto_md(auto_md, hdr)
            if new_blk:
                pat = rf"### 📌 \[{re.escape(hdr)}\].*?(?=\n### |\n---|\n## |\Z)"
                if re.search(pat, t1, flags=re.DOTALL):
                    t1 = re.sub(pat, new_blk + "\n", t1, count=1, flags=re.DOTALL)

        for old_str, new_str in num_replacements:
            t1 = t1.replace(old_str, new_str)

        if t1 != orig_t1:
            with open(p1_path, "w", encoding="utf-8") as f:
                f.write(t1)
            print(f"  [Auto-Patch] Phase1_Report.md SSOT 수치 및 테이블 자동 동기화 완료.")

    # Patch Phase 3
    if os.path.exists(p3_path):
        with open(p3_path, "r", encoding="utf-8") as f:
            t3 = f.read()
        orig_t3 = t3

        for hdr in ("코드 자동 생성 1-C", "코드 자동 생성 2", "코드 자동 생성 2-B"):
            new_blk = extract_section_from_auto_md(auto_md, hdr)
            if new_blk:
                pat = rf"### 📌 \[{re.escape(hdr)}\].*?(?=\n### |\n---|\n## |\Z)"
                if re.search(pat, t3, flags=re.DOTALL):
                    t3 = re.sub(pat, new_blk + "\n", t3, count=1, flags=re.DOTALL)

        # Always replace <div id="dcf-calculator-root"...></div> with canonical_html_tag
        c_tag = curr_ssot.get("canonical_html_tag", "")
        if c_tag:
            t3 = re.sub(
                r'<div\s+id="dcf-calculator-root"[^>]*>\s*</div>',
                c_tag,
                t3,
                flags=re.DOTALL,
            )

        for old_str, new_str in num_replacements:
            t3 = t3.replace(old_str, new_str)

        # Ensure all probe numbers from validate_report.py exist in Phase 3
        s3 = curr_ssot.get("section3", {}) or {}
        s4 = curr_ssot.get("section4", {}) or {}
        probes = [
            curr_ssot.get("anchor_price"),
            s4.get("buy1"),
            s4.get("buy2"),
            s4.get("buy3"),
            s4.get("init_stop_pin"),
            s3.get("base_auto_a"),
            s3.get("tp1_price"),
        ]
        missing_probes = [
            v for v in probes
            if v and (f"{int(round(v)):,}" not in t3 and str(int(round(v))) not in t3)
        ]
        if missing_probes:
            sop_blk = extract_section_from_auto_md(auto_md, "코드 자동 생성 2-B")
            if sop_blk and "[코드 자동 생성 2-B]" not in t3 and c_tag in t3:
                t3 = t3.replace(c_tag, sop_blk + "\n\n" + c_tag)

        if t3 != orig_t3:
            with open(p3_path, "w", encoding="utf-8") as f:
                f.write(t3)
            print(f"  [Auto-Patch] Phase3_DCF.md SSOT 수치·목표가·SOP·계산기 태그 자동 동기화 완료.")


def cmd_build(args):
    comp_dir = get_company_dir(args.corp_name)
    if not os.path.exists(comp_dir):
        print(f"[Error] 기업 폴더가 존재하지 않습니다: {comp_dir}")
        return 1

    if args.patch_ssot:
        patch_ssot_into_reports(comp_dir)

    rpt_dir = os.path.join(comp_dir, "3_Final_Reports")
    ssot_path = os.path.join(comp_dir, "2_Translated_DB", "valuation_metrics.json")
    gen_html_script = os.path.join(SKILL_DIR, "generate_html.py")

    for name in ("Phase1_Report", "Phase2_Story", "Phase3_DCF"):
        md_p = os.path.join(rpt_dir, f"{name}.md")
        html_p = os.path.join(rpt_dir, f"{name}.html")
        if os.path.exists(md_p):
            cmd = [sys.executable, gen_html_script, md_p, html_p]
            if os.path.exists(ssot_path):
                cmd.append(ssot_path)
            subprocess.run(cmd, check=False)

    print("\n======================================================================")
    print(f"🔍 [{args.corp_name}] 파이프라인 무결성 최종 검증 (validate_report.py)")
    print("======================================================================")
    res = validate_company(comp_dir)
    print_validation(res)
    return 1 if res.errors else 0


def cmd_init(args):
    comp_dir = ensure_company_structure(args.corp_name, args.code)
    print(f"✅ [{args.corp_name}] 4대 표준 폴더 및 6열 포퍼식 가설 로그 초기화 완료: {comp_dir}")
    if args.code:
        print(f"   종목코드({args.code})가 감지되어 초기 SSOT 백테스트(prep)를 자동 실행합니다...")
        args.years = 10
        args.sector_type = "A"
        args.rerating_date = None
        args.base_target = None
        args.bull_target = None
        args.dart_exposure = None
        args.forward_eps = None
        args.forward_eps_g = None
        args.expected_dps = None
        args.non_op_assets = None
        args.net_debt = None
        args.distb_shares = 0
        args.total_shares = 0
        args.fcf = None
        args.norm_fcf = None
        args.s_curve_phase2 = False
        args.early_ignition = False
        args.no_s_curve = False
        args.penetration_pct = None
        args.second_penetration_pct = None
        args.bottleneck_grade = None
        args.bottleneck_months = None
        args.capa_util_pct = None
        args.payout_ratio = None
        args.buyback_cliff = False
        args.related_party_eok = None
        args.governance_discount = None
        args.anchor_price = None
        args.shortage_easing = False
        args.slope_decel = False
        args.policy_headwind = False
        args.clear_sell_signals = False
        args.wacc = 0.09
        args.terminal = 0.02
        args.skip_pdf = True
        args.pdf_dirs = None
        args.include_raw_pdfs = False
        args.primary_keywords = None
        args.keywords = None
        args.max_pages = 15
        cmd_prep(args)
    return 0


def cmd_set_models(args):
    cfg = update_model_config(tier1_name=args.tier1, tier2_name=args.tier2)
    t1 = cfg["tier1_model"]["name"]
    t2 = cfg["tier2_model"]["name"]
    print(f"✅ 모델 설정 업데이트 완료 (model_config.json):")
    print(f"   • 1순위 최상위 모델 (Tier-1): {t1}")
    print(f"   • 2순위 고속 모델   (Tier-2): {t2}")

    conv_script = os.path.join(WORKSPACE_DIR, "convert_guide.py")
    if os.path.exists(conv_script):
        subprocess.run([sys.executable, conv_script], check=False)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Unified One-Shot Orchestrator for Korean Stock Analyzer v5.0"
    )
    sub = parser.add_subparsers(dest="subcmd", required=True)

    # 1) init
    p_init = sub.add_parser("init", help="Initialize 4 standard folders and logs for a new company")
    p_init.add_argument("--corp-name", required=True, help="Company name (e.g. 삼양식품)")
    p_init.add_argument("--code", default=None, help="Optional 6-digit stock code (e.g. 003230)")

    # 2) prep
    p_prep = sub.add_parser("prep", help="One-shot SSOT backtest + Reverse DCF + 2-Tier PDF verbatim + ai_prep_digest.md")
    p_prep.add_argument("--corp-name", required=True, help="Company name (e.g. 티씨케이)")
    p_prep.add_argument("--code", default=None, help="6-digit stock code (auto-inherited if valuation_metrics.json exists)")
    p_prep.add_argument("--years", type=int, default=10)
    p_prep.add_argument("--sector-type", default=None, help="A, B, C, or D")
    p_prep.add_argument("--rerating-date", default=None)
    p_prep.add_argument("--base-target", type=float, default=None)
    p_prep.add_argument("--bull-target", type=float, default=None)
    p_prep.add_argument("--dart-exposure", type=float, default=None)
    p_prep.add_argument("--forward-eps", type=float, default=None)
    p_prep.add_argument("--forward-eps-g", type=float, default=None)
    p_prep.add_argument("--expected-dps", type=float, default=None)
    p_prep.add_argument("--non-op-assets", type=float, default=None)
    p_prep.add_argument("--net-debt", type=float, default=None)
    p_prep.add_argument("--distb-shares", type=int, default=0)
    p_prep.add_argument("--total-shares", type=int, default=0)
    p_prep.add_argument("--fcf", type=float, default=None)
    p_prep.add_argument("--norm-fcf", type=float, default=None)
    p_prep.add_argument("--s-curve-phase2", action="store_true")
    p_prep.add_argument("--early-ignition", action="store_true")
    p_prep.add_argument("--no-s-curve", action="store_true")
    p_prep.add_argument("--penetration-pct", type=float, default=None)
    p_prep.add_argument("--second-penetration-pct", type=float, default=None)
    p_prep.add_argument("--bottleneck-grade", default=None)
    p_prep.add_argument("--bottleneck-months", type=int, default=None)
    p_prep.add_argument("--capa-util-pct", type=float, default=None)
    p_prep.add_argument("--payout-ratio", type=float, default=None)
    p_prep.add_argument("--buyback-cliff", action="store_true")
    p_prep.add_argument("--related-party-eok", type=float, default=None)
    p_prep.add_argument("--governance-discount", type=float, default=None)
    p_prep.add_argument("--anchor-price", type=float, default=None)
    p_prep.add_argument("--shortage-easing", action="store_true", help="S-Curve 매도·디레이팅 ①: 쇼티지 해소 / 리드타임 축소 / 경쟁사 진입 팩트")
    p_prep.add_argument("--slope-decel", action="store_true", help="S-Curve 매도·디레이팅 ②: 침투율·실적 성장 기울기 둔화 (2차 도함수 음전환)")
    p_prep.add_argument("--policy-headwind", action="store_true", help="S-Curve 매도·디레이팅 ③: 정책·보조금 축소 / 관세·규제 역풍 확정")
    p_prep.add_argument("--clear-sell-signals", action="store_true", help="기존 저장된 S-Curve 매도·디레이팅 시그널 플래그 초기화")
    p_prep.add_argument("--wacc", type=float, default=0.09)
    p_prep.add_argument("--terminal", type=float, default=0.02)
    p_prep.add_argument("--skip-pdf", action="store_true", help="Skip PDF scanning")
    p_prep.add_argument("--pdf-dirs", nargs="+", default=None, help="Explicit PDF folders/files to scan")
    p_prep.add_argument("--include-raw-pdfs", action="store_true", help="Also scan 1_Raw_Data PDFs")
    p_prep.add_argument("--primary-keywords", default=None, help="Comma-separated Tier-1 primary anchor keywords")
    p_prep.add_argument("--keywords", default=None, help="Comma-separated Tier-2 theme keywords")
    p_prep.add_argument("--max-pages", type=int, default=18, help="Max pages in verbatim_extracts.md (default: 18)")

    # 3) build
    p_build = sub.add_parser("build", help="Auto-patch SSOT into Markdown + compile Phase 1~3 HTML + run validate_report.py")
    p_build.add_argument("--corp-name", required=True, help="Company name")
    p_build.add_argument("--patch-ssot", action="store_true", default=True, help="Deterministically patch SSOT numbers/tables into Phase1 & Phase3 (default: True)")
    p_build.add_argument("--no-patch-ssot", action="store_false", dest="patch_ssot", help="Disable automatic SSOT patching")

    # 4) set-models
    p_models = sub.add_parser("set-models", help="Customize Tier-1 and Tier-2 Gemini model names for future releases")
    p_models.add_argument("--tier1", default=None, help="New Tier-1 Flagship model name (e.g. 'Gemini 4.5 Argon')")
    p_models.add_argument("--tier2", default=None, help="New Tier-2 High-Speed model name (e.g. 'Gemini 4.0 Argon Flash')")

    args = parser.parse_args()
    if args.subcmd == "init":
        sys.exit(cmd_init(args))
    elif args.subcmd == "prep":
        sys.exit(cmd_prep(args))
    elif args.subcmd == "build":
        sys.exit(cmd_build(args))
    elif args.subcmd == "set-models":
        sys.exit(cmd_set_models(args))


if __name__ == "__main__":
    main()
