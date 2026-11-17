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


if __name__ == "__main__":
    unittest.main()
