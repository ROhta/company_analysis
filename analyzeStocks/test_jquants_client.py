# analyzeStocks/test_jquants_client.py
import json
import tempfile
import unittest

from jquants_client import CachingClient, JQuantsClient, JQuantsError


class FakeTransport:
    """(status, body) を順に返し、呼ばれたURL/ヘッダを記録するfake fetch。"""
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append((url, headers))
        return self._responses.pop(0)


class TestJQuantsClient(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(JQuantsError):
            JQuantsClient(api_key="")

    def test_rejects_invalid_max_retries(self):
        with self.assertRaises(JQuantsError):
            JQuantsClient(api_key="KEY", max_retries=0)

    def test_rejects_negative_min_interval(self):
        with self.assertRaises(JQuantsError):
            JQuantsClient(api_key="KEY", min_interval=-1.0)

    def test_sends_x_api_key_header(self):
        t = FakeTransport([(200, json.dumps({"data": [{"Code": "1"}]}))])
        client = JQuantsClient(api_key="KEY", fetch=t)
        client.equities_master()
        _, headers = t.calls[0]
        self.assertEqual(headers.get("x-api-key"), "KEY")

    def test_follows_pagination(self):
        t = FakeTransport([
            (200, json.dumps({"data": [{"Code": "1"}], "pagination_key": "p2"})),
            (200, json.dumps({"data": [{"Code": "2"}]})),
        ])
        client = JQuantsClient(api_key="KEY", fetch=t)
        rows = client.fins_summary(date="2025-05-14")
        self.assertEqual([r["Code"] for r in rows], ["1", "2"])
        self.assertIn("pagination_key=p2", t.calls[1][0])

    def test_retries_on_429_then_succeeds(self):
        t = FakeTransport([
            (429, json.dumps({"message": "rate"})),
            (200, json.dumps({"data": [{"Code": "1"}]})),
        ])
        sleeps = []
        client = JQuantsClient(api_key="KEY", fetch=t, sleep=sleeps.append, min_interval=0)
        rows = client.bars_daily(code="86970", date="20260202")
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(sleeps), 1)

    def test_raises_with_api_message_on_error(self):
        t = FakeTransport([(403, json.dumps({"message": "not available on your subscription"}))])
        client = JQuantsClient(api_key="KEY", fetch=t)
        with self.assertRaises(JQuantsError) as ctx:
            client.fins_summary(code="86970")
        self.assertIn("subscription", str(ctx.exception))

    def test_raises_on_non_json_body(self):
        t = FakeTransport([(503, "<html>Service Unavailable</html>")])
        client = JQuantsClient(api_key="KEY", fetch=t)
        with self.assertRaises(JQuantsError):
            client.fins_summary()

    def test_raises_after_exhausting_retries(self):
        t = FakeTransport([(429, json.dumps({"message": "rate"})) for _ in range(3)])
        sleeps = []
        client = JQuantsClient(api_key="KEY", fetch=t, max_retries=3, sleep=sleeps.append,
                               min_interval=0)
        with self.assertRaises(JQuantsError):
            client.fins_summary()


class TestRequestPacing(unittest.TestCase):
    """min_interval によるリクエスト間ペーシングのテスト。"""

    def test_paces_each_request_with_min_interval(self):
        # 非429（成功）でもペーシングsleepが1回呼ばれる
        t = FakeTransport([(200, json.dumps({"data": [{"Code": "1"}]}))])
        sleeps = []
        client = JQuantsClient(api_key="KEY", fetch=t, sleep=sleeps.append, min_interval=0.5)
        client.equities_master()
        self.assertIn(0.5, sleeps)
        # 429バックオフは無いのでペーシングの1回だけ
        self.assertEqual(sleeps, [0.5])

    def test_paces_each_page_during_pagination(self):
        # ページごと（=論理リクエストごと）にペーシングされる
        t = FakeTransport([
            (200, json.dumps({"data": [{"Code": "1"}], "pagination_key": "p2"})),
            (200, json.dumps({"data": [{"Code": "2"}]})),
        ])
        sleeps = []
        client = JQuantsClient(api_key="KEY", fetch=t, sleep=sleeps.append, min_interval=0.5)
        client.fins_summary(date="2025-05-14")
        self.assertEqual(sleeps, [0.5, 0.5])

    def test_min_interval_zero_is_noop(self):
        # min_interval=0 ならペーシングsleepは呼ばれない（429も無ければsleep無し）
        t = FakeTransport([(200, json.dumps({"data": []}))])
        sleeps = []
        client = JQuantsClient(api_key="KEY", fetch=t, sleep=sleeps.append, min_interval=0)
        client.fins_summary(date="2025-05-14")
        self.assertEqual(sleeps, [])

    def test_default_min_interval_paces(self):
        # 既定 min_interval（>0）でペーシングが行われる
        t = FakeTransport([(200, json.dumps({"data": []}))])
        sleeps = []
        client = JQuantsClient(api_key="KEY", fetch=t, sleep=sleeps.append)
        client.fins_summary(date="2025-05-14")
        self.assertEqual(len(sleeps), 1)
        self.assertGreater(sleeps[0], 0)


class FakeInner:
    """CachingClient テスト用のシンプルなfakeクライアント。"""
    def __init__(self, summary_data=None, bars_data=None, raise_on_call=False):
        self._summary_data = summary_data or []
        self._bars_data = bars_data or []
        self._raise_on_call = raise_on_call
        self.fins_summary_count = 0
        self.bars_daily_count = 0
        self.equities_master_count = 0

    def fins_summary(self, date=None, **kwargs):
        self.fins_summary_count += 1
        if self._raise_on_call:
            raise JQuantsError("テストエラー")
        return self._summary_data

    def bars_daily(self, code, from_=None, to=None, **kwargs):
        self.bars_daily_count += 1
        if self._raise_on_call:
            raise JQuantsError("テストエラー")
        return self._bars_data

    def equities_master(self, **kwargs):
        self.equities_master_count += 1
        return [{"Code": "99990"}]


