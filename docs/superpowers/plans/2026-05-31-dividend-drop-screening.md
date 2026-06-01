# 配当権利落ち下落スクリーニング 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** J-Quants V2 のみを使い、配当を出すプライム/スタンダード銘柄の「権利落ち後10営業日以内に指定日終値の95%未満まで下落した銘柄」を end-to-end で抽出するPythonツールを作る。

**Architecture:** 純粋ロジック（`calendar_logic.py`）／薄いI/Oクライアント（`jquants_client.py`）／CLIオーケストレーション（`screen_dividend_drop.py`）の3分割。純粋関数を `unittest` で厚くテストし、クライアントは注入可能な transport でネットワーク非依存にテストする。

**Tech Stack:** Python 3 標準ライブラリのみ（`urllib.request` / `json` / `datetime` / `csv` / `argparse` / `unittest`）。第三者依存なし。設計書: `docs/superpowers/specs/2026-05-31-dividend-drop-screening-design.md`。

**前提:** 作業は feature ブランチ `feat/jquants-v2-and-dividend-screening`（PR #14）上で継続。テストは `analyzeStocks/` ディレクトリで実行（`cd analyzeStocks && python3 -m unittest ...`）。

---

> **実装後のアップデート（計画との差分・2026-06-01追記）**
> 本計画はTask 1〜10の初期設計。実装中に以下が変わった。**現在の正は `analyzeStocks/README.md` とソース（全テスト77件）**で、本書は計画時点の記録として残す。
> - 列挙: `fins_summary(from_/to)` 一括 → `fins_summary(date=)` を開示日(平日)で反復（APIが from/to 非対応のため）。`disclosure_dates` の窓は対象月末+60日（約44コール）。
> - 追加: `--limit` / `--plan`（プラン別レート） / `--no-cache` / ディスクキャッシュ `CachingClient` / 終了コード分離(0/1/2) / `--retry`・`--retry-wait`（自動再試行）。
> - `run_until_done.sh` を一度追加したが、再試行をPython(`--retry`)へ統合し削除。
> - 型は `typing.NamedTuple`（`DividendEvent` / `AnalysisResult`）。

## ファイル構成

```
analyzeStocks/
  calendar_logic.py         # 純粋関数（_to_float, parse_date, dividend_events,
                            #            filter_events_by_month, settlement_date, analyze_drop）
  jquants_client.py         # JQuantsClient（x-api-key/ページネーション/429リトライ/エラー検知）
  screen_dividend_drop.py   # CLI + main()オーケストレーション
  test_calendar_logic.py    # 純粋関数のテスト
  test_jquants_client.py    # クライアントのテスト（transport注入）
  README.md                 # 新ツール用に書き換え（最終タスク）
  screen_10days_drop_95pct.zsh  # 削除（最終タスク）
```

---

## Task 1: 値変換ヘルパー `_to_float` / `parse_date`

**Files:**
- Create: `analyzeStocks/calendar_logic.py`
- Test: `analyzeStocks/test_calendar_logic.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd analyzeStocks && python3 -m unittest test_calendar_logic -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'calendar_logic'`）

- [ ] **Step 3: Write minimal implementation**

```python
# analyzeStocks/calendar_logic.py
"""配当権利落ちスクリーニングの純粋ロジック（ネットワーク非依存）。"""
import datetime


def _to_float(value):
    """空文字・'-'・None・非数値は None、数値文字列は float に変換する。"""
    if value is None:
        return None
    s = str(value).strip()
    if s in ("", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(value):
    """'YYYY-MM-DD' または 'YYYYMMDD' を datetime.date に変換する。"""
    s = str(value).strip()
    if "-" in s:
        return datetime.date.fromisoformat(s)
    return datetime.date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd analyzeStocks && python3 -m unittest test_calendar_logic -v`
Expected: PASS（5 tests）

- [ ] **Step 5: Commit**

