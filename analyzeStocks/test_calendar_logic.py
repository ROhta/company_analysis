# analyzeStocks/test_calendar_logic.py
import datetime
import unittest

import calendar_logic as cl


class TestToFloat(unittest.TestCase):
    def test_parses_numeric_string(self):
        self.assertEqual(cl._to_float("175.0"), 175.0)

    def test_empty_and_dash_and_none_become_none(self):
        self.assertIsNone(cl._to_float(""))
        self.assertIsNone(cl._to_float("-"))
        self.assertIsNone(cl._to_float(None))

    def test_non_numeric_becomes_none(self):
        self.assertIsNone(cl._to_float("N/A"))


class TestParseDate(unittest.TestCase):
    def test_hyphenated(self):
        self.assertEqual(cl.parse_date("2025-09-30"), datetime.date(2025, 9, 30))

    def test_compact(self):
        self.assertEqual(cl.parse_date("20250930"), datetime.date(2025, 9, 30))


class TestAnalyzeDrop(unittest.TestCase):
    def _series(self):
        # 指定日=9/26(C=1636) 以降に 1610,1520,1490,null。既存zshの1636/1490を再現。
        return [
            {"Date": "2025-09-26", "C": 1636.0},
            {"Date": "2025-09-29", "C": 1610.0},
            {"Date": "2025-09-30", "C": 1520.0},
            {"Date": "2025-10-01", "C": 1490.0},
            {"Date": "2025-10-02", "C": None},
        ]

    def test_equivalent_to_zsh_1636_1490(self):
        r = cl.analyze_drop(self._series(), datetime.date(2025, 9, 26), window=10, threshold=0.95)
        self.assertEqual(r.ref_close, 1636.0)
        self.assertEqual(r.min_close, 1490.0)           # null除外後の最安値
        self.assertEqual(r.min_date, datetime.date(2025, 10, 1))
        self.assertTrue(r.hit)                          # 1490 < 0.95*1636=1554.2

    def test_no_hit_when_above_threshold(self):
        series = [{"Date": "2025-09-26", "C": 1000.0}, {"Date": "2025-09-29", "C": 990.0}]
        r = cl.analyze_drop(series, datetime.date(2025, 9, 26), window=10, threshold=0.95)
        self.assertFalse(r.hit)                          # 990 >= 950

    def test_returns_none_when_kijitsu_missing(self):
        self.assertIsNone(
            cl.analyze_drop(self._series(), datetime.date(2025, 9, 25), window=10, threshold=0.95)
        )

    def test_window_limits_lookahead(self):
        # window=1 なら 9/29(1610)のみ参照 → min=1610, hit=False
        r = cl.analyze_drop(self._series(), datetime.date(2025, 9, 26), window=1, threshold=0.95)
        self.assertEqual(r.min_close, 1610.0)
        self.assertFalse(r.hit)


class TestSettlementDate(unittest.TestCase):
    def test_8697_real_case(self):
        # 実データ: 9/22,24,25,26,29,30,10/1... 基準日9/30 → 指定日(2営業日前)=9/26
        trading_days = [datetime.date(2025, 9, d) for d in (22, 24, 25, 26, 29, 30)]
        trading_days += [datetime.date(2025, 10, d) for d in (1, 2, 3)]
        self.assertEqual(
            cl.settlement_date(datetime.date(2025, 9, 30), trading_days),
            datetime.date(2025, 9, 26),
        )

    def test_month_end_on_weekend(self):
        # 8/31(2025)が日曜のケース: 取引日 8/27,28,29 → 8/31の2営業日前=8/28
        trading_days = [datetime.date(2025, 8, d) for d in (27, 28, 29)]
        self.assertEqual(
            cl.settlement_date(datetime.date(2025, 8, 31), trading_days),
            datetime.date(2025, 8, 28),
        )

    def test_returns_none_when_insufficient_days(self):
        self.assertIsNone(
            cl.settlement_date(datetime.date(2025, 9, 30), [datetime.date(2025, 9, 29)])
        )


class TestFilterEventsByMonth(unittest.TestCase):
    def test_keeps_only_matching_year_month(self):
        events = [
            cl.DividendEvent("1", datetime.date(2025, 9, 30), "2Q", 25.0),
            cl.DividendEvent("2", datetime.date(2025, 3, 31), "FY", 10.0),
            cl.DividendEvent("3", datetime.date(2025, 9, 1), "FY", 5.0),
        ]
        got = cl.filter_events_by_month(events, "2025-09")
        self.assertEqual({e.code for e in got}, {"1", "3"})


class TestDividendEvents(unittest.TestCase):
    def _rows(self):
        return [
            # 期末配当あり(FY)
            {"Code": "86970", "DocType": "FYFinancialStatements_Consolidated_IFRS",
             "CurPerType": "FY", "CurPerEn": "2025-03-31", "DivFY": "29.0", "Div2Q": "33.0"},
            # 中間配当あり(2Q)
            {"Code": "86970", "DocType": "2QFinancialStatements_Consolidated_IFRS",
             "CurPerType": "2Q", "CurPerEn": "2025-09-30", "DivFY": "", "Div2Q": "25.0"},
            # 配当なし(予想修正など)は除外
            {"Code": "86970", "DocType": "EarnForecastRevision",
             "CurPerType": "FY", "CurPerEn": "2026-03-31", "DivFY": "", "Div2Q": ""},
            # FYだが期末配当が空 → 除外
            {"Code": "11110", "DocType": "FYFinancialStatements_Consolidated_JP",
             "CurPerType": "FY", "CurPerEn": "2025-03-31", "DivFY": "", "Div2Q": ""},
        ]

    def test_extracts_fy_and_2q_with_dividend(self):
        events = cl.dividend_events(self._rows())
        keys = {(e.code, e.record_date, e.kind) for e in events}
        self.assertIn(("86970", datetime.date(2025, 3, 31), "FY"), keys)
        self.assertIn(("86970", datetime.date(2025, 9, 30), "2Q"), keys)

    def test_excludes_non_dividend_rows(self):
        events = cl.dividend_events(self._rows())
        self.assertEqual(len(events), 2)
        self.assertNotIn("11110", {e.code for e in events})

    def test_dedupes_same_code_and_record_date(self):
        rows = self._rows() + [dict(self._rows()[0])]  # FY重複
        events = cl.dividend_events(rows)
        self.assertEqual(len(events), 2)


if __name__ == "__main__":
    unittest.main()
