---
description: AI エージェント設定（生成物）を再生成するためのセットアップ手順
applyTo: "**/{mise.toml,apm.yml,apm.lock.yaml}"
---

# セットアップ（AI エージェント設定の再生成）

```bash
mise trust && mise install    # apm 本体（および各 mise ツール）を導入
mise exec -- apm install      # MCP 設定・サブエージェント等を各ツールへ展開
mise exec -- apm compile      # AGENTS.md / CLAUDE.md を生成
```
