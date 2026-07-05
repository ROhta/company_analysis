# GitHub Copilot 用指示（スタブ）

本リポジトリ固有の AI エージェント向け指示の Source of Truth は `.apm/instructions/` 配下にある。
共通の指示（言語ルール・PR レビュー観点・開発/apm 運用フロー）は共有パッケージ `ROhta/apm-config/base` が Source of Truth。

- 言語ルール: 自然言語（応答・コミットメッセージ・コードコメント等）は全て日本語で記述する（詳細は [`.github/instructions/language.instructions.md`](instructions/language.instructions.md)、SoT は apm-config/base）。
- PR レビュー: [`.github/instructions/pr-review.instructions.md`](instructions/pr-review.instructions.md)（SoT は apm-config/base）
- サブエージェント運用: `.apm/instructions/agents-workflow.instructions.md`

このファイルは Copilot Code Review が `AGENTS.md` を読まない仕様への対応として配置している
手書きスタブであり、`apm` の生成物ではない（追跡対象）。
