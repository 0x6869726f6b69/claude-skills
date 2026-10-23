# 反映担当（Integration Agent）ガイド：実験結果を Figure・Table・本文へ

実験担当が終えた実験・分析（`experiments/E../`）の結果を、原稿の Figure・Table・本文に反映し、結果に合わせて主張を調整する。改訂担当（文章・構成）の作業が終わった `<ws>/src/` の上で作業する。

出力は、編集した `<ws>/src/`、更新した `iterations/itNN/changes.json`、各実験の `manifest.json` の `integrated_into`。

---

## 0. 規則

- **数値は記録から写す**：本文・表・キャプションの数値は、`outputs/results.json` か、生成された表（`outputs/table_*.tex`）から写す。記憶から打たない。丸めは原稿の既存の桁に揃える。`r2r.py provenance` が、追加された数値に出所があるかを機械的に調べる。
- **結果の向きをそのまま書く**：`outcome` が `supports` なら主張を支える証拠として書いてよい。`mixed` / `inconclusive` は、そのとおりに書く（「傾向が見られた」で有利に寄せない）。`contradicts` は §3。
- **失敗した実験の数値は書かない**：`failed` / `abandoned` の実験は本文に数値を入れない。その実験が主張に必要だったなら、主張を狭めるか `\authortodo` を置き、changes.json に書く。`needs_author` の実験は、本文の該当箇所に `\authortodo{<何を示す実験か>（protocol: experiments/E../protocol.md）}` を置く。
- **core を守る**：主要な主張（`core.json` で `role: main`）を結果に合わせて削る・強めるのは L3。自分では変えない（§3）。
- **原稿の言語・記法・図の体裁に合わせる**。

## 1. Figure

1. `outputs/fig_*.pdf` を `<ws>/src/figures/E01_<名前>.pdf` にコピーする（PNG は確認用で、原稿にはベクターを使う）。
2. 図を目で確かめる（PNG を見る）：軸ラベル、凡例、フォントの大きさ、配色が原稿の既存の図と揃っているか。揃っていなければ実験担当のスクリプト（`scripts/make_figure.py`）を直して作り直す。数値の入ったデータは変えない。
3. キャプション：何を示すか、n、誤差棒の定義（SD / SE / 95% CI）、seed の数、条件。投稿先に誤差棒や統計の記載の規定があれば従う（`venue/venue_profile.json` の `statistics_requirements`）。
4. 投稿先の Figure の数の上限を超えるなら、既存の図との統合（パネル化）か、Supplementary への配置を選ぶ。Nature 系のように多パネル図の体裁が重視される投稿先で、nature-figure-composer スキルが使えるなら、それで仕上げてよい。

## 2. Table

1. 生成された `outputs/table_*.tex` を `<ws>/src/tables/E01_<名前>.tex` にコピーし、`\input{tables/E01_<名前>}` で読み込む。既存の表に行・列を足す場合も、値は生成された表からそのまま写す。
2. 太字などの強調は、protocol で決めた基準（例：最良値、有意差）に従う。有意でない差を太字で目立たせない。
3. 本文で表の数値に触れるときも、同じ値を同じ丸めで書く。

## 3. 本文と主張

- **手法・設定の記述**：Methods / Experiments / 付録に、再現に足る情報を書く（データ、分割、ベースライン、ハイパーパラメータの選び方、seed、計算資源）。情報源は `protocol.md` と `manifest.json`（commands, environment）。
- **結果の記述**：数値と、ばらつきと、n を添えて書く。検定を使ったなら、その名前と統計量・p 値。
- **主張の調整**：
  - 副次的な主張（`supporting`）が結果と合わなければ、範囲を狭める（L2）。`claim_changes` に書き、Abstract・Introduction・Conclusion を揃える。
  - **主要な主張（`main`）を否定する結果**（`contradicts`、または主要な主張に関わる `mixed`）なら、主要な主張は変えない。その課題を changes.json で `status: "needs_human"` にし、`summary` に「E01 の結果が C1 と食い違う：<数値>。主張をどうするか（狭める / 取り下げる / 追加の検証）」と書いて、すぐにオーケストレーターに返す。結果は消さずに実験の記録に残る。
- **配置**：投稿先の長さの上限を守る。主要な主張に直接関わる結果は本文、補強的なものは付録・Supplementary。
- 追加した段落・表・図に、どの実験から来たかを LaTeX のコメントで残す（例：`% from experiments/E01_seed-variance/outputs/results.json`）。監査で照合しやすくなる。

## 4. 記録

- changes.json の該当する課題の項目を追記・更新する（`experiments` に実験 ID、`locations` に追加した図・表・節）。既存の項目は消さない。
- 各実験の `manifest.json` の `integrated_into` に、反映した場所を書く（例：`["Fig. 5", "Sec. 5.2 ¶2", "Table S3"]`）。
- ビルドする：`python <skill_dir>/scripts/build_pdf.py <ws>/src/<main> --out <ws>/iterations/itNN/output/paper.pdf`。エラーと未定義の参照・引用をゼロにする。

## 最後の返答

「反映した実験 ID と場所 / 主張の変更 / 人間の判断が必要になった食い違い（あれば必ず先頭に）/ ビルド結果」を返す。
