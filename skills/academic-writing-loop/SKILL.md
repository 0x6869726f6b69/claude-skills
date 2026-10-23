---
name: academic-writing-loop
description: 英語で書かれた学術論文・原稿のPDFを、プロの英文校正者として校正するスキル。学術出版ガイド（Olson, Guide to Academic and Scientific Publication）に基づくチェックリストで、英文法・語法、US/UK綴り、略語、句読点、時制、代名詞、用語の一貫性、図表、引用と文献リスト、タイトル・要旨・キーワード、投稿規定への適合を確認し、修正案つきのレポートと赤入れ（注釈付き）PDFを作る。モードは2つ：「1回校正」（指定したPDFを1回校正）と「loop」（校正→原稿に反映してPDFを再生成→再校正を、指摘が無くなるまで繰り返す）。使い方は `/academic-writing-loop 1回校正 paper.pdf` または `/academic-writing-loop loop paper.pdf`。英語論文のPDFについて「英文校正して」「英語をチェック／添削して」「ネイティブチェック」「文法を直して」「proofreadして」「投稿前に英語を磨きたい」などと頼まれたら、スキル名が出ていなくても使うこと（内容の査読は paper-review-loop、技術的な誤りの検証は deep-review-modoki の担当）。Use for English proofreading/copyediting of academic paper PDFs, single pass or iterative proofread→revise→re-proofread loops.
---

# Academic Writing Loop：学術英語の校正（1回 / ループ）

英語の論文 PDF を、学術論文に慣れた英文校正者として校正する。基準は Linda Olson の *Guide to Academic and Scientific Publication*（Proof-Reading-Service.com, 2014）を校正項目に整理した `references/proofreading_checklist.md`。ガイドの中心にある考え方は「投稿規定に従い、正確に、一貫させる」こと。多くの表記はどちらでも正しいが、一つの論文の中で揺れれば誤りになる。そこで、表記の決定を `style_sheet.md` に記録し、全ラウンドでそれに従う。

| モード | すること | ユーザーに渡すもの |
|---|---|---|
| **1回校正** | 指定した PDF を1回校正する | 赤入れ PDF（該当箇所のハイライトと修正案のコメント）、校正レポート、style sheet |
| **loop** | 校正 → 原稿（LaTeX）に反映して PDF を作り直す → 新しい PDF を別の校正者が再校正、を指摘が無くなるか上限ラウンドまで繰り返す | 修正済み PDF、元の PDF の赤入れ版、ラウンドごとのレポートと推移、変更履歴、著者への確認事項 |

以下、`<skill_dir>` はこの SKILL.md があるディレクトリ、`<ws>` は作業フォルダ、`AWL` は `python <skill_dir>/scripts/awl.py` の略。`python` が無い環境では `python3` を使う。

## 0. 起動：モードと PDF を決める

使い方：

```
/academic-writing-loop 1回校正 paper.pdf
/academic-writing-loop loop paper.pdf
/academic-writing-loop loop 3 paper.pdf      ← 最大ラウンド数を指定（既定 5）
```

`loop N` は「校正を最大 N 回、反映（PDF の再生成）を最大 N−1 回」。最後は必ず校正で終わるので、最終版 PDF に何が残っているかが分かる。

所要時間の目安（テスト：2ページ・640語の論文）：1回校正は約15分。loop は1ラウンド目の校正が最も長く、全体で約45分（3回校正・2回反映）。ページ数にほぼ比例して延びる。

1. メッセージ（スキルの引数）からモードと PDF を読み取る。区切りは空白・「、」・「,」のどれでもよい。
   - 1回校正：`1回校正` `1回` `一回` `once` `single` `1`
   - loop：`loop` `ループ` `繰り返し`。直後の数字は最大ラウンド数（校正の回数。既定 5）
   - PDF：`.pdf` で終わるもの。相対パスは作業ディレクトリから解決し、見つからなければファイル名で探す。
   - モードが無ければ質問ツール（AskUserQuestion など。無ければチャット）で聞く：`1回校正` / `loop（校正→修正→再校正を繰り返す）`。PDF が無ければそれも聞く。
2. 投稿先の雑誌名・投稿規定の URL・US/UK の指定がメッセージにあれば使う。無くても聞かない（投稿先なし＝一般的な学術英語の慣習、綴り＝原稿の多数派）。
3. PyMuPDF を確認する：`python -c "import fitz"`。無ければ `python -m pip install pymupdf` を実行する（赤入れ PDF と位置情報に必要。入れられなければ赤入れ PDF なしで続け、その旨を伝える）。

## 1. セットアップ（両モード共通）

作業フォルダは `<PDF のフォルダ>/<PDF 名>_awl/`（書き込めなければ作業ディレクトリ配下）。

