#!/bin/sh
# 配当権利落ちスクリーニングを「完走するまで」自動再実行するラッパー。
#
# screen_dividend_drop.py の終了コードを見て分岐する:
#   0 = 成功               → 終了
#   2 = 一時エラー(レート制限/ネットワーク) → 一定時間待って再試行（キャッシュで続きから再開）
#   1 = 恒久エラー(範囲外の月・空ユニバース等) → 中止
#
# 使い方:
#   export JQUANTS_API_KEY=<キー>
#   ./run_until_done.sh --month 2025-12 --limit 10        # Free(既定)
#   ./run_until_done.sh --month 2025-12 --plan light      # Light以上
#   RETRY_SLEEP=300 ./run_until_done.sh --month 2025-09    # 再試行間隔を300秒に
#
# 渡した引数はそのまま screen_dividend_drop.py に転送される。
set -u

SLEEP="${RETRY_SLEEP:-360}"   # 再試行間隔(秒)。既定6分。RETRY_SLEEP で上書き可
DIR="$(cd "$(dirname "$0")" && pwd)"
attempt=0

while true; do
    attempt=$((attempt + 1))
    echo "[loop] 試行 ${attempt} 回目..." >&2
    python3 "${DIR}/screen_dividend_drop.py" "$@"
    code=$?
    if [ "$code" -eq 0 ]; then
        echo "[loop] 完了しました（試行 ${attempt} 回）。" >&2
        exit 0
    elif [ "$code" -eq 2 ]; then
        echo "[loop] 一時エラー(exit 2)。${SLEEP}秒待って再試行します（取得済みはキャッシュで続きから）。" >&2
        sleep "$SLEEP"
    else
        echo "[loop] 恒久エラー(exit ${code})。中止します。" >&2
        exit "$code"
    fi
done
