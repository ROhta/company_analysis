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

    def test_zero_is_valid(self):
        self.assertEqual(cl._to_float("0"), 0.0)
        self.assertEqual(cl._to_float(0), 0.0)


class TestParseDate(unittest.TestCase):
    def test_hyphenated(self):
        self.assertEqual(cl.parse_date("2025-09-30"), datetime.date(2025, 9, 30))

    def test_compact(self):
        self.assertEqual(cl.parse_date("20250930"), datetime.date(2025, 9, 30))

    def test_invalid_length_raises(self):
        with self.assertRaises(ValueError):
            cl.parse_date("2025103")


class TestTargetMonthHelpers(unittest.TestCase):
    def test_default_target_month_is_about_four_months_back(self):
        self.assertEqual(cl.default_target_month(datetime.date(2026, 5, 31)), "2026-01")
        self.assertEqual(cl.default_target_month(datetime.date(2026, 2, 15)), "2025-10")


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
        self.assertEqual(r.window_used, 4)              # 9/29, 9/30, 10/1, 10/2 の4日

    def test_no_hit_when_above_threshold(self):
        series = [{"Date": "2025-09-26", "C": 1000.0}, {"Date": "2025-09-29", "C": 990.0}]
        r = cl.analyze_drop(series, datetime.date(2025, 9, 26), window=10, threshold=0.95)
        self.assertFalse(r.hit)                          # 990 >= 950
        self.assertEqual(r.window_used, 1)              # window=10 に対し1日のみ（範囲端）

    def test_window_used_equals_window_when_enough_data(self):
        # 指定日以降にちょうど window 分の取引日がある場合、window_used == window
        series = [{"Date": "2025-09-2{}".format(d), "C": float(1000 - d)}
                  for d in range(6)]  # 9/20〜9/25、指定日=9/20
        # window=3: 9/21, 9/22, 9/23 の3日分 → window_used=3
        r = cl.analyze_drop(series, datetime.date(2025, 9, 20), window=3, threshold=0.95)
        self.assertEqual(r.window_used, 3)

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

    def test_record_date_not_in_trading_days(self):
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


class TestDisclosureDates(unittest.TestCase):
    """disclosure_dates(year_month) の単体テスト（対象月末+60日・平日のみ）。"""

    def test_first_date_is_month_end(self):
        dates = cl.disclosure_dates("2025-09")
        self.assertEqual(dates[0], "2025-09-30")  # 2025-09-30 は火曜

    def test_last_date_is_60_days_after_month_end(self):
        # 2025-09-30 + 60日 = 2025-11-29(土) → 直前の平日 2025-11-28(金)
        dates = cl.disclosure_dates("2025-09")
        self.assertEqual(dates[-1], "2025-11-28")

    def test_no_weekends(self):
        dates = cl.disclosure_dates("2025-09")
        for s in dates:
            d = datetime.date.fromisoformat(s)
            self.assertLessEqual(d.weekday(), 4, "{} は土日".format(s))

    def test_all_within_range(self):
        # +60日窓内であることを確認
        dates = cl.disclosure_dates("2025-09")
        start = datetime.date(2025, 9, 30)
        end = datetime.date(2025, 11, 29)  # 2025-09-30 + 60日
        for s in dates:
            d = datetime.date.fromisoformat(s)
            self.assertGreaterEqual(d, start)
            self.assertLessEqual(d, end)

    def test_march_end_is_included(self):
        # 2025-03-31 は月曜 → 先頭
        dates = cl.disclosure_dates("2025-03")
        self.assertEqual(dates[0], "2025-03-31")
        # 2025-03-31 + 60日 = 2025-05-30 は金曜 → 末尾
        self.assertEqual(dates[-1], "2025-05-30")

    def test_returns_strings(self):
        dates = cl.disclosure_dates("2025-09")
        for s in dates:
            self.assertIsInstance(s, str)
            self.assertRegex(s, r"^\d{4}-\d{2}-\d{2}$")

    def test_count_is_approx_44_for_sep2025(self):
        # 2025-09の+60日窓では約44コール（+3ヶ月の約67から大幅削減）
        dates = cl.disclosure_dates("2025-09")
        self.assertEqual(len(dates), 44)


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

    def test_fy_zero_dividend_excluded(self):
        """DivFY="0"（配当0）のFY行は除外される。"""
        rows = [
            {"Code": "99990", "DocType": "FYFinancialStatements_Consolidated_JP",
             "CurPerType": "FY", "CurPerEn": "2025-03-31", "DivFY": "0", "Div2Q": ""},
        ]
        events = cl.dividend_events(rows)
        self.assertEqual(events, [])


class TestAnalyzeDropEdgeCases(unittest.TestCase):
    def test_returns_none_when_ref_close_is_zero_string(self):
        """指定日の終値が "0" (ref_close<=0) の場合は None を返す。"""
        rows = [
            {"Date": "2025-09-26", "C": "0"},
            {"Date": "2025-09-29", "C": 1600.0},
        ]
        self.assertIsNone(
            cl.analyze_drop(rows, datetime.date(2025, 9, 26), window=10, threshold=0.95)
        )

    def test_returns_none_when_all_after_closes_are_null(self):
        """指定日以降が全て C=None（終値欠損）の場合は None を返す。"""
        rows = [
            {"Date": "2025-09-26", "C": 1636.0},
            {"Date": "2025-09-29", "C": None},
            {"Date": "2025-09-30", "C": None},
        ]
        self.assertIsNone(
            cl.analyze_drop(rows, datetime.date(2025, 9, 26), window=10, threshold=0.95)
        )


if __name__ == "__main__":
    unittest.main()
