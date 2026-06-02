# analyzeStocks/jquants_client.py
"""J-Quants API V2 の薄いクライアント(標準ライブラリのみ)。"""
import json
import os
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
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")


class JQuantsClient:
    def __init__(self, api_key, fetch=_default_fetch, max_retries=5, sleep=time.sleep,
                 min_interval=0.34):
        if not api_key:
            raise JQuantsError("JQUANTS_API_KEY が設定されていません")
        if max_retries < 1:
            raise JQuantsError("max_retries は1以上である必要があります")
        if min_interval < 0:
            raise JQuantsError("min_interval は0以上である必要があります")
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


class CachingClient:
    """JQuantsClient と同じI/Fを持つディスクキャッシュラッパー。

    fins_summary(date=d) および bars_daily のレスポンスを JSON ファイルにキャッシュし、
    再実行時はAPI呼び出しをスキップして続きから再開できる。
    - 成功時のみキャッシュ保存（失敗は絶対にキャッシュしない）。
    - equities_master は新規上場の鮮度のためキャッシュせず inner に委譲。
    - date 未指定の fins_summary 呼び出しは inner に委譲。
    """

    def __init__(self, inner, cache_dir):
        self._inner = inner
        self._cache_dir = cache_dir

    def _read_cache(self, path):
        """キャッシュがあれば読んで返す。無い/壊れている場合は None（ベストエフォート）。

        途中書き込み等で壊れたキャッシュは「無し」として扱い、再取得させる
        （壊れたファイルで毎回の再実行が落ちるのを防ぐ）。
        """
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _write_cache(self, path, data):
        """data を JSON でアトミックに保存する（temp に書いて os.replace で差し替え）。

        プロセス中断・ディスク枯渇等で部分的に書かれたファイルが
        正規のキャッシュとして残らないようにする。
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(tmp, path)

    def fins_summary(self, date=None, **kwargs):
        """date 指定時のみキャッシュ対象。未指定は inner に委譲。"""
        if date is None:
            return self._inner.fins_summary(date=date, **kwargs)
        path = os.path.join(self._cache_dir, "summary", "{}.json".format(date))
        cached = self._read_cache(path)
        if cached is not None:
            return cached
        result = self._inner.fins_summary(date=date, **kwargs)
        self._write_cache(path, result)
        return result

    def equities_master(self, **kwargs):
        """新規上場の鮮度のためキャッシュせず inner に委譲する。"""
        return self._inner.equities_master(**kwargs)

    def bars_daily(self, code, from_=None, to=None, **kwargs):
        """from_/to の組み合わせをキーにキャッシュする。"""
        path = os.path.join(
            self._cache_dir, "bars",
            "{}_{}_{}".format(code, from_ or "", to or "") + ".json",
        )
        cached = self._read_cache(path)
        if cached is not None:
            return cached
        result = self._inner.bars_daily(code, from_=from_, to=to, **kwargs)
        self._write_cache(path, result)
        return result
