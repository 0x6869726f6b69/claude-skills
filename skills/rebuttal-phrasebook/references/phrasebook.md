# Rebuttal Phrasebook（典型文と型）

OpenReview で公開された著者の返信から集計した。対象は、フォーラム直下に置かれた著者の全体向け返信（General Response、以下 GR）16,772 件と、査読者ごとの最初の返信 124,973 件。主な会議は ICLR 2019–2025、NeurIPS 2021–2024、CoRL。出典と限界は `data_stats.md` を参照。

**ここに載せている英文は、多数の論文で共通に使われている定型句（使用した論文が数十件以上あるもの）と、それをもとに書き起こした型だけ。** 特定の著者の文章は載せていない。

## 表記

- `[...]` は埋めるスロット。`{A | B}` はどちらかを選ぶ。
- 統計は **典型文全体ではなく、引用符で示した核の句（n-gram）** についての数字。典型文は、その核の句を中心に書き起こした型。
- 〔GR 48%〕：その句を含む GR の割合。〔返信 23%〕は個別返信での割合。「件」は、その句を含む GR（論文）の数。
- 件数が 150 未満の行の採択率は誤差が大きい（±8 ポイント以上）。**（n 少）** と付けた数字は目安にとどめる。
- 「—」は集計していない（言い換えとして加えた）型。
- 採択：その句を含む GR のうち、採択された論文の割合（ICLR 2020–2024 だけで計算。採択・不採択の両方が公開されているため）。GR を出した論文全体では **44%**。
- 上昇：その句を含む論文（個別返信ではその査読者）について、査読者がのちに「スコアを上げた」と書いた割合。GR 全体では 59%（ICLR 51%、NeurIPS 72%）、個別返信では 20%（ICLR 18%、NeurIPS 27%）。会議で大きく違うので、**move や形の比較は同じ会議の中で計算した値**（[ICLR 59% vs 48%] = その move がある GR とない GR）を書いている。句ごとの上昇は会議を混ぜた値なので、NeurIPS で多い句（PDF を指す句など）は高めに出る。
- **どの数字も相関。** 評価の高い論文ほど強みを挙げやすく、丁寧な返信を書きやすい。「この句を使えば採択される」とは読まない。

## 0. 型を選ぶ前に知っておく数字

- GR を出す論文は ICLR で約 4 割（2024: 43%、2025: 42%）、NeurIPS 2023–2024 で約 6 割（global response 欄があった年）。ICLR 2024 では、GR を出した論文の採択率 46%、出さなかった論文 35%。
- GR の中身（どこかに含む割合）：謝辞 92%、追加実験 52%、改訂の知らせ 46%、強みの確認 32%、誤解の説明 28%、疑問があれば答えるという結び 26%、貢献の再確認 26%、個別返信への案内 23%、変更点の列挙 20%、共通の懸念 20%、スコアへの言及 3%。
- 形：箇条書きあり 60%、見出しあり 34%、査読者 ID の明記 28%、変更箇所の色分け 17%、表 13%、査読者の褒め言葉の引用 11%。宛名（"Dear Reviewers," など）を付けるのは 15%。
- 長さ：語数の中央値は採択 261 語、不採択 303 語。ICLR では、150 語未満の GR の採択 48% に対し、600–1,200 語は 37%。逆にスコア上昇は長いほど多い（ICLR：150 語未満 42%、300–600 語 54%、600–1,200 語 53%）。厳しい査読ほど長い GR が必要になるという交絡を含む。**GR は要点と参照先に絞り、詳しい結果は個別返信や付録に置く**のが多数派。
- 形と上昇（ICLR 内）：箇条書きあり 54% vs 45%、見出しあり 56% vs 49%、変更箇所の色分け 60% vs 48%。
- 冒頭 3 文の並び（謝辞を除く）で多いもの：「改訂の知らせ」「追加実験」「強みの確認 → 追加実験」「改訂の知らせ → 変更点の列挙」「強みの確認 → 改訂の知らせ」。

## 1. スケルトン

### A. 全員向けの欄がある場合の標準形（ICLR など）

