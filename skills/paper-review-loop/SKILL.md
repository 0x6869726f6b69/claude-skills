---
name: paper-review-loop
description: 論文PDFを、その分野に精通した厳格かつ建設的な査読者として査読し（Paper Summary / Strengths / Weaknesses / Justification / Rebuttal向け質問 / Rating / Confidence）、指摘に沿って原稿を改訂→PDF再生成→再査読するサイクルを、ユーザーが指定した制限時間内でできるだけ多く繰り返す。起動直後に制限時間をユーザーに確認する。論文・原稿・preprint・投稿前やリジェクト後の論文PDFについて「査読して」「レビューして」「採択されるように改善して」「rebuttalに備えたい」「self-review」「ブラッシュアップして」などと頼まれたら、スキル名が出ていなくても使うこと。Federated Learning（non-IID・partial participation・privacy）、機械学習の理論・大規模実験の論文向けの詳しいチェックリストを持つ。Use for peer review of a paper PDF and time-boxed review→revise→re-review loops.
---

# Paper Review Loop：査読 → 改訂 → 再査読

論文PDFを専門家として査読し、その指摘に沿って原稿を改訂してPDFを作り直し、改訂版をまた査読する。これをユーザーが決めた制限時間の中でできるだけ多く回す。最後にユーザーへ渡すものは次の3つ。

- 改訂版PDF（最終版）と、各ラウンドのPDF
- 各ラウンドの査読レポート（7項目）と、評価・指摘状態の推移
- 著者にしかできない作業のリスト（追加実験など。捏造を避けるため本文ではなくここに回したもの）

以下、`<skill_dir>` はこの SKILL.md があるディレクトリ、`<ws>` は作業フォルダ。`loop_state.py` などのスクリプト名は `python <skill_dir>/scripts/loop_state.py` の略。`python` が無い環境では `python3` を使う。

## 0. 最初に：制限時間を聞く

1. 対象のPDFを特定する。メッセージに無ければ聞く。PDFと同じ場所や添付に LaTeX ソース（フォルダ、.zip、arXiv の .tar.gz、.tex）があるかも確認する。ソースがあると改訂の質と速さが大きく上がる。
2. 制限時間を聞く。AskUserQuestion などの質問ツールがあれば使い、無ければチャットで聞いて答えを待つ。起動メッセージで既に時間が明示されていれば、それを使い聞き直さない。
   - 質問1「制限時間」：`査読のみ（改訂ループなし）` / `1時間` / `2時間` / `3時間`（その他で「30分」「5時間」なども可）
   - 質問2「投稿先・評価基準」（同じ質問ダイアログにまとめる。既に分かっていれば省く）：`指定なし（トップ国際会議の基準）` / `NeurIPS・ICML・ICLR` / `論文誌（Accept / Minor / Major / Reject）`
3. 答えを受けたらすぐ時計を始める。セットアップの時間も予算に含まれる。
   ```bash
   python <skill_dir>/scripts/loop_state.py init <ws> --hours 2 --paper <pdf> --venue "<投稿先>"
   ```
   （`--minutes 90` や `--review-only` も可）
4. スリープ防止ツール（Claude デスクトップの keep-awake など）があれば、予算の時間ぶん有効にする。PCがスリープすると長時間ループは止まってしまう。
5. ユーザーへ2〜3行で伝える：締め切り時刻、作業フォルダ、以後は確認を挟まず自律的に回すこと、いつでも中断できること。

## 1. セットアップ

作業フォルダは `<PDFのあるフォルダ>/<PDF名>_review_loop/`（書き込めなければ作業ディレクトリ配下）。

```
<ws>/
├── state.json          タイマーと各フェーズの記録（loop_state.py が管理）
├── original/           受け取ったPDF・ソース。変更しない
├── src/                編集用ソース（main.tex, figures/, *.bib）
├── work/               ページ画像など作業用の一時ファイル
├── rounds/
│   ├── r01/            paper.pdf(=元のPDF) paper.txt review.md issues.json response.md src/
│   ├── r02/            paper.pdf(改訂1回目) paper.txt review.md issues.json response.md src/ changes.diff
│   └── ...
├── issue_tracker.md    評価と指摘状態の推移（loop_state.py summary が生成）
├── author_todo.md      著者にしか解決できない課題（追加実験など）
└── final_report.md
```

1. `loop_state.py start <ws> --round 0 --phase setup`
2. PDFを `original/` と `rounds/r01/paper.pdf` にコピーし、テキストを抽出する：
   `python <skill_dir>/scripts/pdf_tools.py text <ws>/rounds/r01/paper.pdf -o <ws>/rounds/r01/paper.txt`