```bash
git add analyzeStocks/calendar_logic.py analyzeStocks/test_calendar_logic.py
git commit -m "feat(analyzeStocks): 値変換ヘルパー _to_float / parse_date を追加" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: 配当イベント抽出 `dividend_events`

決算サマリ行から権利確定イベント `(code, record_date, kind, amount)` を抽出する。FY型→期末配当(`DivFY`)、2Q型→中間配当(`Div2Q`)。配当>0のみ。`(code, record_date)` で重複排除。

**Files:**
- Modify: `analyzeStocks/calendar_logic.py`
- Test: `analyzeStocks/test_calendar_logic.py`

- [ ] **Step 1: Write the failing test**

```python
# analyzeStocks/test_calendar_logic.py に追記
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd analyzeStocks && python3 -m unittest test_calendar_logic.TestDividendEvents -v`
Expected: FAIL（`AttributeError: module 'calendar_logic' has no attribute 'dividend_events'`）

- [ ] **Step 3: Write minimal implementation**

```python
# analyzeStocks/calendar_logic.py に追記（先頭の import 群に collections を追加）
import collections

DividendEvent = collections.namedtuple(
    "DividendEvent", ["code", "record_date", "kind", "amount"]
)


def dividend_events(summary_rows):
    """決算サマリ行から配当の権利確定イベントを抽出する。

    FY型→期末配当(DivFY) / 2Q型→中間配当(Div2Q)。配当>0のみ。
    record_date は期末日 CurPerEn。(code, record_date) で重複排除して
    record_date 昇順で返す。
    """
    events = {}
    for row in summary_rows:
        doc = str(row.get("DocType", ""))
        if doc.startswith("FYFinancialStatements"):
            amount = _to_float(row.get("DivFY"))
            kind = "FY"
        elif doc.startswith("2QFinancialStatements"):
            amount = _to_float(row.get("Div2Q"))
            kind = "2Q"
        else:
            continue
        if amount is None or amount <= 0:
            continue
        cur_per_en = row.get("CurPerEn")
        if not cur_per_en:
            continue
        code = row.get("Code")
        if not code:
            continue
        record_date = parse_date(cur_per_en)
        key = (code, record_date)
        if key not in events:
            events[key] = DividendEvent(code, record_date, kind, amount)
    return sorted(events.values(), key=lambda e: (e.record_date, e.code))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd analyzeStocks && python3 -m unittest test_calendar_logic.TestDividendEvents -v`
Expected: PASS（3 tests）

- [ ] **Step 5: Commit**

```bash
git add analyzeStocks/calendar_logic.py analyzeStocks/test_calendar_logic.py
git commit -m "feat(analyzeStocks): 決算サマリから配当権利確定イベントを抽出する dividend_events を追加" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: 対象月フィルタ `filter_events_by_month`

権利確定日が指定の年月(YYYY-MM)に入るイベントだけに絞る。

**Files:**
- Modify: `analyzeStocks/calendar_logic.py`
- Test: `analyzeStocks/test_calendar_logic.py`

- [ ] **Step 1: Write the failing test**

```python
# analyzeStocks/test_calendar_logic.py に追記
class TestFilterEventsByMonth(unittest.TestCase):
    def test_keeps_only_matching_year_month(self):
        events = [
            cl.DividendEvent("1", datetime.date(2025, 9, 30), "2Q", 25.0),
            cl.DividendEvent("2", datetime.date(2025, 3, 31), "FY", 10.0),
            cl.DividendEvent("3", datetime.date(2025, 9, 1), "FY", 5.0),
        ]
        got = cl.filter_events_by_month(events, "2025-09")
        self.assertEqual({e.code for e in got}, {"1", "3"})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd analyzeStocks && python3 -m unittest test_calendar_logic.TestFilterEventsByMonth -v`
Expected: FAIL（`AttributeError`）

- [ ] **Step 3: Write minimal implementation**