```
[宛名：任意]
[謝辞 1 文]  We thank all reviewers for their [thoughtful | constructive] feedback.
[強みの確認 1–2 文、査読者 ID つき]
  We are encouraged that the reviewers found [strength 1] ([IDs]), [strength 2] ([IDs]), and [strength 3] ([IDs]).
[改訂の知らせ 1 文]  We have uploaded a revised version of the paper, with changes highlighted in blue.
[変更点の列挙：3–6 項目]
  The main changes are:
  1. [New experiments on X] (Sec. [N], Table [N]) — [Reviewer IDs]
  2. [Clarification of Y] (Sec. [N]) — [Reviewer IDs]
  3. ...
[共通の懸念：見出し + 2–5 文ずつ]
  **G1. [懸念の名前]** ([IDs]) ...
  **G2. ...**
[個別返信への案内 1 文]  We address the remaining points in our responses to each reviewer below.
[結び 1 文]  We hope these revisions address the reviewers' concerns, and we are happy to answer any further questions.
```

- 変更点の列挙の各項目に、関わる査読者 ID と節・表番号を付けると、査読者が自分の指摘への対応を見つけやすい。
- 共通の懸念が無ければ G の節は作らない（1 人だけの指摘を G に入れない）。

### B. 全員向けの欄 + 1 ページ PDF がある場合（NeurIPS 2023–2024 型）

A と同じ順で、追加の図表を PDF に置き、本文から番号で指す。

```
We thank the reviewers for their [valuable] feedback. In this global response, we [summarize the new results | address the questions raised by multiple reviewers].
The attached PDF contains [Figure R1: ...; Table R1: ...].
**[G1 見出し]** ... (see Table R1 in the attached PDF)
...
We respond to the other questions in the individual responses.
```

〔PDF を指す句は GR の 16%。ほぼ NeurIPS。上昇 [NeurIPS 79% vs 69%]〕

### C. 全員向けの欄が無い場合（NeurIPS 2025 以降、ICML など）

各返信の冒頭に 1–2 文の Opening を置き、すぐに本題へ入る。

```
We thank the reviewer for the [careful | detailed] review and for recognizing [strength the reviewer named].
Below we address each point; [new results | changes to the paper] are summarized at the end.
```

共通の懸念は、それを挙げた査読者すべての返信で、短くても本文で答える（他の返信への参照に頼らない）。

### D. 好意的な査読・変更が少ない場合の短い GR（150 語前後）

```
We thank all reviewers for their positive and constructive feedback. We are glad that the reviewers found [strength 1] and [strength 2].
Following the suggestions, we have [made change 1] and [made change 2] (highlighted in blue in the revised PDF).
We respond to each reviewer's questions individually below.
```

### E. 論文誌の Response letter の冒頭

```
Dear Editor and Reviewers,
We thank the Editor and the Reviewers for their careful reading of our manuscript and for their constructive comments. We have revised the manuscript accordingly; the main changes are summarized below, and a point-by-point response follows. Changes in the manuscript are highlighted in [blue].
```

## 2. 働き（move）ごとの典型文

見出しの括弧内は集計スクリプト（`mine_openreview.py`）での move 名。

### 2.1 宛名（GR の 15%）

| 典型文 | 件数 | メモ |
| --- | --- | --- |
| Dear Reviewers, | 1,376 | 最も多い。迷ったらこれ |
| Dear Reviewers and AC(s), / Dear AC(s) and Reviewers, | 約 550（Area Chair(s) 表記を含む） | AC にも読んでほしいとき |
| Dear Reviewers, Area Chairs, and Program Chairs, | 28 | 丁寧だが長い |
| To all reviewers: | 74 | 見出し風 |

宛名は無くてもよい（85% は付けない）。タイトル欄が "General Response" なら宛名は省いてよい。

### 2.2 謝辞（gratitude：GR 冒頭の 88%）

