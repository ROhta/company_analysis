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
| `.github/copilot-instructions.md` | Copilot Code Review への SoT 参照スタブ（apm 生成対象外） | ✅ |
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

2026 年時点、Copilot Code Review は `AGENTS.md` を読まず `.github/copilot-instructions.md` または `.github/instructions/*.instructions.md` のみ読む。本リポジトリは `.github/copilot-instructions.md` を SoT 参照スタブとして追跡する（apm の生成対象には含めない）。
