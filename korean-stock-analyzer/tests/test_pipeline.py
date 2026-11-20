"""
Regression tests for the Korean Stock Analyzer pipeline (stdlib unittest; also runs under pytest).

    cd korean-stock-analyzer
    python -m unittest discover -s tests -v

What these protect
  * tests/golden/*.json : snapshots of 13 companies' valuation_metrics.json taken BEFORE any refactor.
      - every snapshot must satisfy the SSOT invariants (validate_report.check_ssot)
      - the key schema must not shrink (refactors may add keys, never drop)
  * pure engine functions are pinned with fixed inputs, so a refactor that silently changes
    S-Curve / bottleneck / shareholder-return math fails here.
Offline only - no DART / Naver calls.
"""
import glob
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import validate_report as vr  # noqa: E402
import ssot_common  # noqa: E402

GOLDEN = sorted(p for p in glob.glob(os.path.join(HERE, "golden", "*.json")))

REQUIRED_TOP_KEYS = {
    "version", "generated_at", "stock_code", "corp_name", "anchor_price", "primary_metric", "bench", "sotp",
    "step1_2_bottleneck", "step1_8_k_return", "regime", "section8", "section2", "section3",
    "cyclical_guard", "risk_causal_chain", "section4", "reverse_dcf", "canonical_html_tag",
}
REQUIRED_S3_KEYS = {"base_auto", "bull_auto", "bear_auto", "base_auto_a", "bull_auto_a", "tp1_price",
                    "tp1_price_a", "base_mult_a", "bull_mult_a", "implied_op_base_a_eok", "red_team_capa_verdict"}
REQUIRED_S4_KEYS = {"buy1", "buy2", "buy3", "avg_buy_price", "init_stop_pin", "poc_low"}


def _load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class GoldenSnapshots(unittest.TestCase):
    def test_golden_files_exist(self):
        self.assertGreaterEqual(len(GOLDEN), 13, "golden snapshots missing")

    def test_ssot_invariants_hold(self):
        for p in GOLDEN:
            with self.subTest(company=os.path.basename(p)):
                res = vr.Result(os.path.basename(p))
                vr.check_ssot(_load(p), res)
                self.assertEqual(res.errors, [], res.errors)

    def test_schema_not_shrunk(self):
        for p in GOLDEN:
            d = _load(p)
            with self.subTest(company=os.path.basename(p)):
                self.assertTrue(REQUIRED_TOP_KEYS <= set(d), REQUIRED_TOP_KEYS - set(d))
                self.assertTrue(REQUIRED_S3_KEYS <= set(d["section3"]), REQUIRED_S3_KEYS - set(d["section3"]))
                self.assertTrue(REQUIRED_S4_KEYS <= set(d["section4"]), REQUIRED_S4_KEYS - set(d["section4"]))

    def test_diff_tool_detects_change_and_ignores_timestamp(self):
        d = _load(GOLDEN[0])
        with tempfile.TemporaryDirectory() as td:
            a, b = os.path.join(td, "a.json"), os.path.join(td, "b.json")
            json.dump(d, open(a, "w", encoding="utf-8"))
            d2 = json.loads(json.dumps(d))
            d2["generated_at"] = "2099-01-01 00:00:00"
            json.dump(d2, open(b, "w", encoding="utf-8"))
            self.assertEqual(vr.diff_json(a, b), [])
            d2["section3"]["base_auto_a"] += 10
            json.dump(d2, open(b, "w", encoding="utf-8"))
            self.assertEqual([k for k, _, _ in vr.diff_json(a, b)], ["section3.base_auto_a"])


