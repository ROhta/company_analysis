"""配当権利落ちスクリーニングの純粋ロジック（ネットワーク非依存）。"""
import collections
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


def filter_events_by_month(events, year_month):
    """year_month('YYYY-MM') に record_date が一致するイベントだけ返す。"""
    year, month = (int(x) for x in year_month.split("-"))
    return [e for e in events if e.record_date.year == year and e.record_date.month == month]


def settlement_date(record_date, trading_days):
    """基準日 record_date の2営業日前(=指定日/権利付最終日)を返す。

    trading_days は date のリスト(順不同可)。record_date より前の取引日が
    2日に満たない場合は None。
    """
    before = sorted(d for d in trading_days if d < record_date)
    if len(before) < 2:
        return None
    return before[-2]


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
