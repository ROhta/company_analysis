# 設計書: 配当権利落ち後の下落銘柄スクリーニング（J-Quants完結 / Python）

- 作成日: 2026-05-31
- 対象ディレクトリ: `analyzeStocks/`
- 置換対象: `screen_10days_drop_95pct.zsh`（本ツールに統合し削除。`get_id_token.zsh` は既にV2移行で削除済み）

## 1. 背景・目的

従来は「Comet（Perplexityブラウザ）でSBI証券の優待株ページを開き、`extract-stock` スキルで
コード/銘柄名/市場/指定日のCSVを生成 → `screen_10days_drop_95pct.zsh` で株価下落を判定」という
ブラウザ依存のパイプラインだった。本設計は前半（候補リスト生成）をブラウザ非依存でリポジトリ内に
取り込み、判定まで **J-Quants API V2 のみで end-to-end** に行うPythonツール `screen_dividend_drop.py` を作る。

実現する分析（README「分析内容」と等価）:

> 指定日から10営業日以内の最安値が、指定日終値の95%未満の銘柄を抽出する。

## 2. データソースの決定（重要な制約と確定事項）

- 当初案の `/fins/dividend`（配当エンドポイント）は **利用プランの対象外**（実確認: `"This API is not available on your subscription."`）。→ 不採用。
- 採用: **`/fins/summary`（決算サマリ）から権利確定日を導出**する（Option A′）。`/fins/summary` はプラン利用可・開示日で一括取得可（1日約650件）を実確認済み。
- 対象ユニバースは「**配当を出すプライム/スタンダード銘柄**」。優待のみ・無配当の銘柄は対象外（=配当落ち分析）。これは合意済みのトレードオフ。

### load-bearing な前提（明示）

- 各権利確定日の配当は、その権利落ち日より後（通常は決算発表時）に開示される。本ツールが扱う分析窓は
  データ提供遅延により数ヶ月前になるため、**開示済み＝確定済みの配当データ**を用いる（未確定の最新サイクルは扱わない）。
  したがって「過去に配当を出したから今回も同じスケジュールで出すはず」という推測ではなく、**実績ベース**で権利落ちイベントを特定する。

## 3. アルゴリズム（実データで検証済み）

### 3.1 権利確定日と指定日

- 権利確定日(基準日) `record_date` = 決算サマリの `CurPerEn`（当該期間の期末日）。
  - 期末配当: `DocType` が `FYFinancialStatements_*`、`record_date = CurPerEn(=CurFYEn)`、配当額 `DivFY`
  - 中間配当: `DocType` が `2QFinancialStatements_*`、`record_date = CurPerEn`、配当額 `Div2Q`
  - 配当額が空文字 `""` または 0 のものは除外（配当を出す回のみ対象）
- **指定日(権利付最終日) = `record_date` の2営業日前**。営業日は対象銘柄の株価系列（`/equities/bars/daily`）から導出する（別途のカレンダーAPIや祝日ライブラリは不要）。
  - 月計算ではなく実際の期末日 `CurPerEn` を直接使うため、月末でない決算期や不規則なケースにも頑健。

#### 実証（8697 / 2025-09-30 中間基準日, Div2Q=25円）

```
2025-09-26  C=1690.0   ← 指定日（基準日の2営業日前）
2025-09-29  C=1654.0   ← 権利落ち日（1営業日前）: 1690→1654 = -36円（うち配当25円分のギャップ）
2025-09-30  C=1652.5   ← 基準日 (CurPerEn)
```

「基準日の2営業日前＝指定日」「指定日終値が権利付きの基準価格」という想定が実データと一致することを確認済み。
月末が土日祝のケースは「`record_date` の2営業日前（取引日ベースで遡る）」で吸収する（テストで担保）。

### 3.2 下落判定（既存zshロジックを忠実移植）

- 指定日終値 `ref_close` を取得。
- 指定日**以降** `window`(=10) 営業日の最安値 `min_close`（null除外）を株価系列から計算。
- `min_close < threshold(=0.95) × ref_close` なら該当。
- 既存zshの jq 抽出（`.data[].C`、`null`除外、`min`）と等価であることを 1636/1490 フィクスチャでテストする。

### 3.3 市場区分・銘柄名

- `/equities/master` を1コールで取得（全銘柄）。`MktNm ∈ {"プライム","スタンダード"}` でフィルタし、`CoName` を銘柄名として付与。
  - 旧zshの `"東P"/"東S"` 文字列判定は J-Quants には存在しないため使わない（東P→プライム, 東S→スタンダード に対応）。

## 4. アーキテクチャ（標準ライブラリのみ・第三者依存ゼロ）

依存: `urllib.request` / `json` / `datetime` / `csv` / `argparse` / `unittest`（すべて標準ライブラリ）。
`requirements.txt` は作らない。`.github/dependabot.yml` への `pip` 追加も不要（サプライチェーン運用を増やさない）。

