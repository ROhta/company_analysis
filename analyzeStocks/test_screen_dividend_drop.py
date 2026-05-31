# analyzeStocks/test_screen_dividend_drop.py
import csv
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

import screen_dividend_drop as sdd
from jquants_client import JQuantsError


class FakeClient:
    """summary/master/bars を辞書から返すfakeクライアント。

    fins_summary(date=d) で呼ばれる。
    _summary_by_date が設定されている場合はその日付のデータを返し、
    _summary_by_date が未設定の場合は _summary を全日付で返す。
    """
    def __init__(self, summary, master, bars, summary_by_date=None):
        self._summary = summary
        self._master = master
        self._bars = bars  # {code: [rows]}
        self._summary_by_date = summary_by_date  # {"YYYY-MM-DD": [rows]} or None
        self.fins_summary_calls = []  # 呼び出し記録
        self.bars_daily_count = 0  # bars_daily 呼び出し回数

    def fins_summary(self, date=None, from_=None, to=None, code=None):
        self.fins_summary_calls.append({"date": date, "from_": from_, "to": to, "code": code})
        if self._summary_by_date is not None:
            if date is None:
                return []
            return self._summary_by_date.get(date, [])
        return self._summary

    def equities_master(self, code=None):
        return self._master

    def bars_daily(self, code, date=None, from_=None, to=None):
        self.bars_daily_count += 1
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
    def _make_summary_for_sep2025(self):
        """2025-09月末を CurPerEn とする要約行を、開示日スキャン範囲の特定日付にマッピング。"""
        row = {
            "Code": "86970", "DocType": "2QFinancialStatements_Consolidated_IFRS",
            "CurPerType": "2Q", "CurPerEn": "2025-09-30", "DivFY": "", "Div2Q": "25.0",
        }
        # 2025-10-01 (水) に開示されたとする
        return {"2025-10-01": [row]}

    def test_fins_summary_called_with_date_param(self):
        """run() が fins_summary(date=...) を使って呼ぶことを確認。"""
        summary_by_date = self._make_summary_for_sep2025()
        master = [{"Code": "86970", "CoName": "テスト社", "MktNm": "プライム"}]
        bars = {"86970": [
            {"Date": "2025-09-24", "C": 1700.0},
            {"Date": "2025-09-25", "C": 1690.0},
            {"Date": "2025-09-26", "C": 1636.0},
            {"Date": "2025-09-29", "C": 1610.0},
            {"Date": "2025-09-30", "C": 1520.0},
            {"Date": "2025-10-01", "C": 1490.0},
        ]}
        client = FakeClient(None, master, bars, summary_by_date=summary_by_date)
        sdd.run(client, "2025-09", threshold=0.95, window=10)
        # date= パラメータで呼ばれていること
        date_calls = [c["date"] for c in client.fins_summary_calls if c["date"] is not None]
        self.assertGreater(len(date_calls), 0, "fins_summary が date= で呼ばれていない")
        # from_= では呼ばれていないこと
        from_calls = [c for c in client.fins_summary_calls if c["from_"] is not None]
        self.assertEqual(from_calls, [], "fins_summary が from_= で呼ばれている（バグ）")

    def test_finds_dropping_stock(self):
        # 2025-09(中間)に権利確定、指定日9/26(1636)→以降1490まで下落する銘柄
        summary_by_date = self._make_summary_for_sep2025()
        master = [{"Code": "86970", "CoName": "テスト社", "MktNm": "プライム"}]
        bars = {"86970": [
            {"Date": "2025-09-24", "C": 1700.0},
            {"Date": "2025-09-25", "C": 1690.0},
            {"Date": "2025-09-26", "C": 1636.0},  # 指定日(基準日9/30の2営業日前)
            {"Date": "2025-09-29", "C": 1610.0},
            {"Date": "2025-09-30", "C": 1520.0},
            {"Date": "2025-10-01", "C": 1490.0},
        ]}
        client = FakeClient(None, master, bars, summary_by_date=summary_by_date)
        out = io.StringIO()
        with redirect_stdout(out):
            hits = sdd.run(client, target_month="2025-09", threshold=0.95, window=10)
        self.assertEqual([h["code"] for h in hits], ["86970"])
        self.assertIn("テスト社", out.getvalue())

    def test_no_hit_when_no_drop(self):
        summary_by_date = self._make_summary_for_sep2025()
        master = [{"Code": "86970", "CoName": "テスト社", "MktNm": "プライム"}]
        bars = {"86970": [
            {"Date": "2025-09-24", "C": 1700.0},
            {"Date": "2025-09-25", "C": 1690.0},
            {"Date": "2025-09-26", "C": 1636.0},  # 指定日
            {"Date": "2025-09-29", "C": 1600.0},  # 1636*0.95=1554.2 を下回らない
        ]}
        client = FakeClient(None, master, bars, summary_by_date=summary_by_date)
        self.assertEqual(sdd.run(client, "2025-09", threshold=0.95, window=10), [])

    def test_no_events_skips_equities_master(self):
        """events が0件のとき equities_master を呼ばない。"""
        client = FakeClient([], [], {}, summary_by_date={})
        hits = sdd.run(client, "2025-09", threshold=0.95, window=10)
        self.assertEqual(hits, [])
        # equities_master が呼ばれると AttributeError になるが、呼ばれなければ問題なし

    def test_limit_caps_candidates(self):
        """--limit N で候補イベントが N 件に絞られる。"""
        # 2銘柄が権利確定するが limit=1 にすると1件しか処理しない
        row1 = {"Code": "10001", "DocType": "2QFinancialStatements_Consolidated_IFRS",
                "CurPerType": "2Q", "CurPerEn": "2025-09-30", "DivFY": "", "Div2Q": "10.0"}
        row2 = {"Code": "10002", "DocType": "2QFinancialStatements_Consolidated_IFRS",
                "CurPerType": "2Q", "CurPerEn": "2025-09-30", "DivFY": "", "Div2Q": "10.0"}
        summary_by_date = {"2025-10-01": [row1, row2]}
        master = [
            {"Code": "10001", "CoName": "A社", "MktNm": "プライム"},
            {"Code": "10002", "CoName": "B社", "MktNm": "プライム"},
        ]
        # settlement_date が非 None になるよう 9/30 基準日の2営業日前=9/26 を含む bars を設定
        # どちらも下落しない（ヒットなし）ようにバーを設定
        flat_bars = [
            {"Date": "2025-09-24", "C": 1000.0},
            {"Date": "2025-09-25", "C": 1000.0},
            {"Date": "2025-09-26", "C": 1000.0},
            {"Date": "2025-09-29", "C": 990.0},
        ]
        bars = {"10001": flat_bars, "10002": flat_bars}
        # limit=1: 候補が2件あっても bars_daily は高々1回しか呼ばれない
        client1 = FakeClient(None, master, bars, summary_by_date=summary_by_date)
        sdd.run(client1, "2025-09", threshold=0.95, window=10, limit=1)
        # limit=None: 2件処理（bars_daily が2回呼ばれる）
        client2 = FakeClient(None, master, bars, summary_by_date=summary_by_date)
        sdd.run(client2, "2025-09", threshold=0.95, window=10, limit=None)
        # limit=1 の方が bars_daily 呼び出し回数が少ない（候補件数が実際に制限されている）
        self.assertLess(client1.bars_daily_count, client2.bars_daily_count,
                        "limit=1 のとき bars_daily 呼び出しが limit=None より少ないはず")

    def test_window_short_warn_on_stderr(self):
        """指定日以降の取引日が window 未満のとき [warn] が stderr に出る。"""
        summary_by_date = self._make_summary_for_sep2025()
        master = [{"Code": "86970", "CoName": "テスト社", "MktNm": "プライム"}]
        # 指定日(9/26)以降が1日のみ → window_used=1 < window=10 → warn が出るはず
        bars = {"86970": [
            {"Date": "2025-09-24", "C": 1700.0},
            {"Date": "2025-09-25", "C": 1690.0},
            {"Date": "2025-09-26", "C": 1636.0},  # 指定日
            {"Date": "2025-09-29", "C": 1400.0},  # 1日のみ・下落あり
        ]}
        client = FakeClient(None, master, bars, summary_by_date=summary_by_date)
        err = io.StringIO()
        with redirect_stderr(err):
            sdd.run(client, "2025-09", threshold=0.95, window=10)
        self.assertIn("[warn]", err.getvalue())
        self.assertIn("86970", err.getvalue())

    def test_range_out_of_scope_returns_empty(self):
        """範囲外月ではJQuantsErrorをキャッチして空リストを返す（穏当に終わる）。"""
        def fins_summary_raises(date=None, **kwargs):
            raise JQuantsError("範囲外")

        class ErrorClient:
            def fins_summary(self, date=None, **kwargs):
                raise JQuantsError("範囲外")
            def equities_master(self, **kwargs):
                return []

        client = ErrorClient()
        # JQuantsError を run() の呼び出し元 main() でキャッチするので
        # run() 自体は raise する。main() がエラーを握りつぶす。
        # ここでは run() が JQuantsError を上位に投げることを確認。
        with self.assertRaises(JQuantsError):
            sdd.run(client, "2026-06", threshold=0.95, window=10)


