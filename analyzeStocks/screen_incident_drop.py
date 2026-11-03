"""公表イベント（サイバー攻撃・情報漏洩等）後の下落スクリーニング(J-Quants V2完結, 標準ライブラリのみ)。

入力CSV（code,announce_date の列を持つ）で与えられた公表イベントごとに、
公表直前営業日の終値を基準として、公表日以降 window 営業日以内の最安値までの
下落率を算出し、下落幅の大きい順に Markdown 表で標準出力へ出す。

配当権利落ち版（screen_dividend_drop.py）との違いはイベントの出どころだけであり、
下落判定は calendar_logic.analyze_drop をそのまま使う。対象市場は限定しない
（プライム/スタンダード/グロース等の全上場銘柄が対象になりうるため）。
"""
import argparse
import csv
import datetime
import io
import os
import sys
import time
import typing
import urllib.error

import calendar_logic as cl
from jquants_client import CachingClient, JQuantsClient, JQuantsError
from screen_dividend_drop import resolve_min_interval

# スクリプトのあるディレクトリ基準のキャッシュディレクトリ（固定）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CACHE_DIR = os.path.join(_SCRIPT_DIR, ".jq_cache")

BARS_PAD_DAYS = 45  # 基準日（公表直前営業日）と window 営業日を確保するための暦日マージン

# main() の終了コード（screen_dividend_drop.py と同じ規約）
EXIT_OK = 0          # 成功
EXIT_ERROR = 1       # 恒久的エラー（入力不正・空ユニバースなど。再試行しても直らない）
EXIT_RETRYABLE = 2   # 一時的エラー（レート制限・ネットワーク。時間をおいて再試行すれば回復しうる）


class Incident(typing.NamedTuple):
    code: str
    announce_date: datetime.date
    name: str = ""  # 入力CSVに name 列があれば保持する（表示は master を優先）


