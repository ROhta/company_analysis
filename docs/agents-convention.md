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

`apm install` が `.claude/`・`.codex/`・`.github/agents/`・`.github/instructions/`・`.github/hooks/`・
`.mcp.json`・`.vscode/mcp.json` 等を、`apm compile --single-agents` が `AGENTS.md`・`CLAUDE.md` を
生成する。これらは `apm.lock.yaml` を除き gitignore。

例外的に追跡する手書きファイル: `README.md`（人間/GitHub 向け表紙）、
`.github/copilot-instructions.md`（Copilot Code Review への SoT 参照スタブ）、`apm.lock.yaml`。

## 各ツールへの指示の届き方

| ツール | 指示の取得元 |
|---|---|
| Claude Code | `.claude/rules/*.md`（`apm install` が native 配置） |
| GitHub Copilot | `.github/instructions/*.instructions.md`（`apm install`）+ `.github/copilot-instructions.md`（手書きスタブ） |
| Codex CLI | `AGENTS.md`（`apm compile --single-agents` が monolithic に生成） |

## 新しい指示・エージェントを追加する手順

1. 全体指示なら `.apm/instructions/<topic>.instructions.md`、サブエージェントなら
   `.apm/agents/<name>.agent.md` を作成する。
2. 生成物を更新する:
   ```bash
   mise exec -- apm install                  # agents / MCP / skills 等を各ツールへ展開
   mise exec -- apm compile --single-agents  # AGENTS.md / CLAUDE.md を生成（monolithic）
   ```
3. `apm.lock.yaml` の差分のみコミットする（他の生成物は gitignore）。

> compile は `--single-agents`（monolithic）を標準とする。既定の distributed モードでは
> applyTo を持たない global 指示が AGENTS.md から除外され、AGENTS.md のみを読む Codex CLI に
> global 指示が届かないため。

## バージョン管理

- apm 本体: root `mise.toml`（`github:microsoft/apm`）を SSoT とし `mise install` で更新。
  `apm self-update` / `apm doctor` の更新催促には従わない。
- 外部スキル: `apm.yml` の commit SHA / バージョンを手動更新（サプライチェーン対策でピン必須）。

## CI

CI に apm は導入しない（生成物は CI で不要。`deploy.yml` は AGENTS.md 等を参照しない）。