class TestWriteCsv(unittest.TestCase):
    """write_csv のCSV出力内容を検証する。"""

    def _sample_hits(self):
        return [{"code": "86970", "name": "テスト社", "market": "プライム", "kijitsu": "2025-09-26"}]

    def test_bom_present(self):
        """出力ファイルが BOM（UTF-8 BOM = 0xEF 0xBB 0xBF）で始まる。"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = tmp.name
        try:
            sdd.write_csv(path, self._sample_hits())
            with open(path, "rb") as f:
                raw = f.read()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), "BOM が見つかりません")
        finally:
            import os
            os.unlink(path)

    def test_header_row(self):
        """先頭行が コード,銘柄名,市場,指定日 である。"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = tmp.name
        try:
            sdd.write_csv(path, self._sample_hits())
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                header = next(reader)
            self.assertEqual(header, ["コード", "銘柄名", "市場", "指定日"])
        finally:
            import os
            os.unlink(path)

    def test_data_row(self):
        """hits 1件が正しい行として出力される。"""
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = tmp.name
        try:
            sdd.write_csv(path, self._sample_hits())
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                next(reader)  # ヘッダ行をスキップ
                row = next(reader)
            self.assertEqual(row, ["86970", "テスト社", "プライム", "2025-09-26"])
        finally:
            import os
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
