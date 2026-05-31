# analyzeStocks/test_jquants_client.py
import json
import unittest

from jquants_client import JQuantsClient, JQuantsError


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
        client = JQuantsClient(api_key="KEY", fetch=t, sleep=sleeps.append)
        rows = client.bars_daily(code="86970", date="20260202")
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(sleeps), 1)

    def test_raises_with_api_message_on_error(self):
        t = FakeTransport([(403, json.dumps({"message": "not available on your subscription"}))])
        client = JQuantsClient(api_key="KEY", fetch=t)
        with self.assertRaises(JQuantsError) as ctx:
            client.fins_summary(code="86970")
        self.assertIn("subscription", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
