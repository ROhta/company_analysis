# 財務諸表可視化ツール

企業の財務諸表（P/L、B/S、C/F）をグラフで可視化するReactアプリケーションです。

## 使用方法

### 起動

ランタイム（Node.js / pnpm）は [mise](https://mise.jdx.dev/) で管理しています（`mise.toml`）。パッケージ依存自体は従来どおり pnpm（`pnpm-lock.yaml`）が解決し、mise は「正しい版の Node.js / pnpm を用意して各タスクを束ねる」役割です。

```bash
cd financialStatements
mise install   # 初回のみ: node・pnpm を mise.toml / mise.lock の版で導入
mise run dev   # 依存インストール込みで vite 開発サーバを起動
```

定義済みタスク: `dev`（開発起動）/ `build`（本番ビルド）/ `preview`（ビルド結果のプレビュー）/ `install`（依存インストール）。実バージョンは `mise.lock` で固定されます（Node.js 24系 / pnpm 11系）。

mise を使わない場合は `mise.toml` 記載の版を各自で用意し、`pnpm install && pnpm dev` でも起動できます。

### アクセス

URLパラメータ `companyData` で表示する企業データのJSONファイル名を指定します。

```
http://localhost:5174/?companyData=kakiyasu2026
```

- `companyData` パラメータは必須です
- 指定されたファイルが存在しない場合は404エラーが表示されます

## 企業データJSON形式

企業データは `public` ディレクトリにJSONファイルとして配置します。

### 基本構造

```json
{
  "name": "株式会社サンプル",
  "code": "1234",
  "market": "東証プライム",
  "period": "2025年3月期",
  "announcementDate": "2025年5月15日",
  "chartSettings": { ... },
  "pl": { ... },
  "plComparison": [ ... ],
  "bs": { ... },
  "cf": { ... },
  "cfComparison": [ ... ],
  "comments": { ... }
}
```

各セクション（`pl` / `bs` / `cf`）の項目構成は `public/kakiyasu2026.json` を正としてください。特に以下に注意します。

- **金額の単位は百万円**に統一する。
- **`cf.details` は必須**（`営業CF`: 税前利益・減価償却費・運転資本増減 ／ `投資CF`: 子会社株式取得・有形固定資産取得 ／ `財務CF`: 配当金支払・その他）。コンポーネントが直接参照するため、欠けると描画時にエラーになります。
- `plComparison` の比較チャートは `売上高` / `営業利益` / `当期純利益` を描画します（純利益のキー名は `当期純利益`）。`cfComparison` は `営業CF` / `投資CF` / `財務CF` / `フリーCF` / `期末現金` を使います。
- **会計基準**: スキーマは日本基準（`経常利益`・`営業外損益`・`特別損益等`）前提です。**IFRS適用企業**（例: 三菱電機）には経常利益が無いため、`.agents/financial-data-extractor.md` の「IFRS適用企業のマッピング」に従って科目を割り当ててください（`経常利益`←税引前当期純利益 など）。実例は `public/mitsubishi_electric2026.json` を参照。

### ファイル名

`{企業略称}{決算期の西暦年}.json`（例: `kakiyasu2026.json`, `mitsubishi_electric2026.json`）。「決算期の西暦年」は決算期末の年（2026年3月期→`2026`）を用います。`?companyData=` には拡張子を除いたファイル名を渡します。

### chartSettings（グラフ軸設定）

グラフのY軸の範囲と目盛りを設定します。単位は百万円です。軸の上限は売上高・総資産を内包し、CFの下限は最大の流出額（投資CF・財務CF）を内包するよう、切りの良い値で設定します（データがクリップされないこと）。

#### 大企業向け設定例（売上高1兆円規模）

```json
{
  "chartSettings": {
    "pl": {
      "domain": [0, 1500000],
      "ticks": [0, 300000, 600000, 900000, 1200000, 1500000]
    },
    "bs": {
      "domain": [0, 2000000],
      "ticks": [0, 500000, 1000000, 1500000, 2000000]
    },
    "cf": {
      "composition": {
        "domain": [-200000, 200000],
        "ticks": [-200000, -100000, 0, 100000, 200000]
      },
      "waterfall": {
        "domain": [-200000, 500000],
        "ticks": [-200000, 0, 100000, 200000, 300000, 400000, 500000]
      },
      "comparison": {
        "domain": [-200000, 500000],
        "ticks": [-200000, 0, 100000, 200000, 300000, 400000, 500000]
      }
    }
  }
}
```

#### 中小企業向け設定例（売上高50億円規模）

```json
{
  "chartSettings": {
    "pl": {
      "domain": [0, 6000],
      "ticks": [0, 1000, 2000, 3000, 4000, 5000, 6000]
    },
    "bs": {
      "domain": [0, 4000],
      "ticks": [0, 1000, 2000, 3000, 4000]
    },
    "cf": {
      "composition": {
        "domain": [-1000, 1000],
        "ticks": [-1000, -500, 0, 500, 1000]
      },
      "waterfall": {
        "domain": [-1000, 2000],
        "ticks": [-1000, 0, 500, 1000, 1500, 2000]
      },
      "comparison": {
        "domain": [-1000, 2000],
        "ticks": [-1000, 0, 500, 1000, 1500, 2000]
      }
    }
  }
}
```

数兆円規模（売上高5〜7兆円）の設定例は `public/mitsubishi_electric2026.json` を参照してください。

`chartSettings` を省略した場合はデフォルト値が使用されます。

### comments（コメント設定）

B/SとC/Fセクションに表示するコメントをカスタマイズできます。

```json
{
  "comments": {
    "bs": {
      "assets": null,
      "liabilities": "自己資本比率45% - 業界平均を上回る水準"
    },
    "cf": {
      "operating": null,
      "investing": "※新工場建設による設備投資",
      "financing": false
    }
  }
}
```

#### 設定値

| 値 | 動作 |
|---|---|
| `null` または 未指定 | デフォルトコメントを表示（自動計算） |
| 文字列 | カスタムコメントを表示 |
| `false` | コメントを非表示 |

#### デフォルトコメント

| キー | デフォルト表示 |
|---|---|
| `bs.assets` | 「流動比率{X}% ／ 現金比率{Y}%」 |
| `bs.liabilities` | 「自己資本比率{X}%」 |
| `cf.operating` | 「営業CFマージン{X}% ／ 対純利益比{Y}%」 |
| `cf.investing` | なし |
| `cf.financing` | なし |

### 完全なJSONサンプル

`public/kakiyasu2026.json` を参照してください。
