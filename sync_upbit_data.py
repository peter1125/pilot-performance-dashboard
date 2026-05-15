#!/usr/bin/env python3
"""Build static data for the Pilot 3 Upbit live execution dashboard."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_DIR = Path.home() / ".hermes" / "pilot3-live-executions"
OUT_PATH = Path(__file__).with_name("upbit-data.json")
FEE_RATE = 0.0005


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_krw(value: Any) -> int:
    return int(round(_num(value)))


def format_allocation(weights: dict[str, Any] | None) -> str:
    if not weights:
        return "None"
    ordered = sorted(((k, _num(v)) for k, v in weights.items() if _num(v) > 0.0001), key=lambda kv: (-kv[1], kv[0]))
    if not ordered:
        return "None"
    return ", ".join(f"{symbol} {weight * 100:.1f}%" for symbol, weight in ordered)


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _get_nested(mapping: dict[str, Any] | None, *path: str) -> Any:
    current: Any = mapping or {}
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _derive_strategy_mode(report: dict[str, Any]) -> str:
    """Return the v2 strategy mode label; default public dashboard to paper-aligned."""
    methodology = report.get("methodology") or {}
    config = report.get("config") or {}
    raw = _first_present(
        report.get("strategy_mode"),
        report.get("strategyMode"),
        methodology.get("strategy_mode"),
        methodology.get("strategyMode"),
        config.get("strategy_mode"),
        config.get("strategyMode"),
    )
    if raw is None:
        return "paper-aligned"
    normalized = str(raw).strip().replace("_", "-").lower()
    return normalized or "paper-aligned"


def _derive_live_extension_enabled(report: dict[str, Any]) -> bool | None:
    methodology = report.get("methodology") or {}
    config = report.get("config") or {}
    value = _first_present(
        report.get("live_extension_enabled"),
        report.get("liveExtensionEnabled"),
        methodology.get("live_extension_enabled"),
        methodology.get("liveExtensionEnabled"),
        config.get("live_extension_enabled"),
        config.get("liveExtensionEnabled"),
    )
    if value is None:
        mode = _derive_strategy_mode(report)
        if mode in {"paper-aligned", "paper", "paper-aligned-default"}:
            return False
        if mode in {"full-universe", "full-upbit", "live-extension", "extended"}:
            return True
        return None
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enabled"}
    return bool(value)


def _latest_warning_counts(report: dict[str, Any]) -> dict[str, int]:
    warnings = [str(w) for w in (report.get("warnings") or [])]
    methodology = report.get("methodology") or {}
    order_controls = methodology.get("order_controls") or {}
    liquidity_rejections = 0
    for side in ("sells", "buys"):
        liquidity_rejections += len(((order_controls.get(side) or {}).get("liquidity_rejected") or []))
    rejection_count = sum(1 for warning in warnings if "reject" in warning.lower()) + liquidity_rejections
    eligibility_count = sum(1 for warning in warnings if "eligib" in warning.lower())
    return {
        "warningCount": len(warnings),
        "rejectionWarningCount": rejection_count,
        "eligibilityWarningCount": eligibility_count,
    }


def _execution_notional(execution: dict[str, Any]) -> int:
    request = execution.get("request") or {}
    side = str(request.get("side") or "").upper()
    if side == "BUY":
        return _round_krw(execution.get("submitted_price_krw") or request.get("price_krw"))
    return _round_krw(request.get("notional_krw_est") or request.get("price_krw"))


def _execution_fee(execution: dict[str, Any]) -> float:
    """Recorded Upbit fee when present; otherwise estimated from notional."""
    final_response = execution.get("final_response") or {}
    response = execution.get("response") or {}
    paid = _num(execution.get("fee_krw_actual") or final_response.get("paid_fee") or response.get("paid_fee"))
    if paid > 0:
        return paid
    reserved = _num(final_response.get("reserved_fee") or response.get("reserved_fee"))
    if reserved > 0:
        return reserved
    return _execution_notional(execution) * FEE_RATE


def parse_execution_report(report: dict[str, Any], source_file: str) -> dict[str, Any] | None:
    mode = report.get("mode")
    observed_nav = report.get("observed_nav_after_krw") is not None
    live_reflective_modes = {"live", "risk_freeze", "pending_orders", "frozen_trading_disabled"}
    if mode not in live_reflective_modes or (mode != "live" and not observed_nav):
        return None
    ts = report.get("timestamp_kst")
    if not ts:
        return None
    nav_before = _round_krw(report.get("observed_nav_before_krw") or report.get("observed_nav_after_krw"))
    nav_after = _round_krw(report.get("observed_nav_after_krw"))
    weights_after = report.get("weights_after") or {}
    weights_before = report.get("weights_before") or {}

    risk_freeze = report.get("risk_freeze") or report.get("riskFreeze") or {}
    safety = report.get("safety") or {}
    warning_counts = _latest_warning_counts(report)
    orders_submitted = safety.get("orders_submitted")

    executions = []
    for execution in report.get("executions") or []:
        request = execution.get("request") or {}
        response = execution.get("response") or {}
        final_response = execution.get("final_response") or {}
        status = execution.get("status") or execution.get("final_state") or final_response.get("state") or response.get("state")
        if _num(execution.get("executed_volume") or final_response.get("executed_volume")) > 0:
            status = "filled"
        side = str(request.get("side") or "").upper() or str(response.get("side") or final_response.get("side") or "").upper()
        symbol = request.get("symbol") or (response.get("market", "-").split("-", 1)[-1] if response.get("market") else "")
        fee_krw = _execution_fee(execution)
        executions.append({
            "time": ts,
            "side": side,
            "symbol": symbol,
            "market": request.get("market") or response.get("market"),
            "notionalKrw": _execution_notional(execution),
            "feeKrw": fee_krw,
            "uuid": response.get("uuid") or final_response.get("uuid"),
            "state": status,
            "finalState": final_response.get("state") or execution.get("final_state"),
            "executionStatus": status,
            "executedVolume": execution.get("executed_volume") or final_response.get("executed_volume"),
            "remainingVolume": execution.get("remaining_volume") or final_response.get("remaining_volume"),
            "actualFeeKrw": execution.get("fee_krw_actual") or final_response.get("paid_fee"),
            "feeSource": "actual" if (execution.get("fee_krw_actual") or _num(final_response.get("paid_fee")) > 0) else "estimated_or_reserved",
        })
    fees_krw = sum(row["feeKrw"] for row in executions)

    ranked = []
    for row in report.get("ranked_candidates") or []:
        ranked.append({
            "symbol": row.get("symbol"),
            "r24Pct": _num(row.get("r24_pct")),
            "r7Pct": _num(row.get("r7_pct")),
            "scorePct": _num(row.get("score_pct")),
        })

    return {
        "time": ts,
        "date": ts[:10],
        "sourceFile": source_file,
        "status": report.get("status") or report.get("mode") or "live",
        "reason": report.get("reason") or report.get("target_reason") or "",
        "regime": report.get("regime"),
        "regimeNote": report.get("regime_note") or "",
        "targetReason": report.get("target_reason") or "",
        "targetWeights": report.get("target_weights") or {},
        "targetText": format_allocation(report.get("target_weights") or {}),
        "weightsBefore": weights_before,
        "weightsAfter": weights_after,
        "allocationText": format_allocation(weights_after),
        "navBefore": nav_before,
        "navAfter": nav_after,
        "pnlKrw": nav_after - nav_before,
        "returnPct": ((nav_after - nav_before) / nav_before * 100) if nav_before else 0,
        "plannedSells": report.get("planned_sells") or [],
        "plannedBuys": report.get("planned_buys") or [],
        "executions": executions,
        "feesKrw": fees_krw,
        "cumulativeFeesKrw": fees_krw,
        "tradeCount": len(executions),
        "rankedCandidates": ranked,
        "warnings": report.get("warnings") or [],
        "warningCount": warning_counts["warningCount"],
        "rejectionWarningCount": warning_counts["rejectionWarningCount"],
        "eligibilityWarningCount": warning_counts["eligibilityWarningCount"],
        "safety": safety,
        "ordersSubmitted": orders_submitted,
        "strategyMode": _derive_strategy_mode(report),
        "liveExtensionEnabled": _derive_live_extension_enabled(report),
        "freezeMode": _first_present(report.get("freeze_mode"), report.get("freezeMode"), risk_freeze.get("freeze_mode"), risk_freeze.get("freezeMode")),
        "freezeModeReason": _first_present(report.get("freeze_mode_reason"), report.get("freezeModeReason"), risk_freeze.get("freeze_mode_reason"), risk_freeze.get("freezeModeReason")),
        "riskFreezeReason": _first_present(report.get("risk_freeze_reason"), report.get("riskFreezeReason"), risk_freeze.get("reason"), risk_freeze.get("risk_freeze_reason"), risk_freeze.get("riskFreezeReason")),
    }


def _load_optional_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def build_phase_assessment(state: dict[str, Any] | None, daily_summary: dict[str, Any] | None, governance: dict[str, Any] | None) -> dict[str, Any]:
    state = state or {}
    daily_summary = daily_summary or {}
    governance = governance or {}
    last_status = state.get("last_run_status") or governance.get("lastRunStatus") or "unknown"
    pending_count = governance.get("pendingOrderCount", len(state.get("pending_orders") or []))
    trading_enabled = state.get("trading_enabled") if state.get("trading_enabled") is not None else governance.get("tradingEnabled")
    trading_disabled = any("TRADING_ENABLED" in str(w) for w in (state.get("last_warnings") or [])) or last_status == "frozen_trading_disabled"
    phase1_gate_verified = trading_enabled is True or trading_disabled
    phase1_status = "complete_active" if pending_count == 0 and phase1_gate_verified and last_status not in {"unknown", "error", "reconciliation_mismatch", "pending_orders"} else "needs_review"
    phase3_status = "complete_active" if daily_summary and governance and governance.get("status") not in {None, "unknown"} else "needs_generation"
    phase2_enabled = bool(state.get("phase2_enabled") or state.get("last_phase2_enabled") or governance.get("phase2Enabled"))
    phase2_status = "complete_active" if phase2_enabled else "planned_flag_off"
    return {
        "phase1": {
            "title": "Phase 1 — Safety hardening",
            "status": phase1_status,
            "summary": "Fail-closed trading gate, pending-order block, duplicate-run guard, order polling/reporting, and risk limit checks are active.",
            "evidence": [
                f"last_run_status={last_status}",
                f"pendingOrderCount={pending_count}",
                "trading gate is enabled for live execution" if trading_enabled is True else ("PILOT3_TRADING_ENABLED gate observed fail-closed" if trading_disabled else "trading gate evidence unavailable"),
            ],
        },
        "phase2": {
            "title": "Phase 2 — Methodology robustness",
            "status": phase2_status,
            "summary": "Closed-candle metadata, hysteresis, rebalance bands, orderbook spread checks, and churn controls are live-enabled." if phase2_enabled else "Closed-candle freshness, hysteresis/hold-period, churn/fee controls, orderbook checks, and walk-forward validation remain planned behind a disabled flag.",
            "evidence": [
                f"phase2Enabled={phase2_enabled}",
                "Phase 2 controls are active in live reports." if phase2_enabled else "No live methodology change is active unless this flag is enabled.",
                f"signalCandle={state.get('last_decision_candle_time_kst', 'unknown')}",
                f"priceSnapshot={state.get('last_price_snapshot_time_kst', 'unknown')}",
            ],
        },
        "phase3": {
            "title": "Phase 3 — Reporting & governance",
            "status": phase3_status,
            "summary": "Daily summary, governance status, dashboard schema, public UI cards, and dashboard publisher are active/reporting-only.",
            "evidence": [
                f"governanceStatus={governance.get('status', 'unknown')}",
                f"targetChangesToday={daily_summary.get('targetChanges', 0)}",
                f"legacyUnresolvedOrderCount={daily_summary.get('legacyUnresolvedOrderCount', 0)}",
            ],
        },
    }


def build_upbit_payload(report_dir: Path = REPORT_DIR) -> dict[str, Any]:
    points = []
    if report_dir.exists():
        for path in sorted(report_dir.glob("*.json")):
            if path.name == "live_latest.json":
                continue
            try:
                report = json.loads(path.read_text())
            except Exception:
                continue
            parsed = parse_execution_report(report, path.name)
            if parsed:
                points.append(parsed)
    points.sort(key=lambda row: row["time"])

    cumulative_fees = 0.0
    for point in points:
        cumulative_fees += _num(point.get("feesKrw"))
        point["cumulativeFeesKrw"] = cumulative_fees
        for execution in point["executions"]:
            execution["cumulativeFeesKrw"] = cumulative_fees

    executions = []
    for point in points:
        executions.extend(point["executions"])

    latest = points[-1] if points else None
    first = points[0] if points else None
    starting_nav = first["navBefore"] if first else 0
    current_nav = latest["navAfter"] if latest else 0
    total_pnl = current_nav - starting_nav
    total_return = (total_pnl / starting_nav * 100) if starting_nav else 0

    latest_freeze_mode = None
    if latest:
        latest_freeze_mode = latest.get("freezeMode")
        if not latest_freeze_mode:
            target_weights = latest.get("targetWeights") or {}
            if latest.get("status") == "risk_freeze":
                latest_freeze_mode = "cash" if _num(target_weights.get("Cash")) >= 0.999 else "holding"
            else:
                latest_freeze_mode = "normal"

    strategy_mode = latest.get("strategyMode") if latest else "paper-aligned"
    live_extension_enabled = latest.get("liveExtensionEnabled") if latest else False
    if live_extension_enabled or strategy_mode == "full-universe":
        strategy_label = "Full Upbit KRW Breakout Rotation"
        universe_label = "Full Upbit KRW spot universe"
    else:
        strategy_label = "Paper-Aligned Pilot 3 Breakout Rotation"
        universe_label = "Paper-aligned Upbit-compatible Pilot 3 universe: BTC, ETH, SOL, XRP, SUI, LINK, DOGE, AVAX, AAVE, ONDO, PEPE"

    summary = {
        "name": "Pilot 3 Upbit Live",
        "strategy": strategy_label,
        "currentNav": current_nav,
        "startingNav": starting_nav,
        "totalPnlKrw": total_pnl,
        "totalReturnPct": total_return,
        "latestTime": latest["time"] if latest else None,
        "latestStatus": latest.get("status") if latest else None,
        "currentAllocation": latest["allocationText"] if latest else "None",
        "targetAllocation": latest["targetText"] if latest else "None",
        "latestRegime": latest["regimeNote"] if latest else "No live reports found",
        "latestReason": (latest.get("reason") or latest.get("targetReason") or "") if latest else "",
        "strategyMode": strategy_mode,
        "liveExtensionEnabled": live_extension_enabled,
        "freezeMode": latest_freeze_mode,
        "freezeModeReason": latest.get("freezeModeReason") if latest else None,
        "riskFreezeReason": latest.get("riskFreezeReason") if latest else None,
        "ordersSubmitted": latest.get("ordersSubmitted") if latest else None,
        "latestOrdersSubmitted": latest.get("ordersSubmitted") if latest else None,
        "warningCount": latest.get("warningCount", 0) if latest else 0,
        "eligibilityWarningCount": latest.get("eligibilityWarningCount", 0) if latest else 0,
        "rejectionWarningCount": latest.get("rejectionWarningCount", 0) if latest else 0,
        "reportCount": len(points),
        "tradeCount": len(executions),
        "cumulativeFeesKrw": cumulative_fees,
        "feeNote": "Fees use recorded paid/reserved Upbit fees when present; otherwise estimated at 0.05% of notional.",
    }

    daily_summary = _load_optional_json(report_dir / "daily" / "latest.json")
    governance = _load_optional_json(report_dir / "governance" / "status.json", {"status": "unknown", "alerts": ["Governance status not generated yet"]})
    live_state = _load_optional_json(report_dir / "live_state.json", {})
    phase_assessment = build_phase_assessment(live_state, daily_summary, governance)
    if daily_summary:
        summary["dailyPnlKrw"] = daily_summary.get("pnlKrw")
        summary["dailyReturnPct"] = daily_summary.get("returnPct")
        summary["feeDragTodayKrw"] = (daily_summary.get("actualFeesKrw") or 0) + (daily_summary.get("estimatedFeesKrw") or 0)
    if governance:
        summary["pendingOrderCount"] = governance.get("pendingOrderCount", 0)
        summary["governanceStatus"] = governance.get("status", "unknown")
        if not summary.get("riskFreezeReason"):
            summary["riskFreezeReason"] = governance.get("riskFreezeReason")
        if governance.get("riskFreezeActive") and not summary.get("freezeMode"):
            summary["freezeMode"] = "holding"
    summary["phase1Status"] = phase_assessment["phase1"]["status"]
    summary["phase2Status"] = phase_assessment["phase2"]["status"]
    summary["phase3Status"] = phase_assessment["phase3"]["status"]

    return {
        "source": "local-upbit-live-execution-reports",
        "refreshedAt": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "equitySeries": points,
        "transactions": executions,
        "latest": latest,
        "dailySummary": daily_summary,
        "governance": governance,
        "phaseAssessment": phase_assessment,
        "guardrails": {
            "universe": universe_label,
            "minThirtyMinuteCandles": 337,
            "min24hQuoteVolumeKrw": 1_000_000_000,
            "excluded": ["stable/fiat proxies", "Upbit CAUTION markets", "operator blacklist"],
            "score": "24h + 0.2 × 7d",
            "confirmation": "positive 7d and 24h breakout threshold",
            "capitalPolicy": "full available Upbit account NAV; no fixed KRW cap",
        },
    }


def main() -> None:
    payload = build_upbit_payload(REPORT_DIR)
    OUT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    print(f"Wrote {OUT_PATH} with {len(payload['equitySeries'])} live points and {len(payload['transactions'])} executions")


if __name__ == "__main__":
    main()