| 典型文 | 頻度 | 採択 |
| --- | --- | --- |
| We thank all (the) reviewers for their [adj] [feedback \| comments]. | 〔GR 18%〕 | 48% |
| We sincerely thank all reviewers for their [adj] feedback. | 〔GR 7%〕 | 53% |
| We would like to thank the reviewers for their [adj] comments. | 〔GR 10%〕 | 45% |
| We thank the reviewers for their time and effort in reviewing our paper. | 〔GR 6%〕 | 46% |
| We are grateful to the reviewers for their [adj] feedback. | 〔GR 3%〕 | 53% |
| We sincerely appreciate the reviewers' [adj] comments. | 〔GR 5%〕 | 43% |

形容詞（[adj]）の頻度：*valuable* 8%、*insightful* 6%、*thoughtful* 5%、*constructive* 5%。採択との関係は *thoughtful* 58%、*insightful* 53%、*constructive* 46%、*valuable* 47%。*comments and suggestions* の組み合わせは 35% と低め。

使い方：
- 形容詞は 1 つ、多くて 2 つ（"thoughtful and constructive"）。3 つ以上重ねない。
- 謝辞は 1 文で終え、2 文目から中身（強み・変更）に入る。
- 査読者全員に向けた GR では "thank you for your" より "thank the reviewers for their" が普通（"you" で始まる GR は採択 33% と低いが、これは 1 人宛ての返信が混ざっているためでもある）。

### 2.3 査読者が認めた強みの確認（strengths_ack：GR の 32%、冒頭では 27%）

〔冒頭に強みの確認がある GR：採択 54%（無い GR 41%）、上昇 [ICLR 59% vs 48%]、NeurIPS では差なし（72% vs 73%）〕。ただし好意的な査読を受けた論文ほど書けるので、交絡が強い。

| 典型文 | 頻度 | 採択 |
| --- | --- | --- |
| We are encouraged that the reviewers found [our method novel] ([IDs]) and [our experiments extensive] ([IDs]). | "we are encouraged" 778 件 | 60% |
| We are glad that the reviewers found [the paper well-written and easy to follow]. | "we are glad" 762 件 | 55% |
| We are pleased that the reviewers recognized [the importance of the problem]. | "we are pleased" 602 件 | 50% |
| Reviewers found our [work \| paper] [novel / interesting] ([IDs]). | 365 件 | 48% |
| We are delighted that [all reviewers] [acknowledged / appreciated] [X]. | 283 件 | 56% |
| In particular, reviewers highlighted [X] ([IDs]), [Y] ([IDs]), and [Z] ([IDs]). | ID 列挙の型 180 件以上 | 60% 前後 |

使い方：
- 強みは査読者が実際に書いた語を 2–6 語で使い、査読者 ID を括弧で付ける（"novel" (R1, R3)）。ID 付きの型は採択 60% 前後。
- 褒め言葉を引用符で引くのは GR の 11%（採択 54%）。引用は短く、1 項目 1–4 語。
- 全員が否定的な場合は無理に書かない。1 人でも強みを挙げていれば、その 1 点だけ短く書く。

### 2.4 改訂の知らせと変更箇所の示し方（revision_summary：GR の 46%）

| 典型文 | 頻度 | 採択 |
| --- | --- | --- |
| We have uploaded a revised version of the paper, with changes highlighted in blue. | "we have uploaded" 622 件、"highlighted in blue" 841 件 | 50% / 57% |
| We have revised the manuscript according to the reviewers' suggestions; all changes are highlighted in [blue]. | "we have revised" 891 件 | 50% |
| We have updated the paper to incorporate the reviewers' feedback. | "we have updated" 954 件 | 44% |
| Changes in the revised manuscript are marked in [blue]. | "marked in blue" 238 件 | 58% |

- 色は青が最多（"highlighted in blue" 841 件、"in red" 329 件）。色分けを書く GR は採択 53%（書かない GR 41%）、上昇 [ICLR 60% vs 48%]。
- 改訂 PDF を出せない会議では「改訂しました」ではなく **"We will incorporate [X] into the final version."**（"we will include" 150 件）と書く。

### 2.5 変更点の列挙（change_list：GR の 20%）