```python
# analyzeStocks/calendar_logic.py に追記
def filter_events_by_month(events, year_month):
    """year_month('YYYY-MM') に record_date が一致するイベントだけ返す。"""
    year, month = (int(x) for x in year_month.split("-"))
    return [e for e in events if e.record_date.year == year and e.record_date.month == month]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd analyzeStocks && python3 -m unittest test_calendar_logic.TestFilterEventsByMonth -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add analyzeStocks/calendar_logic.py analyzeStocks/test_calendar_logic.py
git commit -m "feat(analyzeStocks): 権利確定月で絞り込む filter_events_by_month を追加" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: 指定日算出 `settlement_date`

権利確定日(基準日)の2営業日前=指定日(権利付最終日)。営業日は株価系列の取引日リストから判定。8697の実データ(基準日2025-09-30→指定日2025-09-26)で検証。

**Files:**
- Modify: `analyzeStocks/calendar_logic.py`
- Test: `analyzeStocks/test_calendar_logic.py`

- [ ] **Step 1: Write the failing test**

```python
# analyzeStocks/test_calendar_logic.py に追記
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd analyzeStocks && python3 -m unittest test_calendar_logic.TestSettlementDate -v`
Expected: FAIL（`AttributeError`）

- [ ] **Step 3: Write minimal implementation**

```python
# analyzeStocks/calendar_logic.py に追記
def settlement_date(record_date, trading_days):
    """基準日 record_date の2営業日前(=指定日/権利付最終日)を返す。

    trading_days は date のリスト(順不同可)。record_date より前の取引日が
    2日に満たない場合は None。
    """
    before = sorted(d for d in trading_days if d < record_date)
    if len(before) < 2:
        return None
    return before[-2]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd analyzeStocks && python3 -m unittest test_calendar_logic.TestSettlementDate -v`
Expected: PASS（3 tests）

- [ ] **Step 5: Commit**

```bash
git add analyzeStocks/calendar_logic.py analyzeStocks/test_calendar_logic.py
git commit -m "feat(analyzeStocks): 基準日の2営業日前=指定日を求める settlement_date を追加" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: 下落判定 `analyze_drop`（既存zshロジックの移植・等価担保）

指定日終値 vs 指定日以降 window 営業日の最安値(null除外)。既存zshの 1636/1490 フィクスチャで等価性を担保。

**Files:**
- Modify: `analyzeStocks/calendar_logic.py`
- Test: `analyzeStocks/test_calendar_logic.py`

- [ ] **Step 1: Write the failing test**

```python
# analyzeStocks/test_calendar_logic.py に追記
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd analyzeStocks && python3 -m unittest test_calendar_logic.TestAnalyzeDrop -v`
Expected: FAIL（`AttributeError`）

- [ ] **Step 3: Write minimal implementation**

```python
# analyzeStocks/calendar_logic.py に追記
AnalysisResult = collections.namedtuple(
    "AnalysisResult", ["ref_close", "min_close", "min_date", "ratio", "hit"]
)


def analyze_drop(price_rows, kijitsu_date, window, threshold):
    """指定日終値と、指定日以降 window 営業日の最安値(null除外)で下落判定する。

    price_rows は {'Date','C'} のリスト。指定日が系列に無い/終値が欠損なら None。
    対象期間に有効な終値が無ければ None。
    """
    rows = sorted(price_rows, key=lambda r: parse_date(r["Date"]))
    idx = None
    for i, r in enumerate(rows):
        if parse_date(r["Date"]) == kijitsu_date:
            idx = i
            break
    if idx is None:
        return None
    ref_close = _to_float(rows[idx].get("C"))
    if ref_close is None or ref_close <= 0:
        return None
    after = rows[idx + 1: idx + 1 + window]
    closes = [
        (parse_date(r["Date"]), _to_float(r.get("C")))
        for r in after
    ]
    closes = [(d, c) for d, c in closes if c is not None]
    if not closes:
        return None
    min_date, min_close = min(closes, key=lambda dc: dc[1])
    return AnalysisResult(
        ref_close=ref_close,
        min_close=min_close,
        min_date=min_date,
        ratio=min_close / ref_close,
        hit=min_close < threshold * ref_close,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd analyzeStocks && python3 -m unittest test_calendar_logic -v`
Expected: PASS（全テスト）

- [ ] **Step 5: Commit**

