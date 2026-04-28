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
        self.assertEqual(payload['equitySeries'][-1]['Pilot 1Start'], 11491750)
        self.assertEqual(payload['equitySeries'][-1]['Pilot 1DailyPnl'], 68030)
        self.assertAlmostEqual(payload['equitySeries'][-1]['Pilot 1DailyReturnPct'], 0.592, places=3)
        latest_pilot1 = next(row for row in payload['transactions'] if row['pilot'] == 'Pilot 1' and row['date'] == '2026-04-18')
        self.assertEqual(latest_pilot1['startDate'], '2026-04-18')
        self.assertEqual(latest_pilot1['dailyPnl'], 68030)
        self.assertIn('Daily P&L: +KRW 68,030', latest_pilot1['transactionRecord'])
        self.assertEqual(payload['latestDate'], '2026-04-18')

    def test_equity_series_fills_missing_calendar_dates_with_prior_nav(self):
        pilot_rows = {
            'Pilot 1': [
                {
                    'pilot': 'Pilot 1',
                    'strategy': 'Trend Following',
                    'date': '2026-04-14',
                    'log': 'Day 1',
                    'start': 10_000_000,
                    'end': 10_100_000,
                    'cash': 0,
                    'transactions': 'Rebalanced to BTC 100%',
                    'research': '',
                },
                {
                    'pilot': 'Pilot 1',
                    'strategy': 'Trend Following',
                    'date': '2026-04-17',
                    'log': 'Day 4',
                    'start': 10_100_000,
                    'end': 10_400_000,
                    'cash': 0,
                    'transactions': 'Rebalanced to ETH 100%',
                    'research': '',
                },
            ],
        }

        payload = build_dashboard_payload(pilot_rows)

        self.assertEqual([row['date'] for row in payload['equitySeries']], ['2026-04-14', '2026-04-15', '2026-04-16', '2026-04-17'])
        self.assertEqual(payload['equitySeries'][1]['Pilot 1'], 10_100_000)
        self.assertEqual(payload['equitySeries'][2]['Pilot 1'], 10_100_000)
        self.assertEqual(payload['equitySeries'][3]['Pilot 1'], 10_400_000)
        carry_forward_rows = [row for row in payload['transactions'] if row.get('isCarryForward')]
        self.assertEqual([row['date'] for row in sorted(carry_forward_rows, key=lambda row: row['date'])], ['2026-04-15', '2026-04-16'])
        self.assertEqual(carry_forward_rows[0]['start'], carry_forward_rows[0]['end'])
        self.assertIn('not a market revaluation', carry_forward_rows[0]['transactions'])

    def test_known_gap_uses_estimated_retro_marks_instead_of_flat_carry_forward(self):
        pilot_rows = {
            'Pilot 1': [
                {
                    'pilot': 'Pilot 1',
                    'strategy': 'Trend Following',
                    'date': '2026-04-19',
                    'log': 'Day 6',
                    'start': 11_488_838,
                    'end': 11_036_202,
                    'cash': 2_207_240,
                    'transactions': 'Rebalanced to PEPE 35%, XRP 25%, BTC 20%, Cash 20% at 23:53 KST',
                    'research': '',
                },
                {
                    'pilot': 'Pilot 1',
                    'strategy': 'Trend Following',
                    'date': '2026-04-26',
                    'log': 'Day 13',
                    'start': 11_036_202,
                    'end': 11_331_344,
                    'cash': 0,
                    'transactions': 'Rebalanced to DOGE 45%, BTC 35%, ONDO 20%',
                    'research': '',
                },
            ],
        }

        payload = build_dashboard_payload(pilot_rows)

        by_date = {row['date']: row for row in payload['equitySeries']}
        self.assertEqual(by_date['2026-04-20']['Pilot 1'], 10_882_532)
        self.assertEqual(by_date['2026-04-25']['Pilot 1'], 11_138_959)
        retro_rows = [row for row in payload['transactions'] if row.get('isEstimatedRetroMark')]
        self.assertEqual(len(retro_rows), 6)
        self.assertTrue(all('No trade recorded' in row['transactions'] for row in retro_rows))
    def test_snapshot_log_drives_interval_consistent_feed_and_graph_when_available(self):
        pilot_rows = {
            'Pilot 3': [
                {
                    'pilot': 'Pilot 3',
                    'strategy': 'Breakout Rotation',
                    'date': '2026-04-27',
                    'log': 'carry-forward mark',
                    'start': 12_077_729,
                    'end': 12_077_729,
                    'cash': 12_077_729,
                    'transactions': 'Cash 100%',
                    'research': '',
                },
                {
                    'pilot': 'Pilot 3',
                    'strategy': 'Breakout Rotation',
                    'date': '2026-04-28',
                    'log': 'daily row overwritten later',
                    'start': 12_575_311,
                    'end': 12_576_133,
                    'cash': 0,
                    'transactions': 'AAVE 60%, DOGE 25%, PEPE 15%',
                    'research': '',
                },
            ],
        }
        snapshot_rows = [
            {
                'time': '2026-04-28 19:08 KST',
                'timestamp': '2026-04-28T19:08:00.000+09:00',
                'Pilot 3': 12_574_625,
                'Pilot 3Text': 'AAVE 60%, DOGE 25%, PEPE 15% | NAV KRW 12,574,625',
            },
            {
                'time': '2026-04-28 19:13 KST',
                'timestamp': '2026-04-28T19:13:00.000+09:00',
                'Pilot 3': 12_575_311,
                'Pilot 3Text': 'AAVE 60%, DOGE 25%, PEPE 15% | NAV KRW 12,575,311',
            },
            {
                'time': '2026-04-28 19:20 KST',
                'timestamp': '2026-04-28T19:20:00.000+09:00',
                'Pilot 3': 12_576_133,
                'Pilot 3Text': 'AAVE 60%, DOGE 25%, PEPE 15% | NAV KRW 12,576,133',
            },
        ]

        payload = build_dashboard_payload(pilot_rows, snapshot_rows)

        self.assertEqual(payload['equitySeries'][-1]['date'], '2026-04-28 19:20 KST')
        self.assertEqual(payload['equitySeries'][-1]['Pilot 3Start'], 12_575_311)
        self.assertEqual(payload['equitySeries'][-1]['Pilot 3DailyPnl'], 822)
        latest_snapshot = next(row for row in payload['transactions'] if row['pilot'] == 'Pilot 3' and row['date'] == '2026-04-28 19:20 KST')
        self.assertEqual(latest_snapshot['startDate'], '2026-04-28 19:13 KST')
        self.assertEqual(latest_snapshot['start'], 12_575_311)
        self.assertEqual(latest_snapshot['end'], 12_576_133)
        self.assertEqual(latest_snapshot['dailyPnl'], 822)
        self.assertTrue(latest_snapshot['isSnapshotLog'])
        self.assertIn('From 2026-04-28 19:13 KST to 2026-04-28 19:20 KST', latest_snapshot['transactionRecord'])


if __name__ == '__main__':
    unittest.main()