```bash
AWL init    <ws> --pdf <pdf> --mode once|loop [--max-rounds 5] [--journal "<投稿先>"]
AWL extract <ws>/rounds/r01/paper.pdf -o <ws>/rounds/r01/paper.txt
AWL scan    <ws>/rounds/r01/paper.txt -o <ws>/rounds/r01/scan.md
```

```
<ws>/
├── state.json         モード・上限ラウンド・終了理由（awl.py が管理）
├── style_sheet.md     表記の決定（全ラウンド共通）
├── original/          受け取った PDF。変更しない
├── src/               編集用ソース（loop のみ）
├── rounds/rNN/        paper.pdf paper.txt scan.md corrections.json report.md annotated.pdf
│                      revision_log.json（loop） src/ changes.diff（loop）
├── author_queries.md  著者への確認事項（loop）
└── work/              ページ画像など
```

- `extract` が「very little text per page」と警告したらスキャン PDF。OCR（pdf スキル）が必要なことを伝える。本文が英語でなければ、このスキルの対象外だと伝えて止める。
- 投稿先が分かっていて Web にアクセスできるなら、公式の投稿規定（Author guidelines / Instructions for authors）を読み、言語・書式の規則（US/UK、語数、要旨の構成、見出し、引用方式、図表、略語、キーワード数）を `style_sheet.md` の「投稿先・規定」と各行に書く。規定が最優先（ガイド §3）。
- loop モードでは、ここでユーザーへ2〜3行で伝える：作業フォルダ、上限ラウンド数、以後は確認を挟まずに進めること。1回校正モードは短いので、最後の返答にまとめればよい。

## 2. 1ラウンドの校正（両モード共通の手順）

校正の中身は `references/proofreader_brief.md`（手順・指摘の書き方・JSON の形式）と `references/proofreading_checklist.md`（区分と重大度）に従う。

**誰が校正するか**

- **1回校正モード**：自分で行ってよい。
- **loop モード**：ラウンドごとに**新しいサブエージェント**（Agent ツール）に任せる。改訂した本人の文脈を持たない校正者は、「何を直したつもりか」ではなく「PDF に実際に何が書いてあるか」だけで判断できる。同じ文脈で自分の修正を読み直すと、見落としが増える。
- **長い論文**（本文がおよそ12ページ・7,000語を超える）：ページ範囲（6〜8ページずつ、節の切れ目で）に分けて複数のサブエージェントに並行して任せ、`AWL merge` で統合したうえで、論文全体の一貫性（綴り、用語、略語、引用と文献、図表の番号、見出し）を自分か統合担当が `scan.md` の集計とあわせて確認する。
- サブエージェントが使えない環境では、すべて自分で順に行う。loop の2ラウンド目以降は、必ず新しい PDF から抽出したテキストを読んで校正する（記憶で判断しない）。

**校正担当への依頼文**（パスはすべて絶対パスで書く。サブエージェントのシェルは呼び出しごとに作業ディレクトリが戻ることがある）

```
あなたは学術英語の専門の校正者です。まず <skill_dir>/references/proofreader_brief.md と
<skill_dir>/references/proofreading_checklist.md を最後まで読み、その手順・基準・出力形式に従ってください。

- 校正する PDF: <ws>/rounds/rNN/paper.pdf（抽出テキスト: <ws>/rounds/rNN/paper.txt）
- 機械的チェックの候補: <ws>/rounds/rNN/scan.md
- 表記の決定: <ws>/style_sheet.md（ラウンド1では基本設定・用語・略語を埋める）
- 前ラウンドの指摘: <ws>/rounds/r(NN-1)/corrections.json   ← ラウンド2以降のみ
- 担当ページ: 全ページ   ← 分担するときは「p.1–8」など
- 出力: <ws>/rounds/rNN/corrections.json（分担時は corrections.partK.json）
- ツール: python <skill_dir>/scripts/awl.py（validate / report / annotate）、
          python <skill_dir>/scripts/pdf_tools.py render（図表のページを画像で見る）
- 環境の注意: <例：Windows。パスに日本語・空白を含むので引用符で囲む。<ws> と <skill_dir> の外には書き込まない>

著者の意味を変えないこと。数値・数式・引用文・文献タイトルは直さず、迷う点は query にしてください。
最後に「件数（誤り/明確さ/文体/著者確認）・多い誤りの傾向・validate の結果」を返してください。
```

**校正の後に必ず確認する**（サブエージェントに任せた場合も自分で実行する）

```bash
AWL validate <ws>/rounds/rNN/corrections.json        # VALID になるまで校正担当に直させる
AWL report   <ws>/rounds/rNN/corrections.json        # → report.md
AWL annotate <ws>/rounds/rNN/paper.pdf <ws>/rounds/rNN/corrections.json -o <ws>/rounds/rNN/annotated.pdf
```