| 典型文 | 頻度 | 採択 |
| --- | --- | --- |
| We have made the following changes: | 387 件 | 48% |
| Below, we summarize the main changes. / We summarize the major changes below. | "summarize the main" 87 件、"summarize the major" 123 件 | 76%（n 少）/ 62%（n 少） |
| In response to the reviewers' comments, we have made the following revisions: | "made the following revisions" 85 件 | 67%（n 少） |
| The main changes in the revised version are: | — | — |

各項目は「何を — どこに — 誰の指摘か」の順で 1 行にする：
`- Added [comparison with X] on [datasets] (Table [N]; [IDs]).`
`- Clarified [assumption Y] (Sec. [N]; [IDs]).`

### 2.6 追加実験（new_experiments：GR の 52%）

〔追加実験に触れる GR：採択 48%（触れない GR 41%）、上昇 [ICLR 56% vs 45%]、[NeurIPS 76% vs 68%]。下表の「上昇」は会議を混ぜた値〕

| 典型文 | 頻度 | 採択 / 上昇 |
| --- | --- | --- |
| We conducted additional experiments on [X] to address [concern]. | "we conducted additional experiments" 247 件 | 66% / 68% |
| We have conducted additional experiments [as suggested by Reviewer [ID]]. | 207 件 / "suggested by reviewer" 152 件 | 46% / 70% |
| We provide additional experimental results on [X] in [Table N / Appendix N]. | "additional experimental results" 404 件 | 56% / 71% |
| These new results show that [finding — ユーザーの数値で]. | "these new results" 119 件 | 62% / 65% |
| We have added [an ablation study on X] (Appendix [N]). | "additional ablation studies" 128 件 | 53% / 66% |

- 結果の数値は必ずユーザーの事実で埋める。無ければ `[TODO: 結果]`。
- 「誰の提案で行ったか」を書く型（"as suggested by Reviewer [ID]"）は、提案した査読者が自分の指摘への対応を見つけやすい。

### 2.7 共通の懸念の導入（common_concerns：GR の 20%）

| 典型文 | 頻度 | 採択 |
| --- | --- | --- |
| Below, we address the [common \| main] concerns raised by multiple reviewers. | "raised by multiple reviewers" 189 件 | 60% |
| We first address some common questions, and then respond to each reviewer individually. | "address some common questions" 66 件 | 56%（n 少） |
| Here we address the questions shared by several reviewers. | "here we address" 94 件 | 64%（n 少） |
| Several reviewers asked about [X] ([IDs]). | "several reviewers asked" 47 件 | 46%（n 少） |

見出しの付け方：`**G1. [懸念の名前]** ([IDs])` または `**[懸念の名前] ([IDs]).**`。本文は「結論 1 文 → 根拠（数値・節番号） → 改訂した箇所」の順。

注意：共通の懸念の導入句そのものは採択と結びつかない（共通の懸念に触れる GR 全体では採択 39%、触れない GR 45%）。厳しい査読ほど共通の懸念が多いため。**導入句より中身**。

### 2.8 貢献の再確認・誤解への説明（contribution_restate / clarify_misunderstanding：GR の 26% / 28%）

〔"We would like to clarify" 採択 24%、"we would like to emphasize" 34%、"our main contribution(s)" 28%（GR 全体 44%）〕。査読者が貢献を理解していないとき、つまり評価が低いときに使われやすい句なので、採択率が低く出る。使うなら、

- 主張を言い直すだけでなく、**根拠（どの実験・どの定理・どの節）を同じ文で示す**。
- 査読者の誤解を相手のせいにしない。

| 避けたい | 言い換え |
| --- | --- |
| The reviewers misunderstood our contribution. | We realize that our contribution was not stated clearly enough in the original submission. We have revised the introduction (Sec. 1) to state it explicitly: [1 文で貢献]. |
| We would like to emphasize again that our method is novel. | To clarify the novelty: unlike [prior work], our method [具体的な違い] (Sec. [N]). |
| As clearly stated in the paper, ... | As described in Sec. [N], ...; we have made this more explicit in the revision. |

〔"apologize for any (confusion)" は 41 件。謝罪は 1 回、具体的に〕

### 2.9 個別返信への案内（pointer_individual：GR の 23%）