```bash
git add analyzeStocks/calendar_logic.py analyzeStocks/test_calendar_logic.py
git commit -m "feat(analyzeStocks): 下落判定 analyze_drop を追加(既存zshの1636/1490と等価)" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: J-Quants クライアント `JQuantsClient`

`x-api-key` 認証・`pagination_key` 追従・429リトライ・非200時のエラーメッセージ送出。transport(`fetch`)と`sleep`を注入可能にしてネットワーク非依存にテストする。

**Files:**
- Create: `analyzeStocks/jquants_client.py`
- Test: `analyzeStocks/test_jquants_client.py`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd analyzeStocks && python3 -m unittest test_jquants_client -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'jquants_client'`）

- [ ] **Step 3: Write minimal implementation**

```python
# analyzeStocks/jquants_client.py
"""J-Quants API V2 の薄いクライアント(標準ライブラリのみ)。"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.jquants.com/v2"


class JQuantsError(RuntimeError):
    pass


def _default_fetch(url, headers):
    """(status_code, body_text) を返す。HTTPError時もbodyを読んで返す。"""
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")


class JQuantsClient:
    def __init__(self, api_key, fetch=_default_fetch, max_retries=5, sleep=time.sleep):
        if not api_key:
            raise JQuantsError("JQUANTS_API_KEY が設定されていません")
        self._api_key = api_key
        self._fetch = fetch
        self._max_retries = max_retries
        self._sleep = sleep

    def _request_with_retry(self, url, headers):
        status, body = None, None
        for attempt in range(self._max_retries):
            status, body = self._fetch(url, headers)
            if status == 429:
                self._sleep(min(2 ** attempt, 30))
                continue
            return status, body
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
            payload = json.loads(body)
            if status != 200:
                raise JQuantsError(payload.get("message", "HTTP {}: {}".format(status, body)))
            results.extend(payload.get("data", []))
            pagination_key = payload.get("pagination_key")
            if not pagination_key:
                break
        return results

    def fins_summary(self, date=None, from_=None, to=None, code=None):
        params = {}
        if code:
            params["code"] = code
        if date:
            params["date"] = date
        if from_:
            params["from"] = from_
        if to:
            params["to"] = to
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd analyzeStocks && python3 -m unittest test_jquants_client -v`
Expected: PASS（5 tests）

- [ ] **Step 5: Commit**

```bash
git add analyzeStocks/jquants_client.py analyzeStocks/test_jquants_client.py
git commit -m "feat(analyzeStocks): J-Quants V2クライアント(x-api-key/ページネーション/429)を追加" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: 既定対象月 `default_target_month` と開示日スキャン範囲 `disclosure_scan_range`

`--month` 未指定時の既定（今日からおよそ4ヶ月前）と、対象月の権利確定イベントを拾うための開示日スキャン範囲（対象月末〜対象月末+3ヶ月）を求める純粋関数。

**Files:**
- Modify: `analyzeStocks/calendar_logic.py`
- Test: `analyzeStocks/test_calendar_logic.py`

- [ ] **Step 1: Write the failing test**

```python
# analyzeStocks/test_calendar_logic.py に追記
class TestTargetMonthHelpers(unittest.TestCase):
    def test_default_target_month_is_about_four_months_back(self):
        self.assertEqual(cl.default_target_month(datetime.date(2026, 5, 31)), "2026-01")
        self.assertEqual(cl.default_target_month(datetime.date(2026, 2, 15)), "2025-10")

    def test_disclosure_scan_range_covers_period_plus_three_months(self):
        frm, to = cl.disclosure_scan_range("2025-09")
        self.assertEqual(frm, "2025-09-30")   # 対象月末から
        self.assertEqual(to, "2025-12-31")    # +3ヶ月の月末まで
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd analyzeStocks && python3 -m unittest test_calendar_logic.TestTargetMonthHelpers -v`
Expected: FAIL（`AttributeError`）

- [ ] **Step 3: Write minimal implementation**

```python
# analyzeStocks/calendar_logic.py に追記
def _month_end(year, month):
    if month == 12:
        return datetime.date(year, 12, 31)
    return datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)


