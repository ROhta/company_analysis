# analyzeStocks/jquants_client.py
"""J-Quants API V2 の薄いクライアント(標準ライブラリのみ)。"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.jquants.com/v2"
DEFAULT_TIMEOUT = 30  # ネットワークハング防止のデフォルトタイムアウト（秒）


class JQuantsError(RuntimeError):
    pass


def _default_fetch(url, headers):
    """(status_code, body_text) を返す。HTTPError時もbodyを読んで返す。"""
    # url は BASE_URL(固定)+ハードコードパス+urlencode済みパラメータで構成され、
    # ユーザー入力はクエリ値のみ。ホスト/スキームは外部から変更されないため SSRF リスクなし。
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:  # nosemgrep
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


class JQuantsClient:
    def __init__(self, api_key, fetch=_default_fetch, max_retries=5, sleep=time.sleep,
                 min_interval=0.34):
        if not api_key:
            raise JQuantsError("JQUANTS_API_KEY が設定されていません")
        self._api_key = api_key
        self._fetch = fetch
        self._max_retries = max_retries
        self._sleep = sleep
        # 論理リクエストごとに最低 min_interval 秒の間隔を確保する（レート制限緩和）。
        # 0 ならペーシングしない（既存テスト互換）。
        self._min_interval = min_interval

    def _request_with_retry(self, url, headers):
        # 論理リクエスト開始時にペーシング。429時の指数バックオフは別途ループ内で行う。
        if self._min_interval:
            self._sleep(self._min_interval)
        status, body = None, None
        for attempt in range(self._max_retries):
            status, body = self._fetch(url, headers)
            if status != 429:
                return status, body
            if attempt < self._max_retries - 1:
                self._sleep(min(2 ** attempt, 30))
        return status, body

    def _get(self, path, params):
        headers = {"x-api-key": self._api_key}
        results = []
        pagination_key = None
        while True:
            query = dict(params)
            if pagination_key:
                query["pagination_key"] = pagination_key
            url = "{}{}?{}".format(BASE_URL, path, urllib.parse.urlencode(query))
            status, body = self._request_with_retry(url, headers)
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                raise JQuantsError("HTTP {}: (non-JSON body) {}".format(status, body[:200]))
            if status != 200:
                raise JQuantsError(payload.get("message", "HTTP {}: {}".format(status, body)))
            results.extend(payload.get("data", []))
            pagination_key = payload.get("pagination_key")
            if not pagination_key:
                break
        return results

    def fins_summary(self, date=None, code=None):
        """決算サマリを取得する。V2 は date または code のみ受け付ける。"""
        params = {}
        if code:
            params["code"] = code
        if date:
            params["date"] = date
        return self._get("/fins/summary", params)

    def equities_master(self, code=None):
        params = {"code": code} if code else {}
        return self._get("/equities/master", params)

    def bars_daily(self, code, date=None, from_=None, to=None):
        params = {"code": code}
        if date:
            params["date"] = date
        if from_:
            params["from"] = from_
        if to:
            params["to"] = to
        return self._get("/equities/bars/daily", params)