| 典型文 | 頻度 | 採択 |
| --- | --- | --- |
| We respond to each reviewer's comments individually below. | "respond to each reviewer" 147 件 | 63%（n 少） |
| We have provided detailed responses to each reviewer below. | "detailed responses to each reviewer" 129 件 | 54%（n 少） |
| Please see our individual responses for the remaining points. | "our individual responses" 206 件 | 61% |

### 2.10 結び（closing_hope / further_questions）

| 典型文 | 頻度 | 採択 |
| --- | --- | --- |
| We hope our responses address the reviewers' concerns. | "address the reviewers' concerns" 117 件 | 77%（n 少） |
| We hope that these revisions [address your concerns \| improve the clarity of the paper]. | "we hope these revisions" 82 件 | 50%（n 少） |
| Please let us know if you have any further questions. | "please let us know if" 394 件 | 51% |
| We are happy to [answer any further questions \| address any remaining concerns]. | "happy to address" 198 件 | 55% |
| We look forward to the discussion. | "we look forward" 461 件 | 45% |
| Thank you again for your time and feedback. | "thank you again" 342 件 | — |

〔結びで「質問があれば答える」と書く GR：採択 53%（書かない GR 42%）。GR のどこかに書く場合の上昇 [ICLR 58% vs 48%]〕。結びは 1–2 文。

### 2.11 スコアへの言及（score_request：GR の 3%、個別返信の結びの 2%）

GR でスコアに触れる人は少ない。個別返信の結びでスコアに触れた返信は、その査読者が「上げた」と書く割合が高い（[ICLR 21% vs 18%]、[NeurIPS 41% vs 26%]）。ただし、査読者が前向きな反応を見せたあとに書かれることが多いための見かけの差を含み、スコアに触れること自体の効果とは言えない。GR で "reconsider their scores" のように全員に強く求める型は、件数は少ない（24 件）が採択 17%・上昇 46% と低い。

使うなら、**個別返信の最後に 1 回、条件つきで**：

- If our responses have addressed your concerns, we would be grateful if you would consider updating your assessment.
- If any concerns remain, please let us know, and we will do our best to address them before the discussion period ends.

避ける：*We kindly ask the reviewers to raise their scores.* / *We believe our paper deserves a higher score.*

### 2.12 まだ終わっていない対応（実験が期間内に間に合わない場合）

この節と 2.13・2.14 の割合は、著者が何か返信した論文 35,151 件のうち、その句を著者の返信のどこかに含む論文の割合（GR に限らない）。

| 状況 | 典型文 | 頻度 |
| --- | --- | --- |
| 実行中 | We are currently running [the experiments on X] and will post the results {in this thread \| as soon as they are available}. | "we are currently running" 1.1% |
| 一部だけ終わった | We report preliminary results on [subset] below; the full results will be {added to the revision \| reported in this thread}. | "preliminary results" 2.9% |
| 期間内に無理 | We were not able to complete [X] within the rebuttal period {due to its computational cost}. | "due to time constraints" 3.3%、"within the rebuttal period" 0.5% |
| 最終版で足す | We will include [X] in the final version. | "we will include" 23.8%、"in the final version" 15.2%、"camera-ready version" 7.6% |

- 「最終版で足す」は、**ユーザーが実施すると決めたときだけ**書く。決まっていなければ `[TODO: 最終版で追加すると約束するか決める]` にする。
- 理由だけを書いて終えない（"Due to limited time, we could not ..." で止めない）。代わりに出せるもの（一部の結果、計画、既存の結果からの見込み）を 1 つ添える。
- 結果が出たら同じスレッドに追記する。GR に「実行中」と書いた項目は、結果が出たら GR も更新する。

### 2.13 標準的な仮定・設定であることの説明