def _shift_month(year, month, delta):
    """(year, month) を delta ヶ月ずらした (year, month) を返す。"""
    index = (year * 12 + (month - 1)) + delta
    return index // 12, index % 12 + 1


def default_target_month(today):
    """データ遅延を見越して today のおよそ4ヶ月前の年月 'YYYY-MM' を返す。"""
    year, month = _shift_month(today.year, today.month, -4)
    return "{:04d}-{:02d}".format(year, month)


def disclosure_scan_range(year_month):
    """対象月の権利確定イベントを拾うための開示日レンジ('YYYY-MM-DD','YYYY-MM-DD')。

    対象月末から、配当が開示される猶予を見て +3ヶ月の月末まで。
    """
    year, month = (int(x) for x in year_month.split("-"))
    start = _month_end(year, month)
    end_year, end_month = _shift_month(year, month, 3)
    end = _month_end(end_year, end_month)
    return start.isoformat(), end.isoformat()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd analyzeStocks && python3 -m unittest test_calendar_logic.TestTargetMonthHelpers -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add analyzeStocks/calendar_logic.py analyzeStocks/test_calendar_logic.py
git commit -m "feat(analyzeStocks): 既定対象月と開示日スキャン範囲のヘルパーを追加" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: オーケストレーション `screen_dividend_drop.py`（CLI + main）

純粋関数とクライアントを束ね、列挙→指定日算出→市場/銘柄名付与→下落判定→出力を行う。`build_market_index` だけ純粋関数として切り出してテストし、`main()` はfakeクライアントでスモークテストする。

**Files:**
- Create: `analyzeStocks/screen_dividend_drop.py`
- Modify: `analyzeStocks/test_calendar_logic.py`（`build_market_index` のテストを追記）
- Test: `analyzeStocks/test_screen_dividend_drop.py`（main のスモークテスト）

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd analyzeStocks && python3 -m unittest test_screen_dividend_drop -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'screen_dividend_drop'`）

- [ ] **Step 3: Write minimal implementation**

```python
# analyzeStocks/screen_dividend_drop.py
"""配当権利落ち後の下落銘柄スクリーニング(J-Quants V2完結, 標準ライブラリのみ)。"""
import argparse
import csv
import datetime
import os
import sys

import calendar_logic as cl
from jquants_client import JQuantsClient, JQuantsError

TARGET_MARKETS = ("プライム", "スタンダード")
BARS_PAD_DAYS = 20  # 指定日算出のため基準日前後に確保する暦日


def build_market_index(master_rows):
    """master行から {code: (CoName, MktNm)} を作る。プライム/スタンダードのみ。"""
    index = {}
    for row in master_rows:
        if row.get("MktNm") in TARGET_MARKETS:
            index[row["Code"]] = (row.get("CoName", ""), row.get("MktNm", ""))
    return index


def run(client, target_month, threshold, window):
    """スクリーニング本体。該当銘柄の dict リストを返し、結果を標準出力する。"""
    frm, to = cl.disclosure_scan_range(target_month)
    summary_rows = client.fins_summary(from_=frm, to=to)
    events = cl.filter_events_by_month(cl.dividend_events(summary_rows), target_month)

    market_index = build_market_index(client.equities_master())

    hits = []
    for ev in events:
        if ev.code not in market_index:
            continue
        record = ev.record_date
        bars = client.bars_daily(
            ev.code,
            from_=(record - datetime.timedelta(days=BARS_PAD_DAYS)).strftime("%Y%m%d"),
            to=(record + datetime.timedelta(days=BARS_PAD_DAYS + window * 2)).strftime("%Y%m%d"),
        )
        if not bars:
            continue
        trading_days = [cl.parse_date(b["Date"]) for b in bars]
        kijitsu = cl.settlement_date(record, trading_days)
        if kijitsu is None:
            continue
        result = cl.analyze_drop(bars, kijitsu, window=window, threshold=threshold)
        if result is None or not result.hit:
            continue
        name, market = market_index[ev.code]
        hits.append({
            "code": ev.code,
            "name": name,
            "market": market,
            "kijitsu": kijitsu.isoformat(),
            "ref_close": result.ref_close,
            "min_close": result.min_close,
            "min_date": result.min_date.isoformat(),
            "drop_pct": round((1 - result.ratio) * 100, 2),
        })

    _print_results(hits, target_month, threshold)
    return hits


