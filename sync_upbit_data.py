#!/usr/bin/env python3
"""Build static data for the Pilot 3 Upbit live execution dashboard."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_DIR = Path.home() / ".hermes" / "pilot3-live-executions"
OUT_PATH = Path(__file__).with_name("upbit-data.json")


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


def _execution_notional(execution: dict[str, Any]) -> int:
    request = execution.get("request") or {}
    side = str(request.get("side") or "").upper()
    if side == "BUY":
        return _round_krw(execution.get("submitted_price_krw") or request.get("price_krw"))
    return _round_krw(request.get("notional_krw_est") or request.get("price_krw"))


def parse_execution_report(report: dict[str, Any], source_file: str) -> dict[str, Any] | None:
    if report.get("mode") != "live":
        return None
    ts = report.get("timestamp_kst")
    if not ts:
        return None
    nav_before = _round_krw(report.get("observed_nav_before_krw"))
    nav_after = _round_krw(report.get("observed_nav_after_krw"))
    weights_after = report.get("weights_after") or {}
    weights_before = report.get("weights_before") or {}

    executions = []
    for execution in report.get("executions") or []:
        request = execution.get("request") or {}
        response = execution.get("response") or {}
        side = str(request.get("side") or "").upper() or str(response.get("side") or "").upper()
        symbol = request.get("symbol") or (response.get("market", "-").split("-", 1)[-1] if response.get("market") else "")
        executions.append({
            "time": ts,
            "side": side,
            "symbol": symbol,
            "market": request.get("market") or response.get("market"),
            "notionalKrw": _execution_notional(execution),
            "uuid": response.get("uuid"),
            "state": response.get("state"),
        })

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
        "tradeCount": len(executions),
        "rankedCandidates": ranked,
        "warnings": report.get("warnings") or [],
        "safety": report.get("safety") or {},
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

    executions = []
    for point in points:
        executions.extend(point["executions"])

    latest = points[-1] if points else None
    first = points[0] if points else None
    starting_nav = first["navBefore"] if first else 0
    current_nav = latest["navAfter"] if latest else 0
    total_pnl = current_nav - starting_nav
    total_return = (total_pnl / starting_nav * 100) if starting_nav else 0

    summary = {
        "name": "Pilot 3 Upbit Live",
        "strategy": "Full Upbit KRW Breakout Rotation",
        "currentNav": current_nav,
        "startingNav": starting_nav,
        "totalPnlKrw": total_pnl,
        "totalReturnPct": total_return,
        "latestTime": latest["time"] if latest else None,
        "currentAllocation": latest["allocationText"] if latest else "None",
        "targetAllocation": latest["targetText"] if latest else "None",
        "latestRegime": latest["regimeNote"] if latest else "No live reports found",
        "latestReason": latest["targetReason"] if latest else "",
        "reportCount": len(points),
        "tradeCount": len(executions),
    }

    return {
        "source": "local-upbit-live-execution-reports",
        "refreshedAt": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "equitySeries": points,
        "transactions": executions,
        "latest": latest,
        "guardrails": {
            "universe": "Full Upbit KRW spot universe",
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
