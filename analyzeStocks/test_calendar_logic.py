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


if __name__ == "__main__":
    unittest.main()
