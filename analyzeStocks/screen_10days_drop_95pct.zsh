#!/bin/zsh

# J-Quants APIを使用して株価を分析するスクリプト

# 引数チェック
if [[ $# -ne 1 ]]; then
    echo "Error: CSVファイルのパスを引数に指定してください" >&2
    echo "使用方法: $0 <csvファイルのパス>" >&2
    exit 1
fi

CSV_FILE="$1"

# CSVファイルの存在確認
if [[ ! -f "$CSV_FILE" ]]; then
    echo "Error: CSVファイルが見つかりません: $CSV_FILE" >&2
    exit 1
fi

# jqのインストール確認
if ! command -v jq &> /dev/null; then
    echo "Error: jqがインストールされていません" >&2
    echo "Homebrewでインストールしてください: brew install jq" >&2
    exit 1
fi

# 1. 環境変数JQUANTS_API_KEYの確認
if [[ -z "$JQUANTS_API_KEY" ]]; then
    echo "Error: 環境変数JQUANTS_API_KEYが設定されていません" >&2
    echo "J-QuantsダッシュボードでAPIキーを発行し、export JQUANTS_API_KEY=<キー> を設定してください" >&2
    exit 1
fi

# 2. CSVヘッダーの確認
REQUIRED_HEADERS=("コード" "銘柄名" "市場" "指定日")
HEADER=$(head -n 1 "$CSV_FILE")

for required in "${REQUIRED_HEADERS[@]}"; do
    if [[ ! "$HEADER" =~ "$required" ]]; then
        echo "Error: CSVファイルに必須カラム「$required」が含まれていません" >&2
        exit 1
    fi
done

# 日付フォーマット変換関数（YYYY/MM/DD -> YYYYMMDD）
convert_date_format() {
    local date_str="$1"
    # スラッシュで分割して年月日を取得
    local year=$(echo "$date_str" | cut -d'/' -f1)
    local month=$(echo "$date_str" | cut -d'/' -f2 | awk '{printf "%02d", $1}')
    local day=$(echo "$date_str" | cut -d'/' -f3 | awk '{printf "%02d", $1}')
    echo "${year}${month}${day}"
}

# 日付加算関数（YYYYMMDD + N日 -> YYYYMMDD）
add_days() {
    local date="$1"
    local days="$2"
    local year="${date:0:4}"
    local month="${date:4:2}"
    local day="${date:6:2}"

    # dateコマンドを使用（macOS対応）
    date -j -f "%Y%m%d" -v+${days}d "$date" +"%Y%m%d" 2>/dev/null || \
    date -d "$year-$month-$day $days days" +"%Y%m%d" 2>/dev/null
}

# J-Quants APIコール関数（レート制限チェック付き）
call_jquants_api() {
    local url="$1"
    local temp_file=$(mktemp)
    local http_code=$(curl -s -o "$temp_file" -w "%{http_code}" -H "x-api-key: $JQUANTS_API_KEY" "$url")
    local body=$(cat "$temp_file")
    rm -f "$temp_file"

    # HTTPステータスコードチェック
    if [[ "$http_code" == "429" ]]; then
        echo "Error: レート制限に達しました" >&2
        echo "APIレスポンス: $body" >&2
        exit 1
    elif [[ "$http_code" != "200" ]]; then
        echo "Error: APIリクエストが失敗しました (HTTPステータス: $http_code)" >&2
        echo "URL: $url" >&2
        echo "APIレスポンス: $body" >&2
        exit 1
    fi

    # エラーメッセージの確認
    if echo "$body" | jq -e '.error' > /dev/null 2>&1; then
        echo "Error: APIがエラーを返しました" >&2
        echo "APIレスポンス: $body" >&2
        exit 1
    fi

    echo "$body"
}

# 結果格納用一時ファイル
RESULT_FILE=$(mktemp)
trap "rm -f $RESULT_FILE" EXIT

# 3. CSVファイルを1行ずつ処理（ヘッダー行をスキップ）
tail -n +2 "$CSV_FILE" | while IFS=',' read -r code name market ex_date; do
    # 改行コードや余分な空白を削除
    code=$(echo "$code" | tr -d '\r\n' | xargs)
    name=$(echo "$name" | tr -d '\r\n' | xargs)
    market=$(echo "$market" | tr -d '\r\n' | xargs)
    ex_date=$(echo "$ex_date" | tr -d '\r\n' | xargs)

    # 市場区分のチェック（プライムまたはスタンダードのみ）
    if [[ "$market" != "東P" && "$market" != "東S" ]]; then
        continue
    fi

    echo "処理中: $code ($name) - $market - 指定日: $ex_date" >&2

    # 日付フォーマット変換
    ex_date_api=$(convert_date_format "$ex_date")

    # 4. 指定日の株価を取得
    ex_day_response=$(call_jquants_api "https://api.jquants.com/v2/equities/bars/daily?code=$code&date=$ex_date_api")

    # レスポンスから終値を取得（V2: data配列・Cフィールド）
    ex_day_close=$(echo "$ex_day_response" | jq -r '.data[0].C // empty')

    if [[ -z "$ex_day_close" ]]; then
        echo "  警告: 指定日($ex_date)の株価データが取得できませんでした。スキップします。" >&2
        sleep 0.3
        continue
    fi

    echo "  指定日の終値: $ex_day_close" >&2

    # 5. 指定日（翌日）から余裕を持って20日分のデータを取得
    ex_rights_date=$(add_days "$ex_date_api" 1)
    end_date=$(add_days "$ex_date_api" 21)

    # 期間の株価データを取得
    period_response=$(call_jquants_api "https://api.jquants.com/v2/equities/bars/daily?code=$code&from=$ex_rights_date&to=$end_date")

    # 営業日のデータを取得し、最初の10営業日の最安値を計算（nullを除外）（V2: data配列・Cフィールド）
    min_close=$(echo "$period_response" | jq -r '[.data[0:10][].C | select(. != null)] | min')

    if [[ -z "$min_close" || "$min_close" == "null" ]]; then
        echo "  警告: 指定日以降の株価データが取得できませんでした。スキップします。" >&2
        sleep 0.3
        continue
    fi

    echo "  10営業日間の最安値: $min_close" >&2

    # 6. 最安値が指定日の株価の95%未満かチェック
    threshold=$(echo "$ex_day_close * 0.95" | bc)

    if (( $(echo "$min_close < $threshold" | bc -l) )); then
        echo "  ✓ 条件該当: 最安値($min_close) < 95%閾値($threshold)" >&2
        echo "$code,$name" >> "$RESULT_FILE"
    else
        echo "  条件非該当: 最安値($min_close) >= 95%閾値($threshold)" >&2
    fi

    # レート制限対策のため少し待機
    sleep 0.3
done

echo "" >&2
echo "=== 分析完了 ===" >&2
echo "" >&2

# 条件に該当する銘柄を表示
if [[ -s "$RESULT_FILE" ]]; then
    echo "=== 条件に該当する銘柄（最安値が指定日の株価の95%未満）===" >&2
    echo "" >&2
    while IFS=',' read -r code name; do
        echo "証券コード: $code - 銘柄名: $name"
    done < "$RESULT_FILE"
else
    echo "条件に該当する銘柄はありませんでした。" >&2
fi
