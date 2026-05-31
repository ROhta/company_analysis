"""配当権利落ちスクリーニングの純粋ロジック（ネットワーク非依存）。"""
import calendar
import datetime
import typing


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
    if len(s) == 8:
        return datetime.date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
    raise ValueError("parse_date: 予期しない日付形式 {!r}".format(value))


class DividendEvent(typing.NamedTuple):
    code: str
    record_date: datetime.date
    kind: typing.Literal["FY", "2Q"]  # 記録目的（現状 run では未消費）
    amount: float                      # 記録目的（現状 run では未消費）


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
    trading_days に record_date 自体が含まれていても d < record_date で除外する。
    """
    before = sorted(d for d in trading_days if d < record_date)
    if len(before) < 2:
        return None
    return before[-2]


class AnalysisResult(typing.NamedTuple):
    ref_close: float
    min_close: float
    min_date: datetime.date
    ratio: float
    hit: bool
    window_used: int


def analyze_drop(price_rows, kijitsu_date, window, threshold):
    """指定日終値と、指定日の翌営業日以降 window 営業日の最安値(null除外)で下落判定する。

    price_rows は {'Date','C'} のリスト。指定日が系列に無い/終値が欠損なら None。
    対象期間に有効な終値が無ければ None。

    window_used: 指定日の翌営業日以降に実際に存在した取引日数（終値欠損=null含む）。
    window より小さい場合はデータ範囲端の可能性があり、判定の信頼性が低下する。
    """
    # 各行の Date を1度だけパースし、ソート・指定日探索・window抽出で使い回す
    parsed = sorted(
        ((parse_date(r["Date"]), r) for r in price_rows),
        key=lambda dr: dr[0],
    )
    idx = None
    for i, (d, _row) in enumerate(parsed):
        if d == kijitsu_date:
            idx = i
            break
    if idx is None:
        return None
    ref_close = _to_float(parsed[idx][1].get("C"))
    if ref_close is None or ref_close <= 0:
        return None
    after = parsed[idx + 1: idx + 1 + window]
    window_used = len(after)
    closes = [(d, c) for d, c in
              ((d, _to_float(r.get("C"))) for d, r in after)
              if c is not None]
    if not closes:
        return None
    min_date, min_close = min(closes, key=lambda dc: dc[1])
    return AnalysisResult(
        ref_close=ref_close,
        min_close=min_close,
        min_date=min_date,
        ratio=min_close / ref_close,
        hit=min_close < threshold * ref_close,
        window_used=window_used,
    )


def _month_end(year, month):
    return datetime.date(year, month, calendar.monthrange(year, month)[1])


def _shift_month(year, month, delta):
    """(year, month) を delta ヶ月ずらした (year, month) を返す。"""
    index = (year * 12 + (month - 1)) + delta
    return index // 12, index % 12 + 1


def default_target_month(today):
    """データ遅延を見越して today のおよそ4ヶ月前の年月 'YYYY-MM' を返す。"""
    year, month = _shift_month(today.year, today.month, -4)
    return "{:04d}-{:02d}".format(year, month)


def disclosure_dates(year_month):
    """対象月の権利確定イベントを拾うための開示日（平日のみ）の文字列リストを返す。

    範囲は対象月末〜対象月末+60日。
    土曜(weekday=5)・日曜(weekday=6)は除外。祝日は考慮しない。

    根拠: 決算短信は決算期末後45日以内の開示が原則のため、対象月末+60日までで
    対象月に期末を持つFY/2Q短信をほぼ網羅できる。ごく稀な遅延開示は
    取りこぼす可能性がある。
    """
    year, month = (int(x) for x in year_month.split("-"))
    start = _month_end(year, month)
    end = start + datetime.timedelta(days=60)
    result = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # 月〜金
            result.append(current.isoformat())
        current += datetime.timedelta(days=1)
    return result


