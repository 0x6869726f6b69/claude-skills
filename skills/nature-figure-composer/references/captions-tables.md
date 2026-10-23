# Caption・Table・Supplementary

目次: 1. Caption の構成 / 2. Caption の例 / 3. Table / 4. Supplementary・Extended Data /
5. 本文での Figure の参照

---

## 1. Caption（Figure legend）の構成

Figure と Caption だけで主要な内容が理解できることが目標。英語で、次の順に書く。

1. **タイトル文（太字）** — その Figure の科学的主張を1文で。計画書の「主張1文」をそのまま使う。
   トピック名（"Benchmark results."）ではなく結果を述べる。
2. **各パネルを順に** — `**a**, ...` の形式で、何を示し、何が読み取れるかを短く。
   同じ説明が続くパネルはまとめる（`**b**,**c**, ...`）。
3. **記号・色・略語の定義** — 破線、星印、色の役割（凡例が図中にあっても略語は定義する）。
4. **統計情報** — 誤差棒・帯の定義、n とその単位（独立な試料・シード・被験者）、検定名、
   両側/片側、多重比較補正、P 値の示し方。代表例を選んだ基準。
5. スケールバーの長さ（図中に数値がない場合）。

書き方:
- 本文の繰り返しや方法の詳細は書かない（Methods へ）。投稿先の語数上限を確認する。
- 色の名前だけで説明しない（色覚多様性）。"Ours (vermillion circles)" のように形も添えるか、図中の凡例を参照させる。
- 数値は図と一致させる。わからない統計情報は捏造せず `[AUTHOR TODO: ...]` と書いてユーザーに伝える。
- Nature の表記: "Fig. 1 |"、P は斜体、"mean ± s.d."、"n = 5"、"a.u."、単位の前にスペース。

## 2. Caption の例

```markdown
**Fig. 2 | Self-supervised pretraining makes the decoder robust to distribution shift.**
**a**, Validation accuracy during training; lines show the mean and shaded bands the s.d. over
n = 5 random seeds. The dashed line marks the oracle trained on target-domain labels.
**b**, Final accuracy for each method; dots are individual seeds, horizontal lines and error bars
show mean ± s.d. P value from a two-sided Welch's t-test. **c**, Change in accuracy relative to
SOTA-X for five source domains (S1–S5) and eight target domains (D1–D8); red indicates an
improvement. **d**, Predicted versus measured temperature on the held-out set (n = 300 samples);
dashed line, y = x. MAE, mean absolute error. Colours and markers denote the same methods in all
figures (key at top).
```

チェック: タイトル文が主張か／全パネルに言及したか／n・誤差棒・検定があるか／略語を定義したか。

## 3. Table

Table は正確な数値の比較のため、Figure は傾向・構造の理解のため、と役割を分ける。
同じ数値を Figure と Table の両方に載せるなら、本文はどちらか一方にし、もう一方は SI に。

ルール:
- 列・行は必要最小限。主要な指標を左に、付随情報（時間・パラメータ数）を右に。
- 単位はヘッダーに: `Accuracy (%)`, `Time (s)`。同じ列の小数点以下の桁数を揃える。
- 罫線は上・見出し下・下の3本（booktabs）。縦罫線、セルの塗り、過度な太字は使わない。
- 最良値だけ太字（同値はすべて）。提案手法の行を強調したい場合も太字は最良値に限り、
  行の順序（最下段に提案手法）で示す。
- ばらつきは `mean ± s.d.` の形で、定義と n を脚注に。
- 表は画像にしない（Nature は編集可能なテキストを要求）。タイトルは表の上、脚注は下。

```bash
python <SKILL_DIR>/scripts/make_table.py results/benchmark.csv --out paper_figures/tables/table1 \
  --pm "Accuracy (%)=acc_mean,acc_std" --rename "time_s=Time (s)" \
  --cols "Dataset,Method,Accuracy (%),Time (s)" \
  --best "Accuracy (%):max" --best "Time (s):min" --decimals "Accuracy (%)=1" \
  --group Dataset --caption "Accuracy and inference time on three benchmarks." \
  --note "Values are mean ± s.d. over n = 5 random seeds; best value per dataset in bold."
```
1行1シード（1サンプル）の長い形式なら集計前のデータをそのまま渡せる（`--rename` 後の列名で指定）:
```bash
python <SKILL_DIR>/scripts/make_table.py results/benchmark_raw.csv --out paper_figures/tables/table_s1 \
  --rename "dataset=Geometry" --rename "method=Method" \
  --groupby "Geometry,Method" --stat "RMSE (K)=rmse_K" --stat "Training time (h)=train_time_h" \
  --cols "Geometry,Method,RMSE (K),Training time (h),n" --best "RMSE (K):min" \
  --decimals "RMSE (K)=2" --group Geometry --note "Mean ± s.d. over n random seeds."
```
s.d. が丸めで 0 になる列は警告が出るので、桁数か単位を変える。

出力: `table1.tex`（booktabs、`\usepackage{booktabs}` が必要）と `table1.md`。Word 用が必要なら
md を貼り付けるか pandoc で変換する。

## 4. Supplementary Information・Extended Data

- 本文から外した結果は「なぜ外したか」が分かるように整理し、本文から参照する
  （例: "per-dataset learning curves are shown in Supplementary Fig. 3"）。
- SI の Figure も同じスタイル・同じ配色（figure_style.json）で作る。一貫性は SI でも評価される。
- Nature の Extended Data: RGB、最大 300 dpi、10 MB 以下、.jpeg（推奨）/.tiff/.eps、Legend 込みで
  1ページに収める。PDF から作る場合は 300 dpi で JPEG に書き出す。
- 失敗例・適用限界は SI に回してもよいが、本文で必ず言及する。

## 5. 本文での Figure の参照

単に "(Fig. 2)" と置くのではなく、各パネルが何を裏付けるかを書く。
- 良い例: "Accuracy improved on all eight target domains (Fig. 2c), and the gain persisted
  throughout training rather than appearing only at convergence (Fig. 2a)."
- 悪い例: "Results are shown in Fig. 2."

Caption と同時に、本文用の説明文（1パネル1文程度）を `paper_figures/captions.md` の各 Figure の下に
「Text references」として添えると、ユーザーが原稿に組み込みやすい。
