---
description: 本リポジトリのサブエージェント（.apm/agents）運用ルール
applyTo: ".apm/agents/**"
---

# サブエージェント運用ルール

apm を介した AI エージェント設定の共通運用ルール（Source of Truth 宣言・apm CLI 本体のバージョン・生成物のファイル管理方針・ローカルでの `apm install` / `apm compile`・GitHub Copilot Code Review への指示伝達）は、共通パッケージ [`ROhta/apm-config/base`](https://github.com/ROhta/apm-config) の apm-workflow ルールから配信される。本ファイルは base がカバーしないサブエージェント固有の運用だけを定義する。

## Source of Truth

`.apm/agents/*.agent.md` が本リポジトリのサブエージェント定義の Source of Truth（人間が編集する）。frontmatter に `description`（任意で `name`）を持つ。

## ファイルの管理方針（サブエージェント固有）

| パス | 役割 | 追跡 |
|---|---|---|
| `.apm/agents/*.agent.md` | サブエージェント定義の SoT（人間が編集） | ✅ 追跡する |
| `.claude/agents/*.md`・`.codex/agents/*.toml`・`.github/agents/*.agent.md` | `apm install` が生成するサブエージェント 3 形式 | ❌ 追跡しない |

## サブエージェントの追加

`.apm/agents/<name>.agent.md` を追加して `apm install` を実行すると、`.claude/agents/*.md`（Claude Code）・`.codex/agents/*.toml`（Codex CLI）・`.github/agents/*.agent.md`（GitHub Copilot）の 3 形式が生成される。
