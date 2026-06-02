# エージェント定義の規約（Claude Code / Codex CLI / GitHub Copilot 対応）

- 作成日: 2026-06-02
- 対象: 本リポジトリの AI エージェント設定全般

このリポジトリは、AI エージェントの設定を **2 つのレイヤー** に分け、それぞれ **単一ソース** から
Claude Code・Codex CLI・GitHub Copilot の 3 ツールへ展開している。新しいエージェントや指示を
追加するときは本書の手順に従うこと。

## レイヤー① プロジェクト全体指示

言語ルールや目的など、リポジトリ全体に効く指示。**`AGENTS.md` を基軸（実体）** とし、各ツールが読む
ファイルは symlink で同一内容を共有する。

| ファイル | 実体/リンク | 読むツール |
|---|---|---|
| `AGENTS.md` | 実体（単一ソース） | Codex CLI（ネイティブ対応） |
| `CLAUDE.md` → `AGENTS.md` | symlink | Claude Code |
| `README.md` → `AGENTS.md` | symlink | 人間 / GitHub |
| `.github/copilot-instructions.md` → `AGENTS.md` | symlink | GitHub Copilot |

→ 全体指示を変えるときは **`AGENTS.md` だけ** を編集する。

## レイヤー② タスク特化エージェント定義

`financial-data-extractor` のような専用エージェント。3 ツールで **定義フォーマットが非互換** なため、
本文（手順）を 1 箇所に置き、各ツール用は薄いラッパーにする。

### 各ツールの仕様（リポジトリ配置）

| ツール | 配置ディレクトリ | 形式 | 拡張子 | 必須フィールド |
|--------|-----------------|------|--------|-----------------|
| Claude Code | `.claude/agents/` | Markdown + YAML frontmatter | `.md` | `name`, `description` |
| Codex CLI | `.codex/agents/` | **TOML** | `.toml` | `name`, `description`, `developer_instructions` |
| GitHub Copilot | `.github/agents/` | Markdown + YAML frontmatter | `.agent.md` | `description`（`name` 任意） |

- **Claude ↔ Copilot** は同じ Markdown + frontmatter なので、本文を symlink で共有できる。
- **Codex のみ TOML** で本文を文字列フィールドに持つため symlink 共有が不可能 → 本文への参照を指示する
  ポインタ方式にする。

### 単一ソースの配置

- 本文の実体は **`.agents/<name>.md`** に置く（`.claude` / `.codex` / `.github` と並ぶ「ツール用ソース」）。
- ルート直下の `agents/` は **使わない**（Copilot が組織レベル custom agent を `agents/` から拾う規約と
  衝突するため）。

### frontmatter は `name` / `description` のみ

symlink で同一ファイルを共有する以上、ツール間で名前・値が異なる **`tools` / `model` は書かない**。

- `name` + `description` だけなら Claude の必須ペアを満たし、Copilot は余分な `name` を許容する。
- `tools` 省略はデフォルト（全ツール使用可）として扱われる。

## 新しいエージェントを追加する手順

`<name>` を付けたいエージェント名（kebab-case）とする。

1. **本文を 1 ファイル作る**
   `.agents/<name>.md` に frontmatter（`name` / `description` のみ）＋本文を書く。

   ```markdown
   ---
   name: <name>
   description: （いつ使うエージェントかを 1 行で）
   ---

   # （エージェント名）
   …手順・検証・出力形式…
   ```

2. **Claude / Copilot 用に相対 symlink を 2 本張る**

   ```bash
   ln -s ../../.agents/<name>.md .claude/agents/<name>.md
   ln -s ../../.agents/<name>.md .github/agents/<name>.agent.md
   ```

3. **Codex 用に TOML ラッパーを 1 つ書く**
   `.codex/agents/<name>.toml`：

   ```toml
   name = "<name>"
   description = "（.agents の description と同じ要約）"
   developer_instructions = """
   このエージェントの完全な仕様は `.agents/<name>.md` に定義されています。
   作業を始める前に必ずそのファイルを読み込み、記載内容に従ってください。
   """
   ```

これで 3 ツールすべてが同一の本文を共有する。**本文を直すときは `.agents/<name>.md` だけ** を編集すれば
Claude / Copilot には即反映される（Codex は本文を参照する仕様のため同様に追従する）。

## 将来の拡張（生成スクリプト方式）

エージェントごとに `tools` / `model` を出し分けたくなった場合や、Codex に本文を完全インラインしたく
なった場合は、`.agents/<name>.md` を入力に 3 ファイルを生成する **Python 標準ライブラリのみのスクリプト**
へ移行できる（第三者依存なし＝本リポジトリの依存方針に準拠）。`.agents/` を単一ソースに保ってあるため、
symlink を生成物へ置き換えるだけで移行できる。
