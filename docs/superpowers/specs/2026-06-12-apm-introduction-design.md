# apm（Agent Package Manager）導入 設計仕様

- 作成日: 2026-06-12
- ステータス: ドラフト（ユーザーレビュー待ち）
- 対象: 本リポジトリの AI エージェント設定全般
- 参照実装: [ROhta/bingo](https://github.com/ROhta/bingo)（フル踏襲）

## 1. 背景と用語の確定

本書の「apm」は **Application Performance Monitoring ではなく、[microsoft/apm](https://github.com/microsoft/apm)（Agent Package Manager）** を指す。`package.json` がライブラリ依存を宣言するのと同様に、`apm.yml` を宣言的マニフェストとして AI エージェント設定（指示・サブエージェント・MCP サーバ・スキル等）を管理し、`apm install` / `apm compile` で各 AI ツール（Claude Code / Codex CLI / GitHub Copilot 他）のネイティブ設定ファイルへ展開する。

### apm に関する確定事実（実装前調査済み）

- **単独バイナリ**。apm 本体の実行に node/npm は不要。`mise`（`github:microsoft/apm`）でバージョン管理する。
- **7 つの primitive** をサポート: Instructions / Agents / Prompts / Skills / Hooks / Context / MCP Servers。
- `apm install` はランタイムを自動検出し、サブエージェントを **`.claude/agents/*.md`・`.codex/agents/*.toml`・`.github/agents/*.agent.md`** へ生成する（= 既存の手書きサブエージェント規約を apm に置換できる）。
- `apm compile` は **instructions のみ**を `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` へマージ生成する（agents/prompts/skills は `apm install` 側が展開）。Copilot 向けの instructions は `apm install` が `.github/instructions/`（gitignore）へ展開し、`.github/copilot-instructions.md` は **apm 生成対象に含めず手書きスタブとして別管理**する（§5.5）。`targets` に copilot を含めても compile が当該スタブを上書きしないことを実装時に確認する（§9）。
- `apm.lock.yaml` の `deployed_files:` 重複バグは **v0.8.12 で修正済み**。pin する 0.18.0 では発生しないため、bingo の `scripts/dedupe-apm-lock.mjs`（node 製ワークアラウンド）と root `package.json` は**導入しない**。
- ローカル primitive の置き場所は `.apm/<type>/`（`.apm/instructions/`・`.apm/agents/` 等）。`includes: auto` で `.apm/` 配下を全公開。

## 2. ゴール / 非ゴール

### ゴール

- `.apm/` を**人間が編集する唯一の真実源（SSoT）**にする。各ツール設定は生成物にする。
- bingo と同等のフル構成（instructions SSoT 化 + MCP + 外部スキル + 生成物 gitignore）を採用する。
- 既存サブエージェント `financial-data-extractor` を apm の Agents primitive へ移行し、手書きの symlink/TOML ラッパー規約を撤廃する。
- apm 本体を `mise` で固定し、版管理を一本化する。

### 非ゴール

- CI への apm 導入（生成物は CI で不要。`deploy.yml` は `AGENTS.md`/`CLAUDE.md`/`README.md` を参照しないことを確認済み）。
- per-tool（`analyzeStocks/`・`financialStatements/`）の既存 `mise.toml` の変更。
- 機能ロジック（スクリーニング等）の変更。

## 3. 確定した意思決定

| 項目 | 決定 |
|---|---|
| 導入範囲 | **フル＋サブエージェントも apm 化** |
| MCP サーバ | context7 / semgrep / serena / chrome-devtools（bingo と同一セット） |
| 外部 apm 依存 | obra/superpowers のみ（commit SHA ピン） |
| apm 本体バージョン | `mise.toml` で pin（初期値 0.18.0、`mise install` で更新） |
| dedupe ワークアラウンド | 不要（v0.8.12 で修正済み） |
| root node/package.json | 不要 |

## 4. ファイル管理方針（SSoT vs 生成物）

| パス | 役割 | リポジトリ追跡 |
|---|---|---|
| `.apm/instructions/*.instructions.md` | **全体指示の SSoT**（人間が編集） | ✅ 追跡 |
| `.apm/agents/financial-data-extractor.agent.md` | **サブエージェントの SSoT**（人間が編集） | ✅ 追跡 |
| `apm.yml`（`dependencies.mcp` / `dependencies.apm`） | **MCP・外部スキルの SSoT**（人間が編集） | ✅ 追跡 |
| `apm.lock.yaml` | 再現性・オーファン検出のため例外的に追跡 | ✅ 追跡 |
| `mise.toml`（root・新規） | apm 本体の版 SSoT | ✅ 追跡 |
| `README.md` | **symlink 解除 → 人間/GitHub 向け実体ファイル**（apm 生成対象外） | ✅ 追跡 |
| `.github/copilot-instructions.md` | **symlink 解除 → SoT を指す手書きスタブ**（Copilot Code Review 用） | ✅ 追跡 |
| `AGENTS.md` / `CLAUDE.md` | `apm compile` 生成 | ❌ gitignore |
| `.claude/agents/*.md`・`.codex/agents/*.toml`・`.github/agents/*.agent.md` | `apm install` 生成（サブエージェント3形式） | ❌ gitignore |
| `.github/instructions/`・`.claude/rules/` | `apm install` 生成 | ❌ gitignore |
| `.mcp.json`・`.vscode/mcp.json`・`.codex/config.toml` | `apm install` 生成（MCP 設定） | ❌ gitignore |
| `apm_modules/`・`.claude/skills/`・`.claude/commands/`・`.claude/hooks/`・`.claude/settings.json`・`.agents/skills/`・`.github/prompts/`・`.github/hooks/` | `apm install` プラグイン展開先 | ❌ gitignore |

> 注: 現状 `.gitignore` に `.claude/` の記載は無いが `.claude/agents/financial-data-extractor.md`（symlink）が追跡されている。生成物化に伴い `.claude/` 配下の生成物を個別に無視する（`.claude/` 全体ではなく生成サブパスを列挙し、将来の手書き設定と区別できる粒度にする）。

## 5. コンポーネント設計

### 5.1 root `mise.toml`（新規）

```toml
[tools]
"github:microsoft/apm" = { version = "0.18.0", extract_all = "true" }
```

- per-tool mise.toml はそのまま。apm はリポジトリ横断のためルートに置く。
- `apm self-update` / `apm doctor` の更新催促には従わず、版上げは `mise.toml` 編集 → `mise install` に一本化。

### 5.2 `apm.yml`（新規）

```yaml
name: company_analysis
version: 1.0.0
description: 株式分析ツール群リポジトリの AI エージェント設定
author: ROhta
license: AGPL-3.0-or-later
targets: [claude, codex, copilot]
includes: auto          # .apm/ 配下のローカル primitive を全公開
# type: は省略（content-driven）。instructions と agents を両方持つため
#        type: instructions にすると agents の install が抑止される恐れがある。
dependencies:
  mcp:
    - name: context7
      registry: false
      transport: stdio
      command: npx
      args: ["-y", "@upstash/context7-mcp"]
    - name: semgrep
      registry: false
      transport: stdio
      command: uvx
      args: ["semgrep-mcp"]
    - name: serena
      registry: false
      transport: stdio
      command: uvx
      args: ["--from", "git+https://github.com/oraios/serena@<COMMIT_SHA>", "serena", "start-mcp-server"]
    - name: chrome-devtools
      registry: false
      transport: stdio
      command: npx
      args: ["-y", "chrome-devtools-mcp@<PINNED_VERSION>"]
  apm:
    - obra/superpowers#<COMMIT_SHA>
```

- `<COMMIT_SHA>` / `<PINNED_VERSION>` は実装時に最新を解決して固定する（bingo の値を流用せず、その時点の版を明示ピン）。
- MCP サーバはツール実行時に `npx`（node 必要）/ `uvx`（uv 必要）で起動される。これは apm 本体ではなく **MCP クライアント側のランタイム前提**。開発者マシンに node / uv が必要になる点を setup 手順に明記する（実装時に各ツールの導入状況を確認）。

### 5.3 instructions SSoT（`.apm/instructions/`）

現 `AGENTS.md` 本文を主題ごとに分割移行する。各ファイルは frontmatter（`description`・任意で `applyTo`）＋本文。

| 移行元（AGENTS.md の節） | 移行先（案） |
|---|---|
| 目的 / 詳細説明 | `project-overview.instructions.md` |
| 使用言語（日本語ルール） | `language.instructions.md` |
| エージェント定義の運用方針 | `agents-workflow.instructions.md`（apm 運用ルールを内包。bingo の `apm-workflow.instructions.md` 相当） |

- bingo に倣い、apm 自体の運用ルール（SSoT の所在、生成物は触らない、版管理は mise、`apm install`/`apm compile` の使い分け）を SSoT 内の instructions として持たせる。

### 5.4 サブエージェント移行（`.apm/agents/financial-data-extractor.agent.md`）

- 現 `.agents/financial-data-extractor.md`（実体）の本文を `.apm/agents/financial-data-extractor.agent.md` へ移す。frontmatter は `description`（必要なら `name`）。
- `apm install` が `.claude/agents/financial-data-extractor.md`・`.codex/agents/financial-data-extractor.toml`・`.github/agents/financial-data-extractor.agent.md` を生成。
- 旧・手書き実体／symlink／TOML ラッパーは追跡解除（5.6）。

### 5.5 `README.md` と `.github/copilot-instructions.md` の symlink 解除

- **README.md**: `AGENTS.md` への symlink を解除し、人間/GitHub 表紙向けの実体ファイル化（リポジトリ概要・各ツールへの導線・セットアップ手順）。apm の生成対象外なので独立管理する。
- **.github/copilot-instructions.md**: symlink を解除し、SoT（`.apm/instructions/`）を参照する手書きスタブにする。2026 年時点で Copilot Code Review は `AGENTS.md` を読まず本ファイルのみ読むため、追跡対象として残す。

### 5.6 追跡解除するファイル（`git rm --cached`）

- `AGENTS.md`（実体 → 生成物化）
- `CLAUDE.md`（symlink → 生成物化）
- `.claude/agents/financial-data-extractor.md`（symlink）
- `.codex/agents/financial-data-extractor.toml`
- `.github/agents/financial-data-extractor.agent.md`
- `.agents/financial-data-extractor.md`（実体 → `.apm/agents/` へ移行後に削除）

### 5.7 `.gitignore` 追記

```gitignore
# apm 依存・成果物
apm_modules/

# apm コンパイル成果物（.apm/ から apm install / apm compile で再生成）
AGENTS.md
CLAUDE.md
.github/instructions/
.claude/rules/

# apm MCP 設定生成物
.mcp.json
.vscode/mcp.json
.codex/config.toml

# apm サブエージェント生成物
.claude/agents/
.codex/agents/
.github/agents/

# apm プラグイン展開先
.agents/skills/
.claude/skills/
.claude/commands/
.claude/hooks/
.claude/settings.json
.github/prompts/
.github/hooks/
```

> `apm.lock.yaml` は **追跡する**（gitignore しない）。

### 5.8 `docs/agents-convention.md` 改訂

- レイヤー①（AGENTS.md 実体 + symlink）とレイヤー②（`.agents/` 手書き + symlink/TOML）の旧規約を、apm ベースの規約へ全面改訂。
- 記載内容: SSoT は `.apm/`、生成物は触らない、版管理は `mise`、`apm install`/`apm compile` の使い分け、新規 instructions/agent の追加手順（`.apm/<type>/` に置く → `apm install`/`apm compile`）。

## 6. CI / セキュリティ

- **CI に apm を導入しない**。`deploy.yml` は `AGENTS.md`/`CLAUDE.md`/`README.md`/`copilot-instructions.md` を参照しないことを確認済みのため、生成物の gitignore 化は CI に影響しない。
- `dependencies.apm` の外部パッケージは**すべて commit SHA でピン**（リポジトリの SHA 固定方針・サプライチェーン対策に一致）。
- 版上げ運用: apm 本体は `mise.toml`、外部スキルは `apm.yml` の SHA を手動更新。

## 7. 移行手順（概要・順序）

実装の詳細手順は writing-plans で別途プラン化する。順序の骨子:

1. root `mise.toml` 作成 → `mise trust && mise install`（apm 導入確認、`apm --version`）。
2. `apm.yml` 作成（MCP 4 種・外部スキル 1 種、SHA/版を解決して固定）。
3. `AGENTS.md` 本文を `.apm/instructions/*.instructions.md` へ分割移行（apm 運用ルールを内包）。
4. `financial-data-extractor` を `.apm/agents/financial-data-extractor.agent.md` へ移行。
5. `README.md`・`.github/copilot-instructions.md` の symlink 解除 → 実体化。
6. `.gitignore` 更新。
7. 旧・手書き／生成物相当ファイルを `git rm --cached`（5.6）。
8. `apm install && apm compile` → 生成物を検証（3 ツール分のサブエージェント・MCP 設定・AGENTS.md/CLAUDE.md が期待通り生成されるか）。
9. `docs/agents-convention.md` 改訂。
10. `apm.lock.yaml` を含めコミット → PR（main 直 push 不可運用に準拠）。

## 8. トレードオフ / 受容するリスク

- **新規 clone 直後は `AGENTS.md`/`CLAUDE.md` が存在しない**（`apm compile` 実行まで）。→ README とオンボーディング手順に `mise install && apm install && apm compile` を明記して緩和。
- 2026-06-02 に作った `.agents/` 手書き規約は**撤廃**され apm の生成モデルへ置換される。
- MCP サーバ起動に開発者マシンの node（`npx`）/ uv（`uvx`）が必要（apm 本体とは別の前提）。

## 9. 実装時に確認・解決する事項（オープン）

- `apm.yml` のスキーマ（`registry`/`transport` 等のキー名）を、pin する apm 版の `apm init` 生成物または公式ドキュメントで最終確認する。
- serena の commit SHA、chrome-devtools-mcp / context7-mcp の固定版を実装時点の最新で解決。
- 開発者マシンの node / uv 導入状況（MCP ランタイム前提）の確認と setup 手順への反映。
- 生成された Codex TOML（`.codex/agents/*.toml`）が現行 `developer_instructions` 方式と同等に機能するかの検証。
