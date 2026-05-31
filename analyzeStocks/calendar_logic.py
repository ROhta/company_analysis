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