```
analyzeStocks/
  screen_dividend_drop.py   # オーケストレーション + CLI
  jquants_client.py         # I/O: urllib.requestの薄いラッパー
                            #   - x-api-key 付与 / JSONデコード / 429バックオフ / pagination_key 追従
                            #   - fins_summary(date|from,to) / equities_master() / bars_daily(code, from, to|date)
  calendar_logic.py         # 純粋関数（テストの核・ネットワーク不要）
                            #   - dividend_records(summary_rows) -> [(code, record_date, kind, amount)]
                            #   - settlement_date(record_date, trading_days) -> 指定日
                            #   - analyze_drop(price_rows, kijitsu, window, threshold) -> 判定結果
  test_calendar_logic.py    # unittest
  README.md                 # 使い方を書き換え
```

分割理由: ネットワークI/O（`jquants_client`）と純粋な判定ロジック（`calendar_logic`）を分離し、
日付計算・配当選別・下落判定を**ネットワークなしで単体テスト**できるようにする。

## 5. CLIインターフェース

```
JQUANTS_API_KEY=... python analyzeStocks/screen_dividend_drop.py \
  [--month YYYY-MM] [--threshold 0.95] [--window 10] [--csv PATH] [--max-rps N]
```

- `--month`: 分析対象の権利確定月。未指定時はデータ提供範囲内で安全な直近月を概算で既定採用し、警告を表示。
- `--threshold` / `--window`: 比較割合・営業日数（原本の固定値95%・10営業日を可変化）。
- `--csv`: 中間候補リスト（コード/銘柄名/市場/指定日）を任意でCSV出力。無指定なら結果のみ標準出力。
- `--max-rps`: プランのレート上限に合わせる。

## 6. データフロー

1. 列挙: `/fins/summary` を開示日レンジで一括取得 → FY/2Q型かつ配当>0、`CurPerEn` が分析窓内のものを抽出 →
   `(Code, record_date)` の集合（重複排除）。
2. 指定日算出: 各 `record_date` の2営業日前（取引日ベース）。
3. 付与・絞り込み: `/equities/master` で `MktNm∈{プライム,スタンダード}`・`CoName` を付与。
4. 判定: 各銘柄の株価系列を取得し、指定日終値 vs 以降 `window` 営業日の最安値で 95% 判定。
5. 出力: 該当銘柄（コード・銘柄名・指定日・指定日終値・最安値・下落率）を表示。`--csv` 指定時は中間リストも保存。

## 7. エラー処理・データ範囲

- データ提供範囲（現状 約2年・直近約12週は未提供）は**ローリングのためハードコードしない**。
  範囲外アクセス時はAPIの `"...subscription covers..."` メッセージを検知して**明示**する（黙って空リストにしない）。
- HTTP 429 はバックオフして再試行。`--max-rps` で送出間隔を制御。
- `bars` が空の銘柄・指定日が非取引日のケースは警告してスキップ（原本の挙動を踏襲）。

## 8. テスト戦略（unittest）

- `analyze_drop`: 既存zshと同じ 1636/1490 フィクスチャ（null除外含む）で**移植の等価性**を担保。
- `settlement_date`: 8697実データ（基準日2025-09-30→指定日2025-09-26）をフィクスチャ化。月末が土日祝のケースも追加。
- `dividend_records`: FY/2Q型の取り分け、`""`・0配当の除外、期末/中間の `record_date=CurPerEn` を検証。
- `jquants_client` はモックして判定ロジックを厚くテスト（ネットワーク非依存）。
- 任意のゴールデンテスト: 過去のComet/SBI生成CSVがあれば、重複銘柄の「指定日」一致で日付ロジックを追加検証（配当vs優待で銘柄集合は異なるが日付検証になる）。

## 9. 実装時に確定する未決事項

- `/fins/summary` の `from`/`to` 範囲取得とページネーション挙動。enumerationのコール数を見積もり、重い場合は
  会計カレンダー（Code→権利確定月）のローカルJSONキャッシュを追加する。
- `/equities/master` 全銘柄一括取得の件数・ページネーション有無。
- `--month` 未指定時の既定月の具体的な算出規則（データ範囲＋10営業日確保の余裕を見て決定）。

## 10. 完了の定義

- `screen_dividend_drop.py` が `--month` 指定で該当銘柄を出力できる。
- `unittest` が全て通る（特に 1636/1490 等価・8697 指定日一致）。
- 実APIキーで1回 end-to-end 実行し、出力が妥当（範囲外検知・該当/非該当の表示）であることを確認。
- 旧 `screen_10days_drop_95pct.zsh` を削除し、`README.md` を新ツールの使い方に更新。
```
