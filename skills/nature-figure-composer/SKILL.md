---
name: nature-figure-composer
description: 分析結果（グラフ画像・CSV/NPZ等のデータ・解析スクリプト・ノートブック）を、Nature系ジャーナルに採択されるレベルの多パネルFigure・Table・Captionにまとめるスキル。起動後に「どの結果を1枚のFigureにまとめるか」をユーザーに確認し、指示がなければ科学的ストーリー（What→How→Why→Performance→Impact）に沿って結果の取捨選択・パネル配置・配色まで自分で設計し、Arial 5–7 pt・89/183 mm幅・統一配色のベクターPDF/SVGを作ってQAまで行う。「結果を図にまとめて」「論文用のFigureを作って」「複数のグラフを1枚に」「Figure 1の概要図」「図を綺麗に/投稿用に整えて」「配色やフォントを統一」「Figure captionを書いて」「結果の表を作って」など、研究・分析結果を論文・投稿・発表用の図表に仕上げる依頼では、Natureと明示されていなくても必ずこのスキルを使うこと。Also use for any request in English for publication-quality, multi-panel or journal-ready figures from analysis results.
---

# Nature-grade Figure Composer

Figureは「結果の表示」ではなく **「科学的主張を視覚的に論証する手段」** として設計する。
このスキルは、散らばった分析結果を「1 Figure = 1つの主張」のストーリーに組み直し、
Nature系の技術仕様を満たすファイルに仕上げるまでを行う。

`<SKILL_DIR>` はこの SKILL.md があるディレクトリ。必要なもの: Python 3.9+, matplotlib, numpy,
pandas, Pillow, PyMuPDF（`pip install pymupdf`）, scipy（95% CIを使う場合）。

## 同梱リソース

| パス | 内容 | 読むタイミング |
|---|---|---|
| `references/guidelines.md` | ユーザー指定の作図指針（7原則）、Nature技術仕様、最終チェックリスト | 計画前に一読、QAで再読 |
| `references/storyboard.md` | 結果→Figureへのまとめ方、Figure 1の型、レイアウト型、**おまかせ時の設計手順** | Step 3 |
| `references/charts.md` | 主張の型→グラフ形式、不確実性・軸、場（マップ）の描き方、nfigのコード例 | Step 3（形式選び）, 5 |
| `references/captions-tables.md` | Caption・Table・Supplementaryの書き方と例 | Step 7 |
| `scripts/inventory.py` | 結果ファイルの棚卸し＋番号付きコンタクトシート | Step 1 |
| `scripts/nfig.py` | スタイル・意味固定の配色・パネルラベル・作図ヘルパー・自動QA | Step 4–6 |
| `scripts/assemble.py` | 既存PDF/SVG/PNGをベクターのまま多パネルに合成 | 再描画できないパネルがあるとき |
| `scripts/check_figure.py` | 完成ファイルの仕様チェック＋色覚シミュレーション画像 | Step 6 |
| `scripts/make_table.py` | CSV → booktabs LaTeX / Markdown 表 | Step 7 |
| `assets/figure_plan_template.md` | Figure計画書のひな形 | Step 3 |
| `assets/style_template.py` | 表示名・色範囲・軸ラベルなど全Figure共通の約束のひな形 | Step 4 |
| `assets/layout_example.json` | assemble.py のレイアウト例 | assemble 使用時 |

## Workflow

### Step 1 — 結果の棚卸し（質問の前に手早く）

```bash
python <SKILL_DIR>/scripts/inventory.py <project_root> --sheet paper_figures/_inventory --out paper_figures/_inventory/inventory.md
```

- `paper_figures/_inventory/contact_sheet_*.png` を Read で見て、各結果が何を示すかを把握する。
  レポートの「made by / read by」列で、図→生成スクリプト→元データを辿れる（再描画に必要）。
- 原稿・README・メモがあれば読み、研究の問い・提案手法・主張を掴む。
- 各結果に1文の所見を付ける（例: `#6 benchmark.csv → 提案手法が3データセットすべてで最高精度、+6 pt`）。
  これが Step 2 の選択肢と Step 3 の計画の材料になる。
- 結果が見つからなければ、その場所を Step 2 で一緒に尋ねる。

### Step 2 — ヒアリング（スキル起動後に必ず行う）

まとめ方の決定権はユーザーにあるので、作図の前に確認する。ただし起動メッセージで既に
答えが分かっている項目は聞き直さない。AskUserQuestion があればそれを使い、なければ
番号付きの質問をテキストで出して回答を待つ。選択肢は Step 1 の棚卸しから **具体的に**
（ファイル番号・所見入りで）作る。

1. **対象**（必須）「どの結果を1枚のFigureにまとめますか？」
   - おまかせ：全結果から論文全体のFigure構成（Fig. 1〜N＋SI）を設計（Recommended）
   - 棚卸しから作った候補グループ1–2個（例:「性能比較: #1 accuracy_bar, #6 benchmark.csv」）
   - 自由記述（Other）で「#1, #4, #6 を1枚に」のように指定可能
