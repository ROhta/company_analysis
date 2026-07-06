# company_analysis

企業分析に用いる自作ツール群を保管するリポジトリ。

## ドキュメント

リポジトリ固有の指示は `.apm/instructions/` に集約しています。これらは [microsoft/apm](https://github.com/microsoft/apm) によって管理され、`apm compile` で `CLAUDE.md` / `AGENTS.md` に、`apm install` で `.claude/rules/` / `.github/instructions/` 等の各ツール (Claude Code / Codex / GitHub Copilot) 向けファイルに、ローカルで展開されます。

| ファイル | 内容 |
| --- | --- |
| [`project-overview`](.apm/instructions/project-overview.instructions.md) | 本リポジトリの目的と全体像 |
| [`agents-workflow`](.apm/instructions/agents-workflow.instructions.md) | サブエージェント（`.apm/agents`）運用ルール |
| [`tools`](.apm/instructions/tools.instructions.md) | 保管する自作ツール群（analyzeStocks / financialStatements）の一覧 |
| [`setup`](.apm/instructions/setup.instructions.md) | AI エージェント設定（生成物）の再生成手順 |

他リポジトリ共通の指示（言語・PR レビュー・開発フロー・apm 運用）は共通パッケージ [`ROhta/apm-config/base`](https://github.com/ROhta/apm-config) から `apm install` で配信され、ローカルの `.apm/instructions/` には保持しません。共通指示を変更したい場合は apm-config を編集します。

## MCP

共通 MCP サーバー (context7 / serena / deepwiki / chrome-devtools) も apm-config/mcp-toolkit から配信されます。うち chrome-devtools は transitive なプラグイン参照のため、導入時は `apm install --trust-transitive-mcp` が必要です。

MCP サーバーの起動には `node`（`npx` 用）と `uv`（`uvx` 用）が必要です。
