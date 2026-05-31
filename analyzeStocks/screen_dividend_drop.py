# analyzeStocks/screen_dividend_drop.py
"""配当権利落ち後の下落銘柄スクリーニング(J-Quants V2完結, 標準ライブラリのみ)。"""
import argparse
import csv
import datetime
import os
import sys
import urllib.error

import calendar_logic as cl
from jquants_client import JQuantsClient, JQuantsError

TARGET_MARKETS = ("プライム", "スタンダード")
BARS_PAD_DAYS = 20  # 指定日算出のため基準日前後に確保する暦日


def build_market_index(master_rows):
    """master行から {code: (CoName, MktNm)} を作る。プライム/スタンダードのみ。"""
    index = {}
    for row in master_rows:
        code = row.get("Code")
        if code and row.get("MktNm") in TARGET_MARKETS:
            index[code] = (row.get("CoName", ""), row.get("MktNm", ""))
    return index


def run(client, target_month, threshold, window, limit=None):
    """スクリーニング本体。該当銘柄の dict リストを返す。

    ヒット銘柄はstdout、進捗・サマリ・警告はstderrに出力する。
    limit: 候補イベントを先頭 N 件に制限する（None=全件）。大規模月での試験実行用。
    """
    # 開示日を1日ずつスキャンして決算サマリ行を蓄積する
    dates = cl.disclosure_dates(target_month)
    summary_rows = []
    for i, d in enumerate(dates, 1):
        print("[info] 開示日スキャン {}/{}: {}".format(i, len(dates), d), file=sys.stderr)
        rows = client.fins_summary(date=d)
        summary_rows.extend(rows)

    events = cl.filter_events_by_month(cl.dividend_events(summary_rows), target_month)

    if not events:
        print("[info] {} に該当する配当イベントが見つかりませんでした。".format(target_month),
              file=sys.stderr)
        _print_results([], target_month, threshold)
        return []

    # limit で候補数を制限
    if limit is not None:
        events = events[:limit]

    # 候補が多数の月では全件1コールの方が per-code ループより安価なため意図的に全件取得
    market_index = build_market_index(client.equities_master())
    if not market_index:
        raise JQuantsError("市場マスタ(equities/master)が空です。プラン/契約でユニバースが取得できているか確認してください。")

    total = len(events)
    hits = []
    for i, ev in enumerate(events, 1):
        print("[info] 候補 {}/{}: {} 権利確定{}".format(
            i, total, ev.code, ev.record_date), file=sys.stderr)
        if ev.code not in market_index:
            continue
        record = ev.record_date
        bars = client.bars_daily(
            ev.code,
            from_=(record - datetime.timedelta(days=BARS_PAD_DAYS)).strftime("%Y%m%d"),
            to=(record + datetime.timedelta(days=BARS_PAD_DAYS + window * 2)).strftime("%Y%m%d"),
        )
        if not bars:
            print("[warn] {} 株価barsが空。スキップ".format(ev.code), file=sys.stderr)
            continue
        trading_days = [cl.parse_date(b["Date"]) for b in bars]
        kijitsu = cl.settlement_date(record, trading_days)
        if kijitsu is None:
            print("[warn] {} 基準日{}前の取引日が不足。スキップ".format(ev.code, record), file=sys.stderr)
            continue
        result = cl.analyze_drop(bars, kijitsu, window=window, threshold=threshold)
        if result is None:
            print("[warn] {} 指定日の終値取得不可。スキップ".format(ev.code), file=sys.stderr)
            continue
        if result.window_used < window:
            print(
                "[warn] {} 指定日以降の営業日が {} 日のみ(window={})。"
                "データ範囲端の可能性".format(ev.code, result.window_used, window),
                file=sys.stderr,
            )
        if not result.hit:
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
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["コード", "銘柄名", "市場", "指定日"])
        for h in hits:
            writer.writerow([h["code"], h["name"], h["market"], h["kijitsu"]])


def main(argv=None):
    parser = argparse.ArgumentParser(description="配当権利落ち後の下落銘柄スクリーニング")
    parser.add_argument("--month", help="対象の権利確定月 YYYY-MM(未指定なら約4ヶ月前)")
    parser.add_argument("--threshold", type=float, default=0.95)
    parser.add_argument("--window", type=int, default=10)
    parser.add_argument("--csv", help="該当銘柄をCSV出力（コード/銘柄名/市場/指定日）")
    parser.add_argument("--limit", type=int, default=None,
                        help="候補barsの処理数を制限（開示日スキャンのコール数は減らない）")
    parser.add_argument("--max-rps", type=float, default=3.0,
                        help="APIリクエストの最大レート(req/sec)。レート制限緩和用（既定3.0）")
    args = parser.parse_args(argv)

    if args.window < 1:
        parser.error("--window は1以上を指定してください")
    if not (0 < args.threshold <= 1):
        parser.error("--threshold は 0 より大きく 1 以下の値を指定してください")

    api_key = os.environ.get("JQUANTS_API_KEY", "")
    target_month = args.month or cl.default_target_month(datetime.date.today())
    if not args.month:
        print("[info] --month未指定のため既定 {} を使用(範囲外なら--monthで指定)".format(target_month),
              file=sys.stderr)

    try:
        min_interval = 1.0 / args.max_rps if args.max_rps > 0 else 0.0
        client = JQuantsClient(api_key=api_key, min_interval=min_interval)
        hits = run(client, target_month, args.threshold, args.window, limit=args.limit)
    except JQuantsError as e:
        print("[error] {}".format(e), file=sys.stderr)
        return 1
    except (urllib.error.URLError, TimeoutError) as e:
        print("[error] ネットワーク失敗(timeout等): {}。--max-rps を下げて再試行してください".format(e), file=sys.stderr)
        return 1
    except (ValueError, KeyError) as e:
        print("[error] APIレスポンスの形式が想定外です: {}".format(e), file=sys.stderr)
        return 1

    if args.csv:
        try:
            write_csv(args.csv, hits)
        except OSError as e:
            print("[error] CSV出力失敗: {}".format(e), file=sys.stderr)
            return 1
        print("[info] 該当銘柄を {} に出力しました".format(args.csv), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
