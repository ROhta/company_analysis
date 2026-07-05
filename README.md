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
- 共通運用ルール（言語・PR レビュー・開発フロー・apm 運用）は共通パッケージ [`ROhta/apm-config/base`](https://github.com/ROhta/apm-config) が配信する。リポジトリ固有のサブエージェント運用のみ `.apm/instructions/agents-workflow.instructions.md` を参照。

## セットアップ（AI エージェント設定の再生成）

```bash
mise trust && mise install    # apm 本体（および各 mise ツール）を導入
mise exec -- apm install      # MCP 設定・サブエージェント等を各ツールへ展開
mise exec -- apm compile      # AGENTS.md / CLAUDE.md を生成
```

備考:

- MCP サーバの起動には `node`（`npx` 用）と `uv`（`uvx` 用）が必要。