2. **主張**「そのFigureで一番伝えたいことは？」— 推定した主張1–2個＋おまかせ
3. **掲載サイズ** — 2カラム 183 mm（Recommended）／1カラム 89 mm／1.5カラム 120–136 mm／おまかせ
4. **出力物**（複数選択）— Figure（PDF+SVG+PNG）／Caption（英語）／Table／SI候補リスト

回答の扱い:
- 起動メッセージで対象（Q1）が指定済みなら、Q2–Q4 は既定値（主張は推定、183 mm、Figure＋Caption）で
  進めてよく、判断が分かれるときだけ聞く。
- 「おまかせ」または指示のない項目は、どの結果を採用し、どう配置し、どうまとめるかまで
  Claude が決める。`references/storyboard.md` の「おまかせ時の設計手順」に従う。
- 「質問せずに進めて」と言われたら全項目おまかせとして扱う。
- 図中の文字と Caption は英語が既定（投稿先が英語のため）。会話はユーザーの言語で行う。

### Step 3 — Figure計画（ストーリーボード）

コードを書く前に `references/storyboard.md` を読み、`assets/figure_plan_template.md` の形式で
`paper_figures/figure_plan.md` を書く。含めるもの:

- 論文全体の流れ（What → How → Why → Performance → Impact）と各Figureの役割
- 各Figure: **主張1文**（そのまま Caption のタイトル文になる）、パネル表（ラベル／内容／
  グラフ形式（`references/charts.md` §1 で選ぶ）／データ源／hero か support か）、mosaic と寸法、色の役割
- 本文から外す結果（SI行き）とその理由。限界・失敗例は隠さず、本文の限界パネルかSIに置く
- 不足情報（n、誤差棒の定義、検定、単位）を `[AUTHOR TODO]` として列挙

チャットには計画を短い表で示す。おまかせの場合や、ユーザーの指定どおりに組めた場合は
確認を待たずに作図へ進み、「計画は後から変更できます」と添える。指定された結果では主張を
支えられない・指定同士が矛盾する、といった場合だけ止めて相談する。

### Step 4 — 共通スタイルを固定する

- `nfig.py` を `paper_figures/src/` にコピーする（図スクリプトがスキルなしでも再実行できるように）。
- 論文全体で1つの `paper_figures/figure_style.json` に、手法・条件 → 色・マーカー・線種を固定する。
  色の意味が図ごとに変わると読者が毎回凡例を読み直すことになるため、全Figureでこれを使う。

```python
import style                      # paper_figures/src/style.py（パスは実行場所に依存しない）
pal = nfig.Palette.load_or_build(style.PALETTE,
        proposed=["Ours"], highlight=["SOTA-X"],
        baselines=["Base A", "Base B"], references=["Oracle"])
```

- proposed＝アクセント色（彩度を抑えた朱）、highlight＝最強の比較手法1つだけ青、その他の比較手法＝
  灰色の濃淡＋マーカー/線種、reference（理論値・上限・チャンスレベル）＝黒の破線。
- 既存の割当ては変わらず、新しい名前は追記される。手法以外のカテゴリ（データセット等）には
  同じ色を流用せず、位置・パネル分割・マーカーで区別する。
- 全Figureで共有する「表示の約束」は `paper_figures/src/style.py`（`assets/style_template.py` をコピー）に
  1か所にまとめ、各図スクリプトから import する: データ上の名前→表示名（`"PISurr (ours)"` → `"PISurr"`）、同じ量のマップの色範囲
  （例: `TEMP_LIM = (300, 345)`, `ERR_LIM = (0, 6)`）、単位付きの軸ラベル。図ごとに書くとずれるため。

### Step 5 — 作図