class ValidatorCatchesBreakage(unittest.TestCase):
    """The validator itself must fail when a known invariant is violated."""

    def setUp(self):
        self.d = _load(GOLDEN[0])

    def _errs(self, d):
        r = vr.Result("x")
        vr.check_ssot(d, r)
        return r.errors

    def test_clean_passes(self):
        self.assertEqual(self._errs(self.d), [])

    def test_safety_pin_above_buy_fails(self):
        self.d["section4"]["init_stop_pin"] = self.d["section4"]["buy1"] + 1
        self.assertTrue(any("safety pin" in e for e in self._errs(self.d)))

    def test_buy_above_tp1_fails(self):
        self.d["section4"]["is_overvalued"] = False
        self.d["section4"]["is_track2"] = False
        self.d["section4"]["buy3"] = self.d["section3"]["tp1_price"] + 1
        self.assertTrue(any("tp1_price" in e for e in self._errs(self.d)))

    def test_cap_violation_fails(self):
        self.d["section3"]["base_mult_a"] = 1.5
        self.assertTrue(any("cap" in e for e in self._errs(self.d)))

    def test_html_tag_drift_fails(self):
        self.d["section3"]["base_auto_a"] += 1000
        self.assertTrue(any("data-base-a" in e for e in self._errs(self.d)))

    def test_price_anchor_drift_fails(self):
        self.d["reverse_dcf"]["price"] = self.d["anchor_price"] + 100
        self.assertTrue(any("anchor" in e for e in self._errs(self.d)))

    def test_missing_kill_switch_fails(self):
        self.d["section2"]["kill_switch_guide"] = ""
        self.assertTrue(any("kill_switch_guide" in e for e in self._errs(self.d)))

    def test_validator_catches_phase1_phase2_anchor_drift(self):
        with tempfile.TemporaryDirectory() as td:
            comp = os.path.join(td, "테스트기업")
            os.makedirs(os.path.join(comp, "2_Translated_DB"), exist_ok=True)
            os.makedirs(os.path.join(comp, "3_Final_Reports"), exist_ok=True)
            os.makedirs(os.path.join(comp, "Weekly_Trend"), exist_ok=True)
            d = json.loads(json.dumps(self.d))
            d["anchor_price"] = 170000
            d["reverse_dcf"]["price"] = 170000
            d["canonical_html_tag"] = vr.re.sub(r'data-price="[^"]*"', 'data-price="170000"', d["canonical_html_tag"])
            with open(os.path.join(comp, "2_Translated_DB", "valuation_metrics.json"), "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            with open(os.path.join(comp, "3_Final_Reports", "Phase1_Report.md"), "w", encoding="utf-8") as f:
                f.write("- **단일 기준 주가(Single Price Anchor)**: **`170,400원`**\nStep 1.2 Step 1.5 Step 1.8 Step 2.0 Step 3.5\n")
            with open(os.path.join(comp, "3_Final_Reports", "Phase2_Story.md"), "w", encoding="utf-8") as f:
                f.write("> **[파이프라인 SSOT 단일 기준 주가]**: **`173,600원`**\n")
            with open(os.path.join(comp, "3_Final_Reports", "Phase3_DCF.md"), "w", encoding="utf-8") as f:
                f.write("레드팀 안전핀\n")
            res = vr.validate_company(comp)
            self.assertTrue(any("Phase1_Report.md" in e and "170,400" in e for e in res.errors), res.errors)
            self.assertTrue(any("Phase2_Story.md" in e and "173,600" in e for e in res.errors), res.errors)

    def test_patch_ssot_updates_h2_phase1_and_phase2_anchor(self):
        import ksa_orchestrator as ko
        with tempfile.TemporaryDirectory() as td:
            comp = os.path.join(td, "테스트기업")
            os.makedirs(os.path.join(comp, "2_Translated_DB"), exist_ok=True)
            os.makedirs(os.path.join(comp, "3_Final_Reports"), exist_ok=True)
            os.makedirs(os.path.join(comp, "Weekly_Trend"), exist_ok=True)
            d = json.loads(json.dumps(self.d))
            d["anchor_price"] = 170000
            d["reverse_dcf"]["price"] = 170000
            d["canonical_html_tag"] = vr.re.sub(r'data-price="[^"]*"', 'data-price="170000"', d["canonical_html_tag"])
            with open(os.path.join(comp, "2_Translated_DB", "valuation_metrics.json"), "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            # Simulate repeated prep overwriting prev_valuation_metrics.json with identical anchor_price
            with open(os.path.join(comp, "2_Translated_DB", "prev_valuation_metrics.json"), "w", encoding="utf-8") as f:
                json.dump(d, f, ensure_ascii=False)
            with open(os.path.join(comp, "2_Translated_DB", "auto_tables.md"), "w", encoding="utf-8") as f:
                f.write(
                    "### 📌 [코드 자동 생성 1] SOTP 장부 분해\n"
                    "| 항목 | 수치 |\n| :--- | :--- |\n| **단일 기준 주가 (Anchor Price)** | **`170,000원`** |\n"
                )
            with open(os.path.join(comp, "3_Final_Reports", "Phase1_Report.md"), "w", encoding="utf-8") as f:
                f.write(
                    "- **단일 기준 주가(Single Price Anchor)**: **`170,400원`**\n\n"
                    "## 📌 [코드 자동 생성 1] SOTP 장부 분해\n"
                    "| 항목 | 수치 |\n| :--- | :--- |\n| **단일 기준 주가 (Anchor Price)** | **`170,400원`** |\n\n"
                    "---\nStep 1.2 Step 1.5 Step 1.8 Step 2.0 Step 3.5\n"
                )
            with open(os.path.join(comp, "3_Final_Reports", "Phase2_Story.md"), "w", encoding="utf-8") as f:
                f.write(
                    "> **[파이프라인 SSOT 단일 기준 주가]**: **`173,600원`** (`2026-11-13`)\n"
                    "현재 주가 173,600원은 납입가(204,500원) 대비 할인 상태.\n"
                    '<div id="dcf-calculator-root" data-price="173600" data-bear="100"></div>\n'
                )
            s3, s4 = d["section3"], d["section4"]
            with open(os.path.join(comp, "3_Final_Reports", "Phase3_DCF.md"), "w", encoding="utf-8") as f:
                f.write(
                    f"> **단일 기준 주가 (Anchor Price)**: **`170,000원`**\n"
                    f"레드팀 안전핀 {s4['buy1']:,} {s4['buy2']:,} {s4['buy3']:,} {s4['init_stop_pin']:,} {s3['base_auto_a']:,} {s3['tp1_price']:,}\n"
                    '<div id="dcf-calculator-root" data-price="173600"></div>\n'
                )
            with open(os.path.join(comp, "Weekly_Trend", "thesis_log.md"), "w", encoding="utf-8") as f:
                f.write("| 가설 ID | 핵심 | QoQ | 근거 | 반증 Kill-Switch | 판정 |\n| --- | --- | --- | --- | --- | --- |\n| H1 | t | q | f | k | ok |\n")
            ko.patch_ssot_into_reports(comp)
            res = vr.validate_company(comp)
            self.assertEqual(res.errors, [], res.errors)
            with open(os.path.join(comp, "3_Final_Reports", "Phase2_Story.md"), encoding="utf-8") as f:
                p2 = f.read()
            self.assertIn("170,000원", p2)
            self.assertIn("204,500원", p2)  # historical issue price must stay untouched
            self.assertNotIn("173,600원", p2)

    def test_build_ai_prep_digest_excludes_2d(self):
        import ksa_orchestrator as ko
        with tempfile.TemporaryDirectory() as td:
            comp = os.path.join(td, "TEST")
            os.makedirs(os.path.join(comp, "2_Translated_DB"))
            os.makedirs(os.path.join(comp, "3_Final_Reports"))
            os.makedirs(os.path.join(comp, "Weekly_Trend"))
            auto_path = os.path.join(comp, "2_Translated_DB", "auto_tables.md")
            sample_auto = (
                "### 📌 [코드 자동 생성 2] Phase 3 표\n"
                "| A | B |\n| :--- | :--- |\n| x | y |\n\n"
                "### 📌 [코드 자동 생성 2-D] (참고용) 3요소 종합 평가\n"
                "> 참고\n| 축 | 점수 |\n| :--- | :---: |\n| 실적 | 100점 |\n\n"
                "### 📌 [코드 자동 생성 3] HTML 계산기 직결 태그\n"
                '<div id="dcf-calculator-root" data-price="10000"></div>\n'
            )
            with open(auto_path, "w", encoding="utf-8") as f:
                f.write(sample_auto)
            digest_path = ko.build_ai_prep_digest(comp, "TEST")
            with open(digest_path, encoding="utf-8") as f:
                digest = f.read()
            self.assertIn("코드 자동 생성 2]", digest)
            self.assertIn("코드 자동 생성 3]", digest)
            self.assertNotIn("코드 자동 생성 2-D", digest)
            self.assertNotIn("3요소 종합 평가", digest)
            with open(auto_path, encoding="utf-8") as f:
                self.assertIn("코드 자동 생성 2-D", f.read())


class EngineFunctionsPinned(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import backtest_valuation as bv
        cls.bv = bv

    def test_step1_2_golden_inflection_S_grade(self):
        r = self.bv.compute_step1_2_scurve_bottleneck_matrix(
            "999999", "TEST", {}, scurve_override=True, penetration_pct=12.0,
            bottleneck_grade="S", bottleneck_months=30, capa_util_pct=92.0)
        self.assertIn("Zone A", r["penetration_zone"])
        self.assertEqual(r["bottleneck_grade"], "S")
        self.assertAlmostEqual(r["pen_base_boost"], 0.12)
        self.assertAlmostEqual(r["pen_bull_boost"], 0.16)
        self.assertAlmostEqual(r["total_sc_bn_base_mult"], 1.17)
        self.assertAlmostEqual(r["total_sc_bn_bull_mult"], 1.23)

    def test_step1_2_free_call_option_blocks_penetration_boost(self):
        # When dart_exposure < 30% (Free Call Option), S-Curve penetration boost must be 0.0%
        # even if penetration_pct=12.0 is passed; only core bottleneck moat (+8%/+10% for S/24M+/92% util) may apply.
        r = self.bv.compute_step1_2_scurve_bottleneck_matrix(
            "999999", "TEST", {}, dart_exposure=10.0, penetration_pct=12.0,
            bottleneck_grade="S", bottleneck_months=30, capa_util_pct=92.0)
        self.assertFalse(r["is_phase2"])
        self.assertEqual(r["pen_base_boost"], 0.0)
        self.assertEqual(r["pen_bull_boost"], 0.0)
        self.assertTrue(r["core_bottleneck_only_mode"])
        self.assertAlmostEqual(r["total_sc_bn_base_mult"], 1.08)
        self.assertAlmostEqual(r["total_sc_bn_bull_mult"], 1.10)

    def test_step1_2_mature_no_bottleneck_gets_no_premium(self):
        r = self.bv.compute_step1_2_scurve_bottleneck_matrix(
            "999999", "TEST", {}, penetration_pct=50.0, bottleneck_grade="C", bottleneck_months=0,
            capa_util_pct=60.0)
        self.assertIn("Zone D", r["penetration_zone"])
        self.assertAlmostEqual(r["total_sc_bn_base_mult"], 1.0)
        self.assertAlmostEqual(r["total_sc_bn_bull_mult"], 1.0)
        self.assertFalse(r["scurve_sell_triggered"])

    def test_step1_2_scurve_sell_signals_strip_premium_and_derate(self):
        # Even if penetration_pct=12.0 (Zone A) and bottleneck_grade="S", a confirmed sell signal
        # must strip 100% of S-Curve upside and apply bounded de-rating (< 1.00x).
        r1 = self.bv.compute_step1_2_scurve_bottleneck_matrix(
            "999999", "TEST", {}, penetration_pct=12.0, bottleneck_grade="S", bottleneck_months=24,
            capa_util_pct=90.0, shortage_easing=True)
        self.assertTrue(r1["scurve_sell_triggered"])
        self.assertEqual(r1["pen_base_boost"], 0.0)
        self.assertEqual(r1["pen_bull_boost"], 0.0)
        self.assertAlmostEqual(r1["total_sc_bn_base_mult"], 0.94)
        self.assertAlmostEqual(r1["total_sc_bn_bull_mult"], 0.92)
        self.assertAlmostEqual(r1["peg_factor"], 0.65)

        # Compound 3 signals must be bounded by the -15% / -18% floor cap (0.85x / 0.82x)
        r3 = self.bv.compute_step1_2_scurve_bottleneck_matrix(
            "999999", "TEST", {}, penetration_pct=30.0, bottleneck_grade="A",
            shortage_easing=True, slope_decel=True, policy_headwind=True)
        self.assertTrue(r3["scurve_sell_triggered"])
        self.assertAlmostEqual(r3["total_sc_bn_base_mult"], 0.85)
        self.assertAlmostEqual(r3["total_sc_bn_bull_mult"], 0.82)

    def test_step1_8_payout_and_treasury(self):
        r = self.bv.compute_step1_8_k_market_shareholder_return(
            "999999", {"div_yield": 3.0, "eps": 1000.0, "dps": 500.0, "close": 10000.0}, {},
            10000000, 10500000, payout_ratio=50.0)
        self.assertEqual(r["payout_ratio_pct"], 50.0)
        self.assertEqual(r["treasury_shares"], 500000)
        self.assertAlmostEqual(r["treasury_ratio_pct"], 4.76)
        self.assertFalse(r["buyback_cliff_warn"])
        self.assertAlmostEqual(r["kgov_mult"], 1.0)

        # Related-party tunneling (>= 500 eok -> -4%) + buyback cliff (-2%) must auto-discount kgov_mult
        r_pen = self.bv.compute_step1_8_k_market_shareholder_return(
            "999999", {"div_yield": 3.0, "eps": 1000.0, "dps": 500.0, "close": 10000.0}, {},
            10000000, 10000000, payout_ratio=30.0, buyback_cliff=True, related_party_eok=600.0)
        self.assertTrue(r_pen["buyback_cliff_warn"])
        self.assertAlmostEqual(r_pen["kgov_mult"], 0.94)

    def test_section4_c_grade_downtrend_blocks_current_price_buy(self):
        import pandas as pd
        import numpy as np
        # Create a clear downtrend weekly & daily series (price dropping from 300,000 to 200,000)
        dates_w = pd.date_range("2024-01-05", periods=110, freq="W-FRI")
        prices_w = np.linspace(300000, 200000, 110)
        df_w = pd.DataFrame({
            "date": dates_w, "open": prices_w * 1.01, "high": prices_w * 1.02,
            "low": prices_w * 0.98, "close": prices_w, "vol": np.full(110, 50000.0)
        })
        dates_d = pd.date_range("2026-06-01", periods=65, freq="B")
        prices_d = np.linspace(250000, 200000, 65)
        df_d = pd.DataFrame({
            "date": dates_d, "open": prices_d * 1.01, "high": prices_d * 1.015,
            "low": prices_d * 0.985, "close": prices_d, "vol": np.full(65, 10000.0)
        })
        sec2 = {"is_type_b": False, "op_yoy_used": -30.0, "qoq_op_pct": -20.0}
        sec3 = {
            "base_auto": 280000, "base_auto_a": 300000, "bull_auto_a": 350000,
            "tp1_price": 260000, "bear_auto": 150000, "is_low_vol_box": False,
            "is_peak_trap": False, "scurve_sell_triggered": False, "scurve_info": {"is_phase2": True},
        }
        s4 = self.bv.compute_section4_master_sop_indicators(df_d, df_w, sec2, sec3)
        self.assertEqual(s4["w_swing_grade"], "C")
        self.assertTrue(s4["is_downtrend_hold"])
        # All 3 buy steps must be strictly below current price (200,000) to avoid catching a falling knife
        self.assertLess(s4["buy1"], s4["buy2"])
        self.assertLess(s4["buy2"], s4["buy3"])
        self.assertLess(s4["buy3"], 200000)
        self.assertLess(s4["init_stop_pin"], s4["buy1"])

    def test_consistency_fixes_tp1_c_grade_forward_eps_and_rampup_guard(self):
        import pandas as pd
        import numpy as np
        dates_w = pd.date_range("2024-01-05", periods=110, freq="W-FRI")
        prices_w = np.linspace(30000, 40000, 110)
        df_w = pd.DataFrame({
            "date": dates_w, "open": prices_w * 0.99, "high": prices_w * 1.02,
            "low": prices_w * 0.98, "close": prices_w, "vol": np.full(110, 50000.0)
        })
        dates_d = pd.date_range("2026-06-01", periods=65, freq="B")
        prices_d = np.linspace(38000, 40000, 65)
        df_d = pd.DataFrame({
            "date": dates_d, "open": prices_d * 0.99, "high": prices_d * 1.01,
            "low": prices_d * 0.98, "close": prices_d, "vol": np.full(65, 10000.0)
        })
        bench = {"bps": 20000.0, "eps": 3000.0, "pbr": 2.0, "stock_name": "TEST"}
        sec2 = {
            "is_type_b": False, "curr_bps_used": 20000.0, "curr_eps_used": 3000.0,
            "mid_cycle_eps": 2000.0, "mid_cycle_roe": 12.0, "curr_roe": 15.0,
            "qoq_op_pct": 25.0, "op_yoy_used": 30.0,
            "per_3y_p20": 7.0, "per_3y_mean": 10.0, "per_3y_p65": 12.0, "per_3y_p90": 16.0,
            "pbr_3y_p20": 1.1, "pbr_3y_mean": 1.5, "pbr_3y_p65": 1.7, "pbr_3y_p90": 2.5,
        }
        sec8 = {"primary_metric": "PBR", "pbr_min": 0.9, "per_min": 5.0, "pbr_dir": 65.0, "per_dir": 65.0}

        # 1) C-grade suspends optimistic forward_eps
        r_c = self.bv.compute_section3_stock_nature_and_tp1(
            "999999", "TEST", bench, df_w, df_d, sec2, 40000,
            forward_eps=6000.0, tech_snap={"w_swing_grade": "C", "w_swing_score": 35, "w_mfi14": 40.0, "w_mfi14_12w_max": 50.0},
            sec8_res=sec8,
        )
        self.assertTrue(r_c["forward_eps_suspended"])
        self.assertEqual(r_c["forward_bps"], 20000.0)

        # 2) Non-overheated ramp-up exemption passes ONLY when ev_g <= 12 and MFI < 75
        r_ramp_ok = self.bv.compute_section3_stock_nature_and_tp1(
            "999999", "TEST", bench, df_w, df_d, sec2, 40000,
            tech_snap={"w_swing_grade": "S", "w_swing_score": 82, "w_mfi14": 55.0, "w_mfi14_12w_max": 60.0},
            ev_implied_g=-5.0, sec8_res=sec8,
        )
        self.assertTrue(r_ramp_ok["is_non_overheated_rampup"])
        self.assertFalse(r_ramp_ok["is_peak_trap"])
        # TP1 must respect Base <= TP1 <= Bull and have zero circularity with inflated curr_price
        self.assertLessEqual(r_ramp_ok["base_auto"], r_ramp_ok["tp1_price"])
        self.assertLessEqual(r_ramp_ok["tp1_price"], r_ramp_ok["bull_auto"])
        self.assertLessEqual(r_ramp_ok["base_auto_a"], r_ramp_ok["tp1_price_a"])
        self.assertLessEqual(r_ramp_ok["tp1_price_a"], r_ramp_ok["bull_auto_a"])

        # 3) Overheated MFI (>= 80) or high ev_g (> 12%) blocks the ramp-up exemption -> is_peak_trap = True
        r_ramp_hot_mfi = self.bv.compute_section3_stock_nature_and_tp1(
            "999999", "TEST", bench, df_w, df_d, sec2, 40000,
            tech_snap={"w_swing_grade": "A", "w_swing_score": 75, "w_mfi14": 81.0, "w_mfi14_12w_max": 85.0},
            ev_implied_g=-5.0, sec8_res=sec8,
        )
        self.assertFalse(r_ramp_hot_mfi["is_non_overheated_rampup"])
        self.assertTrue(r_ramp_hot_mfi["is_peak_trap"])

        r_ramp_hot_ev = self.bv.compute_section3_stock_nature_and_tp1(
            "999999", "TEST", bench, df_w, df_d, sec2, 40000,
            tech_snap={"w_swing_grade": "A", "w_swing_score": 75, "w_mfi14": 55.0, "w_mfi14_12w_max": 60.0},
            ev_implied_g=25.0, sec8_res=sec8,
        )
        self.assertFalse(r_ramp_hot_ev["is_non_overheated_rampup"])
        self.assertTrue(r_ramp_hot_ev["is_peak_trap"])

        # 4) Close ev_implied_g=None loophole: stretched PBR (2.0x > 3Y mean 1.5x) MUST NOT pass when ev_implied_g is None
        r_ramp_none_stretched = self.bv.compute_section3_stock_nature_and_tp1(
            "999999", "TEST", bench, df_w, df_d, sec2, 40000,
            tech_snap={"w_swing_grade": "A", "w_swing_score": 75, "w_mfi14": 55.0, "w_mfi14_12w_max": 60.0},
            ev_implied_g=None, sec8_res=sec8,
        )
        self.assertFalse(r_ramp_none_stretched["is_non_overheated_rampup"])
        self.assertTrue(r_ramp_none_stretched["is_peak_trap"])

        # When ev_implied_g is None BUT PBR sits strictly in lower-half 3Y band (1.30x <= 1.50x, band <= 50%), exemption is allowed
        r_ramp_none_cheap = self.bv.compute_section3_stock_nature_and_tp1(
            "999999", "TEST", dict(bench, pbr=1.3), df_w, df_d, sec2, 26000,
            tech_snap={"w_swing_grade": "A", "w_swing_score": 75, "w_mfi14": 55.0, "w_mfi14_12w_max": 60.0},
            ev_implied_g=None, sec8_res=sec8,
        )
        self.assertTrue(r_ramp_none_cheap["is_non_overheated_rampup"])
        self.assertFalse(r_ramp_none_cheap["is_peak_trap"])

        # 5) Semiconductor Sobujang Dual-Anchor TP1: when tech_tp1_raw < Base (deeply beaten-down stock),
        #    TP1 anchors cleanly at Base (no artificial >Base jump) and exposes pre-Base tech_resist_1 separately.
        dates_d2 = pd.date_range("2026-06-01", periods=65, freq="B")
        prices_d2 = np.linspace(30000, 32000, 65)
        df_d_low = pd.DataFrame({
            "date": dates_d2, "open": prices_d2 * 0.99, "high": prices_d2 * 1.01,
            "low": prices_d2 * 0.98, "close": prices_d2, "vol": np.full(65, 10000.0)
        })
        sec2_hi = dict(sec2, pbr_3y_p65=2.6, pbr_3y_p90=3.4, per_3y_p65=18.0, per_3y_p90=24.0)
        r_pre = self.bv.compute_section3_stock_nature_and_tp1(
            "999999", "TEST", bench, df_w, df_d_low, sec2_hi, 32000,
            tech_snap={"w_swing_grade": "B", "w_swing_score": 65, "w_mfi14": 55.0, "w_mfi14_12w_max": 60.0},
            ev_implied_g=-5.0, sec8_res=sec8,
        )
        self.assertTrue(r_pre["has_pre_base_resist"])
        self.assertEqual(r_pre["tp1_price"], r_pre["base_auto"])
        self.assertEqual(r_pre["tp1_price_a"], r_pre["base_auto_a"])
        self.assertLess(r_pre["tech_resist_1"], r_pre["base_auto"])

    def test_3factor_price_equation_eval_regimes(self):
        sotp = {"core_roic_pct": 22.0}
        s12 = {"bottleneck_grade": "A"}
        s18 = {"treasury_ratio_pct": 3.0, "buyback_cliff_warn": False}
        s2_good = {"qoq_op_pct": 50.0, "op_yoy_used": 45.0, "curr_roe": 18.0, "is_type_b": False,
                   "curr_bps_used": 18000.0, "pbr_3y_p20": 1.2, "pbr_3y_p90": 2.8}
        s3_ok = {"scurve_info": {"is_phase2": False}, "scurve_sell_triggered": False}
        s4_good = {"w_mfi14": 55.0, "w_mfi14_12w_max": 60.0, "w_vp_status": "매물벽상단순항(+10점)",
                   "w_close": 40000, "w_ma5": 40000, "w_ma20": 39000, "w_ma60": 37000,
                   "w_macd_hist": 100.0, "w_swing_score": 80, "w_swing_grade": "S"}
        ev_low = {"fcf_eok": 600.0, "implied_g_ev_pct": -5.0}

        pe_gem = self.bv.compute_3factor_price_equation_eval(40000, sotp, s12, s18, s2_good, s3_ok, s4_good, ev_low)
        self.assertGreaterEqual(pe_gem["earnings_score"], 75)
        self.assertGreaterEqual(pe_gem["supply_demand_score"], 75)
        self.assertIn("저평가", pe_gem["regime_verdict"])

        # Base-overvalued holder mode (e.g. GST) avoids conflicting "저평가" headline while keeping bullish holder guidance
        s4_over = dict(s4_good, is_overvalued=True)
        pe_holder = self.bv.compute_3factor_price_equation_eval(
            40000, sotp, s12, s18, s2_good, s3_ok, s4_over, ev_low,
            bench={"investor_flow": {"days": 20, "smart_money_vol_pct": 4.2, "smart_money_net_eok": 120.0,
                                     "foreign_5d_shares": 10000, "organ_5d_shares": 5000,
                                     "foreign_hold_ratio_pct": 25.0, "foreign_hold_chg_pctp": 0.6}},
        )
        self.assertIn("FCF 거품 0%", pe_holder["regime_verdict"])
        self.assertIn("KRX 20일 외인·기관", pe_holder["supply_demand_detail"])
        self.assertGreater(pe_holder["supply_demand_score"], pe_gem["supply_demand_score"])

        s4_hot = dict(s4_good, w_mfi14=83.0, w_mfi14_12w_max=86.0)
        pe_hot = self.bv.compute_3factor_price_equation_eval(40000, sotp, s12, s18, s2_good, s3_ok, s4_hot, ev_low)
        self.assertIn("과열", pe_hot["regime_verdict"])

        # Strong earnings + Grade-C chart gets separated into "수급 눌림 vs 실적 우위형" rather than dual-weak "약화"
        s4_c = dict(s4_good, w_swing_grade="C", w_mfi14=28.0, w_vp_status="매물벽하단저항(-8점)", w_ma5=35000, w_ma60=42000, w_macd_hist=-500.0)
        pe_c = self.bv.compute_3factor_price_equation_eval(40000, sotp, s12, s18, s2_good, s3_ok, s4_c, ev_low)
        self.assertIn("역배열", pe_c["regime_verdict"])
        self.assertIn("실적 우위형", pe_c["regime_verdict"])

        s2_weak = dict(s2_good, qoq_op_pct=-30.0, op_yoy_used=-40.0, curr_roe=5.0)
        pe_ice = self.bv.compute_3factor_price_equation_eval(40000, {"core_roic_pct": 4.0}, s12, s18, s2_weak, s3_ok, s4_c, ev_low)
        self.assertIn("약화 대기형", pe_ice["regime_verdict"])


class DcfNeverClobbersSilently(unittest.TestCase):
    def setUp(self):
        ssot_common.reset_warnings()

    def test_corrupt_ssot_is_backed_up_and_flagged(self):
        import calc_reverse_dcf as dcf
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "valuation_metrics.json")
            with open(p, "w", encoding="utf-8") as f:
                f.write("{ this is not json")
            dcf.update_ssot_json(p, {"status": "success", "fcf_eok": 1.0, "norm_fcf_eok": None})
            self.assertTrue(os.path.exists(p + ".corrupt.bak"))
            out = _load(p)
            self.assertEqual(out["data_quality"]["status"], "degraded")

    def test_existing_data_quality_is_preserved(self):
        import calc_reverse_dcf as dcf
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "valuation_metrics.json")
            base = {"data_quality": {"status": "degraded",
                                     "warnings": [{"stage": "x", "severity": "degraded", "detail": "d"}]}}
            with open(p, "w", encoding="utf-8") as f:
                json.dump(base, f)
            dcf.update_ssot_json(p, {"status": "success", "fcf_eok": 1.0, "norm_fcf_eok": None})
            out = _load(p)
            self.assertEqual(out["data_quality"]["status"], "degraded")
            self.assertEqual(out["data_quality"]["warnings"][0]["stage"], "x")


class WarningRegistry(unittest.TestCase):
    def setUp(self):
        ssot_common.reset_warnings()

    def test_status_levels(self):
        self.assertEqual(ssot_common.data_quality_summary()["status"], "ok")
        ssot_common.record_warning("a", "minor")
        self.assertEqual(ssot_common.data_quality_summary()["status"], "warn")
        ssot_common.record_warning("b", "bad", severity="degraded")
        self.assertEqual(ssot_common.data_quality_summary()["status"], "degraded")

    def test_duplicates_collapsed(self):
        ssot_common.record_warning("a", "same")
        ssot_common.record_warning("a", "same")
        self.assertEqual(len(ssot_common.get_warnings()), 1)


class MermaidAndReportHeaderTests(unittest.TestCase):
    def test_sanitize_and_check_mermaid_nested_brackets_and_bare_end(self):
        import generate_html as gh
        import validate_report as vr

        sample = "\n".join([
            "flowchart TD",
            '    O1["수액제 병원 발주"] -->|"판가/원가 압박"| O2["매출총이익률 하락"]',
            '    O2 --> O3["연결 영업이익 급감 (임계치: 분기 영업이익 < 79.9억 원 [QoQ -15%])"]',
            '    M1["초고순도 SiC Ring [점유율 1위]"] -.->|증설 지연| end["종료 (마진 방어)"]',
            "    subgraph SG1[원재료 리스크]",
            "        O3 --> end",
            "    end",
        ])
        fixed = gh.sanitize_mermaid_code(sample)
        self.assertEqual(vr.check_mermaid_syntax(fixed), [])
        self.assertIn('[QoQ -15%]', fixed)
        self.assertNotIn('"])', fixed)
        self.assertIn("end_node", fixed)

    def test_build_html_v5_title_and_validator_catches_broken_html(self):
        import glob
        import generate_html as gh
        import ksa_orchestrator as ko
        import validate_report as vr

        with tempfile.TemporaryDirectory() as td:
            comp = os.path.join(td, "테스트사")
            db = os.path.join(comp, "2_Translated_DB")
            rpt = os.path.join(comp, "3_Final_Reports")
            wt = os.path.join(comp, "Weekly_Trend")
            os.makedirs(db)
            os.makedirs(rpt)
            os.makedirs(wt)

            golden_files = sorted(
                glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "golden", "*.json"))
            )
            self.assertTrue(golden_files, "No golden JSON files found")
            ssot = json.loads(json.dumps(_load(golden_files[0])))
            ssot["version"] = "5.0"
            ssot["generated_at"] = "2026-11-18 20:00:00"
            ssot["corp_name"] = "테스트사"
            with open(os.path.join(db, "valuation_metrics.json"), "w", encoding="utf-8") as f:
                json.dump(ssot, f, ensure_ascii=False)
            with open(os.path.join(db, "auto_tables.md"), "w", encoding="utf-8") as f:
                f.write("<!-- AUTO -->\n")

            p1 = os.path.join(rpt, "Phase1_Report.md")
            p2 = os.path.join(rpt, "Phase2_Story.md")
            p3 = os.path.join(rpt, "Phase3_DCF.md")
            with open(p1, "w", encoding="utf-8") as f:
                f.write(
                    f"# 테스트사 Phase 1 (v5.0)\n\n> **단일 기준 주가**: {ssot['anchor_price']:,}원\n\n"
                    "## 1. BM\n## 2. Step 1.2\n## 3. Step 1.5\n## 4. 원가\n## 5. Step 1.8\n"
                    "## 6. Step 3.5\n## 7. 공식\n## 8. Step 2.0\n"
                    '```mermaid\nflowchart TD\nA["시작 [1차]"] --> B["끝 (2차)"]\n```\n'
                )
            with open(p2, "w", encoding="utf-8") as f:
                f.write("# 테스트사 Phase 2 (v5.0)\n\n본문\n")
            with open(p3, "w", encoding="utf-8") as f:
                f.write(
                    f"# 테스트사 Phase 3 (v5.0)\n\n> **작성 기준일**: 2026-10-01 | **단일 기준 주가**: {ssot['anchor_price']:,}원\n\n"
                    f"레드팀 안전핀 {ssot['section3']['base_auto_a']:,}\n{ssot['canonical_html_tag']}\n"
                )
            with open(os.path.join(wt, "thesis_log.md"), "w", encoding="utf-8") as f:
                f.write("| 가설 | 내용 | QoQ | 근거 | Kill-Switch | 상태 |\n| :--- | :--- | :--- | :--- | :--- | :--- |\n")

            # Before patch: missing 분석완료일 should FAIL v5.0 validator
            res_before = vr.validate_company(comp)
            self.assertTrue(any("분석완료일" in e for e in res_before.errors), msg=f"errors={res_before.errors}")

            # Patch completion dates & build HTML
            ko.patch_ssot_into_reports(comp)
            for md_name in ("Phase1_Report.md", "Phase2_Story.md", "Phase3_DCF.md"):
                txt = open(os.path.join(rpt, md_name), encoding="utf-8").read()
                self.assertIn("> **분석완료일**: 2026-11-18", "\n".join(txt.splitlines()[:10]))
            self.assertNotIn("작성 기준일", open(p3, encoding="utf-8").read())

            h1 = os.path.join(rpt, "Phase1_Report.html")
            gh.build_html(p1, h1, explicit_ssot=os.path.join(db, "valuation_metrics.json"))
            html_out = open(h1, encoding="utf-8").read()
            self.assertIn("<title>테스트사 Phase 1 — Stock Analyzer Report (v5.0)</title>", html_out)
            self.assertNotIn("(v4.2)", html_out)

            res_after = vr.validate_company(comp)
            self.assertEqual(res_after.errors, [], msg=f"Unexpected errors: {res_after.errors}")

            # Corrupt HTML Mermaid block directly -> validator must catch it
            corrupt_html = html_out.replace('A[&quot;시작 [1차]&quot;]', 'O3[&quot;\'급감 [QoQ -15%&quot;])&quot;]')
            with open(h1, "w", encoding="utf-8") as f:
                f.write(corrupt_html)
            res_bad = vr.validate_company(comp)
            self.assertTrue(any("HTML syntax error" in e for e in res_bad.errors), msg=f"errors={res_bad.errors}")


