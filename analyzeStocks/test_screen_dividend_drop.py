# analyzeStocks/test_screen_dividend_drop.py
import datetime
import io
import json
import unittest
from contextlib import redirect_stdout

import screen_dividend_drop as sdd


class FakeClient:
    """summary/master/bars を辞書から返すfakeクライアント。"""
    def __init__(self, summary, master, bars):
        self._summary = summary
        self._master = master
        self._bars = bars  # {code: [rows]}

    def fins_summary(self, date=None, from_=None, to=None, code=None):
        return self._summary

    def equities_master(self, code=None):
        return self._master

    def bars_daily(self, code, date=None, from_=None, to=None):
        return self._bars.get(code, [])


class TestBuildMarketIndex(unittest.TestCase):
    def test_keeps_prime_and_standard_only(self):
        master = [
            {"Code": "1", "CoName": "A社", "MktNm": "プライム"},
            {"Code": "2", "CoName": "B社", "MktNm": "スタンダード"},
            {"Code": "3", "CoName": "C社", "MktNm": "グロース"},
        ]
        idx = sdd.build_market_index(master)
        self.assertEqual(set(idx.keys()), {"1", "2"})
        self.assertEqual(idx["1"], ("A社", "プライム"))


class TestMainSmoke(unittest.TestCase):
    def test_finds_dropping_stock(self):
        # 2025-09(中間)に権利確定、指定日9/26(1636)→以降1490まで下落する銘柄
        summary = [
            {"Code": "86970", "DocType": "2QFinancialStatements_Consolidated_IFRS",
             "CurPerType": "2Q", "CurPerEn": "2025-09-30", "DivFY": "", "Div2Q": "25.0"},
        ]
        master = [{"Code": "86970", "CoName": "テスト社", "MktNm": "プライム"}]
        bars = {"86970": [
            {"Date": "2025-09-24", "C": 1700.0},
            {"Date": "2025-09-25", "C": 1690.0},
            {"Date": "2025-09-26", "C": 1636.0},  # 指定日(基準日9/30の2営業日前)
            {"Date": "2025-09-29", "C": 1610.0},
            {"Date": "2025-09-30", "C": 1520.0},
            {"Date": "2025-10-01", "C": 1490.0},
        ]}
        client = FakeClient(summary, master, bars)
        out = io.StringIO()
        with redirect_stdout(out):
            hits = sdd.run(client, target_month="2025-09", threshold=0.95, window=10)
        self.assertEqual([h["code"] for h in hits], ["86970"])
        self.assertIn("テスト社", out.getvalue())


if __name__ == "__main__":
    unittest.main()
