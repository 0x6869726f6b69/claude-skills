# PDF から編集可能な LaTeX ソースを再構成する

LaTeX ソースが無く PDF しか無いときに使う。目標は、元の PDF と**内容が同じ**（本文、数式、表、図、参考文献）で、コンパイルできる LaTeX ソースを作ること。見た目を完全に一致させる必要はないが、構成と内容は忠実にする。以後のラウンドの査読者はこの版を読むので、再構成の誤りはそのまま「論文の誤り」として指摘されてしまう。

以下、`T = python <skill_dir>/scripts/pdf_tools.py`。

## 手順

1. **全体の把握**
   ```bash
   T info  <ws>/original/<name>.pdf
   T text  <ws>/original/<name>.pdf -o <ws>/work/original.txt
   T render <ws>/original/<name>.pdf -o <ws>/work/pages --dpi 110
   ```
   1ページ目の画像で、1段組か2段組か、どの投稿先のスタイルかを見る。

2. **テンプレート**：投稿先の公式スタイルファイル（例：`neurips_2025.sty`）がユーザーから渡されているか、ローカルにあればそれを使う。無ければ `article` + `geometry`（2段組なら `twocolumn`）で近づける。スタイルファイルを出所の分からないサイトからダウンロードしない。日本語の論文なら `ltjsarticle`（LuaLaTeX）や `jlreq` を使う（`build_pdf.py` がエンジンを自動で選ぶ）。

3. **図**：図は描き直さず、元の PDF から切り出す。
   ```bash
   T figures <ws>/original/<name>.pdf -o <ws>/src/figures
   ```
   `fig_<n>.pdf`（ベクター）と確認用の `fig_<n>.png` ができる。**PNG をすべて目で確認する**。凡例が切れている、隣の本文が入っている、などがあれば、座標入りのページ画像を作って切り出し直す。
   ```bash
   T render <ws>/original/<name>.pdf -o <ws>/work/grid --dpi 110 --pages 4 --grid
   T crop   <ws>/original/<name>.pdf --page 4 --bbox 70,90,300,260 -o <ws>/src/figures/fig_3.pdf
   ```
   グリッドの数値は PDF ポイント（左上原点）で、`--bbox` と同じ単位。本文では `\includegraphics{figures/fig_3.pdf}` で読み込む。

4. **本文**：抽出テキストを節ごとに写し、ハイフネーション、合字、改行の崩れを直す。段落の切れ目と節の構成は元のとおりにする。

5. **数式**：テキスト抽出では数式が壊れるので、ページ画像を見て LaTeX で書き起こす。書いた式は1つずつ画像と照合する（添字、上付き、ノルムや期待値の記号、和の範囲）。番号付きの式は番号を元と合わせ、`\label` をつける。

6. **表**：ページ画像から `booktabs` で組み直す。**数値はセルごとに2回照合する**。太字や下線などの強調も元のとおりにする。

7. **アルゴリズム**：`algorithm` + `algpseudocode` で書き起こす。

8. **参考文献**：元の文献リストを `thebibliography` の `\bibitem` として写す。本文の引用はその key に対応させる。推測で文献を足したり、書誌情報を「修正」したりしない。

9. **相互参照**：節・式・図・表・定理に `\label` をつけ、本文の参照を `\ref` にする。改訂で参照しやすくするため。

10. **付録**：付録も再構成する。付録が長く予算が足りないときは、本文を先に完成させ、付録は元の PDF のページをそのまま差し込んでよい。
    ```latex
    \usepackage{pdfpages}
    ...
    \appendix
    \includepdf[pages=12-20]{../original/<name>.pdf}
    ```
    この場合、付録への修正はできないので、RECONSTRUCTION_NOTES.md にその旨を書く。

11. **ビルドと照合**
    ```bash
    python <skill_dir>/scripts/build_pdf.py <ws>/src/main.tex --out <ws>/rounds/r01/reconstructed.pdf
    ```
    元の PDF と並べて、節・式・図・表・定理の数が一致するか、表の数値がすべて一致するかを確認する。

12. **記録**：`<ws>/src/RECONSTRUCTION_NOTES.md` に、近似した部分（レイアウト、フォント、読み取れなかった箇所、元のまま差し込んだページ）を書く。

## 時間の目安

10ページ程度の本文で20〜40分。数式と表が多いとさらにかかる。予算が短い場合でも、本文の内容を落としてはいけない。削るなら付録の再構成を `\includepdf` で代える。