class Step18KReturnScorecardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import backtest_valuation as bv
        cls.bv = bv

    def test_step1_8_overrides_and_mezzanine_and_parent_channel(self):
        dart_ts = [
            {"year": 2025, "sales_eok": 2200.0, "op_eok": 360.0, "ni_ctrl_eok": 300.0, "eq_ctrl_eok": 2500.0},
            {"year": 2024, "sales_eok": 2000.0, "op_eok": 340.0, "ni_ctrl_eok": 280.0, "eq_ctrl_eok": 2300.0},
        ]
        bench = {"dps": 550.0, "div_yield": 5.19}
        res_jw = self.bv.compute_step1_8_k_market_shareholder_return(
            "234080", bench, dart_ts, 15484554, 15834554, payout_ratio=29.8, governance_discount=10.0
        )
        self.assertIn("29.8%", res_jw["tax_incentive_status"])
        self.assertNotIn("33%+", res_jw["tax_incentive_status"])
        self.assertAlmostEqual(res_jw["gov_discount_pct"], 10.0, places=2)
        self.assertAlmostEqual(res_jw["kgov_mult"], 0.9000, places=4)
        self.assertTrue(res_jw["is_listed_parent_sales"])
        self.assertIn("정상 영업 유통", res_jw["tunneling_status"])

        res_mezz = self.bv.compute_step1_8_k_market_shareholder_return(
            "999999", bench, dart_ts, 10000000, 10000000, payout_ratio=42.0, mezzanine_eok=120.0, mezzanine_pct=11.0
        )
        self.assertIn("요건1 충족", res_mezz["tax_incentive_status"])
        self.assertAlmostEqual(res_mezz["kgov_mult"], 0.9700, places=4)
        self.assertIn("메자닌 오버행 경보", res_mezz["overhang_status"])

    def test_cmd_prep_inherits_step1_8_gov_discount_and_cliff(self):
        import types
        from unittest import mock
        import ksa_orchestrator as ko

        with tempfile.TemporaryDirectory() as td:
            comp = os.path.join(td, "상속테스트")
            db = os.path.join(comp, "2_Translated_DB")
            os.makedirs(db)
            ssot_path = os.path.join(db, "valuation_metrics.json")
            with open(ssot_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "stock_code": "234080",
                        "anchor_price": 10590,
                        "step1_8_k_return": {
                            "payout_ratio_pct": 29.8,
                            "tsr_pct": 31.0,
                            "buyback_cliff_warn": True,
                            "mezzanine_eok": 50.0,
                            "mezzanine_pct": 4.2,
                            "related_party_eok": 1525.0,
                            "is_listed_parent_sales": True,
                            "gov_discount_pct": 10.0,
                            "k_gov_note": "상장 모회사 유통 비할인 + 계열사 보증 할인",
                        },
                    },
                    f,
                    ensure_ascii=False,
                )

            args = types.SimpleNamespace(
                corp_name="상속테스트",
                code=None,
                years=10,
                sector_type=None,
                rerating_date=None,
                base_target=None,
                bull_target=None,
                dart_exposure=None,
                forward_eps=None,
                forward_eps_g=None,
                expected_dps=None,
                non_op_assets=None,
                net_debt=None,
                distb_shares=0,
                total_shares=0,
                fcf=None,
                norm_fcf=None,
                s_curve_phase2=False,
                early_ignition=False,
                no_s_curve=False,
                penetration_pct=None,
                second_penetration_pct=None,
                bottleneck_grade=None,
                bottleneck_months=None,
                capa_util_pct=None,
                payout_ratio=None,
                tsr_pct=None,
                buyback_cliff=False,
                mezzanine_eok=None,
                mezzanine_pct=None,
                related_party_eok=None,
                listed_parent_sales=False,
                governance_discount=None,
                gov_note=None,
                anchor_price=None,
                shortage_easing=False,
                slope_decel=False,
                policy_headwind=False,
                clear_sell_signals=False,
                wacc=0.09,
                terminal=0.02,
                skip_pdf=True,
                pdf_dirs=None,
                include_raw_pdfs=False,
                primary_keywords=None,
                keywords=None,
                max_pages=18,
            )

            captured = {}
            def _fake_bt(*a, **kw):
                captured.update(kw)

            with mock.patch.object(ko, "ensure_company_structure", return_value=comp), \
                 mock.patch.object(ko, "run_valuation_backtest", side_effect=_fake_bt), \
                 mock.patch.object(ko, "append_extended_ssot_tables"), \
                 mock.patch.object(ko, "refresh_price_eq_in_ssot"), \
                 mock.patch.object(ko, "build_ai_prep_digest", return_value=""):
                ko.cmd_prep(args)

            self.assertAlmostEqual(captured["governance_discount"], 10.0)
            self.assertTrue(captured["buyback_cliff"])
            self.assertAlmostEqual(captured["tsr_pct"], 31.0)
            self.assertAlmostEqual(captured["mezzanine_eok"], 50.0)
            self.assertAlmostEqual(captured["mezzanine_pct"], 4.2)
            self.assertTrue(captured["listed_parent_sales"])
            self.assertEqual(captured["gov_note"], "상장 모회사 유통 비할인 + 계열사 보증 할인")


