# claude-skills

研究・論文執筆向けの Claude スキル集です。

## 収録スキル

| スキル | 内容 | ダウンロード |
| --- | --- | --- |
| [paper-review-loop](skills/paper-review-loop) | 論文 PDF を査読し、指摘に沿った改訂 → 再査読を制限時間内で繰り返す | [zip](dist/paper-review-loop.zip) |
| [deep-review-modoki](skills/deep-review-modoki) | Google の Deep Review（旧 Paper Assistant Tool）を模した深い検証レビュー。セグメント分割 → 並列検証 → 反証検証 → 統合で、誤りを Major / Minor / Suggestions にまとめる（スコアなし） | [zip](dist/deep-review-modoki.zip) |
| [review2revise-loop](skills/review2revise-loop) | Review2Revise-loop。`/review2revise-loop <投稿先>` で、投稿先の aims & scope を調べ、deep-review-modoki の査読 → 自動改訂 → 追加実験（事前登録）と Figure/Table/本文への反映 → 再査読を、Major がなくなるか収束するまで反復する。scientific core（研究課題・中心アイデア・主要手法）の変更は人間に確認する。**deep-review-modoki が必要** | [zip](dist/review2revise-loop.zip) |
| [nature-figure-composer](skills/nature-figure-composer) | 分析結果（グラフ画像・CSV/NPZ・解析スクリプト）を Nature 系ジャーナル水準の多パネル Figure / Table / Caption にまとめる。起動後に「どの結果を1枚にまとめるか」を確認し、おまかせなら What → How → Why → Performance → Impact のストーリーで結果の取捨選択・配置・配色まで設計する。89/183 mm 幅・Arial 5–7 pt・意味を固定した配色のベクター PDF/SVG を作り、自動 QA（文字サイズ・重なり・余白・色覚シミュレーション）まで行う。**Python（matplotlib, PyMuPDF）が必要** | [zip](dist/nature-figure-composer.zip) |

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
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\package.ps1 <スキル名>
   ```

## ライセンス

[MIT](LICENSE)
