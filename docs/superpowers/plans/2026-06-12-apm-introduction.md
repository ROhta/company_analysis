# apm（Agent Package Manager）導入 実装プラン

> **エージェント実行者向け:** 必須サブスキル: superpowers:subagent-driven-development（推奨）または superpowers:executing-plans を使い、本プランをタスク単位で実装すること。各ステップは進捗管理のためチェックボックス（`- [ ]`）構文を用いる。

**ゴール:** [microsoft/apm](https://github.com/microsoft/apm) を導入し、`.apm/` を SSoT として各 AI ツール設定（指示・サブエージェント・MCP）を生成する運用へ移行する。

**アーキテクチャ:** `mise` で apm 本体（単独バイナリ）をピン。人間は `.apm/instructions/`・`.apm/agents/`・`apm.yml` のみ編集し、`apm install` / `apm compile` が `AGENTS.md`/`CLAUDE.md`・`.claude|.codex|.github/agents/`・`.mcp.json` 等を生成（`apm.lock.yaml` を除き gitignore）。既存の手書き symlink/TOML 規約は撤廃する。

**技術スタック:** mise, microsoft/apm 0.18.0（単独バイナリ）, YAML（apm.yml）, Markdown（instructions/agents）。MCP ランタイムは npx(node)/uvx(uv)。

**前提:** 設計仕様 `docs/superpowers/specs/2026-06-12-apm-introduction-design.md` 承認済み。作業ブランチ `feat/apm-introduction`（PR #23）。本プランは TDD ではなく**設定移行**のため、各タスクは「期待する検証コマンド → 実行 → 出力確認 → コミット」で進める。

**重要な順序制約:** `apm install` はサブエージェント等を `.claude/agents/` 等へ**実体ファイルで生成**する。これらのパスには現在 symlink が存在するため、**Task 6（旧追跡ファイルの追跡解除＋gitignore）を完了してから Task 7（apm install/compile）を実行**すること。順序を誤ると symlink と衝突する。

**コミット規約:** メッセージは日本語。各コミットに以下を付与する。

```
Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```

---

## File Structure

新規作成・変更・追跡解除するファイルの一覧と責務。

| 操作 | パス | 責務 |
|---|---|---|
| 作成 | `mise.toml`（root） | apm 本体の版 SSoT |
| 作成 | `apm.yml` | MCP・外部スキルの SSoT |
| 作成 | `.apm/instructions/project-overview.instructions.md` | 目的・全体像（旧 AGENTS.md より） |
| 作成 | `.apm/instructions/language.instructions.md` | 日本語ルール（旧 AGENTS.md より） |
| 作成 | `.apm/instructions/agents-workflow.instructions.md` | apm 運用ルール（SSoT・生成物・版管理） |
| 移動 | `.agents/financial-data-extractor.md` → `.apm/agents/financial-data-extractor.agent.md` | サブエージェント SSoT |
| 変更 | `README.md`（symlink → 実体） | 人間/GitHub 向け表紙（apm 生成対象外） |
| 変更 | `.github/copilot-instructions.md`（symlink → 実体スタブ） | Copilot Code Review への SoT 参照 |
| 変更 | `.gitignore` | apm 生成物を無視（`apm.lock.yaml` は追跡） |
| 追跡解除 | `AGENTS.md`, `CLAUDE.md`, `.claude/agents/financial-data-extractor.md`, `.codex/agents/financial-data-extractor.toml`, `.github/agents/financial-data-extractor.agent.md` | apm 生成物に置換 |
| 変更 | `docs/agents-convention.md` | apm ベース規約へ全面改訂 |
| 生成（追跡） | `apm.lock.yaml` | 再現性・オーファン検出 |

---

## Task 0: プリフライト（環境確認）

**Files:** なし（確認のみ）

- [ ] **Step 1: ブランチと作業ツリーの確認**

Run:
```bash
cd "$(git rev-parse --show-toplevel)"   # リポジトリのルートで実行
git branch --show-current
git status --porcelain
```
Expected: ブランチ `feat/apm-introduction`、作業ツリーがクリーン（未コミット変更なし）。

- [ ] **Step 2: mise の存在とバージョン確認**

Run:
```bash
mise --version
```
Expected: バージョンが表示される（apm のアセット解決のため新しめが望ましい。表示されない場合は[公式手順](https://mise.jdx.dev/getting-started.html)で導入）。

- [ ] **Step 3: MCP ランタイム前提の確認（情報収集）**

Run:
```bash
node --version 2>/dev/null || echo "node: なし"
uv --version 2>/dev/null || echo "uv: なし"
```
Expected: `node`（context7/chrome-devtools の `npx` 用）と `uv`（semgrep/serena の `uvx` 用）の有無を記録。
備考: **無くても apm install/compile は成功する**（apm は単独バイナリ）。無い場合は当該 MCP サーバが各 AI ツールで起動しないだけ。Task 8 の README/setup に前提として明記する。

---

## Task 1: root `mise.toml` 作成と apm 導入

**Files:**
- Create: `mise.toml`

- [ ] **Step 1: `mise.toml` を作成**

Create `mise.toml`:
```toml
[tools]
"github:microsoft/apm" = { version = "0.18.0", extract_all = "true" }
```

- [ ] **Step 2: mise を信頼してインストール**

Run:
```bash
mise trust && mise install
```
Expected: `github:microsoft/apm` が version 0.18.0 で導入される。エラーなく完了。

- [ ] **Step 3: apm が動作することを検証**

Run:
```bash
mise exec -- apm --version
```
Expected: `0.18.0`（または同等の版表記）が表示される。
備考: 以降 apm を呼ぶときは `mise exec -- apm ...`（シェルで `mise activate` 済みなら `apm ...` でも可）。

- [ ] **Step 4: コミット**

```bash
git add mise.toml
git commit -m "$(printf 'build(apm): root mise.toml で apm 本体を 0.18.0 に固定\n\napm は単独バイナリ。リポジトリ横断のため root に配置（per-tool mise.toml は不変）。\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 2: `apm.yml` 作成（MCP 4 種・外部スキル 1 種）

**Files:**
- Create: `apm.yml`

- [ ] **Step 1: ピンするバージョン/SHA を解決**

Run（各値を控える）:
```bash
npm view @upstash/context7-mcp version        # → CONTEXT7_VERSION
npm view chrome-devtools-mcp version          # → CHROME_DEVTOOLS_VERSION
git ls-remote https://github.com/oraios/serena HEAD | cut -f1      # → SERENA_SHA
git ls-remote https://github.com/obra/superpowers HEAD | cut -f1   # → SUPERPOWERS_SHA
```
Expected: 4 つの具体値（例: `1.0.x` / `1.x.y` / 40 桁 SHA × 2）。`npm` が無い場合は https://www.npmjs.com の各パッケージページで最新版を確認する。

- [ ] **Step 2: `apm.yml` を作成**（Step 1 で得た値を `<...>` に代入）

Create `apm.yml`:
```yaml
name: company_analysis
version: 1.0.0
description: 株式分析ツール群リポジトリの AI エージェント設定
author: ROhta
license: AGPL-3.0-or-later
targets: [claude, codex, copilot]
includes: auto
dependencies:
  mcp:
    - name: context7
      registry: false
      transport: stdio
      command: npx
      args: ["-y", "@upstash/context7-mcp@<CONTEXT7_VERSION>"]
    - name: semgrep
      registry: false
      transport: stdio
      command: uvx
      args: ["semgrep-mcp"]
    - name: serena
      registry: false
      transport: stdio
      command: uvx
      args: ["--from", "git+https://github.com/oraios/serena@<SERENA_SHA>", "serena", "start-mcp-server"]
    - name: chrome-devtools
      registry: false
      transport: stdio
      command: npx
      args: ["-y", "chrome-devtools-mcp@<CHROME_DEVTOOLS_VERSION>"]
  apm:
    - obra/superpowers#<SUPERPOWERS_SHA>
```
備考: `type:` は省略（content-driven）。`type: instructions` にすると agents の install が抑止される恐れがあるため。`semgrep-mcp` は bingo に倣い uvx で未ピン（uvx が解決）。

- [ ] **Step 3: YAML 構文を検証**

Run:
```bash
mise exec -- apm validate 2>/dev/null || python3 -c "import yaml,sys; yaml.safe_load(open('apm.yml')); print('apm.yml: valid YAML')"
```
Expected: `apm validate` が成功、または最低限 YAML として妥当（`apm.yml: valid YAML`）。
備考: `apm validate` サブコマンドの有無は版依存。無ければ後続 Task 7 の `apm install` 成功が実質的な検証になる。

- [ ] **Step 4: コミット**

```bash
git add apm.yml
git commit -m "$(printf 'feat(apm): apm.yml に MCP 4 種と外部スキルを宣言\n\ncontext7/semgrep/serena/chrome-devtools と obra/superpowers。外部依存は\nバージョン/commit SHA でピン（サプライチェーン対策）。\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 3: 全体指示を `.apm/instructions/` へ移行

**Files:**
- Create: `.apm/instructions/project-overview.instructions.md`
- Create: `.apm/instructions/language.instructions.md`
- Create: `.apm/instructions/agents-workflow.instructions.md`

- [ ] **Step 1: 移行元（現 AGENTS.md）を確認**

Run:
```bash
cat AGENTS.md
```
Expected: 「目的 / 詳細説明 / 使用言語 / エージェント定義」の 4 節。以下の Step で主題ごとに分割移行する。

- [ ] **Step 2: `project-overview.instructions.md` を作成**

Create `.apm/instructions/project-overview.instructions.md`:
```markdown
---
description: 本リポジトリの目的と全体像
---

## 目的

企業分析に用いる様々な自作ツールを保管しておく場所。

## 詳細説明

各ツールの使用方法は各ディレクトリの README.md に記載されているので、参照すること。
```

- [ ] **Step 3: `language.instructions.md` を作成**

Create `.apm/instructions/language.instructions.md`:
```markdown
---
description: 自然言語を記述する際の言語ルール
---

## 使用言語

プロンプトの応答や、コミットメッセージ、ソースコードコメントなど、自然言語を記述する場合は全て日本語で記述する。
```

- [ ] **Step 4: `agents-workflow.instructions.md` を作成（apm 運用ルール）**

Create `.apm/instructions/agents-workflow.instructions.md`:
```markdown
---
description: apm（Agent Package Manager）を介した AI エージェント設定の運用ルール
applyTo: ".apm/**"
---

# apm 運用ルール

## Source of Truth

`.apm/instructions/*.instructions.md`（全体指示）・`.apm/agents/*.agent.md`（サブエージェント）・`apm.yml`（MCP サーバと外部スキル）が人間の編集対象。ここを直すことで Claude Code / Codex CLI / GitHub Copilot すべてに同じ設定が届く。

## apm 本体のバージョン

apm CLI 本体のバージョンは root `mise.toml`（`github:microsoft/apm`）を SSoT とする。更新は `mise.toml` の version を上げて `mise install`。`apm self-update` / `apm doctor` の更新催促には従わない（mise 管理外のグローバルインストールを増やさないため）。

## ファイルの管理方針

| パス | 役割 | 追跡 |
|---|---|---|
| `.apm/instructions/*.instructions.md` | 全体指示の SSoT（人間が編集） | ✅ |
| `.apm/agents/*.agent.md` | サブエージェントの SSoT（人間が編集） | ✅ |
| `apm.yml` | MCP・外部スキルの SSoT（人間が編集） | ✅ |
| `apm.lock.yaml` | 再現性・オーファン検出のため例外的に追跡 | ✅ |
| `README.md` | 人間/GitHub 向け実体（apm 生成対象外） | ✅ |
| `.github/copilot-instructions.md` | Copilot Code Review への SoT 参照スタブ | ✅ |
| `AGENTS.md` / `CLAUDE.md` | `apm compile` 生成 | ❌ |
| `.claude/agents/`・`.codex/agents/`・`.github/agents/` | `apm install` 生成（サブエージェント3形式） | ❌ |
| `.mcp.json`・`.vscode/mcp.json`・`.codex/config.toml` | `apm install` 生成（MCP 設定） | ❌ |
| `.github/instructions/`・`.claude/rules/`・`apm_modules/` 等 | `apm install` 生成 | ❌ |

## ローカルでの作業

`.apm/` または `apm.yml` を編集後、以下で生成物を更新する。

```bash
mise exec -- apm install   # MCP 設定・サブエージェント・instructions 等を各ツールへ展開
mise exec -- apm compile   # AGENTS.md / CLAUDE.md を生成
```

`apm.lock.yaml` を除く生成物は `.gitignore` 対象のためコミットに含まれない。

## 新しい指示・エージェントの追加

- 全体指示: `.apm/instructions/<topic>.instructions.md` を追加 → `apm compile`。
- サブエージェント: `.apm/agents/<name>.agent.md`（frontmatter に `description`、任意で `name`）を追加 → `apm install` が `.claude/agents/*.md`・`.codex/agents/*.toml`・`.github/agents/*.agent.md` を生成。

## GitHub Copilot Code Review への指示伝達

2026 年時点、Copilot Code Review は `AGENTS.md` を読まず `.github/copilot-instructions.md` または `.github/instructions/*.instructions.md` のみ読む。本リポジトリは `.github/copilot-instructions.md` を SoT 参照スタブとして追跡する。
```

- [ ] **Step 5: 3 ファイルが揃ったことを検証**

Run:
```bash
ls -1 .apm/instructions/
```
Expected:
```
agents-workflow.instructions.md
language.instructions.md
project-overview.instructions.md
```

- [ ] **Step 6: コミット**

```bash
git add .apm/instructions/
git commit -m "$(printf 'feat(apm): 全体指示を .apm/instructions/ へ移行\n\n旧 AGENTS.md 本文を主題別に分割し、apm 運用ルールを追加。\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 4: サブエージェントを `.apm/agents/` へ移行

**Files:**
- Move: `.agents/financial-data-extractor.md` → `.apm/agents/financial-data-extractor.agent.md`

- [ ] **Step 1: `.apm/agents/` を作成し本文を移動**

Run:
```bash
mkdir -p .apm/agents
git mv .agents/financial-data-extractor.md .apm/agents/financial-data-extractor.agent.md
```
Expected: 実体ファイル（10249 bytes）が移動。frontmatter は `name` + `description` のままで apm 互換（`description` 必須を満たす）。

- [ ] **Step 2: frontmatter が apm 互換であることを検証**

Run:
```bash
sed -n '1,4p' .apm/agents/financial-data-extractor.agent.md
```
Expected:
```
---
name: financial-data-extractor
description: 企業の財務資料（...）から... companyData JSON を生成するときに使う。
---
```

- [ ] **Step 3: コミット**

```bash
git add -A .apm/agents/ .agents/
git commit -m "$(printf 'feat(apm): financial-data-extractor を .apm/agents/ へ移行\n\n手書き symlink/TOML ラッパーを廃し、apm Agents primitive を SSoT に。\n各ツール形式は apm install が生成する。\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 5: `README.md` と `.github/copilot-instructions.md` を symlink から実体へ

**Files:**
- Modify: `README.md`（symlink → 実体）
- Modify: `.github/copilot-instructions.md`（symlink → 実体スタブ）

- [ ] **Step 1: README.md の symlink を解除**

Run:
```bash
rm README.md
```
Expected: symlink 削除（実体 AGENTS.md は残る）。

- [ ] **Step 2: 人間/GitHub 向け README.md を作成**

Create `README.md`:
```markdown
# company_analysis

企業分析に用いる自作ツール群を保管するリポジトリ。

## ツール

- **analyzeStocks/** — J-Quants API を用いた株価スクリーニング等（Python / mise 管理）。
- **financialStatements/** — 財務諸表の可視化ダッシュボード（Vite / mise 管理）。

各ツールの詳細は各ディレクトリの README.md を参照。

## AI エージェント設定

本リポジトリは [microsoft/apm](https://github.com/microsoft/apm)（Agent Package Manager）で
Claude Code / Codex CLI / GitHub Copilot 向けの設定を管理している。

- 編集対象（SSoT）: `.apm/instructions/`・`.apm/agents/`・`apm.yml`
- 生成物（`apm install` / `apm compile`）: `AGENTS.md` / `CLAUDE.md` / 各ツールの agents・MCP 設定（`apm.lock.yaml` を除き gitignore）
- 運用ルールの詳細: `.apm/instructions/agents-workflow.instructions.md` および `docs/agents-convention.md`

## セットアップ（AI エージェント設定の再生成）

```bash
mise trust && mise install            # apm 本体（および各 mise ツール）を導入
mise exec -- apm install              # MCP 設定・サブエージェント等を各ツールへ展開
mise exec -- apm compile              # AGENTS.md / CLAUDE.md を生成
```

備考: MCP サーバの起動には `node`（`npx` 用）と `uv`（`uvx` 用）が必要。
```

- [ ] **Step 3: copilot-instructions.md の symlink を解除しスタブを作成**

Run:
```bash
rm .github/copilot-instructions.md
```
Create `.github/copilot-instructions.md`:
```markdown
# GitHub Copilot 用指示（スタブ）

本リポジトリの AI エージェント向け指示の Source of Truth は `.apm/instructions/` 配下にある。
全体指示・言語ルール・運用ルールはそこを参照すること。

- 言語ルール: 自然言語（応答・コミットメッセージ・コードコメント等）は全て日本語で記述する。
- 運用ルール: `.apm/instructions/agents-workflow.instructions.md`

このファイルは Copilot Code Review が `AGENTS.md` を読まない仕様への対応として配置している
手書きスタブであり、`apm` の生成物ではない（追跡対象）。
```

- [ ] **Step 4: 両ファイルが実体（非 symlink）になったことを検証**

Run:
```bash
for f in README.md .github/copilot-instructions.md; do test -L "$f" && echo "$f: まだ symlink（NG）" || echo "$f: 実体（OK）"; done
```
Expected:
```
README.md: 実体（OK）
.github/copilot-instructions.md: 実体（OK）
```

- [ ] **Step 5: コミット**

```bash
git add README.md .github/copilot-instructions.md
git commit -m "$(printf 'refactor(apm): README と copilot-instructions を symlink から実体化\n\nREADME は apm 生成対象外のため人間向け表紙として独立。copilot は\nSoT 参照スタブに（Copilot Code Review は AGENTS.md を読まないため）。\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 6: `.gitignore` 更新と旧追跡ファイルの追跡解除（フリップ）

**Files:**
- Modify: `.gitignore`
- 追跡解除: `AGENTS.md`, `CLAUDE.md`, `.claude/agents/financial-data-extractor.md`, `.codex/agents/financial-data-extractor.toml`, `.github/agents/financial-data-extractor.agent.md`

> このタスク完了後に Task 7 を実行すること（生成物が symlink と衝突しないため）。

- [ ] **Step 1: `.gitignore` に apm 生成物を追記**

現在の `.gitignore` 末尾に以下を追記（既存行は残す）:
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
備考: `apm.lock.yaml` は **記載しない**（追跡する）。

- [ ] **Step 2: 旧追跡ファイルを index から除去**

Run:
```bash
git rm --cached AGENTS.md CLAUDE.md \
  .claude/agents/financial-data-extractor.md \
  .codex/agents/financial-data-extractor.toml \
  .github/agents/financial-data-extractor.agent.md
```
Expected: 5 ファイルが index から除去（`rm '...'` が 5 行）。symlink（CLAUDE.md ほか）は作業ツリーからも消えるが問題ない（apm が再生成）。AGENTS.md は実体が作業ツリーに残るが gitignore 済みのため次の generate で上書きされる。

- [ ] **Step 3: 追跡状態を検証**

Run:
```bash
git status --porcelain | grep -E 'AGENTS|CLAUDE|agents/financial' || echo "対象ファイルは追跡から外れた"
git check-ignore AGENTS.md CLAUDE.md .claude/agents .codex/agents .github/agents
```
Expected: 1 行目は削除（`D`）として表示、`git check-ignore` は各パスを ignore 対象として出力。

- [ ] **Step 4: コミット**

```bash
git add .gitignore
git commit -m "$(printf 'chore(apm): 生成物を gitignore 化し旧追跡ファイルを追跡解除\n\nAGENTS.md/CLAUDE.md・各ツールの agents・MCP 設定生成物を無視。\napm.lock.yaml は再現性のため追跡継続。\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 7: `apm install` / `apm compile` 実行と生成物検証

**Files:**
- 生成（追跡）: `apm.lock.yaml`
- 生成（gitignore）: `AGENTS.md`, `CLAUDE.md`, `.mcp.json`, `.vscode/mcp.json`, `.codex/config.toml`, `.claude/agents/*.md`, `.codex/agents/*.toml`, `.github/agents/*.agent.md` ほか

- [ ] **Step 1: 依存をインストール（MCP 設定・サブエージェント等を展開）**

Run:
```bash
mise exec -- apm install
```
Expected: エラーなく完了。`apm_modules/` に obra/superpowers が取得され、`apm.lock.yaml` が生成される。

- [ ] **Step 2: instructions をコンパイル（AGENTS.md / CLAUDE.md 生成）**

Run:
```bash
mise exec -- apm compile
```
Expected: `AGENTS.md` と `CLAUDE.md` が生成される。

- [ ] **Step 3: MCP 設定生成物を検証（4 サーバが含まれるか）**

Run:
```bash
for f in .mcp.json .vscode/mcp.json .codex/config.toml; do echo "--- $f ---"; grep -oE 'context7|semgrep|serena|chrome-devtools' "$f" 2>/dev/null | sort -u; done
```
Expected: 各ファイルに `chrome-devtools / context7 / semgrep / serena` の 4 つが現れる（フォーマットは各ツール仕様による）。

- [ ] **Step 4: サブエージェント生成物を検証（3 形式）**

Run:
```bash
ls .claude/agents/financial-data-extractor.md \
   .codex/agents/financial-data-extractor.toml \
   .github/agents/financial-data-extractor.agent.md
test -f .codex/agents/financial-data-extractor.toml && grep -c 'financial-data-extractor' .codex/agents/financial-data-extractor.toml
```
Expected: 3 ファイルが存在し、Codex TOML 内にエージェント名が含まれる（Markdown→TOML 変換が機能）。

- [ ] **Step 5: AGENTS.md / CLAUDE.md の中身を検証**

Run:
```bash
grep -q '企業分析' AGENTS.md && grep -q '日本語' AGENTS.md && echo "AGENTS.md: 期待内容あり"
diff <(cat AGENTS.md) <(cat CLAUDE.md) >/dev/null && echo "CLAUDE.md は AGENTS.md と同等" || echo "CLAUDE.md は AGENTS.md と差分あり（ツール別整形のため許容）"
```
Expected: `AGENTS.md: 期待内容あり` が出る（移行した目的・日本語ルールが含まれる）。

- [ ] **Step 6: 生成物が追跡対象に漏れていないことを検証（apm.lock.yaml のみ追跡）**

Run:
```bash
git status --porcelain
```
Expected: `?? apm.lock.yaml` のみ（AGENTS.md/CLAUDE.md/.mcp.json/各 agents 等は gitignore により出てこない）。もし生成物が `??` で出る場合は Task 6 Step 1 の gitignore 記載漏れ → 追記して再確認。

- [ ] **Step 7: `apm.lock.yaml` をコミット**

```bash
git add apm.lock.yaml
git commit -m "$(printf 'chore(apm): apm.lock.yaml を追加（再現性・オーファン検出）\n\napm install の生成物。dup バグは v0.8.12 で修正済みのため dedupe 後処理は不要。\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 8: `docs/agents-convention.md` を apm ベースへ改訂

**Files:**
- Modify: `docs/agents-convention.md`（全面置換）

- [ ] **Step 1: 既存内容を apm 版へ全面置換**

Replace `docs/agents-convention.md` の全内容を以下に:
```markdown
# エージェント設定の規約（apm ベース / Claude Code・Codex CLI・GitHub Copilot 対応）

- 改訂日: 2026-06-12
- 対象: 本リポジトリの AI エージェント設定全般

本リポジトリは [microsoft/apm](https://github.com/microsoft/apm)（Agent Package Manager）で
AI エージェント設定を管理する。人間は `.apm/` と `apm.yml` のみを編集し、各 AI ツールが読む
ファイルは `apm install` / `apm compile` が生成する。

## 単一ソース（SSoT）

| 編集対象 | 役割 |
|---|---|
| `.apm/instructions/*.instructions.md` | プロジェクト全体指示（目的・言語ルール・運用ルール等） |
| `.apm/agents/*.agent.md` | タスク特化サブエージェント（frontmatter は `description`、任意で `name`） |
| `apm.yml` | MCP サーバ（`dependencies.mcp`）と外部スキル（`dependencies.apm`） |
| `mise.toml`（root） | apm 本体のバージョン |

## 生成物（編集しない）

`apm install` が `.claude/agents/`・`.codex/agents/`・`.github/agents/`・`.mcp.json`・
`.vscode/mcp.json`・`.codex/config.toml`・`.github/instructions/`・`.claude/rules/` 等を、
`apm compile` が `AGENTS.md`・`CLAUDE.md` を生成する。これらは `apm.lock.yaml` を除き gitignore。

例外的に追跡する手書きファイル: `README.md`（人間/GitHub 向け表紙）、
`.github/copilot-instructions.md`（Copilot Code Review への SoT 参照スタブ）、`apm.lock.yaml`。

## 新しい指示・エージェントを追加する手順

1. 全体指示なら `.apm/instructions/<topic>.instructions.md`、サブエージェントなら
   `.apm/agents/<name>.agent.md` を作成する。
2. 生成物を更新する:
   ```bash
   mise exec -- apm install   # agents / MCP / skills 等を各ツールへ展開
   mise exec -- apm compile   # AGENTS.md / CLAUDE.md を生成
   ```
3. `apm.lock.yaml` の差分のみコミットする（他の生成物は gitignore）。

## バージョン管理

- apm 本体: root `mise.toml`（`github:microsoft/apm`）を SSoT とし `mise install` で更新。
  `apm self-update` / `apm doctor` の更新催促には従わない。
- 外部スキル: `apm.yml` の commit SHA / バージョンを手動更新（サプライチェーン対策でピン必須）。

## CI

CI に apm は導入しない（生成物は CI で不要。`deploy.yml` は AGENTS.md 等を参照しない）。
```

- [ ] **Step 2: 旧規約（symlink/TOML 手書き手順）が残っていないことを検証**

Run:
```bash
grep -nE 'symlink|ln -s|developer_instructions' docs/agents-convention.md || echo "旧手順の記述なし（OK）"
```
Expected: `旧手順の記述なし（OK）`。

- [ ] **Step 3: コミット**

```bash
git add docs/agents-convention.md
git commit -m "$(printf 'docs(apm): agents-convention.md を apm ベース規約へ全面改訂\n\nAGENTS.md 実体+symlink / .agents 手書き規約を廃し、.apm SSoT と\napm install/compile 生成モデルへ更新。\n\nCo-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>')"
```

---

## Task 9: 最終検証と push

**Files:** なし（検証と push）

- [ ] **Step 1: AGENTS.md 内のエージェント定義への言及を確認・更新**

Run:
```bash
grep -n 'docs/agents-convention.md\|\.agents/' .apm/instructions/*.md
```
Expected: instructions 内の参照が `.apm/` ベースに整合していること（`.agents/` への古い参照が残っていれば該当 instructions を修正して `apm compile` を再実行し、Task 3 の該当コミットを amend せず追加コミットする）。

- [ ] **Step 2: 作業ツリーがクリーンで、生成物が追跡されていないことを確認**

Run:
```bash
git status --porcelain
git ls-files | grep -E '^(AGENTS\.md|CLAUDE\.md|\.mcp\.json|\.claude/agents/|\.codex/agents/|\.github/agents/)' || echo "生成物は追跡されていない（OK）"
git ls-files | grep -E '^(apm\.yml|apm\.lock\.yaml|mise\.toml|README\.md|\.github/copilot-instructions\.md)$'
```
Expected: 1 行目は空（クリーン）。2 行目は `生成物は追跡されていない（OK）`。3 行目に SSoT/手書きファイルが列挙される。

- [ ] **Step 3: コミット履歴を確認**

Run:
```bash
git --no-pager log --oneline origin/main..HEAD
```
Expected: Task 1〜8 のコミット（+ 設計仕様・description 修正の既存 2 コミット）が並ぶ。

- [ ] **Step 4: push（PR #23 を更新）**

Run:
```bash
git push
```
Expected: `feat/apm-introduction` が更新され、PR #23 に反映される。

- [ ] **Step 5: 後片付けの確認**

Run:
```bash
ls .agents/ 2>/dev/null
```
Expected: `.agents/` は空、または `skills/`（apm 生成・gitignore）のみ。空なら `.agents/` ディレクトリ自体の扱い（削除 or 保持）を判断する（git は空ディレクトリを追跡しないため通常は放置で可）。

---

## Self-Review メモ（プラン作成者による確認結果）

- **Spec coverage:** 仕様 §5.1〜5.8（mise / apm.yml / instructions / agents / README・copilot / gitignore・追跡解除 / agents-convention）は Task 1〜8 に対応。§6（CI/セキュリティ）は agents-convention と README に明記、SHA ピンは Task 2 で実施。§7 手順は Task 0〜9 に展開。§9 オープン事項は Task 0 Step 3（node/uv）・Task 2 Step 1,3（SHA/版・schema）・Task 7 Step 4（Codex TOML 検証）でクローズ。
- **Placeholder scan:** `<CONTEXT7_VERSION>` 等はプレースホルダではなく Task 2 Step 1 の解決コマンド出力を代入する具体値（解決手順あり）。
- **Type consistency:** ファイルパス・コマンドは全 Task で一貫（`.apm/agents/financial-data-extractor.agent.md`、`mise exec -- apm ...`）。

## 既知の不確実性（実行時に確認）

- `apm.yml` の MCP エントリのキー名（`registry`/`transport`/`command`/`args`）は bingo の apm 0.18.0 実績スキーマに準拠。万一 `apm install` が schema エラーを出す場合は、`mise exec -- apm init` を一時ディレクトリで実行して当該版の正規スキーマを確認し、差分を反映する。
- `apm compile` / `apm install` が生成する正確なパス（特に Codex の `.codex/config.toml` か別名か）は版により差異の可能性。Task 7 Step 3,6 の `git status` で実際の生成パスを確認し、gitignore 記載と齟齬があれば Task 6 の記載を追補する。