class ScenarioDriverPreservationTests(unittest.TestCase):
    def test_patch_ssot_preserves_ai_drivers_in_auto2_while_updating_numbers(self):
        import ksa_orchestrator as ko

        with tempfile.TemporaryDirectory() as td:
            comp = os.path.join(td, "테스트사")
            os.makedirs(os.path.join(comp, "2_Translated_DB"))
            os.makedirs(os.path.join(comp, "3_Final_Reports"))
            os.makedirs(os.path.join(comp, "Weekly_Trend"))

            ssot = json.loads(json.dumps(_load(GOLDEN[0])))
            ssot["version"] = "5.1"
            ssot["generated_at"] = "2026-11-20 12:00:00"
            with open(os.path.join(comp, "2_Translated_DB", "valuation_metrics.json"), "w", encoding="utf-8") as f:
                json.dump(ssot, f, ensure_ascii=False)

            auto_md = (
                "### 📌 [코드 자동 생성 2] Phase 3 6열 시나리오 밸류에이션 표 (주 지표: PER)\n"
                "| 시나리오 | 확률 (고정) | 핵심 드라이버 가정 (AI 해석 영역) | 적용 멀티플 (코드 산출) | 적정주가 (🛡️대안 B / 🚀대안 A) | 현재가 대비 등락률 (🛡️대안 B / 🚀대안 A) |\n"
                "| :--- | :---: | :--- | :--- | :--- | :--- |\n"
                "| **Bull (호황 상단)** | **25%** | [AI 작성 필수: Bull 구체 서술] | PER 상위 90% (대안A ×1.1500) | 🛡️ **120,000원** / 🚀 **138,000원** | 🛡️ **+20.0%** / 🚀 **+38.0%** |\n"
                "| **Base (기본 적정)** | **50%** | [AI 작성 필수: Base 구체 서술] | PER 상위 65% (대안A ×1.1000) | 🛡️ **100,000원** / 🚀 **110,000원** | 🛡️ **+0.0%** / 🚀 **+10.0%** |\n"
                "| **Bear (하방 지지)** | **25%** | [AI 작성 필수: Bear 구체 서술] | 하방 지지선 (할증 0% 고정) | 🛡️ **75,000원** / 🚀 **75,000원** | 🛡️ **-25.0%** / 🚀 **-25.0%** |\n"
            )
            with open(os.path.join(comp, "2_Translated_DB", "auto_tables.md"), "w", encoding="utf-8") as f:
                f.write(auto_md)

            bull_drv = "HBM4용 핵심 부품 수주 확대 + 가동률 95% 돌파 및 OPM 28% 달성 + 자사주 소각 리레이팅"
            base_drv = "주력 라인 가동률 85%·OPM 24% 안착 + TTM 영업이익 500억 유지 및 배당성향 30% 지속"
            bear_drv = "전방 CapEx 지연으로 가동률 65% 하락 + 분기 영업이익 95억(QoQ -15%) 하회 시 하방 압축"
            p3_md = (
                f"# 테스트사 Phase 3 (v5.1)\n\n> **분석완료일**: 2026-11-20 | **단일 기준 주가**: {ssot['anchor_price']:,}원\n\n"
                "### 📌 [코드 자동 생성 2] Phase 3 6열 시나리오 밸류에이션 표 (주 지표: PER)\n"
                "| 시나리오 | 확률 (고정) | 핵심 드라이버 가정 (AI 해석 영역) | 적용 멀티플 (코드 산출) | 적정주가 (🛡️대안 B / 🚀대안 A) | 현재가 대비 등락률 (🛡️대안 B / 🚀대안 A) |\n"
                "| :--- | :---: | :--- | :--- | :--- | :--- |\n"
                f"| **Bull (호황 상단)** | **25%** | {bull_drv} | PER 상위 90% (대안A ×1.1000) | 🛡️ **110,000원** / 🚀 **121,000원** | 🛡️ **+10.0%** / 🚀 **+21.0%** |\n"
                f"| **Base (기본 적정)** | **50%** | {base_drv} | PER 상위 65% (대안A ×1.0500) | 🛡️ **95,000원** / 🚀 **99,750원** | 🛡️ **-5.0%** / 🚀 **-0.3%** |\n"
                f"| **Bear (하방 지지)** | **25%** | {bear_drv} | 하방 지지선 (할증 0% 고정) | 🛡️ **70,000원** / 🚀 **70,000원** | 🛡️ **-30.0%** / 🚀 **-30.0%** |\n\n"
                "- **확률가중 기대 적정주가**: 커스텀 요약 문단 유지 확인\n\n"
                "---\n레드팀 안전핀\n"
            )
            p3_path = os.path.join(comp, "3_Final_Reports", "Phase3_DCF.md")
            with open(p3_path, "w", encoding="utf-8") as f:
                f.write(p3_md)

            ko.patch_ssot_into_reports(comp)
            patched = open(p3_path, encoding="utf-8").read()
            # AI-written drivers and custom bullet must be preserved
            self.assertIn(bull_drv, patched)
            self.assertIn(base_drv, patched)
            self.assertIn(bear_drv, patched)
            self.assertIn("커스텀 요약 문단 유지 확인", patched)
            # Numeric SSOT columns must be updated
            self.assertIn("138,000원", patched)
            self.assertIn("110,000원", patched)
            self.assertIn("75,000원", patched)
            self.assertNotIn("[AI 작성 필수", patched)

    def test_validator_rejects_ai_driver_placeholders_and_stubs(self):
        with tempfile.TemporaryDirectory() as td:
            comp = os.path.join(td, "테스트사")
            os.makedirs(os.path.join(comp, "2_Translated_DB"))
            os.makedirs(os.path.join(comp, "3_Final_Reports"))
            os.makedirs(os.path.join(comp, "Weekly_Trend"))

            ssot = json.loads(json.dumps(_load(GOLDEN[0])))
            ssot["version"] = "5.1"
            with open(os.path.join(comp, "2_Translated_DB", "valuation_metrics.json"), "w", encoding="utf-8") as f:
                json.dump(ssot, f, ensure_ascii=False)
            with open(os.path.join(comp, "Weekly_Trend", "thesis_log.md"), "w", encoding="utf-8") as f:
                f.write("| 가설 | 내용 | QoQ | 근거 | Kill-Switch | 판정 |\n| --- | --- | --- | --- | --- | --- |\n")

            p3_path = os.path.join(comp, "3_Final_Reports", "Phase3_DCF.md")
            with open(p3_path, "w", encoding="utf-8") as f:
                f.write(
                    f"# 테스트사 Phase 3 (v5.1)\n> **분석완료일**: 2026-11-20\n\n"
                    "### 📌 [코드 자동 생성 2] Phase 3 6열 시나리오 밸류에이션 표 (주 지표: PER)\n"
                    "| 시나리오 | 확률 | 핵심 드라이버 가정 | 멀티플 | 적정주가 | 등락률 |\n"
                    "| :--- | :---: | :--- | :--- | :--- | :--- |\n"
                    "| **Bull (호황 상단)** | **25%** | [AI가 전방 호황/가동률 상단 서술] | PER 90% | 100원 | +10% |\n"
                    "| **Base (기본 적정)** | **50%** | 가동률 상단 서술 | PER 65% | 90원 | 0% |\n"
                    "| **Bear (하방 지지)** | **25%** | [AI 작성 필수: Bear 구체 서술] | 하방 | 70원 | -20% |\n"
                    "레드팀 안전핀\n"
                )
            res = vr.validate_company(comp)
            self.assertTrue(any("leftover placeholder" in e for e in res.errors), res.errors)
            self.assertTrue(any("핵심 드라이버 가정" in e for e in res.errors), res.errors)


