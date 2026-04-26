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

# Indicative retroactive marks for the 2026-04-20..2026-04-25 dashboard gap.
# Basis: 2026-04-19 23:53 KST allocation, Upbit KRW 30m close at 23:30 KST for
# the base and each daily mark. These are estimates, not originally recorded Notion marks.
RETRO_MARKS = {
    'Pilot 1': {
        '2026-04-20': {'end': 10_882_532, 'cash': 2_207_240, 'returnPct': -1.3924},
        '2026-04-21': {'end': 10_969_720, 'cash': 2_207_240, 'returnPct': -0.6024},
        '2026-04-22': {'end': 11_248_201, 'cash': 2_207_240, 'returnPct': 1.9209},
        '2026-04-23': {'end': 11_104_277, 'cash': 2_207_240, 'returnPct': 0.6168},
        '2026-04-24': {'end': 11_153_892, 'cash': 2_207_240, 'returnPct': 1.0664},
        '2026-04-25': {'end': 11_138_959, 'cash': 2_207_240, 'returnPct': 0.9311},
    },
    'Pilot 2': {
        '2026-04-20': {'end': 11_245_984, 'cash': 9_605_337, 'returnPct': -0.4815},
        '2026-04-21': {'end': 11_262_544, 'cash': 9_605_337, 'returnPct': -0.3350},
        '2026-04-22': {'end': 11_303_945, 'cash': 9_605_337, 'returnPct': 0.0314},
        '2026-04-23': {'end': 11_267_276, 'cash': 9_605_337, 'returnPct': -0.2931},
        '2026-04-24': {'end': 11_276_739, 'cash': 9_605_337, 'returnPct': -0.2094},
        '2026-04-25': {'end': 11_270_824, 'cash': 9_605_337, 'returnPct': -0.2617},
    },
    'Pilot 3': {
        '2026-04-20': {'end': 12_077_729, 'cash': 12_077_729, 'returnPct': 0.0},
        '2026-04-21': {'end': 12_077_729, 'cash': 12_077_729, 'returnPct': 0.0},
        '2026-04-22': {'end': 12_077_729, 'cash': 12_077_729, 'returnPct': 0.0},
        '2026-04-23': {'end': 12_077_729, 'cash': 12_077_729, 'returnPct': 0.0},
        '2026-04-24': {'end': 12_077_729, 'cash': 12_077_729, 'returnPct': 0.0},
        '2026-04-25': {'end': 12_077_729, 'cash': 12_077_729, 'returnPct': 0.0},
    },
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


def get_retro_mark(pilot: str, mark_date: str) -> Dict[str, Any]:
    return RETRO_MARKS.get(pilot, {}).get(mark_date)


def build_equity_series(pilot_rows: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    observed_dates = sorted({row['date'] for rows in pilot_rows.values() for row in rows if is_usable_row(row) and row.get('date')})
    dates = calendar_date_range(observed_dates)
    latest_by_pilot: Dict[str, Any] = {pilot: None for pilot in pilot_rows.keys()}
    series: List[Dict[str, Any]] = []
    for series_date in dates:
        item = {'date': series_date}
        for pilot, rows in pilot_rows.items():
            exact = next((row for row in rows if is_usable_row(row) and row.get('date') == series_date), None)
            retro_mark = get_retro_mark(pilot, series_date)
            if exact:
                latest_by_pilot[pilot] = round(exact.get('end') or exact.get('start') or 0)
            elif retro_mark and latest_by_pilot[pilot] is not None:
                latest_by_pilot[pilot] = round(retro_mark['end'])
            item[pilot] = latest_by_pilot[pilot]
        series.append(item)
    return series


def build_transaction_feed(pilot_rows: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    observed_dates = sorted({row['date'] for rows in pilot_rows.values() for row in rows if is_usable_row(row) and row.get('date')})
    dates = calendar_date_range(observed_dates)
    feed: List[Dict[str, Any]] = []

    for pilot, rows in pilot_rows.items():
        usable = sorted((row for row in rows if is_usable_row(row)), key=lambda row: row['date'])
        rows_by_date = {row['date']: row for row in usable}
        latest_actual = None
        previous_nav = None
        previous_cash = None
        for feed_date in dates:
            actual = rows_by_date.get(feed_date)
            retro_mark = get_retro_mark(pilot, feed_date)
            if actual:
                latest_actual = actual
                previous_nav = actual.get('end') or actual.get('start') or 0
                previous_cash = actual.get('cash') or 0
                feed.append(clean_transaction_row(actual, is_carry_forward=False, is_estimated_retro_mark=False))
            elif retro_mark and latest_actual and previous_nav is not None:
                feed.append(
                    clean_transaction_row(
                        {
                            **latest_actual,
                            'date': feed_date,
                            'log': f'{feed_date} estimated retroactive mark',
                            'start': previous_nav,
                            'end': retro_mark['end'],
                            'cash': retro_mark['cash'],
                            'transactions': retro_mark_transaction_text(pilot),
                            'research': retro_mark_research_text(pilot, feed_date, retro_mark),
                        },
                        is_carry_forward=False,
                        is_estimated_retro_mark=True,
                    )
                )
                previous_nav = retro_mark['end']
                previous_cash = retro_mark['cash']
            elif latest_actual:
                current_nav = previous_nav if previous_nav is not None else latest_actual.get('end') or latest_actual.get('start') or 0
                current_cash = previous_cash if previous_cash is not None else latest_actual.get('cash') or 0
                feed.append(
                    clean_transaction_row(
                        {
                            **latest_actual,
                            'date': feed_date,
                            'log': f'{feed_date} carry-forward mark',
                            'start': current_nav,
                            'end': current_nav,
                            'cash': current_cash,
                            'transactions': 'No dashboard update or retroactive estimate recorded for this date; carrying forward the last Notion mark. This is not a market revaluation.',
                            'research': 'Synthetic carry-forward row generated by the public dashboard so missing dates are visible. NAV stayed unchanged here only because no new Notion mark or retroactive estimate was recorded for this date.',
                        },
                        is_carry_forward=True,
                        is_estimated_retro_mark=False,
                    )
                )

    feed.sort(key=lambda row: (row['date'], 0 if row.get('isCarryForward') else 1, row['pilot']), reverse=True)
    return feed


def clean_transaction_row(row: Dict[str, Any], is_carry_forward: bool, is_estimated_retro_mark: bool) -> Dict[str, Any]:
    current_nav = row.get('end') or row.get('start') or 0
    start_amount = row.get('start') or current_nav
    return {
        **row,
        'start': round(start_amount),
        'end': round(current_nav),
        'cash': round(row.get('cash') or 0),
        'isCarryForward': is_carry_forward,
        'isEstimatedRetroMark': is_estimated_retro_mark,
    }


def retro_mark_transaction_text(pilot: str) -> str:
    if pilot == 'Pilot 1':
        return 'Estimated retro mark from 2026-04-19 allocation: PEPE 35%, XRP 25%, BTC 20%, Cash 20%. No trade recorded.'
    if pilot == 'Pilot 2':
        return 'Estimated retro mark from 2026-04-19 allocation: SUI 15%, Cash 85%. No trade recorded.'
    if pilot == 'Pilot 3':
        return 'Estimated retro mark from 2026-04-19 allocation: Cash 100%. No trade recorded.'
    return 'Estimated retroactive market mark. No trade recorded.'


def retro_mark_research_text(pilot: str, mark_date: str, retro_mark: Dict[str, Any]) -> str:
    return (
        f'{mark_date} estimated retroactive mark for {pilot}. Basis: 2026-04-19 23:53 KST allocation, '
        'Upbit KRW 30-minute candle close at 23:30 KST for the base and the daily mark. '
        f'Estimated NAV KRW {round(retro_mark["end"]):,}; estimated return vs 2026-04-19 mark {retro_mark["returnPct"]:+.4f}%. '
        'This was not an originally recorded Notion/dashboard update.'
    )


def build_dashboard_payload(pilot_rows: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    summaries = build_summaries(pilot_rows)
    leaderboard = compute_leaderboard(summaries)
    latest_date = max((row['latestDate'] for row in summaries), default=None)
    return {
        'pilotMeta': PILOT_META,
        'summaries': leaderboard,
        'leaderboard': leaderboard,
        'equitySeries': build_equity_series(pilot_rows),
        'transactions': build_transaction_feed(pilot_rows),
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
