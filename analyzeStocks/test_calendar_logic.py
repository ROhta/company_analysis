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