class Step13BmOpSlopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import backtest_valuation as bv
        cls.bv = bv

    def _make_price_dfs(self, start_p=30000, end_p=40000):
        import pandas as pd
        import numpy as np
        dates_w = pd.date_range("2024-01-05", periods=110, freq="W-FRI")
        prices_w = np.linspace(start_p, end_p, 110)
        df_w = pd.DataFrame({
            "date": dates_w, "open": prices_w * 0.99, "high": prices_w * 1.02,
            "low": prices_w * 0.98, "close": prices_w, "vol": np.full(110, 50000.0)
        })
        dates_d = pd.date_range("2026-06-01", periods=65, freq="B")
        prices_d = np.linspace(end_p * 0.96, end_p, 65)
        df_d = pd.DataFrame({
            "date": dates_d, "open": prices_d * 0.99, "high": prices_d * 1.01,
            "low": prices_d * 0.98, "close": prices_d, "vol": np.full(65, 10000.0)
        })
        return df_w, df_d

    def test_high_fixed_cost_low_roe_leverage_model_a_only(self):
        # High fixed cost (35% of sales) + low OPM (10%) + low ROE (7.6% < 12%) + util up + var cost down
        # -> DOL = 4.50x, strong_accel (Base 1.12x / Bull 1.15x) reflected ONLY in Model A; Model B is 100% invariant!
        df_w, df_d = self._make_price_dfs(25000, 32000)
        bench = {"bps": 25000.0, "eps": 2000.0, "pbr": 1.28, "stock_name": "고정비테스트"}
        sec2 = {
            "is_type_b": False, "curr_bps_used": 25000.0, "curr_eps_used": 2000.0,
            "mid_cycle_eps": 2200.0, "mid_cycle_roe": 10.0, "curr_roe": 7.6,
            "qoq_op_pct": 65.0, "op_yoy_used": 95.0,
            "per_3y_p20": 10.0, "per_3y_mean": 14.0, "per_3y_p65": 16.0, "per_3y_p90": 22.0,
            "pbr_3y_p20": 1.0, "pbr_3y_mean": 1.4, "pbr_3y_p65": 1.7, "pbr_3y_p90": 2.4,
        }
        sec8 = {"primary_metric": "PBR", "pbr_min": 0.9, "per_min": 8.0, "pbr_dir": 70.0, "per_dir": 65.0}
        s12 = {"capa_util_pct": 68.0, "curr_opm_pct": 10.0, "total_sc_bn_base_mult": 1.0, "total_sc_bn_bull_mult": 1.0, "scurve_sell_triggered": False}
        tech = {"w_swing_grade": "A", "w_swing_score": 74, "w_mfi14": 58.0, "w_mfi14_12w_max": 64.0}

        r_neutral = self.bv.compute_section3_stock_nature_and_tp1(
            "999999", "고정비테스트", bench, df_w, df_d, sec2, 32000,
            sector_type="A", step1_2_res=s12, sec8_res=sec8, tech_snap=tech, ev_implied_g=4.0,
            bm_slope_params={"op_slope": "neutral", "slope_evidence": "high"},
        )
        r_lev = self.bv.compute_section3_stock_nature_and_tp1(
            "999999", "고정비테스트", bench, df_w, df_d, sec2, 32000,
            sector_type="A", step1_2_res=s12, sec8_res=sec8, tech_snap=tech, ev_implied_g=4.0,
            bm_slope_params={
                "bm_core_driver": "감가상각 고정비(35%) 기반 가동률(68%→82%) 및 변동비율 하락",
                "fixed_cost_ratio_pct": 35.0,
                "util_trend": "up",
                "var_cost_trend": "down",
                "slope_evidence": "high",
            },
        )
        # Model B MUST be 100% untouched!
        self.assertEqual(r_lev["base_auto"], r_neutral["base_auto"])
        self.assertEqual(r_lev["bull_auto"], r_neutral["bull_auto"])
        self.assertEqual(r_lev["bear_auto"], r_neutral["bear_auto"])
        # Step 1.3 must compute DOL = 4.50x and reflect strong_accel ONLY in Model A
        s13 = r_lev["step1_3_bm_slope"]
        self.assertAlmostEqual(s13["dol"], 4.5, places=2)
        self.assertTrue(s13["is_high_fixed_cost"])
        self.assertEqual(s13["final_grade"], "strong_accel")
        self.assertAlmostEqual(r_lev["op_slope_base_mult"], 1.12, places=4)
        self.assertAlmostEqual(r_lev["op_slope_bull_mult"], 1.15, places=4)
        self.assertGreater(r_lev["base_auto_a"], r_neutral["base_auto_a"])
        self.assertGreater(r_lev["bull_auto_a"], r_neutral["bull_auto_a"])

    def test_anti_peakout_guard1_physical_capa_ceiling(self):
        # Case A: 96.4% full utilization + NO expansion/ASP hike + negative QoQ (-6.0%) -> auto downgrade to decel (0.94/0.92)
        r_rollover = self.bv.compute_step1_3_bm_op_slope(
            "064760", "천장테스트", {},
            sec2_res={"op_yoy_used": 37.7, "qoq_op_pct": -6.0, "curr_roe": 15.1, "is_type_b": False},
            step1_2_res={"capa_util_pct": 96.4, "curr_opm_pct": 28.3},
            sector_type="A", op_slope="accel", slope_evidence="high",
            capa_expand=False, asp_up=False,
        )
        self.assertTrue(r_rollover["ceiling_guard_triggered"])
        self.assertEqual(r_rollover["final_grade"], "decel")
        self.assertAlmostEqual(r_rollover["op_slope_base_mult"], 0.94, places=4)
        self.assertTrue(r_rollover["op_slope_decel_warn"])

        # Case B: 98.9% full utilization + flat/positive QoQ (+0.6%) + NO expansion -> cap upside to neutral (1.00)
        r_cap = self.bv.compute_step1_3_bm_op_slope(
            "234080", "천장캡테스트", {},
            sec2_res={"op_yoy_used": 32.9, "qoq_op_pct": 0.6, "curr_roe": 12.3, "is_type_b": False},
            step1_2_res={"capa_util_pct": 98.9, "curr_opm_pct": 14.1},
            sector_type="A", op_slope="accel", slope_evidence="high",
            capa_expand=False, asp_up=False,
        )
        self.assertTrue(r_cap["ceiling_guard_triggered"])
        self.assertEqual(r_cap["final_grade"], "neutral")
        self.assertAlmostEqual(r_cap["op_slope_base_mult"], 1.00, places=4)

        # Case C: Confirmed Capa expansion exempts physical ceiling guard -> accel preserved
        r_exp = self.bv.compute_step1_3_bm_op_slope(
            "234080", "증설예외테스트", {},
            sec2_res={"op_yoy_used": 32.9, "qoq_op_pct": 5.0, "curr_roe": 12.3, "is_type_b": False},
            step1_2_res={"capa_util_pct": 96.0, "curr_opm_pct": 14.1},
            sector_type="A", op_slope="accel", slope_evidence="high",
            capa_expand=True, asp_up=False,
        )
        self.assertFalse(r_exp["ceiling_guard_triggered"])
        self.assertAlmostEqual(r_exp["op_slope_base_mult"], 1.06, places=4)

    def test_anti_peakout_guard2_priced_in_overheating_asymmetric(self):
        # 1 hot flag (EV g > +15%) halves upside boost: 1.12 -> 1.06
        r_1hot = self.bv.compute_step1_3_bm_op_slope(
            "999999", "선반영1", {},
            sec2_res={"op_yoy_used": 40.0, "qoq_op_pct": 20.0, "curr_roe": 14.0},
            step1_2_res={"capa_util_pct": 78.0, "curr_opm_pct": 15.0},
            op_slope="strong_accel", slope_evidence="high",
            ev_implied_g=22.0, curr_pbr=1.5, pbr_p90=2.5,
            tech_snap={"w_mfi14": 60.0, "w_mfi14_12w_max": 65.0},
        )
        self.assertTrue(r_1hot["priced_in_guard_triggered"])
        self.assertAlmostEqual(r_1hot["op_slope_base_mult"], 1.06, places=4)

        # 2+ hot flags (EV g > +15% AND PBR >= p90*0.95) strips upside to 1.00
        r_2hot = self.bv.compute_step1_3_bm_op_slope(
            "999999", "선반영2", {},
            sec2_res={"op_yoy_used": 40.0, "qoq_op_pct": 20.0, "curr_roe": 14.0},
            step1_2_res={"capa_util_pct": 78.0, "curr_opm_pct": 15.0},
            op_slope="strong_accel", slope_evidence="high",
            ev_implied_g=22.0, curr_pbr=2.45, pbr_p90=2.5,
            tech_snap={"w_mfi14": 60.0, "w_mfi14_12w_max": 65.0},
        )
        self.assertTrue(r_2hot["priced_in_guard_triggered"])
        self.assertAlmostEqual(r_2hot["op_slope_base_mult"], 1.00, places=4)

        # Asymmetric safety: downside contraction penalty is NEVER weakened by overheating flags!
        r_down = self.bv.compute_step1_3_bm_op_slope(
            "999999", "하방보존", {},
            sec2_res={"op_yoy_used": -10.0, "qoq_op_pct": -20.0, "curr_roe": 8.0},
            step1_2_res={"capa_util_pct": 70.0, "curr_opm_pct": 8.0},
            op_slope="contraction", slope_evidence="high",
            ev_implied_g=25.0, curr_pbr=2.5, pbr_p90=2.5,
            tech_snap={"w_mfi14": 82.0, "w_mfi14_12w_max": 85.0},
        )
        self.assertAlmostEqual(r_down["op_slope_base_mult"], 0.88, places=4)
        self.assertAlmostEqual(r_down["op_slope_bull_mult"], 0.85, places=4)

    def test_anti_peakout_guard3_evidence_tier_and_track2_block(self):
        # Medium evidence halves upside (1.12 -> 1.06); Low evidence blocks upside (1.00)
        r_med = self.bv.compute_step1_3_bm_op_slope(
            "999999", "신뢰도중", {}, step1_2_res={"capa_util_pct": 75.0, "curr_opm_pct": 15.0},
            op_slope="strong_accel", slope_evidence="medium",
        )
        self.assertTrue(r_med["evidence_guard_triggered"])
        self.assertAlmostEqual(r_med["op_slope_base_mult"], 1.06, places=4)

        r_low = self.bv.compute_step1_3_bm_op_slope(
            "999999", "신뢰도하", {}, step1_2_res={"capa_util_pct": 75.0, "curr_opm_pct": 15.0},
            op_slope="strong_accel", slope_evidence="low",
        )
        self.assertAlmostEqual(r_low["op_slope_base_mult"], 1.00, places=4)

        # Track 2 MUST be blocked when op_slope_decel_warn is True!
        df_w, df_d = self._make_price_dfs(30000, 42000)
        sec2 = {"is_type_b": False, "op_yoy_used": 25.0, "qoq_op_pct": -5.0}
        sec3_ok = {
            "base_auto": 40000, "base_auto_a": 48000, "bull_auto_a": 56000,
            "tp1_price": 45000, "bear_auto": 30000, "is_low_vol_box": False,
            "is_peak_trap": False, "scurve_sell_triggered": False,
            "op_slope_decel_warn": False, "scurve_info": {"is_phase2": True},
        }
        sec3_decel = dict(sec3_ok, op_slope_decel_warn=True)
        s4_ok = self.bv.compute_section4_master_sop_indicators(df_d, df_w, sec2, sec3_ok, anchor_price=42000)
        s4_decel = self.bv.compute_section4_master_sop_indicators(df_d, df_w, sec2, sec3_decel, anchor_price=42000)
        self.assertTrue(s4_ok["is_track2"])
        self.assertFalse(s4_decel["is_track2"])

        # Validator must catch Track 2 violation if SSOT has both op_slope_decel_warn=True & is_track2=True
        bad_ssot = json.loads(json.dumps(_load(GOLDEN[0])))
        bad_ssot["step1_3_bm_slope"] = {"op_slope_base_mult": 0.94, "op_slope_bull_mult": 0.92, "op_slope_decel_warn": True}
        bad_ssot["section3"]["op_slope_decel_warn"] = True
        bad_ssot["section4"]["is_track2"] = True
        r_val = vr.Result("track2_decel_violation")
        vr.check_ssot(bad_ssot, r_val)
        self.assertTrue(any("is_track2" in e for e in r_val.errors), r_val.errors)

    def test_orchestrator_step13_inheritance_diff_table_and_patch_1d(self):
        import types
        from unittest import mock
        import ksa_orchestrator as ko

        with tempfile.TemporaryDirectory() as td:
            comp = os.path.join(td, "스텝13테스트")
            db = os.path.join(comp, "2_Translated_DB")
            rpt = os.path.join(comp, "3_Final_Reports")
            wt = os.path.join(comp, "Weekly_Trend")
            os.makedirs(db)
            os.makedirs(rpt)
            os.makedirs(wt)

            prev_ssot = json.loads(json.dumps(_load(GOLDEN[0])))
            prev_ssot["version"] = "5.2"
            prev_ssot["step1_3_bm_slope"] = {
                "bm_core_driver": "감가상각 고정비 기반 가동률 상승",
                "fixed_cost_ratio_pct": 34.0,
                "var_cost_ratio_pct": 54.0,
                "dol": 3.8,
                "is_high_fixed_cost": True,
                "util_trend": "up",
                "var_cost_trend": "down",
                "input_mode": "explicit_op_slope",
                "raw_grade": "strong_accel",
                "final_grade": "strong_accel",
                "slope_evidence": "high",
                "capa_expand": True,
                "asp_up": False,
                "has_explicit_inputs": True,
                "op_slope_base_mult": 1.12,
                "op_slope_bull_mult": 1.15,
                "guardrail_summary": "🟢 3중 안티-피크아웃 가드레일 정상 통과",
            }
            ssot_path = os.path.join(db, "valuation_metrics.json")
            with open(ssot_path, "w", encoding="utf-8") as f:
                json.dump(prev_ssot, f, ensure_ascii=False)

            args = types.SimpleNamespace(
                corp_name="스텝13테스트", code=None, years=10, sector_type=None, rerating_date=None,
                base_target=None, bull_target=None, dart_exposure=None, forward_eps=None, forward_eps_g=None,
                expected_dps=None, non_op_assets=None, net_debt=None, distb_shares=0, total_shares=0,
                fcf=None, norm_fcf=None, s_curve_phase2=False, early_ignition=False, no_s_curve=False,
                penetration_pct=None, second_penetration_pct=None, bottleneck_grade=None, bottleneck_months=None,
                capa_util_pct=None, payout_ratio=None, tsr_pct=None, buyback_cliff=False,
                mezzanine_eok=None, mezzanine_pct=None, related_party_eok=None, listed_parent_sales=False,
                governance_discount=None, gov_note=None, anchor_price=None,
                shortage_easing=False, slope_decel=False, policy_headwind=False, clear_sell_signals=False,
                bm_core_driver=None, fixed_cost_ratio=None, var_cost_ratio=None, util_trend=None,
                var_cost_trend=None, op_slope=None, slope_evidence=None, capa_expand=False, asp_up=False,
                clear_bm_slope=False, wacc=0.09, terminal=0.02, skip_pdf=True, pdf_dirs=None,
                include_raw_pdfs=False, primary_keywords=None, keywords=None, max_pages=18,
            )
            captured = {}
            def _fake_bt(*a, **kw):
                captured.update(kw)

            with mock.patch.object(ko, "ensure_company_structure", return_value=comp), \
                 mock.patch.object(ko, "run_valuation_backtest", side_effect=_fake_bt), \
                 mock.patch.object(ko, "append_extended_ssot_tables"), \
                 mock.patch.object(ko, "refresh_price_eq_in_ssot"), \
                 mock.patch.object(ko, "build_ai_prep_digest", return_value=""):
                ko.cmd_prep(args)

            self.assertEqual(captured["bm_core_driver"], "감가상각 고정비 기반 가동률 상승")
            self.assertAlmostEqual(captured["fixed_cost_ratio"], 34.0)
            self.assertAlmostEqual(captured["var_cost_ratio"], 54.0)
            self.assertEqual(captured["util_trend"], "up")
            self.assertEqual(captured["var_cost_trend"], "down")
            self.assertEqual(captured["op_slope"], "strong_accel")
            self.assertTrue(captured["capa_expand"])

            diff_md = ko.format_ssot_comparison_table({}, prev_ssot, "스텝13테스트")
            self.assertIn("직전 vs 신규 SSOT 비교표", diff_md)
            self.assertIn("Step 1.3", diff_md)
            self.assertIn("DOL 3.80x", diff_md)
            self.assertIn("대안 B 적정가", diff_md)
            self.assertIn("대안 A 적정가", diff_md)

            # Verify patch_ssot updates [코드 자동 생성 1-D] and validator checks Step 1.3 on v5.2
            with open(os.path.join(db, "auto_tables.md"), "w", encoding="utf-8") as f:
                f.write(
                    "### 📌 [코드 자동 생성 1-D] Step 1.3 테스트\n"
                    "| 항목 | 값 |\n| :--- | :--- |\n| 계수 | ×1.1200 |\n"
                )
            p1_path = os.path.join(rpt, "Phase1_Report.md")
            with open(p1_path, "w", encoding="utf-8") as f:
                f.write(
                    f"# 스텝13테스트 Phase 1 (v5.2)\n> **분석완료일**: 2026-11-20 | **단일 기준 주가**: {prev_ssot['anchor_price']:,}원\n\n"
                    "## 1. BM\n## 2. Step 1.2\n## 3. Step 1.5\n"
                    "## 4. 원가 구조 및 Step 1.3\n"
                    "### 📌 [코드 자동 생성 1-D] Step 1.3 구버전\n"
                    "| 항목 | 값 |\n| :--- | :--- |\n| 계수 | ×1.0000 |\n\n"
                    "## 5. Step 1.8\n## 6. Step 3.5\n## 7. 공식\n## 8. Step 2.0\n"
                )
            with open(os.path.join(wt, "thesis_log.md"), "w", encoding="utf-8") as f:
                f.write("| 가설 | 내용 | QoQ | 근거 | Kill-Switch | 판정 |\n| --- | --- | --- | --- | --- | --- |\n")
            ko.patch_ssot_into_reports(comp)
            p1_after = open(p1_path, encoding="utf-8").read()
            self.assertIn("×1.1200", p1_after)
            self.assertNotIn("×1.0000", p1_after)
            res_ok = vr.validate_company(comp)
            self.assertEqual(res_ok.errors, [], res_ok.errors)

            # Removing Step 1.3 from a v5.2 Phase 1 must FAIL validator
            with open(p1_path, "w", encoding="utf-8") as f:
                f.write(p1_after.replace("Step 1.3", "원가분석"))
            res_fail = vr.validate_company(comp)
            self.assertTrue(any("Step 1.3" in e for e in res_fail.errors), res_fail.errors)

    def test_parse_pdf_captures_dart_cost_by_nature_without_company_name(self):
        from unittest import mock
        import parse_pdf as pp

        class _FakePage:
            def __init__(self, txt):
                self._txt = txt
            def extract_text(self):
                return self._txt

        class _FakeReader:
            def __init__(self, _path):
                self.pages = [
                    _FakePage("표지 - 테스트반도체 2026년 3분기보고서"),
                    _FakePage("일반 개요 페이지 테스트반도체 소개"),
                    _FakePage("주석 24. 비용의 성격별 분류\n원재료 및 소모품의 사용 450억\n감가상각비 320억\n종업원급여 180억"),
                    _FakePage("생산설비 가동률 현황\n생산능력 1,000 / 생산실적 680 / 평균가동률 68.0%"),
                ]

        with tempfile.TemporaryDirectory() as td:
            pdf_p = os.path.join(td, "[테스트반도체]분기보고서(2026.11.14).pdf")
            with open(pdf_p, "wb") as f:
                f.write(b"%PDF-1.4\n")
            out_md = os.path.join(td, "verbatim.md")
            with mock.patch.object(pp.pypdf, "PdfReader", _FakeReader):
                pp.batch_verbatim_extract(
                    [td],
                    ["테스트반도체", "반도체", "소부장"],
                    output_md=out_md,
                    primary_keywords=["테스트반도체"],
                    max_pages_total=4,
                )
            content = open(out_md, encoding="utf-8").read()
            self.assertIn("비용의 성격별 분류", content)
            self.assertIn("평균가동률 68.0%", content)
            self.assertIn("Step1.3 비용·가동률", content)