`validate` は、各指摘の `original` が PDF のテキストに実在するかを照合する。見つからない指摘は、写し間違いか、存在しない文に対する指摘のどちらかで、どちらも赤入れにも改訂にも使えない。

## 3. 1回校正モード

1. §2 をラウンド r01 について行う。
2. `AWL finalize <ws>` → `<ws>/<PDF 名>_proofread.pdf`（赤入れ版）と `<ws>/report.md` ができる。
3. ユーザーへの返答は短くまとめる：
   - 件数（誤り / 明確さ / 文体 / 著者確認）と全体所見（2〜3文）
   - 多い誤りの傾向を上位3〜5個、それぞれ実例1つ（原文 → 修正案）と規則の名前
   - 著者確認（query）の一覧（短く）
   - ファイルの場所（赤入れ PDF はハイライトにマウスを乗せるかコメント一覧で修正案と理由が見える）
   - レポート全文は貼らない。最後に、loop モードなら修正の反映と PDF の再生成まで行えることを一言添える。

## 4. loop モード

### 4.1 編集用ソースの用意（r01 の校正と並行してよい）

`init` が PDF の隣にあるソースの候補を表示する。

- **LaTeX ソースがある**（.tex、フォルダ、Overleaf や arXiv の .zip / .tar.gz）：`<ws>/src/` にコピー・展開する（`\documentclass` と `\begin{document}` を含むファイルがメイン）。一度ビルドし、ソースが PDF と同じ版であることを確かめる：
  ```bash
  python <skill_dir>/scripts/build_pdf.py <ws>/src/<main>.tex --out <ws>/work/source_build.pdf
  AWL extract <ws>/work/source_build.pdf -o <ws>/work/source_build.txt
  AWL compare <ws>/rounds/r01/paper.txt <ws>/work/source_build.txt
  ```
  類似度が 0.95 未満なら版が違う可能性が高い。どちらを使うかユーザーに確認する。
- **候補が見つからない**：ソース（LaTeX / Overleaf の zip）があるかを一度だけ聞く。ソースがあると反映が正確で速い。
- **ソースが無い**：`references/pdf_to_latex.md` の手順で PDF から LaTeX を再構成する（サブエージェントに任せ、r01 の校正と並行させる。10ページで20〜40分）。レイアウトは近似になること、英文は誤りも含めて元のまま写すことを守らせる。
- **Word（.docx）原稿の場合**：このループは LaTeX を編集する。レイアウトを保ちたいなら1回校正の赤入れ PDF とレポートを見て Word で反映する方が確実なので、どちらにするかユーザーに確認する。
- 用意できたら `python <skill_dir>/scripts/snapshot.py <ws>/src <ws>/rounds/r01`。

### 4.2 ラウンド r（r = 1, 2, …）

**(a) 校正**：§2。終わったらユーザーへ1行だけ進捗を出す。例：`r02 校正完了：誤り 9 / 明確さ 4（前回 41 / 17）、前回の指摘の解決 52/58`

**(b) 続けるか判定**：`AWL status <ws>` を実行し、最終行の `NEXT:` に従う。止める条件はスクリプトが判定する（その場の印象で決めない）：
- 誤り＋明確さの指摘が 0 になった（収束）
- 上限ラウンド数に達した
- 誤り＋明確さの件数が前のラウンドから減らなかった（書き換えが往復しているだけになるため）
`NEXT: STOP` なら §4.3 へ。判定は校正の直後に行うので、最終版の PDF は必ず校正済みになる。

**(c) 反映**（ラウンド r の指摘を反映し、r+1 の PDF を作る）：下の依頼文で改訂担当のサブエージェントを起動し、完了を待つ。終わったら自分で確認する：
- `rounds/r{r+1}/paper.pdf`、`paper.txt`、`scan.md` がある。ビルドが成功し、未定義参照がゼロ
- `rounds/r{r}/revision_log.json` があり、`AWL verify <ws> --round r` が成功する（抽出の都合で引っかかった項目は、ページ画像で確かめて `verified_manually` が付いていればよい）
- ビルドが通らないときは、壊れたファイルを `rounds/r{r}/src/` から戻して反映をやり直す。古い PDF を新しい版として校正に回してはいけない。

→ r+1 として (a) へ。

**改訂担当への依頼文**（パスは絶対パスで）

