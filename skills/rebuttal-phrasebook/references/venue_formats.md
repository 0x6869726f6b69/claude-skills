# 投稿先ごとの rebuttal の形式

Opening Statement と General Response をどこに・どの長さで書けるかは、会議と年度でかなり違う。**毎年変わるので、下書きの前に必ずその年の Author Guide / FAQ / Dates / OpenReview の入力欄で確認する**（Web が使えるなら検索して確かめ、確認した URL と日付を出力に書く）。確認するのは、(1) 議論期間がまだ開いているか（終わっていれば投稿できないことを最初に伝える）、(2) 全員向けの欄の有無、(3) 文字数・語数の上限、(4) 改訂 PDF の可否と期限、(5) リンクと LLM 利用の規定。下表は 2026-11 時点で確認できた情報で、出典のない項目は推測として扱うこと。

| 会議 | 全員向けの General Response | 個別返信の制限 | 改訂 PDF | 出典 |
| --- | --- | --- | --- | --- |
| ICLR 2027 | フォーラム直下のコメントとして置ける（公開範囲は、全体・査読者以上・AC 以上・PC のみから選べる）。議論期間は 2026-11-05〜11-18 | コメントの数に制限はないが、**1 コメントごとに語数の上限がある**（数はガイドに書かれていないので入力欄で確認） | 公開議論の終わり（11-18）まで改訂可。何を変えたかを著者が明示することが求められている。議論期間中は本文 10 ページまで | [ICLR 2027 Author Guidelines](https://iclr.cc/Conferences/2027/AuthorGuidelines), [Dates](https://www.iclr.cc/Conferences/2027/Dates) |
| ICLR 2024–2026 | 同上（タイトル例: "General Response", "Summary of Revisions"） | 年度ごとに入力欄で確認 | 議論期間中にアップロード可。2026 は議論期間中だけ本文上限が 9 → 10 ページ | [ICLR 2026 Author Guide](https://www.iclr.cc/Conferences/2026/AuthorGuide), [AC Guide](https://iclr.cc/Conferences/2026/AreaChairGuide) |
| NeurIPS 2023–2024 | あり。"Author Rebuttal"（全員向け）＋ 1 ページの PDF（図表用） | 査読者ごとに文字数制限あり | 不可（camera-ready まで） | データ上の慣行。公式ページは未確認 |
| NeurIPS 2025– | **なし**（global rebuttal は廃止） | 査読者ごとに 10,000 字。リンク禁止 | 不可（camera-ready まで） | [NeurIPS 2025 FAQ](https://neurips.cc/Conferences/2025/PaperInformation/NeurIPS-FAQ) |
| ICML 2026 | 個別返信が中心（全員向け欄の有無は年度ごとに確認） | rebuttal → 査読者の追加質問 → 著者の追加返信の 3 往復、各 5,000 字。査読者は返信を確認したことの表明が必須 | 年度ごとに確認 | [ICML 2026 Reviewer Instructions](https://icml.cc/Conferences/2026/ReviewerInstructions) |
| ACL ARR / EMNLP | 個別返信が中心。AC 宛ての "Author response to AC"（confidential comment）がある回もある | サイクルごとに確認 | 不可 | サイクルごとに確認 |
| 論文誌（Response letter） | 冒頭の Cover letter / Opening が General Response に当たる | なし | 改訂版を一緒に提出 | 雑誌ごとに確認 |

## 形式ごとの書き分け

- **General Response を置ける場合（ICLR、NeurIPS 2023–2024）**：Opening（謝辞＋査読者が認めた強み）→ 改訂・追加実験の要約 → 複数の査読者に共通する懸念への回答 → 結び、の順に 1 本にまとめ、個別返信では「General Response の G2 を参照」と参照番号で指す。ICLR は改訂 PDF の変更箇所の示し方（色・節番号）もここに書く。
- **General Response を置けない場合（NeurIPS 2025–、ICML）**：Opening を 1–2 文に縮めて各個別返信の冒頭に入れる。共通の懸念への回答は、文字数の余裕がある返信に本文で書き、他の返信では短く要点だけ繰り返す（他の査読者の返信は読まれないことがあるので参照に頼らない）。
- **文字数制限が厳しい場合**：謝辞は 1 文に抑え、強みの列挙を削り、懸念への回答に字数を回す。データでも、採択された論文の GR は短め（中央値 261 語）で、詳しい結果は個別返信や付録に置かれている（`phrasebook.md` の「0. 型を選ぶ前に知っておく数字」を参照）。
- **論文誌**：Opening に "We thank the Editor and the Reviewers ..." を置き、主要な変更点の箇条書き → 以降は査読者ごとの point-by-point、が定型。

## 期間中の追加メッセージ

OpenReview の会議では、最初の返信のあとにも次のような定型の投稿がよく使われる（`phrasebook.md` の「4. 期間中の追加メッセージ」を参照）。

- 議論期限が近いことを知らせ、返信を促す（丁寧に、1 回まで。繰り返すと逆効果）
- スコアを上げてくれた査読者へのお礼
- 議論の最後に、AC 向けに議論全体を要約する投稿（"Summary of the discussion"）
