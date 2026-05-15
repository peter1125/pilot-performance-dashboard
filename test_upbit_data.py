import json
import tempfile
import unittest
from pathlib import Path

from sync_upbit_data import build_upbit_payload, parse_execution_report


class UpbitDataTests(unittest.TestCase):
    def test_parse_execution_report_keeps_live_runs_and_flattens_allocations(self):
        report = {
            "timestamp_kst": "2026-05-08T05:51:18+09:00",
            "mode": "live",
            "regime_note": "caution; 24h breadth 57%",
            "target_weights": {"JTO": 0.6, "FLOCK": 0.25, "CFG": 0.15},
            "target_reason": "three strong breakouts -> 60% / 25% / 15%",
            "observed_nav_before_krw": 987496,
            "observed_nav_after_krw": 985324,
            "weights_before": {"ONDO": 0.797, "Cash": 0.203},
            "weights_after": {"JTO": 0.6, "FLOCK": 0.251, "CFG": 0.149},
            "planned_sells": [{"side": "SELL", "symbol": "ONDO", "notional_krw_est": 787236}],
            "planned_buys": [{"side": "BUY", "symbol": "JTO", "price_krw": 592498}],
            "executions": [
                {"request": {"side": "SELL", "symbol": "ONDO", "notional_krw_est": 787236}, "response": {"uuid": "sell-1", "state": "done"}},
                {"request": {"side": "BUY", "symbol": "JTO"}, "submitted_price_krw": 592497, "response": {"uuid": "buy-1", "state": "done", "reserved_fee": "296.2485"}},
            ],
            "ranked_candidates": [{"symbol": "JTO", "r24_pct": 45.2, "r7_pct": 75.1, "score_pct": 60.2}],
            "warnings": ["universe guardrails rejected 120 KRW markets"],
        }

        parsed = parse_execution_report(report, "sample.json")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["time"], "2026-05-08T05:51:18+09:00")
        self.assertEqual(parsed["navAfter"], 985324)
        self.assertEqual(parsed["allocationText"], "JTO 60.0%, FLOCK 25.1%, CFG 14.9%")
        self.assertEqual(len(parsed["executions"]), 2)
        self.assertEqual(parsed["executions"][1]["notionalKrw"], 592497)
        self.assertEqual(parsed["executions"][1]["feeKrw"], 296.2485)
        self.assertAlmostEqual(parsed["feesKrw"], 689.8665, places=4)
        self.assertAlmostEqual(parsed["cumulativeFeesKrw"], 689.8665, places=4)

    def test_parse_execution_report_treats_cancel_with_filled_volume_as_filled(self):
        report = {
            "timestamp_kst": "2026-05-08T21:41:58+09:00",
            "mode": "live",
            "observed_nav_before_krw": 873556,
            "observed_nav_after_krw": 876081,
            "weights_after": {"AZTEC": 0.15},
            "target_weights": {"AZTEC": 0.15},
            "executions": [{
                "request": {"side": "BUY", "symbol": "AZTEC"},
                "submitted_price_krw": 131033,
                "response": {"uuid": "u", "state": "wait"},
                "final_response": {"uuid": "u", "state": "cancel", "executed_volume": "3560.679", "paid_fee": "65.5"},
                "status": "cancelled",
            }],
            "warnings": [],
            "ranked_candidates": [],
        }

        parsed = parse_execution_report(report, "sample.json")

        self.assertEqual(parsed["executions"][0]["state"], "filled")
        self.assertEqual(parsed["executions"][0]["executionStatus"], "filled")

    def test_parse_execution_report_includes_risk_freeze_with_observed_nav(self):
        report = {
            "timestamp_kst": "2026-05-09T19:02:57+09:00",
            "mode": "risk_freeze",
            "status": "risk_freeze",
            "reason": "daily loss -9.02% breached max 8.00%",
            "observed_nav_before_krw": 801555,
            "observed_nav_after_krw": 801555,
            "weights_after": {"SAHARA": 0.6, "Cash": 0.25, "ICP": 0.15},
            "target_weights": {"SAHARA": 0.6, "AKT": 0.25, "ICP": 0.15},
            "executions": [],
            "warnings": ["daily loss -9.02% breached max 8.00%", "risk-freeze sells rejected AKT: spread too wide"],
            "safety": {"orders_submitted": False},
            "risk_freeze_reason": "daily loss -9.02% breached max 8.00%",
            "freeze_mode": "cash",
            "freeze_mode_reason": "no guarded sells available",
            "methodology": {"strategy_mode": "paper_aligned", "live_extension_enabled": False},
            "ranked_candidates": [],
        }

        parsed = parse_execution_report(report, "freeze.json")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["status"], "risk_freeze")
        self.assertEqual(parsed["reason"], "daily loss -9.02% breached max 8.00%")
        self.assertEqual(parsed["navAfter"], 801555)
        self.assertEqual(parsed["tradeCount"], 0)
        self.assertEqual(parsed["strategyMode"], "paper-aligned")
        self.assertFalse(parsed["liveExtensionEnabled"])
        self.assertEqual(parsed["freezeMode"], "cash")
        self.assertEqual(parsed["freezeModeReason"], "no guarded sells available")
        self.assertEqual(parsed["riskFreezeReason"], "daily loss -9.02% breached max 8.00%")
        self.assertFalse(parsed["ordersSubmitted"])
        self.assertEqual(parsed["warningCount"], 2)
        self.assertEqual(parsed["rejectionWarningCount"], 1)

    def test_build_payload_uses_newer_risk_freeze_nav_as_current_live_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            live = {
                "timestamp_kst": "2026-05-09T18:34:59+09:00",
                "mode": "live",
                "observed_nav_before_krw": 804938,
                "observed_nav_after_krw": 803457,
                "weights_after": {"SAHARA": 0.601, "Cash": 0.249, "ICP": 0.150},
                "target_weights": {"SAHARA": 0.6, "AKT": 0.25, "ICP": 0.15},
                "executions": [],
                "warnings": [],
                "ranked_candidates": [],
            }
            freeze = {
                "timestamp_kst": "2026-05-09T19:02:57+09:00",
                "mode": "risk_freeze",
                "status": "risk_freeze",
                "reason": "daily loss -9.02% breached max 8.00%",
                "observed_nav_before_krw": 801555,
                "observed_nav_after_krw": 801555,
                "weights_after": {"SAHARA": 0.6, "Cash": 0.25, "ICP": 0.15},
                "target_weights": {"SAHARA": 0.6, "AKT": 0.25, "ICP": 0.15},
                "executions": [],
                "warnings": ["daily loss -9.02% breached max 8.00%"],
                "ranked_candidates": [],
            }
            (root / "a.json").write_text(json.dumps(live))
            (root / "b.json").write_text(json.dumps(freeze))

            payload = build_upbit_payload(root)

        self.assertEqual(payload["summary"]["currentNav"], 801555)
        self.assertEqual(payload["summary"]["latestTime"], "2026-05-09T19:02:57+09:00")
        self.assertEqual(payload["summary"]["latestStatus"], "risk_freeze")
        self.assertEqual(payload["summary"]["latestReason"], "daily loss -9.02% breached max 8.00%")
        self.assertEqual(payload["summary"]["strategyMode"], "paper-aligned")
        self.assertFalse(payload["summary"]["liveExtensionEnabled"])
        self.assertEqual(payload["summary"]["freezeMode"], "holding")
        self.assertIsNone(payload["summary"]["ordersSubmitted"])
        self.assertEqual(payload["summary"]["warningCount"], 1)
        self.assertEqual(payload["summary"]["rejectionWarningCount"], 0)
        self.assertEqual([p["navAfter"] for p in payload["equitySeries"]], [803457, 801555])

    def test_parse_execution_report_ignores_dry_run_even_with_observed_nav(self):
        report = {
            "timestamp_kst": "2026-05-07T01:04:45+09:00",
            "mode": "dry_run",
            "observed_nav_before_krw": 1000247,
            "observed_nav_after_krw": 1000247,
            "weights_after": {"ONDO": 0.6},
            "target_weights": {"ONDO": 0.6},
            "executions": [],
        }

        self.assertIsNone(parse_execution_report(report, "dry.json"))

    def test_build_payload_sorts_reports_and_computes_summary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            older = {
                "timestamp_kst": "2026-05-08T05:00:00+09:00",
                "mode": "live",
                "observed_nav_before_krw": 1000000,
                "observed_nav_after_krw": 1010000,
                "weights_after": {"ONDO": 0.8, "Cash": 0.2},
                "target_weights": {"ONDO": 0.8, "Cash": 0.2},
                "executions": [],
                "warnings": [],
                "ranked_candidates": [],
            }
            newer = {
                "timestamp_kst": "2026-05-08T05:30:00+09:00",
                "mode": "live",
                "observed_nav_before_krw": 1010000,
                "observed_nav_after_krw": 1030000,
                "weights_after": {"JTO": 0.6, "FLOCK": 0.25, "CFG": 0.15},
                "target_weights": {"JTO": 0.6, "FLOCK": 0.25, "CFG": 0.15},
                "executions": [{"request": {"side": "BUY", "symbol": "JTO"}, "submitted_price_krw": 600000, "response": {"uuid": "u", "reserved_fee": "300"}}],
                "warnings": [],
                "ranked_candidates": [],
            }
            (root / "b.json").write_text(json.dumps(newer))
            (root / "a.json").write_text(json.dumps(older))

            payload = build_upbit_payload(root)

        self.assertEqual(payload["summary"]["currentNav"], 1030000)
        self.assertEqual(payload["summary"]["startingNav"], 1000000)
        self.assertAlmostEqual(payload["summary"]["totalReturnPct"], 3.0)
        self.assertEqual(payload["summary"]["cumulativeFeesKrw"], 300)
        self.assertEqual([p["navAfter"] for p in payload["equitySeries"]], [1010000, 1030000])
        self.assertEqual([p["cumulativeFeesKrw"] for p in payload["equitySeries"]], [0, 300])
        self.assertEqual(payload["transactions"][0]["cumulativeFeesKrw"], 300)
        self.assertEqual(payload["summary"]["currentAllocation"], "JTO 60.0%, FLOCK 25.0%, CFG 15.0%")
        self.assertIn("BTC, ETH, SOL, XRP, SUI, LINK, DOGE, AVAX, AAVE, ONDO, PEPE", payload["guardrails"]["universe"])

    def test_build_payload_surfaces_full_universe_mode_and_latest_safety_counts(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = {
                "timestamp_kst": "2026-05-08T05:00:00+09:00",
                "mode": "live",
                "status": "live",
                "observed_nav_before_krw": 1000000,
                "observed_nav_after_krw": 1005000,
                "weights_after": {"ONDO": 0.8, "Cash": 0.2},
                "target_weights": {"ONDO": 0.8, "Cash": 0.2},
                "executions": [],
                "warnings": ["eligibility rejected XYZ: low volume", "guardrail warning"],
                "safety": {"orders_submitted": True},
                "methodology": {
                    "strategyMode": "full_universe",
                    "liveExtensionEnabled": True,
                    "order_controls": {"buys": {"liquidity_rejected": [{"symbol": "XYZ"}]}, "sells": {"liquidity_rejected": []}},
                },
                "ranked_candidates": [],
            }
            (root / "a.json").write_text(json.dumps(report))

            payload = build_upbit_payload(root)

        self.assertEqual(payload["summary"]["strategyMode"], "full-universe")
        self.assertTrue(payload["summary"]["liveExtensionEnabled"])
        self.assertTrue(payload["summary"]["latestOrdersSubmitted"])
        self.assertEqual(payload["summary"]["freezeMode"], "normal")
        self.assertEqual(payload["summary"]["warningCount"], 2)
        self.assertEqual(payload["summary"]["eligibilityWarningCount"], 1)
        self.assertEqual(payload["summary"]["rejectionWarningCount"], 2)
    def test_build_payload_includes_daily_summary_and_governance_when_present(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = {
                "timestamp_kst": "2026-05-08T05:00:00+09:00",
                "mode": "live",
                "observed_nav_before_krw": 1000000,
                "observed_nav_after_krw": 1010000,
                "weights_after": {"ONDO": 0.8, "Cash": 0.2},
                "target_weights": {"ONDO": 0.8, "Cash": 0.2},
                "executions": [],
                "warnings": [],
                "ranked_candidates": [],
            }
            (root / "a.json").write_text(json.dumps(report))
            daily_dir = root / "daily"
            gov_dir = root / "governance"
            daily_dir.mkdir()
            gov_dir.mkdir()
            (daily_dir / "latest.json").write_text(json.dumps({"dateKst": "2026-05-08", "pnlKrw": 10000}))
            (gov_dir / "status.json").write_text(json.dumps({"status": "ok", "pendingOrderCount": 0}))

            payload = build_upbit_payload(root)

        self.assertEqual(payload["dailySummary"]["pnlKrw"], 10000)
        self.assertEqual(payload["governance"]["status"], "ok")

    def test_build_payload_includes_phase_assessment_from_current_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = {
                "timestamp_kst": "2026-05-08T05:00:00+09:00",
                "mode": "live",
                "observed_nav_before_krw": 1000000,
                "observed_nav_after_krw": 1010000,
                "weights_after": {"ONDO": 0.8, "Cash": 0.2},
                "target_weights": {"ONDO": 0.8, "Cash": 0.2},
                "executions": [],
                "warnings": [],
                "ranked_candidates": [],
            }
            (root / "a.json").write_text(json.dumps(report))
            (root / "live_state.json").write_text(json.dumps({
                "last_run_status": "frozen_trading_disabled",
                "pending_orders": [],
                "last_warnings": ["PILOT3_TRADING_ENABLED is not explicitly true; no order calls made"],
            }))
            daily_dir = root / "daily"
            gov_dir = root / "governance"
            daily_dir.mkdir()
            gov_dir.mkdir()
            (daily_dir / "latest.json").write_text(json.dumps({"targetChanges": 2, "legacyUnresolvedOrderCount": 3}))
            (gov_dir / "status.json").write_text(json.dumps({"status": "ok", "pendingOrderCount": 0}))

            payload = build_upbit_payload(root)

        phases = payload["phaseAssessment"]
        self.assertEqual(phases["phase1"]["status"], "complete_active")
        self.assertEqual(phases["phase2"]["status"], "planned_flag_off")
        self.assertEqual(phases["phase3"]["status"], "complete_active")
        self.assertIn("frozen_trading_disabled", " ".join(phases["phase1"]["evidence"]))
        self.assertEqual(payload["summary"]["phase1Status"], "complete_active")

    def test_phase_assessment_marks_phase1_and_phase2_complete_from_verified_state_after_skip(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            report = {
                "timestamp_kst": "2026-05-08T05:00:00+09:00",
                "mode": "live",
                "observed_nav_before_krw": 1000000,
                "observed_nav_after_krw": 1010000,
                "weights_after": {"ONDO": 0.8, "Cash": 0.2},
                "target_weights": {"ONDO": 0.8, "Cash": 0.2},
                "executions": [],
                "warnings": [],
                "ranked_candidates": [],
                "methodology": {"phase2_enabled": True},
            }
            (root / "a.json").write_text(json.dumps(report))
            (root / "live_state.json").write_text(json.dumps({
                "last_run_status": "skipped_recent_run",
                "pending_orders": [],
                "trading_enabled": True,
                "last_phase2_enabled": True,
                "last_decision_candle_time_kst": "2026-05-08T04:30:00+09:00",
                "last_price_snapshot_time_kst": "2026-05-08T05:00:00+09:00",
            }))
            daily_dir = root / "daily"
            gov_dir = root / "governance"
            daily_dir.mkdir()
            gov_dir.mkdir()
            (daily_dir / "latest.json").write_text(json.dumps({"targetChanges": 2, "legacyUnresolvedOrderCount": 0}))
            (gov_dir / "status.json").write_text(json.dumps({
                "status": "ok",
                "pendingOrderCount": 0,
                "tradingEnabled": True,
                "phase2Enabled": True,
            }))

            payload = build_upbit_payload(root)

        phases = payload["phaseAssessment"]
        self.assertEqual(phases["phase1"]["status"], "complete_active")
        self.assertEqual(phases["phase2"]["status"], "complete_active")
        self.assertIn("trading gate is enabled", " ".join(phases["phase1"]["evidence"]))
        self.assertIn("phase2Enabled=True", " ".join(phases["phase2"]["evidence"]))


if __name__ == "__main__":
    unittest.main()