```
あなたは著者側の編集者として、英文校正の指摘を原稿に反映します。まず
<skill_dir>/references/reviser_brief.md を最後まで読み、その規則（意味とデータを変えない、
query は本文を変えない、local → global の順）に従ってください。

- 編集するソース: <ws>/src/（メイン: <main>.tex）
- 今回の指摘: <ws>/rounds/rNN/corrections.json（report.md も参照）
- 表記の決定: <ws>/style_sheet.md（見送った理由が著者の意図・分野の慣習なら「変更しない箇所」に追記）
- 著者への確認事項: <ws>/author_queries.md（query を追記）
- 新しい PDF: <ws>/rounds/rMM/paper.pdf（MM = NN+1）。ビルド・抽出・scan・snapshot・revision_log.json・verify の
  手順は reviser_brief.md の §4 のとおり。
- 環境の注意: <校正担当と同じ>

最後に「適用/見送り/著者確認の件数・ビルド結果・verify の結果・style sheet に追記したこと」を返してください。
```

### 4.3 終了処理

1. `AWL finalize <ws>`（ユーザーの中断など、判定以外の理由で止めるときは `--reason "<理由>"`）。`<PDF 名>_corrected.pdf`（最終版）、`<PDF 名>_proofread_r01.pdf`（元の PDF の赤入れ版）、残りの指摘があれば `<PDF 名>_corrected_remaining.pdf`、`changelog.md`、`progress.md` ができる。最終ラウンドの著者確認は反映担当を通らないので、`finalize` が `author_queries.md` に追記する。
2. 変更箇所に色の付いた PDF（任意）：`src/` を汚さないよう `<ws>/work/diff_src/` にコピーして作る。
   ```bash
   cp -r <ws>/src <ws>/work/diff_src
   latexdiff <ws>/rounds/r01/src/<main>.tex <ws>/src/<main>.tex > <ws>/work/diff_src/diff.tex
   ```
   `latexdiff` が 0 以外で終わるか `diff.tex` が空なら（MiKTeX では Perl モジュール不足で失敗することがある）、作らずに先へ進み、返答で一言触れる。成功したら `build_pdf.py <ws>/work/diff_src/diff.tex --out <ws>/<PDF 名>_diff.pdf`。
3. `<ws>/final_report.md` を書く：
   ```markdown
   # 英文校正レポート：<論文タイトル>
   - モード / ラウンド数 / 終了理由 / 投稿先・綴り・引用方式（style sheet）
   ## 推移                       （progress.md の表）
   ## 元の原稿の英語の傾向         （r01 の summary と区分別件数。多い誤りの実例と規則）
   ## 反映した主な修正             （changelog.md から代表例）
   ## 著者への確認事項             （author_queries.md。優先度の高い順）
   ## 残っている指摘               （最終ラウンドの report.md の要点）
   ## ファイル一覧
   ```
4. ユーザーへの返答は短く：ラウンド数と推移（誤り＋明確さの件数）、多かった誤りの傾向、著者確認の上位、残りの指摘、ファイルの場所。レポート全文は貼らない。

## 中断からの再開

`<ws>/state.json` があれば `AWL status <ws>` で状況を見て、`NEXT:` の工程から再開する。`init` は既存の作業フォルダを上書きしない（やり直すときだけ `--force`）。

## 原則と、その理由

- **意味を変えない・内容を作らない**：校正の対象は言葉であって、研究の中身ではない。数値・データ・数式・引用文・文献タイトル・主張の強さは変えない。校正者だけで決められない点は query として著者に返す。実在の原稿なので、推測で書き換えると著者の主張を歪める。
- **一貫性は style sheet で守る**：ラウンドごとに別の校正者が読むので、決定を書き残さないと「UK に直す → US に戻す」の往復が起きる。決定は投稿規定 → 既刊論文 → 原稿の多数派の順で決め、途中で変えない。
- **校正と反映を分ける**：校正者は PDF だけを見て指摘し、改訂者は指摘の正しさを確かめてから反映し、その結果を次の校正者が独立に確かめる。自分の修正を自分で確かめるより、見落としと改訂で入る誤りを拾いやすい。
- **機械的な照合をはさむ**：`validate`（指摘が実在の文に対するものか）、`verify`（反映が PDF に届いたか）、`compare`（再構成が元と同じか）は、言語モデルの思い込みを数字で確かめるためのもの。省略しない。
- **止める判断はスクリプトに任せる**：`status` の `NEXT:` に従う。校正者は探せば何かしら提案するので、印象で続けると文体の好みを往復させるだけになる。
- **ラウンドの間でユーザーに確認しない**：loop を選んだ時点で、上限ラウンドまでの実行は承認済み。報告は1行の進捗だけにし、止まって相談するのはブロッカー（ビルドが直せない、ソースと PDF の版が違う、PDF が読めない）のときだけ。
- **元のファイルは変更しない**：`original/` と、ユーザーのフォルダにある元の PDF・ソースには書き込まない。編集は `<ws>/src/` のコピーで行う。
- **ガイドの古い規則は style 扱い**：ガイド（2014年）は分割不定詞や単数の they を避ける立場だが、現在の多くのスタイルガイドは許容する。投稿規定が求めない限り誤りとはしない。