3. 編集用ソースを `src/` に用意する（査読のみモードでは不要なので飛ばす）。
   - **LaTeX ソースがある場合**：`src/` へコピー／展開する（`\documentclass` と `\begin{document}` を含むファイルがメイン）。`build_pdf.py` で一度ビルドし、通ることを確認する。
   - **PDFしか無い場合**：`references/pdf_to_latex.md` の手順で LaTeX ソースを再構成する。最も重い工程（10ページで20〜40分程度）なので、予算を食うことをユーザーに一言伝える。
4. `python <skill_dir>/scripts/snapshot.py <ws>/src <ws>/rounds/r01`
5. `loop_state.py end <ws> --round 0 --phase setup`

ラウンド1の査読は元のPDFが対象なので、ソースの再構成と並行して走らせてよい。サブエージェントが使えるなら、査読担当と再構成担当を同時に起動する。

## 2. ループ

### 役割分担と、その理由

- **査読はラウンドごとに新しいサブエージェント**（Agent ツール）に任せる。改訂した本人の文脈を持たない査読者は「何を直したつもりか」ではなく「PDFに実際に何が書いてあるか」だけで判断できる。同じ文脈で自己採点すると評価が甘くなる。
- **改訂もサブエージェント**に任せ、メインはオーケストレーション（時計、起動、検証、集計）に徹する。数時間のループでもメインの文脈が膨らまず、状態はすべてファイルに残る。
- サブエージェントが使えない環境では全部を自分で順に行う。その場合も、査読の前に新しいPDFからテキストを抽出し直してそれを読み、記憶ではなく紙面で評価する。

### ラウンド r（r = 1, 2, …）

**(a) 査読**
1. `loop_state.py start <ws> --round r --phase review`
2. 下の「査読担当への依頼文」でサブエージェントを起動し、完了を待つ。
3. 出力を検証する：`review.md` に必要な節（r≥2 は第0節も）があること、`issues.json` が JSON として読めること。欠けていれば同じ査読担当に直させる。
4. `loop_state.py end <ws> --round r --phase review`、続けて `loop_state.py summary <ws>`（`issue_tracker.md` を更新）。
5. ユーザーへ1行だけ進捗を出す。例：`r02 査読完了：総合 3→4、Major未解決 5→2、残り 1h12m`

**(b) 続けるか判定**
1. `loop_state.py status <ws>` を実行する。Claude は経過時間を感じ取れないので、時間の判断は必ずこの出力に従う。
2. `NEXT: STOP` なら §3 へ。判定は査読の直後に行うので、最終版PDFは必ず査読済みになる。
3. `CONTINUE` でも、最新の `issues.json` に `status` が `open` / `partially_resolved` の指摘が残っていなければ（すべて `resolved` か、`[AUTHOR TODO]` で保留した `needs_author`）終了してよい。本文で直せるものが尽きており、それ以上回しても文言を磨くだけになる。理由は final_report に書く。

**(c) 改訂**（ラウンド r の査読に対応し、r+1 のPDFを作る）
1. `loop_state.py start <ws> --round r --phase revise`。status に出ている `revise by` の時刻を控える。
2. 下の「改訂担当への依頼文」でサブエージェントを起動し、完了を待つ。
3. 検証する：`rounds/r{r+1}/paper.pdf` と `paper.txt` があること、ビルドが成功し未定義参照がゼロであること、`rounds/r{r}/response.md` があること。ビルドが通らない場合は、壊れたファイルを `rounds/r{r}/src/` から戻して変更をやり直す。古いPDFを改訂版として査読に回してはいけない。
4. `loop_state.py end <ws> --round r --phase revise` → r+1 として (a) へ。

改訂担当は `revise by` を過ぎたら新しい修正を始めず、ビルドを通して終える。次の査読の時間を残すため。

### 査読担当への依頼文

```
あなたはこの論文の査読者です。まず <skill_dir>/references/reviewer_guide.md と
<skill_dir>/references/review_template.md を最後まで読み、査読者像・基準・出力形式に従ってください。

- 査読対象: <ws>/rounds/rNN/paper.pdf（抽出テキスト: <ws>/rounds/rNN/paper.txt）
- ラウンド: NN
- 前ラウンドの指摘: <ws>/rounds/r(NN-1)/issues.json   ← ラウンド2以降のみ
- 投稿先・評価尺度: <venue または「指定なし」>
- 査読レポートの言語: 日本語
- 出力: <ws>/rounds/rNN/review.md と <ws>/rounds/rNN/issues.json
- 補助: python <skill_dir>/scripts/pdf_tools.py（render で図表のあるページを画像にして確認できる）

評価の根拠は、このPDFに書かれている内容だけです。改訂者の意図や回答書は渡していません。
[AUTHOR TODO] と書かれた箇所は約束にすぎないので、未解決として扱ってください。
最後に「総合評価 / Confidence / Major未解決数 / 新規指摘数」を4行で返してください。
```

