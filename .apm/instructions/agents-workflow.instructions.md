---
description: apm（Agent Package Manager）を介した AI エージェント設定の運用ルール
applyTo: "{.apm/**,apm.yml,apm.lock.yaml,.gitignore}"
---

# apm 運用ルール

## 単一ソース（SSoT）

`.apm/instructions/*.instructions.md`（全体指示）・`.apm/agents/*.agent.md`（サブエージェント）・`apm.yml`（MCP サーバと外部スキル）がリポジトリ固有の編集対象。ここを直すことで Claude Code / Codex CLI / GitHub Copilot すべてに同じ設定が届く。

全リポジトリ共通の指示（言語ルール・PR レビュー観点）は [`ROhta/apm-config/base`](https://github.com/ROhta/apm-config) が、共通 MCP サーバーセットは [`ROhta/apm-config/mcp-toolkit`](https://github.com/ROhta/apm-config) が SSoT。`apm.yml` の `dependencies.apm` から参照する。共通ルールを直すときは本リポジトリではなく apm-config を編集し、`apm update` で取り込む。

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
| `.github/copilot-instructions.md` | Copilot Code Review への SoT 参照スタブ（apm 生成対象外） | ✅ |
| `AGENTS.md` / `CLAUDE.md` | `apm compile` 生成 | ❌ |
| `.claude/agents/`・`.codex/agents/`・`.github/agents/` | `apm install` 生成（サブエージェント3形式） | ❌ |
| `.mcp.json`・`.vscode/mcp.json`・`.codex/config.toml` | `apm install` 生成（MCP 設定） | ❌ |
| `.github/instructions/{pr-review,language}.instructions.md` | `apm install` 生成（base 由来）。クラウド Copilot Code Review 用に例外的に追跡 | ✅ |
| `.github/instructions/` のその他 | `apm install` 生成。SoT は `.apm/` にあり重複のため追跡しない | ❌ |
| `.claude/rules/`・`apm_modules/` 等 | `apm install` 生成 | ❌ |

## ローカルでの作業

`.apm/` または `apm.yml` を編集後、以下で生成物を更新する。

```bash
mise exec -- apm install                  # MCP 設定・サブエージェント・instructions 等を各ツールへ展開
mise exec -- apm compile --single-agents  # AGENTS.md / CLAUDE.md を生成（monolithic）
```

生成物のうち `apm.lock.yaml` と `.github/instructions/*.instructions.md`（クラウド Copilot 経路確保のための例外）は追跡対象としてコミットする。それ以外の生成物（`AGENTS.md` / `CLAUDE.md` / `.claude/rules/` など）は `.gitignore` 対象のためコミットに含まれない。

compile は `--single-agents`（monolithic）を標準とする。既定の distributed モードでは applyTo を持たない global 指示が「既に `.github/instructions/` にある」として AGENTS.md から除外され、AGENTS.md のみを読む Codex CLI に global 指示が届かないため（Claude は `.claude/rules/`、Copilot は `.github/instructions/` から native に取得するので影響しない）。

## 新しい指示・エージェントの追加

- 全体指示: `.apm/instructions/<topic>.instructions.md` を追加 → `apm compile`。
- サブエージェント: `.apm/agents/<name>.agent.md`（frontmatter に `description`、任意で `name`）を追加 → `apm install` が `.claude/agents/*.md`・`.codex/agents/*.toml`・`.github/agents/*.agent.md` を生成。

## GitHub Copilot Code Review への指示伝達

2026 年時点、Copilot Code Review は `AGENTS.md` を読まず `.github/copilot-instructions.md` または `.github/instructions/*.instructions.md` のみ読む。共通指示（pr-review / language）を apm-config/base へ移したため、その生成物 `.github/instructions/pr-review.instructions.md` / `language.instructions.md` のみ追跡対象にしてクラウド経路へ届ける（第三者依存や重複生成物は追跡しない。`.gitignore` 参照）。あわせて `.github/copilot-instructions.md` を SoT 参照スタブとして追跡する（apm の生成対象には含めない）。