def _print_results(hits, target_month, threshold):
    print("=== {} 権利確定・指定日終値の{:.0f}%未満まで下落した銘柄 ===".format(
        target_month, threshold * 100), file=sys.stderr)
    if not hits:
        print("該当銘柄はありませんでした。", file=sys.stderr)
        return
    for h in hits:
        print("{code} {name} ({market}) 指定日{kijitsu} 終値{ref_close}→最安{min_close}"
              "({min_date}) 下落{drop_pct}%".format(**h))


def write_csv(path, hits):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["コード", "銘柄名", "市場", "指定日"])
        for h in hits:
            writer.writerow([h["code"], h["name"], h["market"], h["kijitsu"]])


def main(argv=None):
    parser = argparse.ArgumentParser(description="配当権利落ち後の下落銘柄スクリーニング")
    parser.add_argument("--month", help="対象の権利確定月 YYYY-MM(未指定なら約4ヶ月前)")
    parser.add_argument("--threshold", type=float, default=0.95)
    parser.add_argument("--window", type=int, default=10)
    parser.add_argument("--csv", help="中間候補リストCSVの出力先")
    args = parser.parse_args(argv)

    api_key = os.environ.get("JQUANTS_API_KEY", "")
    target_month = args.month or cl.default_target_month(datetime.date.today())
    if not args.month:
        print("[info] --month未指定のため既定 {} を使用(範囲外なら--monthで指定)".format(target_month),
              file=sys.stderr)

    try:
        client = JQuantsClient(api_key=api_key)
        hits = run(client, target_month, args.threshold, args.window)
    except JQuantsError as e:
        print("[error] {}".format(e), file=sys.stderr)
        return 1

    if args.csv:
        write_csv(args.csv, hits)
        print("[info] 中間候補リストを {} に出力しました".format(args.csv), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd analyzeStocks && python3 -m unittest test_screen_dividend_drop -v`
Expected: PASS（2 tests）

- [ ] **Step 5: Commit**

```bash
git add analyzeStocks/screen_dividend_drop.py analyzeStocks/test_screen_dividend_drop.py
git commit -m "feat(analyzeStocks): end-to-endオーケストレーション screen_dividend_drop.py を追加" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: 実APIでの end-to-end 動作確認

**Files:** なし（手動実行・検証のみ）

- [ ] **Step 1: 全テストを通す**

Run: `cd analyzeStocks && python3 -m unittest discover -p 'test_*.py' -v`
Expected: 全テスト PASS

- [ ] **Step 2: 実APIキーで実行（契約範囲内の月を指定）**

Run:
```bash
cd analyzeStocks && python3 screen_dividend_drop.py --month 2025-09 --csv /tmp/candidates.csv
```
Expected: エラーなく実行され、該当銘柄が0件以上表示される。`/tmp/candidates.csv` にコード/銘柄名/市場/指定日が出力される。

- [ ] **Step 3: 範囲外月での挙動確認**

Run: `cd analyzeStocks && python3 screen_dividend_drop.py --month 2026-05`
Expected: データ提供範囲外に起因する空結果、または `[error]` でAPIの "subscription covers..." 系メッセージが明示される（黙ってクラッシュしない）。

- [ ] **Step 4: 妥当性の目視確認**

`--month 2025-09` の結果数件について、設計の意図（指定日=基準日の2営業日前、下落率が95%閾値を満たす）と矛盾しないか目視確認する。問題があれば該当タスクに戻る。

---

## Task 10: 旧zsh削除と README 書き換え

**Files:**
- Delete: `analyzeStocks/screen_10days_drop_95pct.zsh`
- Modify: `analyzeStocks/README.md`

- [ ] **Step 1: 旧スクリプトを削除**

```bash
git rm analyzeStocks/screen_10days_drop_95pct.zsh
```

- [ ] **Step 2: README を新ツール用に全面更新**

`analyzeStocks/README.md` を以下の内容に置き換える:

````markdown
## 概要

- [J-Quants API](https://jpx.gitbook.io/j-quants-ja/api-reference) V2 を使用して、株の分析を行う
- 配当を出すプライム/スタンダード銘柄について、**権利落ち（指定日）後10営業日以内の最安値が指定日終値の95%未満**になった銘柄を抽出する

## 用意するもの

- Python 3（標準ライブラリのみ。第三者パッケージのインストール不要）
- J-Quants APIの**APIキー**（[J-Quants Dashboard](https://jpx-jquants.com/dashboard/menu/?lang=ja)で発行）
  - `export JQUANTS_API_KEY=<発行したキー>`

## 使い方

```sh
export JQUANTS_API_KEY=<発行したキー>
python3 screen_dividend_drop.py [--month YYYY-MM] [--threshold 0.95] [--window 10] [--csv 出力先.csv]
```

- `--month`: 対象の権利確定月（未指定なら約4ヶ月前を既定採用）
- `--threshold` / `--window`: 比較割合（既定0.95）・営業日数（既定10）
- `--csv`: 候補リスト（コード/銘柄名/市場/指定日）を任意で出力

## 仕組み

1. `/fins/summary`（決算サマリ）を開示日レンジで取得し、配当を出すFY（期末）・2Q（中間）から権利確定日(`CurPerEn`)を導出
2. 指定日 = 権利確定日の2営業日前（営業日は株価系列から判定）
3. `/equities/master` で市場区分(`MktNm`)・銘柄名(`CoName`)を付与（プライム/スタンダードのみ）
4. `/equities/bars/daily` で指定日終値と以降10営業日の最安値を比較し95%判定

## 注意事項

- 取得できる日付範囲は契約プランのデータ提供期間に依存する。`--month` がその範囲外だと結果が空、またはAPIの範囲外メッセージが表示される。
- 対象は「配当を出す銘柄」。優待のみ・無配当の銘柄は対象外（`/fins/dividend` はプラン非対応のため `/fins/summary` から導出）。
- 終値は調整前の生値（V2の `C`）で比較する。

## テスト

```sh
cd analyzeStocks && python3 -m unittest discover -p 'test_*.py' -v
```
````

- [ ] **Step 3: テストが壊れていないか確認**

Run: `cd analyzeStocks && python3 -m unittest discover -p 'test_*.py' -v`
Expected: 全テスト PASS

- [ ] **Step 4: Commit**

```bash
git add -A analyzeStocks/
git commit -m "refactor(analyzeStocks): 旧zshを削除しREADMEを新Pythonツール用に更新" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review 結果

- **Spec coverage:** §2データソース→Task6/8、§3.1指定日→Task4、§3.2下落判定→Task5、§3.3市場/銘柄名→Task8(build_market_index)、§4標準ライブラリ構成→全タスク、§5エラー/範囲→Task6(エラー送出)/Task8(範囲外明示)/Task9-3、§6データフロー→Task8、§8テスト(1636/1490・8697)→Task4/5、§10完了定義(zsh削除・README)→Task10。全項目に対応タスクあり。
- **Placeholder scan:** 各ステップに実コードと実コマンド・期待結果を記載。"TODO"等なし。
- **Type consistency:** `DividendEvent(code, record_date, kind, amount)` / `AnalysisResult(ref_close,min_close,min_date,ratio,hit)` / `build_market_index`→`{code:(name,market)}` / `run(client,target_month,threshold,window)` を全タスクで一貫使用。`from_` 引数名・`MktNm`/`CoName`/`CurPerEn`/`DivFY`/`Div2Q`/`DocType` のフィールド名も実APIで確認済みのものを一貫使用。

## 未確定事項（実装中に確認）

- `/fins/summary` の `from`/`to` 範囲取得の挙動とページネーション（Task9-2で実確認。重ければ会計カレンダーのローカルJSONキャッシュを追加検討）。
- `/equities/master` 全件取得の件数・ページネーション（Task9で実確認。`JQuantsClient._get` はページネーション追従済み）。
