import json
import os
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

NOTION_VERSION = '2025-09-03'
NOTION_BASE = 'https://api.notion.com/v1'
PILOT_SOURCES = {
    'Pilot 1': {
        'strategy': 'Trend Following',
        'data_source_id': 'ad7e18ea-59f3-4113-9507-7d13724ece0e',
    },
    'Pilot 2': {
        'strategy': 'Sentiment Accelerator',
        'data_source_id': 'b68eba93-071d-4447-bfef-710aaa59a366',
    },
    'Pilot 3': {
        'strategy': 'Breakout Rotation',
        'data_source_id': '7d655ec8-b920-43c7-ab2a-f6a34bf442a4',
    },
}
PILOT_META = {
    'Pilot 1': {'color': '#8b5cf6', 'accent': 'rgba(139, 92, 246, 0.18)'},
    'Pilot 2': {'color': '#06b6d4', 'accent': 'rgba(6, 182, 212, 0.18)'},
    'Pilot 3': {'color': '#f97316', 'accent': 'rgba(249, 115, 22, 0.18)'},
}


class NotionApiError(RuntimeError):
    pass


def notion_request(method: str, path: str, token: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode('utf-8')
    request = urllib.request.Request(
        NOTION_BASE + path,
        method=method,
        data=body,
        headers={
            'Authorization': f'Bearer {token}',
            'Notion-Version': NOTION_VERSION,
            'Content-Type': 'application/json',
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='replace')
        raise NotionApiError(f'Notion API {exc.code} on {path}: {detail}') from exc


def plain_text(items: List[Dict[str, Any]]) -> str:
    return ''.join(item.get('plain_text', '') for item in items or [])


def parse_row(page: Dict[str, Any], pilot: str, strategy: str) -> Dict[str, Any]:
    props = page.get('properties', {})
    date_obj = props.get('Date', {}).get('date') or {}
    return {
        'pilot': pilot,
        'strategy': strategy,
        'date': date_obj.get('start'),
        'log': plain_text(props.get('Log', {}).get('title', [])),
        'start': props.get("Day's Starting Amount", {}).get('number'),
        'end': props.get('End Amount', {}).get('number'),
        'cash': props.get('Cash Amount', {}).get('number'),
        'transactions': plain_text(props.get("Day's Transactions", {}).get('rich_text', [])),
        'research': plain_text(props.get('Summary of Research', {}).get('rich_text', [])),
    }


def is_usable_row(row: Dict[str, Any]) -> bool:
    return bool(
        row.get('date')
        and (
            row.get('start') is not None
            or row.get('end') is not None
            or (row.get('transactions') or '').strip()
            or (row.get('research') or '').strip()
        )
    )


def extract_allocation(transaction_text: str) -> str:
    if not transaction_text:
        return 'No transaction note'
    normalized = transaction_text.strip()
    normalized = normalized.replace('Rebalanced at ', 'Rebalanced ')
    prefixes = ['Rebalanced to ', 'Rebalanced ']
    for prefix in prefixes:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
    if ': ' in normalized and normalized[:10].count('-') >= 1:
        normalized = normalized.split(': ', 1)[1]
    stop_markers = [
        ' based on',
        ' Following strongest',
        ' Momentum leadership',
        ' Top 24h breakouts',
        ' Some role buckets',
        ' Allocated to strongest',
        ' All four sentiment',
        ' using ',
    ]
    for marker in stop_markers:
        if marker in normalized:
            normalized = normalized.split(marker, 1)[0]
    return normalized.strip() or transaction_text


def build_summaries(pilot_rows: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    summaries = []
    for pilot, rows in pilot_rows.items():
        usable = sorted((row for row in rows if is_usable_row(row)), key=lambda row: row['date'])
        if not usable:
            continue
        first = usable[0]
        latest = usable[-1]
        current_nav = latest['end'] or latest['start'] or 0
        start_amount = latest['start'] or current_nav
        day_pnl = current_nav - (latest['start'] or current_nav)
        day_return_pct = ((day_pnl / latest['start']) * 100) if latest.get('start') else 0.0
        base_start = first['start'] or 10_000_000
        total_return_pct = ((current_nav - base_start) / base_start) * 100 if base_start else 0.0
        summaries.append(
            {
                'pilot': pilot,
                'strategy': latest['strategy'],
                'currentNav': round(current_nav),
                'startingCapital': round(base_start),
                'dayPnl': round(day_pnl),
                'dayReturnPct': round(day_return_pct, 4),
                'totalReturnPct': round(total_return_pct, 4),
                'cash': round(latest.get('cash') or 0),
                'latestDate': latest['date'],
                'latestLog': latest.get('log') or latest['date'],
                'latestTransaction': latest.get('transactions') or '',
                'latestResearch': latest.get('research') or '',
                'latestAllocation': extract_allocation(latest.get('transactions') or ''),
            }
        )
    return summaries


def compute_leaderboard(summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ordered = sorted(summaries, key=lambda row: row['currentNav'], reverse=True)
    return [{**row, 'rank': index + 1} for index, row in enumerate(ordered)]


def calendar_date_range(dates: List[str]) -> List[str]:
    """Return every ISO date from the first to the last date, inclusive."""
    if not dates:
        return []
    start = date.fromisoformat(min(dates))
    end = date.fromisoformat(max(dates))
    days = (end - start).days
    return [(start + timedelta(days=offset)).isoformat() for offset in range(days + 1)]


def build_equity_series(pilot_rows: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    observed_dates = sorted({row['date'] for rows in pilot_rows.values() for row in rows if is_usable_row(row) and row.get('date')})
    dates = calendar_date_range(observed_dates)
    latest_by_pilot: Dict[str, Any] = {pilot: None for pilot in pilot_rows.keys()}
    series: List[Dict[str, Any]] = []
    for series_date in dates:
        item = {'date': series_date}
        for pilot, rows in pilot_rows.items():
            exact = next((row for row in rows if is_usable_row(row) and row.get('date') == series_date), None)
            if exact:
                latest_by_pilot[pilot] = round(exact.get('end') or exact.get('start') or 0)
            item[pilot] = latest_by_pilot[pilot]
        series.append(item)
    return series


def flatten_transactions(pilot_rows: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    rows = [row for pilot in pilot_rows.values() for row in pilot if is_usable_row(row)]
    rows.sort(key=lambda row: row['date'], reverse=True)
    cleaned = []
    for row in rows:
        current_nav = row.get('end') or row.get('start') or 0
        start_amount = row.get('start') or current_nav
        cleaned.append(
            {
                **row,
                'start': round(start_amount),
                'end': round(current_nav),
                'cash': round(row.get('cash') or 0),
            }
        )
    return cleaned


def build_dashboard_payload(pilot_rows: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    summaries = build_summaries(pilot_rows)
    leaderboard = compute_leaderboard(summaries)
    latest_date = max((row['latestDate'] for row in summaries), default=None)
    return {
        'pilotMeta': PILOT_META,
        'summaries': leaderboard,
        'leaderboard': leaderboard,
        'equitySeries': build_equity_series(pilot_rows),
        'transactions': flatten_transactions(pilot_rows),
        'latestDate': latest_date,
        'refreshedAt': datetime.now(timezone.utc).isoformat(),
        'source': 'notion-live',
    }


def fetch_live_pilot_rows(token: str) -> Dict[str, List[Dict[str, Any]]]:
    pilot_rows: Dict[str, List[Dict[str, Any]]] = {}
    for pilot, config in PILOT_SOURCES.items():
        payload = {
            'page_size': 100,
            'sorts': [{'property': 'Date', 'direction': 'ascending'}],
        }
        response = notion_request('POST', f"/data_sources/{config['data_source_id']}/query", token, payload)
        pilot_rows[pilot] = [parse_row(item, pilot, config['strategy']) for item in response.get('results', [])]
    return pilot_rows


def load_live_dashboard_payload(token: str = None) -> Dict[str, Any]:
    notion_token = token or os.getenv('NOTION_API_KEY')
    if not notion_token:
        raise NotionApiError('NOTION_API_KEY is not set for the live dashboard server.')
    return build_dashboard_payload(fetch_live_pilot_rows(notion_token))