| 典型文 | 頻度 |
| --- | --- |
| This assumption is standard in the analysis of [method family] (e.g., [cite], [cite]). | "standard assumption" 1.0%、"is standard in" 1.3%、"common assumption" 1.1% |
| Following prior work [cite], we adopt [setting]. | "following prior work / previous work" 計 1.1% |
| [Setting] is widely used in [area] (e.g., [cite]). | "widely used in" 4.5%、"commonly used in" 3.8%、"widely adopted" 3.1% |
| We agree that relaxing [assumption] is an interesting direction; we have added this to the limitations (Sec. [N]). | "we agree that" 40.9%（あらゆる用途を含む）、"limitation of our" 3.0% |

- 「標準的」と書くときは、**引用する先行研究が本当にその仮定を使っているかを確かめる**（`[TODO: 引用の確認]`）。誤っていると、反論の根拠ごと信頼を失う。
- 「標準的だから問題ない」で終えず、仮定が成り立たないときに何が起きるか（実験で確かめたか、限界として書いたか）を 1 文添える。

### 2.14 個別返信の本文でよく使う定型句

| 働き | 典型文 | 頻度 |
| --- | --- | --- |
| 指摘への感謝（項目ごと） | Thank you for pointing this out. / Thank you for raising this point. | "thank you for pointing" 22.9%、"thank you for raising" 9.2% |
| 同意 | We agree with the reviewer that [X]. | "we agree with the reviewer" 13.6% |
| 限界を認める | We acknowledge that [limitation]; we have added a discussion in Sec. [N]. | "we acknowledge" 27.5% |
| 丁寧な反論 | We respectfully disagree with [the claim that X], because [根拠]. | "we respectfully disagree" 7.4% |
| 結果を指す | As shown in Table [N] (revised), [finding]. | "as shown in table" 12.6%、"as shown in figure" 10.8% |
| 誤りの修正 | We have corrected [the typo in Eq. N]. / We will fix [X] in the revision. | "we have corrected" 6.3%、"we have fixed" 5.6%、"we will fix" 5.8% |
| 範囲外 | [X] is beyond the scope of this paper, but we have added a brief discussion in Sec. [N]. | "beyond the scope" 9.3%、"out of the scope" 2.8% |
| 今後の課題 | We leave [X] for future work. | "future work" 45.6%（あらゆる用途を含む）、"we leave" 8.9% |

- 反論（"respectfully disagree"）は、同じ文か次の文で根拠（数値・定理・節番号）を示す。根拠のない反論は書かない。
- "beyond the scope" と "future work" は便利だが、査読者が中心的だと考えている懸念に使うと、答えていないと受け取られる。中心的な懸念には一部でも答えを示す。

## 3. 個別返信の書き出しと結び

### 書き出し（最初の 1–2 文）

| 典型文 | 頻度 | 上昇 |
| --- | --- | --- |
| We thank the reviewer for their [thoughtful \| detailed] review. | "we thank the reviewer for their" 〔返信 7%〕 | 21% |
| Thank you for your [valuable \| constructive \| thoughtful] feedback. | "thank you for your" 〔返信 21%〕 | 19% |
| We sincerely appreciate your [detailed] comments. | 〔返信 2%〕 | 24% |
| We thank Reviewer [ID] for [the careful reading / the insightful questions]. | 〔返信 3%〕 | 21% |
| We are glad that you found [strength the reviewer named]. | "we are glad" 〔返信 2%〕 | 21% |
| Below, we address your [comments \| concerns] point by point. | "below we address" 〔返信 2%〕 | 22% |

- 表の「上昇」は会議を混ぜた値（個別返信全体 20%）。
- "Thank you for your comments." / "Thank you for your review." だけの書き出しは上昇 14% / 17% とやや低い。何に感謝するのかを 1 語足す（*careful reading*, *questions about X*）。
- 個別返信で強みの確認から入る返信は上昇が低い（[ICLR 17% vs 18%]、[NeurIPS 19% vs 28%]）。もともと好意的でスコアを上げる余地の少ない査読者に書かれやすいため。好意的な査読者には強みの確認を 1 文、批判的な査読者には感謝 1 文ですぐ本題、が無難。
- 書き出しの定型を全員に同じ文で使わない。

### 結び（最後の 1–2 文）