class PatchV521CyclicalCapexAndIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import backtest_valuation as bv
        cls.bv = bv

    def _make_sample_dfs(self, n_weeks=270, start_p=35000, end_p=66800):
        import pandas as pd
        import numpy as np

        dates_w = pd.date_range("2021-09-03", periods=n_weeks, freq="W-FRI")
        # Construct realistic 5Y PBR cycle: 2021-2023 normal upcycle, 2024-2025 trough, 2026-05 spike (177,800), then 66,800
        prices = np.linspace(start_p, end_p, n_weeks)
        prices[:100] = np.linspace(60000, 75000, 100)       # 5Y normal upcycle (~2.8-3.8x)
        prices[100:210] = np.linspace(45000, 28000, 110)    # 2024-2025 trough (~1.2-2.0x)
        prices[210:255] = np.linspace(50000, 177800, 45)    # 2026 short-term spike (up to 7.73x)
        prices[255:] = np.linspace(110000, end_p, n_weeks - 255)
        df_w = pd.DataFrame({
            "date": dates_w, "open": prices * 0.99, "high": prices * 1.03,
            "low": prices * 0.97, "close": prices, "vol": np.full(n_weeks, 500000.0),
        })
        dates_d = pd.date_range("2026-08-20", periods=65, freq="B")
        prices_d = np.linspace(80000, end_p, 65)
        df_d = pd.DataFrame({
            "date": dates_d, "open": prices_d * 1.01, "high": prices_d * 1.02,
            "low": prices_d * 0.98, "close": prices_d, "vol": np.full(65, 250000.0),
        })
        s5 = pd.DataFrame({
            "date": dates_w.strftime("%Y-%m-%d"),
            "price": prices,
            "BPS": np.full(n_weeks, 23439.0),
            "PBR": prices / 23439.0,
            "PER": np.where(prices > 0, prices / 1500.0, np.nan),
        })
        return df_w, df_d, s5

    def _make_dart_ts_tax_distorted(self, s5):
        import pandas as pd

        # 20 quarters (5 full years) of TTM data: 2022-2024 upcycle (ROE 14~18%, mid-cycle ROE ~14.5%),
        # 2025-2026 trough (OP=314eok, Core NOPAT ROE 5.17%), BUT latest 3Q26 has +212eok one-off tax credit
        # so headline NI=534eok (headline ROE=11.28%)!
        sh = 19245628.0
        eq = 4731.9e8
        rows_s3 = []
        for i in range(20):
            yr = 2022 + (i // 4)
            q = f"{(i % 4) + 1}Q"
            if i < 12:
                op = 600e8
                ni = 520e8
                roe = 15.5
            elif i < 19:
                op = 356e8
                ni = 342e8
                roe = 7.6
            else:
                op = 313.8e8
                ni = 533.7e8  # inflated by +211.8eok one-off deferred tax credit
                roe = 11.28
            rows_s3.append({
                "Year": yr, "Quarter": q, "매출액": 3200e8, "영업이익": op,
                "당기순이익": ni, "지배순이익": ni, "자본총계": eq, "지배자본": eq,
                "현재주식수": sh, "BPS": eq / sh, "EPS": ni / sh, "ROE": roe,
            })
        s3 = pd.DataFrame(rows_s3)
        s2 = pd.DataFrame([
            {"Year": 2025, "Quarter": "3Q", "매출액": 832e8, "영업이익": 52.9e8, "당기순이익": 28.8e8, "지배순이익": 28.8e8, "현재주식수": sh, "EPS": 28.8e8 / sh},
            {"Year": 2025, "Quarter": "4Q", "매출액": 855e8, "영업이익": 150.3e8, "당기순이익": 158.6e8, "지배순이익": 158.6e8, "현재주식수": sh, "EPS": 158.6e8 / sh},
            {"Year": 2026, "Quarter": "1Q", "매출액": 768e8, "영업이익": 54.8e8, "당기순이익": 84.5e8, "지배순이익": 84.5e8, "현재주식수": sh, "EPS": 84.5e8 / sh},
            {"Year": 2026, "Quarter": "2Q", "매출액": 809e8, "영업이익": 98.5e8, "당기순이익": 70.4e8, "지배순이익": 70.4e8, "현재주식수": sh, "EPS": 70.4e8 / sh},
            {"Year": 2026, "Quarter": "3Q", "매출액": 734e8, "영업이익": 10.2e8, "당기순이익": 220.2e8, "지배순이익": 220.2e8, "현재주식수": sh, "EPS": 220.2e8 / sh},
        ])
        return {"source": "mock_tax_distorted", "sheet2": s2, "sheet3": s3, "sheet5": s5}

    def test_patch2_and_3_dual_split_and_user_value_trap_switches(self):
        df_w, df_d, s5 = self._make_sample_dfs()
        dart_ts = self._make_dart_ts_tax_distorted(s5)
        bench = {"bps": 24587.0, "eps": 2773.0, "pbr": 2.72, "stock_name": "두산테스나테스트"}
        sec8 = {"primary_metric": "PBR", "pbr_min": 1.01, "per_min": 8.2, "pbr_dir": 58.0, "per_dir": 58.0}
        s12 = self.bv.compute_step1_2_scurve_bottleneck_matrix(
            "131970", "두산테스나", dart_ts, scurve_override=True,
            penetration_pct=18.0, second_penetration_pct=11.0,
            bottleneck_grade="B", bottleneck_months=15, capa_util_pct=57.9,
        )
        bm_kw = {
            "fixed_cost_ratio_pct": 70.0, "var_cost_ratio_pct": 22.9,
            "util_trend": "up", "var_cost_trend": "flat", "op_slope": "accel",
            "slope_evidence": "medium", "capa_expand": True, "asp_up": True,
        }

        # MODE 1 (Default: value_trap_override=None) -> Tax distortion caught & A/B FULLY SPLIT!
        # Model B stays conservative Value Trap; Model A shows 5Y Cycle Normalized + Step 1.3/1.2!
        s2_dual = self.bv.compute_section2_value_trap(
            "131970", bench, df_w, dart_ts, 66800,
            sector_type="A", fixed_cost_ratio=70.0, capa_expand=True, util_trend="up", capa_util_pct=57.9,
            value_trap_override=None,
        )
        self.assertTrue(s2_dual["roe_non_op_distortion"])
        self.assertLess(s2_dual["core_nopat_roe"], 8.5)
        self.assertTrue(s2_dual["is_type_b_raw"])
        self.assertTrue(s2_dual["is_dual_split"])
        self.assertEqual(s2_dual["value_trap_mode"], "dual_split_review")
        self.assertTrue(s2_dual["is_type_a2_candidate"])
        self.assertLess(s2_dual["pbr_5y_p90"], s2_dual["pbr_3y_p90"])  # 5Y window filters 2026 short-term bubble spike

        s3_dual = self.bv.compute_section3_stock_nature_and_tp1(
            "131970", "두산테스나", bench, df_w, df_d, s2_dual, 66800,
            sector_type="A", scurve_override=True, step1_2_res=s12, sec8_res=sec8,
            distb_shares=19245628, ev_implied_g=19.0, dart_ts=dart_ts, bm_slope_params=bm_kw,
        )
        self.assertEqual(s3_dual["valuation_regime_mode"], "dual_split_review")
        self.assertIn("가치함정", s3_dual["bull_mult_label"])
        self.assertIn("비함정 정상화", s3_dual["bull_mult_label"])
        # Model A is cleanly separated above Model B (Value Trap anchor)
        self.assertGreater(s3_dual["base_auto_a"], s3_dual["base_auto"] * 1.3)
        self.assertGreater(s3_dual["bull_auto_a"], s3_dual["bull_auto"] * 1.3)
        # Step 1.3 DART divergence guard (-89.6% QoQ) & sheet3 OPM 2nd derivative both active on Model A!
        self.assertTrue(s3_dual["step1_3_bm_slope"]["dart_divergence_warn"])
        self.assertIsNotNone(s3_dual["step1_3_bm_slope"]["opm_accel_pctp"])
        self.assertAlmostEqual(s3_dual["sc_base_mult"], round(1.0 + (s12["total_sc_bn_base_mult"] - 1.0) * 0.5, 4), places=4)
        # SOP stays defensively guarded pending user decision
        s4_dual = self.bv.compute_section4_master_sop_indicators(df_d, df_w, s2_dual, s3_dual, anchor_price=66800)
        self.assertTrue(s4_dual["is_value_trap_hold"])
        self.assertIn("--no-value-trap", s4_dual["sop_mode_desc"])

        # MODE 2 (User confirms --value-trap -> value_trap_override=True): BOTH B & A locked to Type B!
        s2_vt = self.bv.compute_section2_value_trap(
            "999999", bench, df_w, dart_ts, 66800,
            sector_type="D", fixed_cost_ratio=15.0, capa_expand=False, util_trend="flat", capa_util_pct=60.0,
            value_trap_override=True,
        )
        self.assertEqual(s2_vt["value_trap_mode"], "confirmed_type_b")
        self.assertFalse(s2_vt["is_dual_split"])
        self.assertTrue(s2_vt["is_type_b"])
        s3_vt = self.bv.compute_section3_stock_nature_and_tp1(
            "999999", "가치함정확정", bench, df_w, df_d, s2_vt, 66800,
            sector_type="D", scurve_override=True, step1_2_res=s12, sec8_res=sec8,
            distb_shares=19245628, dart_ts=dart_ts, bm_slope_params=bm_kw,
        )
        self.assertEqual(s3_vt["valuation_regime_mode"], "type_b_value_trap")
        self.assertIn("유형 B 확정", s3_vt["bull_mult_label"])
        self.assertNotIn("상위 90%", s3_vt["bull_mult_label"])
        self.assertEqual(s3_vt["base_auto_a"], s3_vt["base_auto"])
        self.assertEqual(s3_vt["bull_auto_a"], s3_vt["bull_auto"])

        # MODE 3 (User confirms --no-value-trap -> value_trap_override=False): BOTH B & A + SOP unlock to 5Y Cycle!
        s2_nt = self.bv.compute_section2_value_trap(
            "131970", bench, df_w, dart_ts, 66800,
            sector_type="A", fixed_cost_ratio=70.0, capa_expand=True, util_trend="up", capa_util_pct=57.9,
            value_trap_override=False,
        )
        self.assertEqual(s2_nt["value_trap_mode"], "confirmed_non_trap")
        self.assertFalse(s2_nt["is_dual_split"])
        self.assertFalse(s2_nt["is_type_b"])
        self.assertTrue(s2_nt["is_type_a2_capex_trough"])
        s3_nt = self.bv.compute_section3_stock_nature_and_tp1(
            "131970", "두산테스나", bench, df_w, df_d, s2_nt, 66800,
            sector_type="A", scurve_override=True, step1_2_res=s12, sec8_res=sec8,
            distb_shares=19245628, ev_implied_g=19.0, dart_ts=dart_ts, bm_slope_params=bm_kw,
        )
        self.assertEqual(s3_nt["valuation_regime_mode"], "type_a2_capex_trough")
        self.assertIn("유형 A-2 비함정 확정", s3_nt["bull_mult_label"])
        self.assertGreater(s3_nt["base_auto"], s3_vt["base_auto"])
        self.assertGreater(s3_nt["bull_auto"], s3_vt["bull_auto"])
        # Model A matches Dual-Split Model A cleanly!
        self.assertEqual(s3_nt["base_auto_a"], s3_dual["base_auto_a"])
        self.assertEqual(s3_nt["bull_auto_a"], s3_dual["bull_auto_a"])
        # SOP unlocked to realistic pullback/Track 1 ladder, while Track 2 stays blocked during -89.6% QoQ trough
        s4_nt = self.bv.compute_section4_master_sop_indicators(df_d, df_w, s2_nt, s3_nt, anchor_price=66800)
        self.assertFalse(s4_nt["is_value_trap_hold"])
        self.assertFalse(s4_nt["is_track2"])
        self.assertGreater(s4_nt["buy1"], s4_dual["buy1"])
        self.assertGreater(s4_nt["avg_buy_price"], s4_dual["avg_buy_price"])
        self.assertGreater(s4_nt["buy3"], s4_dual["buy3"])
        self.assertLess(s4_nt["init_stop_pin"], s4_nt["buy1"])

    def test_orchestrator_inherits_and_clears_value_trap_override(self):
        import types
        from unittest import mock
        import ksa_orchestrator as ko

        with tempfile.TemporaryDirectory() as td:
            comp = os.path.join(td, "함정스위치테스트")
            db = os.path.join(comp, "2_Translated_DB")
            os.makedirs(db)
            ssot_path = os.path.join(db, "valuation_metrics.json")
            with open(ssot_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "stock_code": "131970",
                        "anchor_price": 66800,
                        "input_params": {"value_trap_override": False},
                        "section2": {"value_trap_override": False, "value_trap_mode": "confirmed_non_trap"},
                    },
                    f,
                    ensure_ascii=False,
                )

            def _base_args(**over):
                d = dict(
                    corp_name="함정스위치테스트", code=None, years=10, sector_type=None, rerating_date=None,
                    base_target=None, bull_target=None, dart_exposure=None, forward_eps=None, forward_eps_g=None,
                    expected_dps=None, non_op_assets=None, net_debt=None, distb_shares=0, total_shares=0,
                    fcf=None, norm_fcf=None, s_curve_phase2=False, early_ignition=False, no_s_curve=False,
                    penetration_pct=None, second_penetration_pct=None, bottleneck_grade=None, bottleneck_months=None,
                    capa_util_pct=None, payout_ratio=None, tsr_pct=None, buyback_cliff=False,
                    mezzanine_eok=None, mezzanine_pct=None, related_party_eok=None, listed_parent_sales=False,
                    governance_discount=None, gov_note=None, anchor_price=None,
                    shortage_easing=False, slope_decel=False, policy_headwind=False, clear_sell_signals=False,
                    bm_core_driver=None, fixed_cost_ratio=None, var_cost_ratio=None, util_trend=None,
                    var_cost_trend=None, op_slope=None, slope_evidence=None, capa_expand=False, asp_up=False,
                    clear_bm_slope=False, value_trap=False, no_value_trap=False, clear_value_trap=False,
                    wacc=0.09, terminal=0.02, skip_pdf=True, pdf_dirs=None, include_raw_pdfs=False,
                    primary_keywords=None, keywords=None, max_pages=18,
                )
                d.update(over)
                return types.SimpleNamespace(**d)

            captured = {}
            def _fake_bt(*a, **kw):
                captured.clear()
                captured.update(kw)

            with mock.patch.object(ko, "ensure_company_structure", return_value=comp), \
                 mock.patch.object(ko, "run_valuation_backtest", side_effect=_fake_bt), \
                 mock.patch.object(ko, "append_extended_ssot_tables"), \
                 mock.patch.object(ko, "refresh_price_eq_in_ssot"), \
                 mock.patch.object(ko, "build_ai_prep_digest", return_value=""):
                # 1) Inherit saved value_trap_override=False when omitted
                ko.cmd_prep(_base_args())
                self.assertIs(captured["value_trap_override"], False)
                # 2) Explicit --value-trap overrides to True
                ko.cmd_prep(_base_args(value_trap=True))
                self.assertIs(captured["value_trap_override"], True)
                # 3) --clear-value-trap resets to None (Dual-Split review mode)
                ko.cmd_prep(_base_args(clear_value_trap=True))
                self.assertIsNone(captured["value_trap_override"])

    def test_patch4_red_team_implied_op_never_inverts_under_trough_per(self):
        df_w, df_d, s5 = self._make_sample_dfs()
        bench = {"bps": 23439.0, "eps": 1771.0, "pbr": 2.85, "stock_name": "레드팀테스트"}
        sec2 = {
            "is_type_b": False, "is_type_a2_capex_trough": True,
            "curr_bps_used": 23439.0, "curr_eps_used": 1771.0,
            "mid_cycle_eps": 2831.0, "mid_cycle_roe": 12.9, "curr_roe": 7.6,
            "qoq_op_pct": 10.0, "op_yoy_used": 25.0,
            "per_3y_p20": 14.0, "per_3y_mean": 40.7, "per_3y_p65": 20.5, "per_3y_p90": 90.4,
            "pbr_3y_p20": 1.30, "pbr_3y_mean": 2.50, "pbr_3y_p65": 2.53, "pbr_3y_p90": 4.66,
            "pbr_5y_p20": 1.59, "pbr_5y_median": 2.30, "pbr_5y_p65": 2.77, "pbr_5y_p90": 3.84,
        }
        sec8 = {"primary_metric": "PBR", "pbr_min": 1.01, "per_min": 8.2, "pbr_dir": 58.0, "per_dir": 58.0}
        s3 = self.bv.compute_section3_stock_nature_and_tp1(
            "131970", "레드팀테스트", bench, df_w, df_d, sec2, 66800,
            sector_type="A", sec8_res=sec8, distb_shares=19245628,
        )
        # Bull annual implied OP must strictly exceed Base annual implied OP and reflect normalized PER (~20.5x, not 40.7x/90.4x)
        self.assertGreater(s3["implied_op_base_a_eok"], 400.0)
        self.assertGreater(s3["implied_op_bull_a_eok"], s3["implied_op_base_a_eok"])

    def test_v522_orchestrator_banner_digest_and_validator_value_trap_modes(self):
        import copy
        import ksa_orchestrator as ko
        import validate_report as vr

        base_ssot = {
            "version": "5.2",
            "stock_code": "131970",
            "anchor_price": 66800,
            "bench": {"close": 66800, "bps": 23439, "eps": 1771},
            "sotp": {"sotp_triggered": False, "non_op_max_ratio_pct": 8.1, "non_op_assets_eok": 365.2},
            "step1_2_bottleneck": {"bottleneck_grade": "B", "bottleneck_lead_time_months": 15, "capa_util_pct": 57.9, "is_phase2": True},
            "step1_3_bm_slope": {"bm_core_driver": "고정비 테스트", "guardrail_summary": "정상", "op_slope_base_mult": 1.0, "op_slope_bull_mult": 1.0},
            "step1_8_k_return": {"kgov_mult": 1.0, "payout_ratio_pct": 8.4, "tsr_pct": 8.4},
            "reverse_dcf": {"status": "success", "price": 66800, "distb_shares": 19245628, "total_shares": 19327238, "net_debt_eok": 2320.1, "fcf_eok": -643.2, "norm_fcf_eok": 520.0},
            "section2": {
                "value_trap_mode": "dual_split_review",
                "is_type_b": True,
                "is_dual_split": True,
                "value_trap_override": None,
                "roe_non_op_distortion": True,
                "curr_roe": 11.28,
                "core_nopat_roe": 5.17,
                "qoq_summary_str": "매출 +5%",
                "kill_switch_guide": "영업이익 < 80억",
            },
            "section3": {
                "bear_auto": 16410, "base_auto": 30490, "bull_auto": 58650,
                "base_auto_a": 59800, "bull_auto_a": 92000,
                "tp1_price": 58650, "tp1_price_a": 72000,
                "base_mult_a": 1.04, "bull_mult_a": 1.06,
            },
            "section4": {
                "d_close": 66800, "buy1": 16410, "buy2": 21620, "buy3": 26830,
                "avg_buy_price": 21620, "init_stop_pin": 15590, "poc_low": 67620, "poc_high": 77440,
                "is_value_trap_hold": True, "is_track2": False,
            },
            "canonical_html_tag": (
                '<div id="dcf-calculator-root" data-price="66800" data-shares="19245628" data-total-shares="19327238" '
                'data-net-debt="2320.1" data-bear="16410" data-base="30490" data-bull="58650" '
                'data-base-a="59800" data-bull-a="92000" data-tp1="58650" data-tp1-a="72000" '
                'data-buy1="16410" data-buy2="21620" data-buy3="26830" data-stop-pin="15590" data-poc-low="67620"></div>'
            ),
            "data_quality": {"status": "ok", "warnings": []},
        }

        # 1) Comparison table includes Dual-Split guidance banner
        cmp_dual = ko.format_ssot_comparison_table({}, base_ssot, "분리테스트")
        self.assertIn("가치함정 판정 안내", cmp_dual)
        self.assertIn("--no-value-trap", cmp_dual)

        # 2) Validator passes clean dual_split_review and catches broken confirmed_non_trap mismatch
        res_ok = vr.Result("dual_ok")
        vr.check_ssot(base_ssot, res_ok)
        self.assertEqual(res_ok.errors, [])

        bad_nt = copy.deepcopy(base_ssot)
        bad_nt["section2"]["value_trap_mode"] = "confirmed_non_trap"
        bad_nt["section2"]["is_type_b"] = False
        bad_nt["section2"]["is_dual_split"] = False
        # Intentionally leave is_value_trap_hold=True to verify validator catches inconsistency
        res_bad = vr.Result("nt_mismatch")
        vr.check_ssot(bad_nt, res_bad)
        self.assertTrue(any("confirmed_non_trap" in e for e in res_bad.errors))

        # 3) append_extended_ssot_tables + build_ai_prep_digest reflect dual_split & confirmed_non_trap cleanly
        with tempfile.TemporaryDirectory() as td:
            db = os.path.join(td, "2_Translated_DB")
            os.makedirs(db)
            ssot_p = os.path.join(db, "valuation_metrics.json")
            auto_p = os.path.join(db, "auto_tables.md")
            with open(ssot_p, "w", encoding="utf-8") as f:
                json.dump(base_ssot, f, ensure_ascii=False)
            with open(auto_p, "w", encoding="utf-8") as f:
                f.write("### 📌 [코드 자동 생성 1]\n| a | b |\n")
            ko.append_extended_ssot_tables(ssot_p)
            auto_txt = open(auto_p, encoding="utf-8").read()
            self.assertIn("A/B 분리 판독 — 확정 전 보류", auto_txt)
            digest_p = ko.build_ai_prep_digest(td, "분리테스트")
            digest_txt = open(digest_p, encoding="utf-8").read()
            self.assertIn("일회성 ROE 착시 보정 활성", digest_txt)
            self.assertIn("가치함정 A/B 분리 판독 모드", digest_txt)

    def test_v523_kr_dol_continuous_scale_and_consensus_absorption(self):
        import pandas as pd
        import validate_report as vr

        s3 = pd.DataFrame({
            "매출액": [1000, 1020, 1040, 1060, 1100, 1150, 1200, 1250, 1300, 1350],
            "영업이익": [100, 103, 106, 110, 118, 128, 138, 148, 158, 168],
        })
        dart_ts = {"sheet3": s3}
        s2_ok = {"op_yoy_used": 15.0, "qoq_op_pct": 5.0, "curr_roe": 13.0, "is_type_b": False}

        def _run_s13(**kw):
            s12 = {"capa_util_pct": kw.pop("util", 80.0), "curr_opm_pct": kw.pop("opm", 12.0)}
            return self.bv.compute_step1_3_bm_op_slope(
                "000000", "KR테스트", dart_ts, sec2_res=s2_ok, step1_2_res=s12, sector_type="A", **kw
            )

        # 1) KR-DOL continuous scaling (dol_ref=2.5, range 0.6~1.4, quant_driver_synthesis only)
        r_d10 = _run_s13(fixed_cost_ratio_pct=0.0, var_cost_ratio_pct=88.0, util_trend="up")
        r_d25 = _run_s13(fixed_cost_ratio_pct=18.0, var_cost_ratio_pct=70.0, util_trend="up")
        r_d60 = _run_s13(fixed_cost_ratio_pct=60.0, var_cost_ratio_pct=28.0, util_trend="up")
        r_d60_dn = _run_s13(fixed_cost_ratio_pct=60.0, var_cost_ratio_pct=28.0, util_trend="down")
        r_bke_up = _run_s13(fixed_cost_ratio_pct=40.0, var_cost_ratio_pct=57.0, util_trend="up", opm=3.0)
        r_bke_dn = _run_s13(fixed_cost_ratio_pct=40.0, var_cost_ratio_pct=57.0, util_trend="down", opm=3.0)
        r_exp = _run_s13(fixed_cost_ratio_pct=60.0, var_cost_ratio_pct=28.0, op_slope="accel")
        self.assertAlmostEqual(r_d10["dol_scale"], 0.60, places=3)
        self.assertAlmostEqual(r_d10["op_slope_base_mult"], 1.0360, places=4)
        self.assertAlmostEqual(r_d25["dol_scale"], 1.00, places=3)
        self.assertAlmostEqual(r_d25["op_slope_base_mult"], 1.0600, places=4)
        self.assertAlmostEqual(r_d60["dol_scale"], 1.40, places=3)
        self.assertAlmostEqual(r_d60["op_slope_base_mult"], 1.0840, places=4)
        self.assertAlmostEqual(r_d60_dn["op_slope_base_mult"], 0.9160, places=4)
        # Asymmetric breakeven guard (OPM < 5%): upside unamplified, downside amplified
        self.assertAlmostEqual(r_bke_up["dol_scale"], 1.00, places=3)
        self.assertAlmostEqual(r_bke_dn["dol_scale"], 1.40, places=3)
        self.assertAlmostEqual(r_exp["dol_scale"], 1.00, places=3)

        # 2) KR-Consensus upside-only absorption (5% / 15%) & Model B invariance
        df_w, df_d, _ = self._make_sample_dfs()
        bench = {"stock_name": "KR테스트", "eps": 1000.0, "bps": 10000.0, "per": 12.0, "pbr": 1.2}
        sec2 = {
            "is_type_b": False, "is_dual_split": False, "is_type_a2_capex_trough": False,
            "curr_roe": 12.0, "op_yoy_used": 18.0, "qoq_op_pct": 5.0,
            "per_3y_p20": 8.0, "per_3y_p65": 12.0, "per_3y_p90": 16.0, "per_3y_mean": 11.5,
            "pbr_3y_p20": 0.9, "pbr_3y_p65": 1.3, "pbr_3y_p90": 1.8, "pbr_3y_mean": 1.25,
            "pbr_5y_p20": 0.9, "pbr_5y_median": 1.2, "pbr_5y_p65": 1.3, "pbr_5y_p90": 1.8,
            "per_10y_min": 7.5, "pbr_10y_min": 0.85,
        }
        tech_a = {"w_swing_grade": "A", "w_swing_score": 80, "w_mfi14": 55.0, "w_mfi14_12w_max": 60.0}
        tech_c = {"w_swing_grade": "C", "w_swing_score": 35, "w_mfi14": 35.0, "w_mfi14_12w_max": 50.0}
        s12_n = {"capa_util_pct": 75.0, "curr_opm_pct": 12.0, "total_sc_bn_base_mult": 1.0, "total_sc_bn_bull_mult": 1.0, "scurve_sell_triggered": False}
        bm_up = {"fixed_cost_ratio_pct": 60.0, "var_cost_ratio_pct": 28.0, "util_trend": "up"}
        bm_dn = {"fixed_cost_ratio_pct": 60.0, "var_cost_ratio_pct": 28.0, "util_trend": "down"}

        # Fwd EPS +20% (>=15% -> 100% absorb) with 50:50 PER/PBR blend -> 1.0840 -> 1.0420
        s3_a = self.bv.compute_section3_stock_nature_and_tp1(
            "000000", "KR테스트", bench, df_w, df_d, sec2, 12000.0,
            forward_eps=1200.0, step1_2_res=s12_n,
            sec8_res={"primary_metric": "PER", "per_dir": 60.0, "pbr_dir": 60.0},
            tech_snap=tech_a, dart_ts=dart_ts, bm_slope_params=bm_up,
        )
        self.assertAlmostEqual(s3_a["step1_3_bm_slope"]["op_slope_base_mult_pre_absorb"], 1.0840, places=4)
        self.assertAlmostEqual(s3_a["step1_3_bm_slope"]["op_slope_base_mult"], 1.0420, places=4)
        self.assertEqual(s3_a["step1_3_bm_slope"]["consensus_absorb_ratio"], 1.0)

        # Downside decel never absorbed, and Model B strictly invariant
        s3_dn = self.bv.compute_section3_stock_nature_and_tp1(
            "000000", "KR테스트", bench, df_w, df_d, sec2, 12000.0,
            forward_eps=1300.0, step1_2_res=s12_n,
            sec8_res={"primary_metric": "PER", "per_dir": 60.0, "pbr_dir": 40.0},
            tech_snap=tech_a, dart_ts=dart_ts, bm_slope_params=bm_dn,
        )
        self.assertAlmostEqual(s3_dn["step1_3_bm_slope"]["op_slope_base_mult"], 0.9160, places=4)
        self.assertEqual(s3_dn["step1_3_bm_slope"]["consensus_absorb_ratio"], 0.0)

        s3_up_same = self.bv.compute_section3_stock_nature_and_tp1(
            "000000", "KR테스트", bench, df_w, df_d, sec2, 12000.0,
            forward_eps=1300.0, step1_2_res=s12_n,
            sec8_res={"primary_metric": "PER", "per_dir": 60.0, "pbr_dir": 40.0},
            tech_snap=tech_a, dart_ts=dart_ts, bm_slope_params=bm_up,
        )
        self.assertEqual(s3_dn["base_auto"], s3_up_same["base_auto"])
        self.assertEqual(s3_dn["bull_auto"], s3_up_same["bull_auto"])

        # Weekly Grade-C suspends Fwd EPS -> zero absorption
        s3_c = self.bv.compute_section3_stock_nature_and_tp1(
            "000000", "KR테스트", bench, df_w, df_d, sec2, 12000.0,
            forward_eps=1300.0, step1_2_res=s12_n,
            sec8_res={"primary_metric": "PER", "per_dir": 60.0, "pbr_dir": 40.0},
            tech_snap=tech_c, dart_ts=dart_ts, bm_slope_params=bm_up,
        )
        self.assertTrue(s3_c["forward_eps_suspended"])
        self.assertAlmostEqual(s3_c["step1_3_bm_slope"]["op_slope_base_mult"], 1.0840, places=4)

        # Validator rejects out-of-bounds dol_scale
        res_bad = vr.Result("dol_oob")
        vr.check_ssot({
            "stock_code": "000000",
            "anchor_price": 12000,
            "bench": {"close": 12000},
            "sotp": {"sotp_triggered": False, "non_op_max_ratio_pct": 5.0},
            "step1_2_bottleneck": {"bottleneck_grade": "B", "bottleneck_lead_time_months": 15, "is_phase2": False},
            "step1_3_bm_slope": {"op_slope_base_mult": 1.0, "op_slope_bull_mult": 1.0, "dol_scale": 1.8},
            "step1_8_k_return": {"kgov_mult": 1.0},
            "section2": {"value_trap_mode": "normal_type_a"},
            "section3": {"bear_auto": 9000, "base_auto": 12000, "bull_auto": 15000, "base_auto_a": 12000, "bull_auto_a": 15000, "tp1_price": 12000, "tp1_price_a": 12000},
            "section4": {"d_close": 12000, "buy1": 10000, "buy2": 10500, "buy3": 11000, "avg_buy_price": 10500, "init_stop_pin": 9000, "poc_low": 10800},
            "canonical_html_tag": (
                '<div id="dcf-calculator-root" data-price="12000" data-bear="9000" data-base="12000" data-bull="15000" '
                'data-base-a="12000" data-bull-a="15000" data-tp1="12000" data-tp1-a="12000" '
                'data-buy1="10000" data-buy2="10500" data-buy3="11000" data-stop-pin="9000" data-poc-low="10800"></div>'
            ),
        }, res_bad)
        self.assertTrue(any("dol_scale" in e for e in res_bad.errors), res_bad.errors)


if __name__ == "__main__":
    unittest.main()