class TestCachingClientFinsSummary(unittest.TestCase):
    """CachingClient.fins_summary のキャッシュ動作を検証する。"""

    def test_miss_calls_inner_and_saves_cache(self):
        """キャッシュなし: inner を呼び、JSONファイルを保存し、返り値が一致する。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            inner = FakeInner(summary_data=[{"Code": "1"}])
            client = CachingClient(inner, tmpdir)
            result = client.fins_summary(date="2025-10-01")
            self.assertEqual(result, [{"Code": "1"}])
            self.assertEqual(inner.fins_summary_count, 1)
            # キャッシュファイルが作成されている
            import os
            cache_path = os.path.join(tmpdir, "summary", "2025-10-01.json")
            self.assertTrue(os.path.exists(cache_path))

    def test_corrupt_cache_is_treated_as_miss(self):
        """壊れたキャッシュは「無し」扱いで inner を呼び、正しい内容で上書きする。"""
        import json
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "summary", "2025-10-01.json")
            os.makedirs(os.path.dirname(cache_path), exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                f.write("{壊れたJSON")  # 途中書き込み等を模した不正JSON
            inner = FakeInner(summary_data=[{"Code": "X"}])
            client = CachingClient(inner, tmpdir)
            result = client.fins_summary(date="2025-10-01")
            self.assertEqual(result, [{"Code": "X"}])     # ミス扱いで inner から取得
            self.assertEqual(inner.fins_summary_count, 1)
            with open(cache_path, encoding="utf-8") as f:
                self.assertEqual(json.load(f), [{"Code": "X"}])  # 正しい内容で上書き

    def test_write_leaves_no_temp_file(self):
        """アトミック書き込み: 成功後に .tmp が残らない。"""
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            inner = FakeInner(summary_data=[{"Code": "1"}])
            client = CachingClient(inner, tmpdir)
            client.fins_summary(date="2025-10-01")
            files = os.listdir(os.path.join(tmpdir, "summary"))
            self.assertEqual(files, ["2025-10-01.json"])

    def test_hit_does_not_call_inner(self):
        """キャッシュあり: 2回目は inner を呼ばずキャッシュから返す。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            inner = FakeInner(summary_data=[{"Code": "1"}])
            client = CachingClient(inner, tmpdir)
            # 1回目: miss → 保存
            result1 = client.fins_summary(date="2025-10-01")
            # 2回目: hit → inner 呼ばず
            result2 = client.fins_summary(date="2025-10-01")
            self.assertEqual(result1, result2)
            self.assertEqual(inner.fins_summary_count, 1)  # 1回のみ

    def test_error_does_not_save_cache_and_propagates(self):
        """inner が例外を投げた場合、キャッシュファイルを書かず例外を伝播する。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            inner = FakeInner(raise_on_call=True)
            client = CachingClient(inner, tmpdir)
            with self.assertRaises(JQuantsError):
                client.fins_summary(date="2025-10-01")
            # キャッシュファイルが存在しない
            import os
            cache_path = os.path.join(tmpdir, "summary", "2025-10-01.json")
            self.assertFalse(os.path.exists(cache_path))

    def test_resume_after_error(self):
        """inner 失敗→キャッシュなし→inner 正常化→取得・保存される（再開相当）。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            inner = FakeInner(raise_on_call=True)
            client = CachingClient(inner, tmpdir)
            # 1回目: 失敗 → キャッシュなし
            with self.assertRaises(JQuantsError):
                client.fins_summary(date="2025-10-01")
            # inner を正常化して再試行
            inner._raise_on_call = False
            inner._summary_data = [{"Code": "RESUME"}]
            result = client.fins_summary(date="2025-10-01")
            self.assertEqual(result, [{"Code": "RESUME"}])
            # 今度はキャッシュが保存される
            import os
            cache_path = os.path.join(tmpdir, "summary", "2025-10-01.json")
            self.assertTrue(os.path.exists(cache_path))

    def test_no_cache_when_date_is_none(self):
        """date 未指定の呼び出しは inner に委譲してキャッシュしない。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            inner = FakeInner(summary_data=[{"Code": "1"}])
            client = CachingClient(inner, tmpdir)
            client.fins_summary()  # date=None
            client.fins_summary()  # date=None (2回目)
            # inner は2回呼ばれる（キャッシュされない）
            self.assertEqual(inner.fins_summary_count, 2)


class TestCachingClientEquitiesMaster(unittest.TestCase):
    """equities_master はキャッシュせず毎回 inner を呼ぶことを検証する。"""

    def test_equities_master_always_calls_inner(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            inner = FakeInner()
            client = CachingClient(inner, tmpdir)
            client.equities_master()
            client.equities_master()
            self.assertEqual(inner.equities_master_count, 2)


class TestCachingClientBarsDaily(unittest.TestCase):
    """bars_daily のキャッシュ動作を検証する。"""

    def test_bars_daily_caches_on_second_call(self):
        """2回目は inner を呼ばずキャッシュから返す。"""
        with tempfile.TemporaryDirectory() as tmpdir:
            inner = FakeInner(bars_data=[{"Date": "2025-09-30", "C": 1000.0}])
            client = CachingClient(inner, tmpdir)
            result1 = client.bars_daily("86970", from_="20250901", to="20251031")
            result2 = client.bars_daily("86970", from_="20250901", to="20251031")
            self.assertEqual(result1, result2)
            self.assertEqual(inner.bars_daily_count, 1)


if __name__ == "__main__":
    unittest.main()
