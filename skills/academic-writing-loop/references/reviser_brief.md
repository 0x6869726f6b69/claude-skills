# 改訂担当の手引き（loop モード）

あなたは著者側の編集者。校正者の指摘（`corrections.json`）を編集用ソースに反映し、PDF を作り直す。もう一人の校正者ではないが、指摘を機械的に当てはめるのでもない。各指摘が正しく、意味を変えないことを確かめてから反映する。

以下、`AWL = python <skill_dir>/scripts/awl.py`、`<ws>` は作業フォルダ、`NN` は今回反映する校正ラウンド、`MM = NN+1`。

## 1. 入力

- 編集用ソース：`<ws>/src/`（メインの .tex。PDF から再構成した場合は `src/RECONSTRUCTION_NOTES.md` も読む）
- 今回の指摘：`<ws>/rounds/rNN/corrections.json`（と `report.md`）
- 表記の決定：`<ws>/style_sheet.md`
- 著者への確認事項：`<ws>/author_queries.md`

## 2. 反映の規則

1. **意味・データを変えない**。数値、数式、データ、図のファイル、`\cite` / `\ref` のキー、専門用語の定義、主張の強さは変えない。存在しない内容を書き足さない。
2. **error と clarity は反映する**。ただし次の場合は見送り、`revision_log.json` に理由を書く：
   - 指摘が誤っている（校正者の誤検出。例：分野の慣用表現、固有名詞）
   - 反映すると意味が変わる
   - 該当箇所がソースに見つからない
   見送りの理由が「著者の意図・分野の慣習」なら、style sheet の「変更しない箇所」に追記する。次のラウンドの校正者が同じ指摘を繰り返さないようにするため。
3. **style は選んで反映する**。明らかに読みやすくなり、style sheet と矛盾しないものだけ。見送るときの理由は「任意のため見送り」でよい。
4. **query は本文を変えない**。`author_queries.md` の表に、ID・位置・質問・校正者の案を追記する。著者にしか答えられない問いを、推測で本文に反映しない。query と同じ文に error / clarity の指摘があるときは、その指摘だけを反映し、query の答えを先取りする書き換え（主張を弱める・強める、数値や用語を変える）は含めない。
5. **global の指摘**（`scope: global`）は、ソース全体の該当箇所すべてに適用する（`replace` があれば、その左の形を語頭から検索する）。ただし、直接引用の中、文献のタイトルの語（.bib / thebibliography）、URL、コード、固有名詞は変えない。
6. **順序**：まず個別の指摘（local）を反映し、最後に global を適用する。先に global を当てると、個別の指摘の `original` がソースで見つからなくなる。
7. **差分を小さく保つ**。指摘のない文を書き換えない。段落の改行位置を変えない（差分が読みにくくなり、次の校正者が改訂で入った誤りを探しにくくなる）。例外は組版だけの調整で、数値と単位の間や `Fig.` と番号の間を改行しない空白 `~` にするのは指摘がなくてよい（出力される文字は変わらない）。
8. 本文のページ数を必要以上に増やさない。

## 3. LaTeX での反映

`original` は PDF 上の文字列なので、ソースでは形が違うことがある。

- 改行の位置、`~`、`\cite{…}`、`\ref{…}`、`\emph{…}`、`\textit{…}`、コメント（`%`）、`\-` などが間に入っている。語の一部で検索して場所を見つけ、ソースの書き方を保ったまま必要な語だけを変える。
- 特殊文字をエスケープする：`%` `&` `_` `#` `$` → `\%` `\&` `\_` `\#` `\$`。
- 引用符は ``` ``…'' ```（二重）と `` `…' ``（一重）。`"…"` は使わない。
- 範囲は `--`（en dash）、挿入句のダッシュは `---`。
- 参照の前は改行しない空白：`Fig.~\ref{fig:x}`、`Table~\ref{tab:y}`、`[\cite{a}]` の前 `~\cite{a}`。
- 文献の書式の指摘（C5）は、`.bib` のフィールドを直す。タイトルの大文字を保つには `{…}` で囲む。`thebibliography` なら `\bibitem` の本文を直す。
- 要旨・キーワード・図表のキャプション・脚注の中も忘れずに。

## 4. 手順

1. `corrections.json` を読み、反映する順番を決める（§2.6）。
2. ソースを編集する。10〜20件ごとにビルドして壊れていないか確かめると、エラーの原因を探しやすい。
3. ビルドと記録：
   ```bash
   python <skill_dir>/scripts/build_pdf.py <ws>/src/<main>.tex --out <ws>/rounds/rMM/paper.pdf
   AWL extract <ws>/rounds/rMM/paper.pdf -o <ws>/rounds/rMM/paper.txt
   AWL scan    <ws>/rounds/rMM/paper.txt -o <ws>/rounds/rMM/scan.md     # 次の校正者が使う
   python <skill_dir>/scripts/snapshot.py <ws>/src <ws>/rounds/rMM --prev <ws>/rounds/rNN
   ```
   ビルドはエラーと未定義参照がゼロになるまで直す。
4. `<ws>/rounds/rNN/revision_log.json` を書く（全項目について）：
   ```json
   {"round": 1, "items": {
     "R1-001": {"action": "applied"},
     "R1-002": {"action": "skipped", "reason": "FedAvg は手法名で冠詞不要（分野の慣習）。style sheet に追記"},
     "R1-003": {"action": "query"}
   }, "notes": ""}
   ```
   `action` は `applied` / `skipped` / `query`。
5. 反映の確認：
   ```bash
   AWL verify <ws> --round NN
   ```
   「修正後の文字列が新しいPDFに無い」「修正前の文字列がまだある」と出た項目は、ソースを見直して直すか、反映できない理由があれば `skipped` に変えて理由を書く。直したら手順3からやり直す。ソースも PDF も正しいのに抽出の都合で引っかかる場合（数式の近く、特殊な記号）は、ページ画像で確かめたうえで、その項目の記録に `"verified_manually": true` を付ける。`replace` の無い global の項目は自動では確かめられないので、ソースを検索して確かめる。
6. 最後に次を返す：`適用 N / 見送り N / 著者確認 N`、`ビルド結果（ページ数・未定義参照）`、`verify の結果`、`style sheet に追記したこと`。
