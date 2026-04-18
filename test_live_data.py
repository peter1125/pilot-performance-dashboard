import unittest

from live_data import build_dashboard_payload


class BuildDashboardPayloadTests(unittest.TestCase):
    def test_ignores_future_placeholder_rows_and_uses_latest_usable_rows(self):
        pilot_rows = {
            'Pilot 1': [
                {
                    'pilot': 'Pilot 1',
                    'strategy': 'Trend Following',
                    'date': '2026-04-20',
                    'log': 'Day 7',
                    'start': None,
                    'end': None,
                    'cash': None,
                    'transactions': '',
                    'research': '',
                },
                {
                    'pilot': 'Pilot 1',
                    'strategy': 'Trend Following',
                    'date': '2026-04-18',
                    'log': 'Day 5',
                    'start': 11491750,
                    'end': 11559780,
                    'cash': 0,
                    'transactions': 'Rebalanced to AAVE 45%, PEPE 35%, XRP 20%. Momentum leadership remains intact.',
                    'research': 'Trend leadership remained intact.',
                },
            ],
            'Pilot 2': [
                {
                    'pilot': 'Pilot 2',
                    'strategy': 'Sentiment Accelerator',
                    'date': '2026-04-18',
                    'log': 'Day 5',
                    'start': 11171491,
                    'end': 11247020,
                    'cash': 2811755,
                    'transactions': 'Rebalanced to ETH 35%, ONDO 20%, PEPE 20%, Cash 25%. Some role buckets lacked aligned 24h/7d support, so residual capital stays in cash.',
                    'research': 'Kept 25% in cash.',
                },
            ],
            'Pilot 3': [
                {
                    'pilot': 'Pilot 3',
                    'strategy': 'Breakout Rotation',
                    'date': '2026-04-18',
                    'log': 'Day 5',
                    'start': 11874745,
                    'end': 11973309,
                    'cash': 0,
                    'transactions': 'Rebalanced to ETH 60%, BTC 25%, XRP 15%. Top 24h breakouts also retained positive 7d confirmation.',
                    'research': 'Breakout leadership broadened into ETH, BTC, and XRP.',
                },
            ],
        }

        payload = build_dashboard_payload(pilot_rows)

        self.assertEqual(payload['leaderboard'][0]['pilot'], 'Pilot 3')
        self.assertEqual(payload['leaderboard'][1]['pilot'], 'Pilot 1')
        self.assertEqual(payload['leaderboard'][2]['pilot'], 'Pilot 2')
        self.assertEqual(payload['summaries'][0]['latestDate'], '2026-04-18')
        self.assertEqual(payload['equitySeries'][-1]['Pilot 1'], 11559780)
        self.assertEqual(payload['latestDate'], '2026-04-18')


if __name__ == '__main__':
    unittest.main()