def parse_incidents(csv_text):
    """CSV文字列を Incident のリストに変換する純粋関数。

    必須列は code と announce_date（YYYY-MM-DD または YYYYMMDD）。
    name 列は任意。空行は無視する。形式不正は ValueError。
    (code, announce_date) で重複排除し、入力順を保って返す。
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise ValueError("CSVにヘッダ行がありません")
    fields = {f.strip() for f in reader.fieldnames if f}
    if "code" not in fields or "announce_date" not in fields:
        raise ValueError("CSVには code と announce_date の列が必要です（実際: {}）".format(
            ",".join(sorted(fields))))
    incidents = []
    seen = set()
    for lineno, row in enumerate(reader, start=2):
        code = (row.get("code") or "").strip()
        raw_date = (row.get("announce_date") or "").strip()
        if not code and not raw_date:
            continue
        if not code or not raw_date:
            raise ValueError("{}行目: code と announce_date の両方を指定してください".format(lineno))
        try:
            announce_date = cl.parse_date(raw_date)
        except ValueError:
            raise ValueError("{}行目: announce_date の形式が不正です: {!r}".format(lineno, raw_date))
        key = (code, announce_date)
        if key in seen:
            continue
        seen.add(key)
        incidents.append(Incident(code, announce_date, (row.get("name") or "").strip()))
    if not incidents:
        raise ValueError("CSVに有効な事例がありません")
    return incidents


def normalize_code(code):
    """表示用の4桁コードを J-Quants の5桁形式（末尾0）へ正規化する純粋関数。

    J-Quants の master / bars は 86970 のような5桁コードで返るため、
    入力が4桁のときは末尾に "0" を付けて API 呼び出し・master 照合に使う。
    5桁以上はそのまま返す。表示には入力コードをそのまま使うこと。
    """
    code = str(code).strip()
    if len(code) == 4:
        return code + "0"
    return code


def build_market_index_all(master_rows):
    """master行から {code: (CoName, MktNm)} を作る。市場は限定しない。"""
    index = {}
    for row in master_rows:
        code = row.get("Code")
        if code:
            index[code] = (row.get("CoName", ""), row.get("MktNm", ""))
    return index


def anchor_date(announce_date, trading_days):
    """公表日の直前営業日を返す（公表日に市場反応が始まる前提の基準日）。

    trading_days は date のリスト（順不同可）。公表日より前の取引日が
    無い場合は None。公表日自体が取引日でも d < announce_date で除外する
    （公表が引け後の場合に当日終値が反応前価格にならないよう一律に前日基準とする）。
    """
    before = [d for d in trading_days if d < announce_date]
    if not before:
        return None
    return max(before)


def run(client, incidents, window):
    """スクリーニング本体。下落率の大きい順に並べた結果 dict のリストを返す。

    進捗・警告は stderr、結果表は呼び出し側（_print_results）が stdout へ出す。
    """
    market_index = build_market_index_all(client.equities_master())
    if not market_index:
        raise JQuantsError("市場マスタ(equities/master)が空です。プラン/契約でユニバースが取得できているか確認してください。")

    total = len(incidents)
    results = []
    for i, ev in enumerate(incidents, 1):
        print("[info] 事例 {}/{}: {} 公表{}".format(i, total, ev.code, ev.announce_date),
              file=sys.stderr)
        api_code = normalize_code(ev.code)
        bars = client.bars_daily(
            api_code,
            from_=(ev.announce_date - datetime.timedelta(days=BARS_PAD_DAYS)).strftime("%Y%m%d"),
            to=(ev.announce_date + datetime.timedelta(
                days=BARS_PAD_DAYS + window * 2)).strftime("%Y%m%d"),
        )
        name, market = market_index.get(api_code, (ev.name, ""))
        if not bars:
            print("[warn] {} 株価barsが空。スキップ".format(ev.code), file=sys.stderr)
            continue
        trading_days = [cl.parse_date(b["Date"]) for b in bars]
        anchor = anchor_date(ev.announce_date, trading_days)
        if anchor is None:
            print("[warn] {} 公表{}の直前営業日が取得範囲内にありません。スキップ".format(
                ev.code, ev.announce_date), file=sys.stderr)
            continue
        result = cl.analyze_drop(bars, anchor, window=window, threshold=1.0)
        if result is None:
            print("[warn] {} 基準日の終値取得不可。スキップ".format(ev.code), file=sys.stderr)
            continue
        if result.window_used < window:
            print(
                "[warn] {} 基準日以降の営業日が {} 日のみ(window={})。"
                "データ範囲端の可能性".format(ev.code, result.window_used, window),
                file=sys.stderr,
            )
        results.append({
            "code": ev.code,
            "name": name,
            "market": market,
            "announce_date": ev.announce_date.isoformat(),
            "anchor_date": anchor.isoformat(),
            "ref_close": result.ref_close,
            "min_close": result.min_close,
            "min_date": result.min_date.isoformat(),
            "drop_pct": round((1 - result.ratio) * 100, 2),
            "window_used": result.window_used,
        })

    results.sort(key=lambda r: r["drop_pct"], reverse=True)
    return results


def format_results_markdown(results, window):
    """結果を Markdown 表の文字列にする純粋関数（Issueコメントへの投稿を想定）。"""
    lines = []
    lines.append("## 公表後の下落率ランキング（基準：公表直前営業日の終値 → 以後{}営業日以内の最安値）".format(window))
    lines.append("")
    if not results:
        lines.append("該当する結果はありませんでした（株価データを取得できた事例がありません）。")
        return "\n".join(lines)
    lines.append("| 順位 | コード | 銘柄名 | 市場 | 公表日 | 基準日 | 基準終値 | 最安値 | 最安日 | 下落率 |")
    lines.append("|---:|---|---|---|---|---|---:|---:|---|---:|")
    for rank, r in enumerate(results, 1):
        lines.append("| {} | {} | {} | {} | {} | {} | {:,.1f} | {:,.1f} | {} | {:.2f}% |".format(
            rank, r["code"], r["name"], r["market"], r["announce_date"], r["anchor_date"],
            r["ref_close"], r["min_close"], r["min_date"], r["drop_pct"]))
    lines.append("")
    lines.append("※ 終値は調整前の生値（V2の `C`）で比較。株式分割・併合をまたぐ場合は実勢とずれることがあります。")
    return "\n".join(lines)


def _run_once(args, incidents, min_interval):
    """1回分のスクリーニングを実行し終了コードを返す（再試行はしない）。"""
    api_key = os.environ.get("JQUANTS_API_KEY", "")
    try:
        client = JQuantsClient(api_key=api_key, min_interval=min_interval)
        if not args.no_cache:
            client = CachingClient(client, _DEFAULT_CACHE_DIR)
        results = run(client, incidents, args.window)
    except JQuantsError as e:
        print("[error] {}".format(e), file=sys.stderr)
        if "rate limit" in str(e).lower():
            print(
                "[hint] レート制限です。--retry を付けるか、時間をおいて再実行すれば、"
                "取得済み分はキャッシュで続きから再開できます。",
                file=sys.stderr,
            )
            return EXIT_RETRYABLE
        return EXIT_ERROR
    except (urllib.error.URLError, TimeoutError) as e:
        print("[error] ネットワーク失敗(timeout等): {}。時間をおいて再実行してください".format(e),
              file=sys.stderr)
        return EXIT_RETRYABLE
    except (ValueError, KeyError) as e:
        print("[error] APIレスポンスの形式が想定外です: {}".format(e), file=sys.stderr)
        return EXIT_ERROR

    print(format_results_markdown(results, args.window))
    return EXIT_OK


def main(argv=None, sleep=time.sleep):
    """CLIエントリポイント。

    終了コード: 0=成功 / 1=恒久エラー(再試行不可) / 2=一時エラー(レート制限・ネットワーク, 再試行可)。
    --retry 指定時は exit 2 のとき --retry-wait 秒待って自動再試行する。
    """
    parser = argparse.ArgumentParser(description="公表イベント後の下落スクリーニング")
    parser.add_argument("--input", required=True, help="事例CSVのパス（列: code,announce_date[,name]）")
    parser.add_argument("--window", type=int, default=10, help="公表日以降に最安値を探す営業日数（既定10）")
    parser.add_argument(
        "--plan",
        choices=["free", "light", "standard", "premium"],
        default="free",
        help="契約プラン（既定: free）。プラン別の安全なレートを自動適用",
    )
    parser.add_argument(
        "--max-rps",
        type=float,
        default=None,
        help="APIリクエストの最大レート(req/sec)。指定した場合は --plan より優先",
    )
    parser.add_argument("--no-cache", action="store_true", help="ディスクキャッシュを無効化する")
    parser.add_argument("--retry", action="store_true",
                        help="一時エラー(レート制限等/exit 2)のとき自動で待って再試行する")
    parser.add_argument("--retry-wait", type=float, default=360.0,
                        help="--retry 時の再試行間隔(秒)。既定360")
    args = parser.parse_args(argv)

    if args.window < 1:
        parser.error("--window は1以上を指定してください")
    if args.retry_wait < 0:
        parser.error("--retry-wait は0以上を指定してください")
    if args.max_rps is not None and args.max_rps < 0:
        parser.error("--max-rps は0以上を指定してください（0はスロットル無効）")

    try:
        with open(args.input, "r", encoding="utf-8-sig") as f:
            csv_text = f.read()
    except OSError as e:
        print("[error] 入力CSVを読めません: {}".format(e), file=sys.stderr)
        return EXIT_ERROR
    try:
        incidents = parse_incidents(csv_text)
    except ValueError as e:
        print("[error] 入力CSVが不正です: {}".format(e), file=sys.stderr)
        return EXIT_ERROR

    min_interval = resolve_min_interval(args.plan, args.max_rps)
    print("[info] 事例 {} 件 / window={}営業日 / プラン: {}".format(
        len(incidents), args.window, args.plan), file=sys.stderr)

    attempt = 0
    while True:
        attempt += 1
        if args.retry:
            print("[loop] 試行 {} 回目...".format(attempt), file=sys.stderr)
        code = _run_once(args, incidents, min_interval)
        if not args.retry:
            return code
        if code == EXIT_OK:
            print("[loop] 完了しました（試行 {} 回）。".format(attempt), file=sys.stderr)
            return EXIT_OK
        if code == EXIT_ERROR:
            print("[loop] 恒久エラー(exit 1)。中止します。", file=sys.stderr)
            return EXIT_ERROR
        print("[loop] 一時エラー(exit 2)。{:.0f}秒待って再試行します。".format(args.retry_wait),
              file=sys.stderr)
        sleep(args.retry_wait)


if __name__ == "__main__":
    raise SystemExit(main())
