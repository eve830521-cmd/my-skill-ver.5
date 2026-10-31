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


class EngineFunctionsPinned(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import backtest_valuation as bv
        cls.bv = bv

    def test_step1_2_golden_inflection_S_grade(self):
        r = self.bv.compute_step1_2_scurve_bottleneck_matrix(
            "999999", "TEST", {}, penetration_pct=12.0, bottleneck_grade="S", bottleneck_months=30,
            capa_util_pct=92.0)
        self.assertIn("Zone A", r["penetration_zone"])
        self.assertEqual(r["bottleneck_grade"], "S")
        self.assertAlmostEqual(r["pen_base_boost"], 0.12)
        self.assertAlmostEqual(r["pen_bull_boost"], 0.16)
        self.assertAlmostEqual(r["total_sc_bn_base_mult"], 1.20)
        self.assertAlmostEqual(r["total_sc_bn_bull_mult"], 1.26)

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