### 改訂担当への依頼文

```
あなたはこの論文の著者として、査読に基づいて原稿を改訂します。まず
<skill_dir>/references/revision_guide.md を最後まで読み、特に「捏造しない」規則を守ってください。

- 編集するソース: <ws>/src/（メイン: <main>.tex）
- 今回の査読: <ws>/rounds/rNN/review.md, <ws>/rounds/rNN/issues.json
- 推移: <ws>/issue_tracker.md（自動生成なので読むだけ。編集しない）
- 著者TODO: <ws>/author_todo.md（無ければ作り、追記・更新する）
- 時間: <revise_by> までにビルドまで終えること。残り時間は
  python <skill_dir>/scripts/loop_state.py status <ws> で確認できる。
- 終わったら:
  1. python <skill_dir>/scripts/build_pdf.py <ws>/src/<main>.tex --out <ws>/rounds/r(NN+1)/paper.pdf
     （エラーと未定義参照がゼロになるまで直す）
  2. python <skill_dir>/scripts/pdf_tools.py text <ws>/rounds/r(NN+1)/paper.pdf -o <ws>/rounds/r(NN+1)/paper.txt
  3. python <skill_dir>/scripts/snapshot.py <ws>/src <ws>/rounds/r(NN+1) --prev <ws>/rounds/rNN
  4. <ws>/rounds/rNN/response.md を書く（形式は revision_guide.md）
最後に「対応した指摘ID / 著者TODOに回したID / ビルド結果（ページ数・未定義参照・AUTHOR TODO数）」を返してください。
```

PDFからの再構成を任せる場合は「`<skill_dir>/references/pdf_to_latex.md` を読み、`<ws>/original/<name>.pdf` を `<ws>/src/` に再構成し、ビルドしたPDFを `<ws>/rounds/r01/reconstructed.pdf` に保存して、差異を `<ws>/src/RECONSTRUCTION_NOTES.md` に書く」と依頼する。

## 3. 終了処理

1. `loop_state.py finish <ws> --reason "<締め切り / 本文で直せる指摘が尽きた / 査読のみ>"` → `loop_state.py summary <ws>`
2. 改訂を1回以上したら、最新のPDFを `<ws>/<PDF名>_revised.pdf` としてコピーする。
3. `<ws>/final_report.md` を書く：

```markdown
# 査読・改訂レポート：<論文タイトル>
- 制限時間 / 使用時間 / ラウンド数 / 終了理由
## 評価の推移            （issue_tracker.md の表）
## 元原稿（r01）の査読の要点   （Justification の要約と主要な Weakness）
## 改訂で解決した主な指摘
## 残っている課題
### 本文の修正で対応できるが時間内に終わらなかったもの
### 著者の作業が必要なもの（author_todo.md の優先度上位）
## 最終ラウンドの評価と、採択側に動かすための条件
## ファイル一覧
```

4. ユーザーへの返答は短くまとめる：ラウンド数、評価の推移、解決した主な指摘、残る重要課題と著者TODO上位3件、ファイルの場所。査読全文は貼らずファイルを示す。査読のみモードなら、r01 の review.md の要点（Justification・Rating・主要な Weakness・Rebuttal 質問）を返答に含める。

## 中断からの再開

`<ws>/state.json` があり status が running なら、`loop_state.py status <ws>` と `rounds/` の中身を見て、最後に完了したフェーズの次から再開する。`init` をやり直すと時計がリセットされるので、ユーザーが新しい予算を望んだときだけ `--force` で行う。

## 原則と、その理由

- **捏造しない**：実験結果・数値・データ・引用・証明を作らない。これは実在の研究原稿であり、作った数値が一つでも混じれば研究不正になってユーザーに深刻な害を与える。新しい結果が必要な指摘は、本文では主張を証拠の範囲に合わせ、必要な実験は `[AUTHOR TODO]` と `author_todo.md` に回す。
- **査読の基準を緩めない**：ラウンドが進んでも同じ基準で評価する。`[AUTHOR TODO]` は未解決であり、言い換えだけでは新しい証拠にならない。評価が上がるのは、紙面上で問題が解決されたときだけ。そうでなければ、このループは見かけのスコアを上げるだけの作業になってしまう。
- **時間の判断はスクリプトに任せる**：経過時間を推測しない。毎ラウンド `status` を見る。
- **ラウンド間でユーザーに確認しない**：制限時間を受け取った時点でループ全体の実行は承認済み。報告は1行の進捗だけにし、止まって相談するのはブロッカー（ビルドが直せない、PDFが読めない等）のときだけ。
- **元ファイルは変更しない**：`original/` は読み取り専用として扱い、編集は `src/` のコピーで行う。
