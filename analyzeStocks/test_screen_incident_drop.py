# analyzeStocks/test_screen_incident_drop.py
import datetime
import unittest

import screen_incident_drop as sid


class FakeClient:
    """master/bars を辞書から返す fake クライアント（ネットワーク非依存）。"""

    def __init__(self, master, bars):
        self._master = master
        self._bars = bars  # {code: [rows]}
        self.bars_calls = []  # 呼び出し記録（code, from_, to）

    def equities_master(self, code=None):
        return self._master

    def bars_daily(self, code, date=None, from_=None, to=None):
        self.bars_calls.append({"code": code, "from_": from_, "to": to})
        return self._bars.get(code, [])


class TestParseIncidents(unittest.TestCase):
    def test_parses_rows_and_dedupes(self):
        text = (
            "code,announce_date,name\n"
            "7203,2025-12-29,トヨタ自動車\n"
            "7203,2025-12-29,トヨタ自動車\n"
            "6758,20260105,\n"
            "\n"
        )
        incidents = sid.parse_incidents(text)
        self.assertEqual(len(incidents), 2)
        self.assertEqual(incidents[0].code, "7203")
        self.assertEqual(incidents[0].announce_date, datetime.date(2025, 12, 29))
        self.assertEqual(incidents[0].name, "トヨタ自動車")
        self.assertEqual(incidents[1].announce_date, datetime.date(2026, 1, 5))

    def test_missing_column_raises(self):
        with self.assertRaises(ValueError):
            sid.parse_incidents("code,date\n7203,2025-12-29\n")

    def test_bad_date_raises(self):
        with self.assertRaises(ValueError):
            sid.parse_incidents("code,announce_date\n7203,2025/12/29\n")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            sid.parse_incidents("code,announce_date\n")


class TestAnchorDate(unittest.TestCase):
    def test_strictly_before_announce_date(self):
        days = [datetime.date(2025, 12, 26), datetime.date(2025, 12, 29),
                datetime.date(2025, 12, 30)]
        # 公表日が取引日でも前営業日を基準にする
        self.assertEqual(sid.anchor_date(datetime.date(2025, 12, 30), days),
                         datetime.date(2025, 12, 29))
        # 公表日が休日（年末年始）なら大納会が基準になる
        self.assertEqual(sid.anchor_date(datetime.date(2026, 1, 3), days),
                         datetime.date(2025, 12, 30))

    def test_none_when_no_prior_trading_day(self):
        self.assertIsNone(sid.anchor_date(datetime.date(2025, 12, 26),
                                          [datetime.date(2025, 12, 26)]))


class TestBuildMarketIndexAll(unittest.TestCase):
    def test_keeps_all_markets(self):
        master = [
            {"Code": "1", "CoName": "A社", "MktNm": "プライム"},
            {"Code": "2", "CoName": "B社", "MktNm": "グロース"},
        ]
        idx = sid.build_market_index_all(master)
        self.assertEqual(set(idx.keys()), {"1", "2"})


class TestRun(unittest.TestCase):
    def test_ranks_by_drop_descending(self):
        # master / bars のキーは J-Quants 形式の5桁コード。入力は4桁で与える。
        master = [
            {"Code": "11110", "CoName": "下落社", "MktNm": "プライム"},
            {"Code": "22220", "CoName": "堅調社", "MktNm": "グロース"},
        ]
        bars = {
            # 公表 2026-01-05（月）。基準日は直前営業日 2025-12-30。
            "11110": [
                {"Date": "2025-12-30", "C": 1000.0},
                {"Date": "2026-01-05", "C": 950.0},
                {"Date": "2026-01-06", "C": 880.0},
                {"Date": "2026-01-07", "C": 920.0},
            ],
            "22220": [
                {"Date": "2025-12-30", "C": 500.0},
                {"Date": "2026-01-05", "C": 505.0},
                {"Date": "2026-01-06", "C": 498.0},
                {"Date": "2026-01-07", "C": 510.0},
            ],
        }
        incidents = [
            sid.Incident("2222", datetime.date(2026, 1, 5)),
            sid.Incident("1111", datetime.date(2026, 1, 5)),
        ]
        results = sid.run(FakeClient(master, bars), incidents, window=10)
        self.assertEqual([r["code"] for r in results], ["1111", "2222"])
        self.assertEqual(results[0]["anchor_date"], "2025-12-30")
        self.assertEqual(results[0]["min_date"], "2026-01-06")
        self.assertAlmostEqual(results[0]["drop_pct"], 12.0)
        self.assertAlmostEqual(results[1]["drop_pct"], 0.4)

    def test_skips_code_without_bars(self):
        master = [{"Code": "1111", "CoName": "下落社", "MktNm": "プライム"}]
        incidents = [sid.Incident("9999", datetime.date(2026, 1, 5))]
        results = sid.run(FakeClient(master, {}), incidents, window=10)
        self.assertEqual(results, [])


class TestNormalizeCode(unittest.TestCase):
    def test_four_digit_gets_trailing_zero(self):
        self.assertEqual(sid.normalize_code("5803"), "58030")
        self.assertEqual(sid.normalize_code(" 8697 "), "86970")

    def test_five_digit_unchanged(self):
        self.assertEqual(sid.normalize_code("86970"), "86970")


class TestRunCodeNormalization(unittest.TestCase):
    def test_four_digit_input_matches_five_digit_master_and_bars(self):
        # master / bars は J-Quants 形式の5桁コードで返る
        master = [{"Code": "58030", "CoName": "フジクラ", "MktNm": "プライム"}]
        bars = {"58030": [
            {"Date": "2025-12-24", "C": 2000.0},
            {"Date": "2025-12-25", "C": 1900.0},
            {"Date": "2025-12-26", "C": 1800.0},
        ]}
        client = FakeClient(master, bars)
        incidents = [sid.Incident("5803", datetime.date(2025, 12, 25))]
        results = sid.run(client, incidents, window=10)
        self.assertEqual(len(results), 1)
        # 表示コードは入力どおり4桁、名称・市場は5桁マスタから付与される
        self.assertEqual(results[0]["code"], "5803")
        self.assertEqual(results[0]["name"], "フジクラ")
        self.assertEqual(results[0]["market"], "プライム")
        self.assertEqual(client.bars_calls[0]["code"], "58030")

    def test_fetch_range_extends_with_window(self):
        master = [{"Code": "11110", "CoName": "A社", "MktNm": "プライム"}]
        bars = {"11110": [
            {"Date": "2025-12-30", "C": 100.0},
            {"Date": "2026-01-05", "C": 99.0},
        ]}
        incidents = [sid.Incident("1111", datetime.date(2026, 1, 5))]
        client_small = FakeClient(master, bars)
        sid.run(client_small, incidents, window=10)
        client_large = FakeClient(master, bars)
        sid.run(client_large, incidents, window=60)
        self.assertGreater(client_large.bars_calls[0]["to"],
                           client_small.bars_calls[0]["to"])


class TestFormatResultsMarkdown(unittest.TestCase):
    def test_table_contains_rows(self):
        results = [{
            "code": "1111", "name": "下落社", "market": "プライム",
            "announce_date": "2026-01-05", "anchor_date": "2025-12-30",
            "ref_close": 1000.0, "min_close": 880.0, "min_date": "2026-01-06",
            "drop_pct": 12.0, "window_used": 3,
        }]
        md = sid.format_results_markdown(results, window=10)
        self.assertIn("下落社", md)
        self.assertIn("12.00%", md)

    def test_empty_results(self):
        md = sid.format_results_markdown([], window=10)
        self.assertIn("ありません", md)


if __name__ == "__main__":
    unittest.main()