原則として **元データから nfig で再描画** する。既存PNGの貼り合わせではフォント・線幅・色が
揃わず、縮小で文字が5 pt未満になりやすいため。グラフ形式は `references/charts.md` で選ぶ。

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))   # どこから実行しても動く
import nfig
nfig.use_style()                                          # Arial 7/6 pt, 0.5 pt 軸, TrueType 42
fig, axd = nfig.figure("double", 120, mosaic="aab;cde")  # 最終掲載サイズで描く
# ... 各パネル（charts.md のレシピ） ...
nfig.shared_legend(fig, pal.handles(["Ours", "SOTA-X", "Base A"]))  # 凡例は図全体で1つ
nfig.label_panels(fig, axd)          # 最後に呼ぶ: a, b, c… 8 pt 太字、行・列で整列
nfig.save(fig, "paper_figures/fig2")       # .pdf/.svg/.png ＋ 自動QAの報告
```

`label_panels` はレイアウトを確定（固定）するので、凡例・注釈・カラーバーはすべてその前に追加する。

- 1 Figure = 1スクリプト（`paper_figures/src/fig2.py`）。データ読み込み〜保存まで再現できるようにする。
- 最終サイズで描き、後から縮小しない。`bbox_inches="tight"` は幅が変わるので使わない。
- hero パネルを最大にして左上か最上段へ。同種のグラフはサイズ・軸範囲・目盛りを揃える。
- 行ごとにパネルの種類が違う図（模式図の帯／画像・マップの列／グラフ）は1つの mosaic にせず
  `nfig.figure("double", 120, rows=[("a", 0.8), ("bcdef", 1), ("g", 1)])` で行ごとに組む。
  1つのグリッドだと、ある列の目盛りラベルの余白が同じ列の他の行にも適用され、画像やマップが潰れる。
  同種の行だけなら1つの mosaic のままにする（列の端が揃う）。
- 温度場・誤差マップなどの場は `nfig.field`（色範囲は style.py の共通値）＋ `nfig.colorbar` で、
  同じ量には1本のカラーバー。写真・顕微鏡像は `nfig.image_panel`。
- 再描画できないパネル（外部ツールの概要図、顕微鏡像、データが残っていない図）:
  - 少数なら `nfig.image_panel(ax, path)` で埋め込む（ラスタになる）。
  - ベクターのまま組むなら、nfig で描いたパネルPDFと外部PDFを `scripts/assemble.py` で合成する
    （`assets/layout_example.json`、パスは JSON からの相対）。nfig 側のパネルは合成後のセルと同じ
    寸法（mm）で描いて縮小率を ≈1 にする。報告の「text below 5 pt」「below 300 dpi」
    「cell mostly empty」が消えるまでセル比率と高さを調整する。
  - 再描画できなかった理由と、元データがあれば揃えられることをユーザーに伝える。
- データの誠実さ: 値を変えない、都合のよい部分だけを選ばない、棒は0から、差を誇張する軸の
  切り詰めをしない。画像は全体に一様な調整とトリミングのみ（部分加工・合成・生成AI編集は不可）。

### Step 6 — QAと修正ループ（最低2周）

1. 自動チェック: `nfig.save` の報告に加えて
   `python <SKILL_DIR>/scripts/check_figure.py paper_figures/fig2.pdf` を実行する。
   ERROR は必ず解消し、WARN は意図がある場合だけ残してその理由を記録する。
2. 目視: `paper_figures/qa/fig2_preview.png`（最終サイズ相当）と `fig2_access.png`（2型・1型色覚、
   グレースケール）を Read で見て、`references/guidelines.md` の最終チェックリストを確認する。
   特に: 3秒で主張が伝わるか／hero が一番目立つか／左上→右下に読めるか／文字・線の重なりや
   はみ出し・整列のずれ／意味のない余白や詰まりすぎ／色覚・グレースケールでも区別できるか。
3. 直して再生成し、もう一度確認する。最後に査読者の立場で「この図と Caption だけで主張に
   納得できるか」を自問する。

### Step 7 — Caption・Table・納品

- Caption は `references/captions-tables.md` の形式で `paper_figures/captions.md` に書く
  （太字のタイトル文＝主張 → 各パネルを順に → 記号・色・略語の定義 → n・誤差棒・検定）。
- 正確な数値比較は Table に: `scripts/make_table.py`（booktabs、縦罫線なし、最良値のみ太字）。
  1行1シードの長い形式のデータは `--groupby` と `--stat` でそのまま mean ± s.d. と n に集計できる。
- ユーザーへの報告: 作成ファイル一覧、各Figureの主張とパネル構成、SIに回した結果と理由、
  `[AUTHOR TODO]`（未確認の統計情報など）、残した WARN とその理由。

## 出力の配置（既定）

ユーザーの既存ファイル（`figures/` など）と混ざらず上書きもしないよう、出力は `paper_figures/` にまとめる。
ユーザーが別の場所を指定したらそれに従う。

```
paper_figures/
├── figure_plan.md  figure_style.json  captions.md
├── src/            nfig.py, fig1.py, fig2.py, ...
├── fig1.pdf .svg .png, fig2.*, ...
├── tables/         table1.tex, table1.md
├── qa/             *_preview.png, *_access.png
└── _inventory/     inventory.md, contact_sheet_*.png
```

## 判断に迷ったとき

- 何を見せるかは「その主張の証拠になるか」で決める。証拠にならない結果は、どれほど手間が
  かかったものでもSIへ回す。
- 数値の改善には、それが実際に何を意味するかを示す具体例を必ず組み合わせる。
- 最良の結果だけでなく、適用条件・限界・失敗例も示すと主張の信頼性が上がる。
- 迷ったら簡潔な方を選ぶ: 色を減らす、文字を減らす（説明は Caption へ）、凡例を共有する。