| 典型文 | 頻度 | 上昇 |
| --- | --- | --- |
| Please let us know if you have any further questions; we would be happy to address them. | "please let us know if" 〔返信 2%〕 | 22% |
| We hope our responses have addressed your concerns. | "we hope our" 〔返信 1%〕 | 23% |
| We will add [X] to the final version. | "we will add" 〔返信 2%〕 | 18% |
| Thank you again for your [time and] constructive feedback. | "thank you again" 〔返信 1%〕 | 19% |

結びに「疑問があれば答える」または「回答が役立つことを願う」を書いた返信は上昇 22% 前後（書かない返信 20%）。差は小さいので、1 文で十分。

## 4. 期間中の追加メッセージ

### 4.1 返信のお願い（リマインド）

個別スレッドでのリマインドは 8,901 件、全員向けは 1,268 件。期限の 2–3 日前に 1 回が典型。

```
Dear Reviewer [ID],
Thank you again for your time and feedback. As the author–reviewer discussion period {is coming to an end | ends on [date]}, we would greatly appreciate it if you could let us know whether our responses have addressed your concerns. If any questions remain, we would be happy to clarify them.
```

（核の句："thank you again for your" 784 件、"discussion period ends" 733 件、"our responses have" 730 件、"have addressed your concerns" 674 件、"appreciate it if you could" 668 件、"period is coming / approaching" 約 1,200 件）

避ける：同じ査読者に何度も送る、スコアの変更を求める、査読者の反応の遅さを責める。

### 4.2 スコアを上げた査読者へのお礼（15,011 件）

```
Thank you for {raising | increasing} your score and for your [thoughtful] feedback. We are glad that our responses addressed your concerns. We will incorporate [the new results / the clarifications] into the final version.
```

（"thank you for your" 3,218 件、"raising the / your score" 計 1,479 件、"addressed your concerns" 730 件、"recognition of our work" 514 件、"your positive feedback" 511 件）

### 4.3 スコアが据え置かれた・否定的な追加コメントへの返答

データでは型が定まっていない（個別の議論になる）。次の順が無難：感謝 1 文 → 残った懸念を 1 文で言い直して確認 → 追加の根拠 → それでも残る違いは率直に認める。

```
Thank you for the follow-up. If we understand correctly, your remaining concern is [X]. [根拠 / 追加結果]. We agree that [限界] remains, and we have added this to the limitations section (Sec. [N]).
```

### 4.4 AC 向けの議論の要約（726 件）

議論期間の終わりに、フォーラム直下に置く。宛名は "Dear AC(s)," / "Dear Area Chairs and Reviewers,"。

```
Dear Area Chair(s),
We thank all reviewers for their engagement during the discussion. We briefly summarize the discussion:
- Strengths acknowledged: [X] ([IDs]), [Y] ([IDs]).
- Concerns addressed: [concern] → [what we did] ([ID] {raised the score | confirmed that the concern was addressed}).
- Remaining points: [concern] ([ID]); [our position in one sentence].
We thank the AC and the reviewers for their time.
```

（"we would like to express our" 44 件、"during the rebuttal" 45 件。査読者の発言は正確に要約し、言っていないことを書かない）

## 5. 避けたい表現と言い換え

| 避けたい | 理由 | 言い換え |
| --- | --- | --- |
| We deeply appreciate the extremely insightful, valuable, and constructive comments. | 形容詞の重ねすぎ | We thank the reviewers for their constructive comments. |
| We apologize for ... （何度も） | 弱く見える | We have clarified ... (Sec. N). |
| The reviewer is wrong / misunderstood. | 対立的 | We realize this was unclear; we have clarified ... |
| As we clearly stated ... | 相手を責める | As described in Sec. N ... |
| We will definitely add all experiments. | できない約束 | We will add [具体的な 1 つ] to the final version. |
| We kindly ask you to raise your score. | 圧力 | If our responses have addressed your concerns, we would be grateful if you would consider updating your assessment. |
| Due to limited time, we could not ... （理由だけ） | 言い訳に見える | We were not able to complete [X] within the rebuttal period. [出せるもの：一部の結果・計画]。（"we will include it in the final version" は、ユーザーが実施を決めたときだけ足す。2.12 参照） |
