# PDF から編集可能な LaTeX ソースを再構成する（loop モード）

LaTeX ソースが無く PDF しか無いときに使う。目標は、元の PDF と**本文の文字列が同じ**で、コンパイルできる LaTeX ソースを作ること。見た目（フォント・行送り・改ページ）を完全に一致させる必要はないが、本文・見出し・キャプション・表・数式・参考文献の内容と構成は忠実にする。

**英文は一字一句そのまま写す。誤りも直さない。** ラウンド1の校正は元の PDF に対して行われ、その指摘（`corrections.json`）を改訂担当が記録付きで反映する。再構成の段階で黙って直すと、その修正は変更履歴にも残らず、次の校正者の確認からも漏れる。また `original` がソースに見つからなくなり、指摘を反映できなくなる。

以下、`T = python <skill_dir>/scripts/pdf_tools.py`、`AWL = python <skill_dir>/scripts/awl.py`。

## 手順

1. **全体の把握**
   ```bash
   T info   <ws>/original/<name>.pdf
   T render <ws>/original/<name>.pdf -o <ws>/work/pages --dpi 110
   ```
   本文のテキストは `<ws>/rounds/r01/paper.txt`（段落ごと・行番号付き）を使う。1ページ目の画像で、1段組か2段組か、どの投稿先のスタイルかを見る。

2. **テンプレート**：投稿先の公式スタイルファイルがユーザーから渡されているか、ローカルにあればそれを使う。無ければ `article` ＋ `geometry`（2段組なら `twocolumn`）で近づける。出所の分からないサイトからスタイルファイルをダウンロードしない。

3. **図**：描き直さず、元の PDF から切り出す。
   ```bash
   T figures <ws>/original/<name>.pdf -o <ws>/src/figures
   ```
   `fig_<n>.pdf`（ベクター）と確認用の `fig_<n>.png` ができる。**PNG をすべて目で確認する**。凡例が切れている、隣の本文が入っている、などがあれば座標入りのページ画像で切り出し直す。
   ```bash
   T render <ws>/original/<name>.pdf -o <ws>/work/grid --dpi 110 --pages 4 --grid
   T crop   <ws>/original/<name>.pdf --page 4 --bbox 70,90,300,260 -o <ws>/src/figures/fig_3.pdf
   ```
   図の中の語（軸ラベルなど）は画像なので、この方法では直せない。図の中の語への指摘は、改訂担当が `skipped`（理由：図は画像のため著者が元データから修正）とし、`author_queries.md` に回す。

4. **本文**：`paper.txt` を節ごとに写す。行末の自動ハイフネーションをつなぎ、合字を戻し、段落の切れ目と節の構成は元のとおりにする。**語・綴り・句読点・大文字化は変えない**（上の注意）。特殊文字はエスケープする（`%` `&` `_` `#` `$`）。引用符は元の見た目に合わせて ``` ``…'' ``` か `"`（元が直線の引用符なら直線のまま）。

5. **数式**：テキスト抽出では数式が壊れるので、ページ画像を見て LaTeX で書き起こし、1つずつ画像と照合する。番号付きの式は番号を元と合わせる。

6. **表**：ページ画像から `booktabs` などで組み直す。**数値はセルごとに2回照合する**。表の中の語も元のまま。

7. **参考文献**：元の文献リストを `thebibliography` の `\bibitem` として、書式も含めてそのまま写す（書式の不統一も校正の対象なので、整えない）。本文の引用番号・著者名は元の表記どおり（`\cite` を使うなら出力が元と同じになるようにする）。

8. **相互参照**：節・式・図・表に `\label` を付け、本文の参照を `\ref` にしてよい（出力される文字列が元と同じ限り）。

9. **付録**：付録も再構成する。量が多く時間がかかるなら、本文を先に完成させ、付録は元の PDF のページを差し込んでよい（`\usepackage{pdfpages}`、`\includepdf[pages=12-20]{../original/<name>.pdf}`）。その場合、付録の英文は改訂できないので、付録への指摘は `author_queries.md` に回し、`RECONSTRUCTION_NOTES.md` にその旨を書く。

10. **ビルドと照合**
    ```bash
    python <skill_dir>/scripts/build_pdf.py <ws>/src/main.tex --out <ws>/work/reconstructed.pdf
    AWL extract <ws>/work/reconstructed.pdf -o <ws>/work/reconstructed.txt
    AWL compare <ws>/rounds/r01/paper.txt <ws>/work/reconstructed.txt
    ```
    `compare` は2つのテキストを語単位で比べる。類似度は 0.98 以上を目安にし、差分の一覧をすべて見る。抽出の副作用（数式、ヘッダー・ページ番号、表の並び）以外の差（語の脱落・追加・綴りの違い）は、ソースを直して一致させる。

11. **記録**：`<ws>/src/RECONSTRUCTION_NOTES.md` に、近似した部分（レイアウト、フォント、読み取れなかった箇所、差し込んだページ、図の中の語は直せないこと）を書く。

## 時間の目安

10ページ程度の本文で20〜40分。数式と表が多いとさらにかかる。ラウンド1の校正（元の PDF が対象）と並行して進められる。
