# claude-skills-researchreview

研究・論文執筆向けの Claude スキル集です。

## 収録スキル

| スキル | 内容 | ダウンロード |
| --- | --- | --- |
| [paper-review-loop](skills/paper-review-loop) | 論文 PDF を査読し、指摘に沿った改訂 → 再査読を制限時間内で繰り返す | [zip](dist/paper-review-loop.zip) |

## インストール
- **claude.ai**: zip をダウンロードし、「設定 → 機能 → スキル」からアップロード
- **Claude Code**: `skills/<スキル名>` フォルダを `~/.claude/skills/` にコピー

## 構成

```
├── skills/            # スキル本体（1フォルダ = 1スキル）
│   └── _template/     # ひな形（_ 始まりはパッケージ対象外）
│       ├── SKILL.md   # 必須: frontmatter の name / description
│       ├── scripts/   # 任意
│       ├── references/# 任意
│       └── assets/    # 任意
├── dist/              # 配布用 zip
└── package.ps1        # skills/ → dist/*.zip
```

## スキルの追加
1. `skills/_template` をコピーして `skills/<スキル名>` にリネーム（小文字・ハイフン区切り）
2. `SKILL.md` の `name` をフォルダ名と同じにし、`description` と本文を書く
3. パッケージ化（引数なしで全スキル）
   ```
   powershell -ExecutionPolicy Bypass -File .\package.ps1 <スキル名>
   ```

## ライセンス
[MIT](LICENSE)
