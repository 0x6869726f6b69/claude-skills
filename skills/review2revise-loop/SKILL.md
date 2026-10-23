---
name: review2revise-loop
description: Review2Revise-loop。査読駆動で論文を自律的に改善する closed-loop。`/review2revise-loop 投稿先の雑誌名・会議名 [論文のパス]` で起動し、投稿先の aims & scope・投稿規定・査読基準を Web で調べたうえで、(1) deep-review-modoki による複数の専門査読エージェントの厳密な査読と投稿先レビュー、(2) 文章・構成の自動改訂、(3) Experiment Agent による追加分析・追加実験の事前登録・実行と Figure/Table/本文への反映、(4) 再査読を、Major な指摘がなくなるか改善が収束するまで反復する。研究課題・中心的アイデア・主要手法（scientific core）は維持し、それを変える必要が出たら自動では変えず人間に確認する。各 iteration の査読コメント・対応・追加実験・変更箇所・未解決事項を記録し、捏造の禁止・数値の出所検査・健全性監査によって、査読 AI の満足より科学的妥当性・再現性・主張と証拠の整合を優先する。「投稿先に合わせて論文を仕上げて」「査読→改訂→再査読を自動で回して」「追加実験も含めて採択レベルまで改善して」「revise and resubmit を自動化して」などと頼まれたら、スキル名が出ていなくても使うこと。Use for autonomous, venue-aware review→revise→re-review manuscript refinement.
---

# Review2Revise-loop：査読駆動の自律的な論文改善ループ

入力された論文を、指定された投稿先の基準で査読し、その指摘に沿って原稿を改訂し、必要なら追加分析・追加実験を行って結果を反映し、改訂版を再び査読する。これを Major な指摘がなくなるか、改善が収束するまで繰り返す。

```
投稿先の調査 ─┐
scientific core ┴→ ┌─ A 査読（deep-review-modoki）＋ B 投稿先レビュー ─┐
                    │                                                    ↓
                    │   I 記録・次の版へ ← H 健全性監査 ← G ビルド・検査 ← C 仕分け・収束判定 ─→ 終了
                    │                                       ↑                 ↓
                    └──────────────── F 反映 ← E 改訂 ＋ 実験（並列）← D 人間への確認（L3 のみ）
```

**最優先の原則**：査読 AI を満足させることを目的にしない。指摘数を減らすことより、科学的妥当性・再現性・主張と証拠の整合を常に優先する。そのために、査読者は毎回まっさらな目で紙面だけを読み（回答書を見ない）、実験は事前登録してから実行し、追加された数値と文献は出所を機械的に調べ、改訂は毎回独立の監査担当が点検する。正しくない指摘には根拠を示して反論してよい。

ユーザーに最後に渡すもの：
- 改訂版の PDF とソース（最も評価の良かった版）、各反復の版
- 各反復の記録 `iterations/itNN/iteration_log.md`：査読コメント・対応内容・追加実験・論文の変更箇所・未解決事項
- 課題台帳 `ledger.md`、改善の推移 `progress.md`、response letter の下書き `response_letter.md`
- 人間の判断が必要な事項 `human_decisions.md`、著者の作業が必要な事項 `author_todo.md`
- 最終レポート `final_report.md`

以下、`<skill_dir>` はこの SKILL.md があるディレクトリ、`<ws>` は作業フォルダ、`r2r.py` は `python <skill_dir>/scripts/r2r.py` の略（`build_pdf.py`・`pdf_tools.py`・`snapshot.py` も同じ場所）。`python` が無ければ `python3` を使う。`NN` は反復の番号（01, 02, …）。

## 起動のしかた

```
/review2revise-loop <投稿先> [論文のパス] [オプション]
```

例：
- `/review2revise-loop Nature Communications ./paper/manuscript.pdf`
- `/review2revise-loop NeurIPS 2026 ./fedopt/`（LaTeX ソースのフォルダ）
- `/review2revise-loop IEEE Transactions on Medical Imaging paper.zip code=./repo data=./data iter=5 hours=6`

引数の読み方：存在するファイル・フォルダのパスは論文（`code=` / `data=` を付けたものは実験用のコード・データ）、`key=value` はオプション、残りの語が投稿先の名前。オプションは `iter=`（最大反復数、既定 5）、`hours=`（時間の上限。`hours=1.5` のように小数も可。「90分」「6時間で」のような依頼文の表現も読み取る）、`depth=`（quick / standard / deep）、`experiments=`（auto / design / off）、`lang=`（記録の言語 ja / en）。**反復数と時間の両方を指定したら、先に達した方で止まる**。引数が無く、依頼文に投稿先や論文が書かれていればそれを使う。

**対象は著者自身の原稿**。ユーザーが査読者として他人の原稿を扱おうとしている様子なら、このスキルは著者向けであること、多くの投稿先が査読中の原稿を AI ツールに入力することを禁じていることを伝えて止まる。

## 0. 最初に：設定を確認する

1. 論文と投稿先を特定する。無ければ聞く。論文の形式を確かめる：LaTeX ソース（フォルダ・.zip・arXiv の .tar.gz・.tex）が最良。PDF だけなら再構成が要る（§1）。.docx / .md も扱える。
2. 残りの設定を、AskUserQuestion などの質問ツールで**一度に**聞く（無ければチャットで聞いて待つ）。起動の引数で分かっている項目は聞かない。「任せる」「すぐやって」なら推奨の値で始める。
   - 質問1「反復の上限」：`最大5反復（推奨）` / `最大3反復` / `最大2反復（お試し）`（その他で任意の回数）
   - 質問2「時間の上限」（質問1と両方かかり、先に達した方で止まる）：`時間制限なし` / `2時間` / `4時間` / `8時間`（その他で「90分」「6時間」なども可）。説明に、Standard の深さで1反復がおよそ1時間であることを添える。
   - 質問3「査読の深さ」（deep-review-modoki に渡す。全反復で同じにする）：`Standard（推奨・1回 20〜45分）` / `Quick（1回 10〜20分）` / `Deep（1回 45〜90分）`
   - 質問4「追加実験」：`自動で実行（コード・データあり）` / `設計のみ（実行は著者）` / `実験なし（文章と既存データの分析のみ）`。コード・データのパスが分かっていれば「自動で実行」を推奨にし、無ければ「設計のみ」を推奨にする。自動で実行を選び、パスが未指定なら続けてチャットで聞く。
3. 作業フォルダを作る。答えを受けた時点から時計が動く（セットアップの時間も予算に含まれる）。
   ```bash
   python <skill_dir>/scripts/r2r.py init <論文のパス> --venue "<投稿先>" --max-iter 5 --hours 4 --depth standard --experiments design [--code <dir>] [--data <dir>] --lang ja
   ```
   時間制限なしなら `--hours` を付けない。90分なら `--hours 1.5`。作業フォルダは `<論文のあるフォルダ>/<論文名>_r2r/`。出力の `deep-review-modoki:` が `NOT FOUND` なら止まり、deep-review-modoki をこのスキルと同じ場所（例：`~/.claude/skills/`）に入れるようユーザーに頼む。査読はそのスキルで行う。
4. スリープ防止のツール（Claude デスクトップの keep-awake など）があれば、時間の上限ぶん（制限なしなら長めに）有効にする。長いループの途中で PC が眠ると止まる。
5. ユーザーへ2〜3行で伝える：作業フォルダ、止まる条件（例：「最大5反復、または 18:30 のどちらか早い方」。締め切りの時刻は init の出力から）、以後は自律的に回すこと、人間に聞くのは「セットアップ時の core の確認」と「core に触れる変更が必要になったとき」だけであること、いつでも中断でき、途中で上限を変えられること（§4）。

## 1. セットアップ

```
<ws>/
├── config.json  state.json  ledger.json    設定・時計・課題台帳（r2r.py が管理）
├── original/          受け取った原稿。変更しない
├── src/               編集用ソース（改訂はここだけで行う）
├── venue/             venue_profile.json / .md（投稿先の調査結果）、review_focus.txt
├── core/              core.json / core.md（scientific core）
├── experiments/E01_<slug>/   protocol.md manifest.json scripts/ outputs/ logs/ report.md
├── iterations/itNN/
│   ├── input/         この反復で査読する版（paper.pdf paper.txt src/）
│   ├── review/        deep-review-modoki の作業フォルダ（findings.json, report.html …）
│   ├── venue_review.json  triage.json  changes.json  provenance.md  audit.json
│   ├── output/        改訂した版（paper.pdf paper.txt src/ changes.diff）→ 次の反復の input
│   └── iteration_log.md
├── ledger.md  progress.md  response_letter.md  human_decisions.md  author_todo.md
└── final_report.md  <論文名>_revised.pdf  final_src/
```

`r2r.py start <ws> --phase setup` で始め、最後に `end` する。まず最初の反復で査読する版（`iterations/it01/input/`）を作る（数分）。投稿先の調査と core の書き出しがこれを読む。

- **LaTeX ソースがある**：`<ws>/src/` にコピー・展開する（`\documentclass` と `\begin{document}` を含むファイルがメイン）。ビルドして通ることを確かめ、`r2r.py baseline` に渡す：
  ```bash
  python <skill_dir>/scripts/build_pdf.py <ws>/src/<main>.tex --out <ws>/work/baseline.pdf
  python <skill_dir>/scripts/r2r.py baseline <ws> --pdf <ws>/work/baseline.pdf --main <main>.tex
  ```
- **PDF だけ**：`r2r.py baseline <ws>`（original の PDF を使う）。編集用のソースは下の (a) で再構成する。
- **.docx**：pandoc があれば `pandoc <file>.docx -o <ws>/src/main.md --extract-media=<ws>/src/media` で Markdown にして編集し、最後に `pandoc main.md -o <name>_revised.docx --reference-doc=<元の.docx>` で戻す（書式は簡略化されることをユーザーに伝える）。PDF は `build_pdf.py <ws>/src/main.md --out <ws>/work/baseline.pdf` で作り、`baseline --pdf … --main main.md`。pandoc が無ければ docx スキルで扱うか、LaTeX / Markdown での提出をユーザーに相談する。
- **.md / .html**：そのまま `<ws>/src/` へ置き、LaTeX と同じ手順で baseline を作る。

続けて次を**並列に**進める（サブエージェントが使えるなら同時に起動する）。

**(a) PDF からのソースの再構成**（PDF だけのときのみ）：`<skill_dir>/references/pdf_to_latex.md` の手順で LaTeX ソースを `<ws>/src/` に再構成する（10ページで20〜40分）。サブエージェントに任せてよい。最初の反復は元の PDF を査読するので、再構成は反復1の査読と並行してよい（反復1の改訂までに終わらせる）。終わったら `r2r.py baseline <ws> --src-only --main main.tex` を実行する（改訂の差分の基準になる）。

**(b) 投稿先を調べる**（`--phase venue`）。下の依頼文でサブエージェントを起動する。

```
あなたは Review2Revise-loop の「投稿先調査担当」です。まず <skill_dir>/references/venue_research.md を最後まで読み、
手順と出力形式に従ってください。

- 投稿先: <ユーザーが指定した名前>（年度・種別の指定: <あれば。無ければ「なし」>）
- 原稿（適合判断のためだけに読む。検索クエリに原稿の内容を入れない）: <ws>/iterations/it01/input/paper.txt
- 今日の日付: <YYYY-MM-DD>
- 出力: <ws>/venue/venue_profile.json, <ws>/venue/venue_profile.md
```

終わったら、`venue_profile.json` の `review_focus` を `<ws>/venue/review_focus.txt` に保存する（全反復で同じ焦点を deep-review-modoki に渡すため。途中で変えない）。

**(c) scientific core を書き出す**（`--phase core`）。`<skill_dir>/references/scientific_core.md` §1 に従い、元の原稿から `core/core.json` と `core/core.md` を書く。自分で行っても、サブエージェントに任せてもよい。

**(d) 人間に確認する**（セットアップでの唯一の確認）。(b)(c) が終わったら、質問ツールで一度に聞く：
- 質問1「scientific core」：core.md の要点（研究課題・中心的アイデア・主要手法・主要な主張を各1行）を示し、`この理解で正しい` / `修正する`（その他で修正内容）。修正を受けたら core.json を直す。答えたら `confirmed_by_human: true`。
- 質問2（scope fit が `borderline` / `out_of_scope` のときだけ）「投稿先との適合」：理由と代わりの候補を示し、`このまま進める（core は変えない）` / `投稿先を変える`（その他で新しい投稿先）/ `中止`。投稿先を変えるなら (b) をやり直す。
- 投稿先の生成 AI 利用方針に開示義務などがあれば、一言添える。
- 「任せる」と言われていた場合も、この確認は行う（core を取り違えたまま回すと、ループ全体が誤った方向に進む）。返答が得られない環境では、`confirmed_by_human: false` のまま進め、最終レポートにそう書く。

## 2. ループ：反復 NN

### 役割分担と、その理由

- **メイン（あなた）はオーケストレーターに徹する**：起動・検証・スクリプトの実行・記録。候補ファイルや査読の全文を自分の文脈に読み込まず、スクリプトの出力と各担当の短い返答で判断する。数時間のループでも文脈が膨らまず、状態はすべてファイルに残る。
- **査読は毎回まっさらな担当**：deep-review-modoki と投稿先レビュー担当は、紙面（PDF）だけを読む。改訂の意図・回答書・課題台帳は渡さない（前回の指摘の一覧だけは、解決したかの判定のために渡す）。自分で改訂した文脈のまま自己採点すると甘くなる。
- **改訂・実験・反映・監査も別の担当**：書いた本人に監査させない。
- サブエージェントが使えない環境では全部を自分で順に行う。その場合も、各担当のガイドを読み直し、そのガイドの観点だけで作業し、査読と監査の前には紙面（paper.txt とページ画像）を読み直して記憶に頼らない。

### A. 査読（deep-review-modoki）

1. `r2r.py start <ws> --it NN --phase review`
2. 同時に B の投稿先レビュー担当をバックグラウンドで起動する。
3. **Skill ツールで deep-review-modoki を起動する**（見つからなければ `config.json` の `deep_review_dir` にある SKILL.md を Read で読み、その手順に従う）。引数として次を渡す：

```
Review2Revise-loop の反復 NN の査読として実行してください。ユーザーへの質問はしません。
- 入力: <ws>/iterations/itNN/input/paper.pdf
- 作業フォルダ: <ws>/iterations/itNN/review（init に --ws で指定。--force は付けない）
- 深さ: <config.json の depth>   言語: <lang>
- 焦点: <venue/review_focus.txt の文>
- 投稿先: <venue_profile.json の name>
- 前回の findings.json: <ws>/iterations/it(NN-1)/review/findings.json（反復1は「なし」）。統合担当に渡し previous を書かせる
- §7 のユーザーへの報告は件数の一行だけ。次の一手の提案はしない
```

4. deep-review-modoki の手順（取り込み → セグメント分割 → 並列の検証 → 照合 → 反証検証 → 統合 → render）を最後まで行い、`iterations/itNN/review/findings.json` と `report.html` を得る。
5. `r2r.py end <ws> --it NN --phase review`

深さを反復の途中で変えない。深さが変わると指摘の数の意味が変わり、収束の判定が比べられなくなる。

### B. 投稿先レビュー（A と並列）

`--phase venue_review` で時間を記録する。

```
あなたは Review2Revise-loop の「投稿先レビュー担当」です。まず <skill_dir>/references/venue_reviewer.md を最後まで読み、
観点と出力形式に従ってください。

- 査読対象: <ws>/iterations/itNN/input/paper.pdf（抽出テキスト: paper.txt）
- 投稿先の情報: <ws>/venue/venue_profile.json, venue_profile.md
- 規定の機械的な確認: python <skill_dir>/scripts/r2r.py venue-check <ws> --it NN --which input を実行して使う
- 前回の投稿先レビュー: <ws>/iterations/it(NN-1)/venue_review.json（反復1は「なし」）
- 反復: NN   言語: <lang>
- 出力: <ws>/iterations/itNN/venue_review.json

評価の根拠は、この PDF に書かれていることだけです。改訂者の意図や回答書は渡していません。
[AUTHOR TODO] と書かれた箇所は約束にすぎないので、未解決として扱ってください。
```

### C. 仕分けと収束の判定

1. `r2r.py start <ws> --it NN --phase triage` → 編集担当を起動する：

```
あなたは Review2Revise-loop の「編集担当」です。まず <skill_dir>/references/editor_triage.md と
<skill_dir>/references/scientific_core.md を最後まで読み、手順と出力形式に従ってください。

- 今回の指摘: <ws>/iterations/itNN/review/findings.json, <ws>/iterations/itNN/venue_review.json
- 課題台帳: <ws>/ledger.json（人が読む版: <ws>/ledger.md）
- 守るもの: <ws>/core/core.json   投稿先: <ws>/venue/venue_profile.json   設定: <ws>/config.json
- 査読した版: <ws>/iterations/itNN/input/（paper.txt, src/）、ページ画像: <ws>/iterations/itNN/review/pages/
- 前回の記録: <ws>/iterations/it(NN-1)/iteration_log.md（反復1は「なし」）
- 出力: <ws>/iterations/itNN/triage.json
```

2. `r2r.py ingest <ws> --it NN`。`TRIAGE INVALID` なら、エラーを編集担当に渡して直させ（SendMessage。無ければ同じ依頼で起動し直す）、通るまで繰り返す。ingest は新しい課題に ID（I001…）を振り、`triage.json` に書き戻す。
3. `r2r.py end ... --phase triage` → `r2r.py status <ws>`。経過時間と収束の判定は、必ずこの出力に従う（経過時間を推測しない）。
   - `NEXT: STOP` → 理由が `blocked` で `ASK HUMAN` があるなら、先に D を行い、判断を記録してから `status` を再実行する（承認で動ける課題が生まれれば `CONTINUE` になる）。それ以外の STOP は §3 へ。判定は査読の直後に行うので、最終版は必ず査読済みになる。
   - `REGRESSION` が出たら、前回の改訂が新しい Major を生んだ可能性がある。編集担当の計画で、その Major を最優先にしているか確かめる。
   - `NEXT: CONTINUE` → E へ。

収束の判定（`r2r.py status` が計算する）：
| 判定 | 条件 |
|---|---|
| 収束（Major なし） | 今回の査読（deep-review ＋ 投稿先レビュー）に Major が無い |
| 行き詰まり（blocked） | 残る Major がすべて、人間の判断待ち・著者の作業待ち・反論中のいずれかで、ループが自分で動かせるものが無い |
| 停滞（plateau） | 2回続けて、Major が減らず、かつ W（= 3×Major + Minor）が 10% 以上減っていない |
| 反復の上限 | 反復数が上限に達した |
| 時間の上限 | 残り時間では「改訂（最低20分）＋ビルド・監査（約20分）＋次の査読（これまでの査読の平均時間。未計測なら深さごとの目安）＋終了処理（約10分）」が収まらない |

時間の上限があるとき、`status` は `time plan:` の行に3つの時刻を出す。`revise by`（改訂を終える時刻）、`experiments by`（実験を終える時刻。反映の時間を残す）、`start the next review by`（次の査読を始められる最後の時刻）。これらは次の査読と終了処理の時間を残すように計算されているので、各担当に締め切りとして渡す。`TIME: past revise-by` が出たら新しい修正・実験を始めず、ビルドと監査に進む。

### D. 人間への確認（L3 のときだけ）

`ASK HUMAN` に挙がった課題（`human_decisions.md`）について、質問ツールで聞く（1回に最大4件、`scientific_core.md` §3 の形で）。**E の担当を起動した後に聞く**と、答えを待つ間も他の作業が進む。答えは `r2r.py decide <ws> --issue <ID> --choice approve|reject|defer [--action edit|experiment|analysis] --note "<人間の答え>"` で記録する。

- 承認された課題は、改訂担当の作業が終わった後に同じ担当（SendMessage）か新しい改訂担当に渡す。実験が必要なら次の反復で扱う。
- 人間に聞けない環境では判断待ちのまま進め、L3 の変更は行わない。

### E. 改訂と実験（並列）

`r2r.py start <ws> --it NN --phase revise`。時間の上限があれば、出力の `revise by` と `experiments by` を各担当の締め切りとして渡す（無ければ「なし」）。

**改訂担当**（文章・構成）：

```
あなたは Review2Revise-loop の「改訂担当」です。まず <skill_dir>/references/revision_writer.md と
<skill_dir>/references/scientific_core.md §2 を最後まで読み、特に「捏造の禁止」と「core を守る」を守ってください。

- 編集するソース: <ws>/src/（メイン: <config.json の main>）
- 計画: <ws>/iterations/itNN/triage.json（action が edit のもの、および ledger.json で human.choice が approve の課題）
- 課題台帳: <ws>/ledger.json   守るもの: <ws>/core/core.json   投稿先: <ws>/venue/venue_profile.json
- 査読: <ws>/iterations/itNN/review/findings.json, <ws>/iterations/itNN/venue_review.json（各指摘の詳細）
- 締め切り: <revise by の時刻 または「なし」>（この時刻までにビルドまで終える。足りなければ Major を優先し Minor を残す）
- 出力: <ws>/src/ の編集、<ws>/iterations/itNN/changes.json、ビルドした <ws>/iterations/itNN/output/paper.pdf
```

**実験担当**（`triage.json` の `experiments` ごと）：まず各実験の作業フォルダを作る。`findings` の指摘 ID は、ingest 後の `triage.json` で課題 ID に読み替える。

```bash
python <skill_dir>/scripts/r2r.py exp-new <ws> --it NN --slug <slug> --issues I003,I007 --kind experiment|analysis|simulation
```

```
あなたは Review2Revise-loop の「実験担当」です。まず <skill_dir>/references/experiment_agent.md を最後まで読み、
特に §0 の規則（数値を作らない・設計を先に固定する・不利な結果を隠さない）を守ってください。

- 実験: <ws>/experiments/<E01_slug>/（protocol.md と manifest.json は作成済み）
- 依頼: <ws>/iterations/itNN/triage.json の experiments[<slug>] と、課題 <I003, I007>（<ws>/ledger.json）
- 守るもの: <ws>/core/core.json（関わる主張: <C 番号>）
- 論文: <ws>/iterations/itNN/input/paper.txt, src/
- 設定: <ws>/config.json（experiments モード: <auto|design>、コード: <パス>、データ: <パス>、1実験の予算: <分>）
- 締め切り: <experiments by の時刻 または「なし」>（1実験の予算とこの時刻の早い方を守る。見積もりが収まらなければ、
  §0 のとおり科学的に妥当な縮小か needs_author にする。この時刻を過ぎたら新しい run を始めず、終わった run だけで記録をまとめる）
- 反復: NN
```

独立な実験は並列に起動する。GPU などの資源を取り合う実験は順に回す。実験担当がダウンロードの許可を求めて止まったら、名前・入手元・サイズを示してユーザーに聞く（許可が得られるまで、その実験は保留）。実験の結果が**主要な主張を否定する**と返ってきたら、その場でユーザーに伝えて判断を聞く（D と同じ手順）。

### F. 反映

改訂担当と、すべての実験担当が終わったら（`--phase integrate`）。完了・失敗・設計のみ、のいずれかになった実験があるときだけ行う。

```
あなたは Review2Revise-loop の「反映担当」です。まず <skill_dir>/references/integration.md を最後まで読み、
手順と規則に従ってください。

- 編集するソース: <ws>/src/（改訂担当の作業後。メイン: <main>）
- 反映する実験: <ws>/experiments/<E01_slug>/, …（各 manifest.json, outputs/, report.md）
- 課題台帳: <ws>/ledger.json   守るもの: <ws>/core/core.json   投稿先: <ws>/venue/venue_profile.json
- 更新する記録: <ws>/iterations/itNN/changes.json（既存の項目は消さない）、各実験の manifest.json の integrated_into
- 締め切り: <revise by の時刻 または「なし」>
- 出力: ビルドした <ws>/iterations/itNN/output/paper.pdf
```

`r2r.py end <ws> --it NN --phase revise`（実験・反映の時間も含めた改訂の区切り）。

### G. ビルドと機械的な検査

`--phase build`。順に実行する：

```bash
python <skill_dir>/scripts/build_pdf.py <ws>/src/<main> --out <ws>/iterations/itNN/output/paper.pdf
python <skill_dir>/scripts/pdf_tools.py text <ws>/iterations/itNN/output/paper.pdf -o <ws>/iterations/itNN/output/paper.txt
python <skill_dir>/scripts/snapshot.py <ws>/src <ws>/iterations/itNN/output --prev <ws>/iterations/itNN/input
python <skill_dir>/scripts/r2r.py changes <ws> --it NN
python <skill_dir>/scripts/r2r.py exp-check <ws> --it NN
python <skill_dir>/scripts/r2r.py provenance <ws> --it NN
python <skill_dir>/scripts/r2r.py venue-check <ws> --it NN
```

- ビルドが失敗する、未定義の参照・引用が残る → 改訂担当に直させる。直らなければ壊れたファイルを `iterations/itNN/input/src/` から戻す。古い PDF を改訂版として次の査読に回してはいけない。
- `changes` が `INVALID`（特に「L3 の変更が人間の承認なしに適用された」）→ 担当に元に戻させる。
- `exp-check` の問題 → 実験担当に直させる（記録の不足を埋める。数値は作らない）。
- `provenance` の `UNTRACED` と新しい引用は、次の監査で一件ずつ確かめられる。

### H. 健全性監査

`--phase audit`。改訂に関わっていない新しい担当に任せる。

```
あなたは Review2Revise-loop の「健全性監査担当」です。まず <skill_dir>/references/integrity_audit.md と
<skill_dir>/references/scientific_core.md を最後まで読み、全項目を点検してください。

- 守るもの: <ws>/core/core.json   課題台帳: <ws>/ledger.json
- 改訂前: <ws>/iterations/itNN/input/   改訂後: <ws>/iterations/itNN/output/（changes.diff を含む）
- 対応の記録: <ws>/iterations/itNN/triage.json, changes.json
- 機械的な検査: <ws>/iterations/itNN/provenance.md、r2r.py exp-check <ws> --it NN と
  r2r.py venue-check <ws> --it NN の出力（自分で実行してよい）
- 実験: <ws>/experiments/（この反復のもの: <E01, …>）
- 出力: <ws>/iterations/itNN/audit.json
```

`r2r.py audit <ws> --it NN`。
- `BLOCK`（修正が未適用、または `fail`）→ `required_fixes` を改訂担当に渡して適用させ、G をやり直す（ビルド → テキスト → snapshot → changes → provenance）。適用した修正の `applied` を `true` にして `r2r.py audit` を再実行する。修正の内容が自明でない、または `fail` が core の無断変更や捏造の疑いなら、同じ監査担当（SendMessage）に修正後の版を確かめさせてから `applied` にする。
- 反論が認められなかった課題（`reopened (rebuttal not upheld)`）は、時間があれば今回の改訂で対応し、無ければ次の反復に回る。

### I. 記録と次の版へ

```bash
python <skill_dir>/scripts/r2r.py log <ws> --it NN        # iterations/itNN/iteration_log.md
python <skill_dir>/scripts/r2r.py summary <ws>            # ledger.md progress.md response_letter.md human_decisions.md author_todo.md
python <skill_dir>/scripts/r2r.py promote <ws> --it NN    # itNN/output → it(NN+1)/input（監査済みの版だけが通る）
```

次の査読を始める前に `r2r.py status <ws>` を見る。時間の上限があり `NEXT: STOP — time` なら、次の査読は始めずに §3 へ（最後に査読した版を成果物とし、今回の改訂版は「未査読」として別に渡す）。`CONTINUE` なら、ユーザーへ1行だけ進捗を出す。例：`it02 完了：Major 6→3（新規 0）、Minor 14→9、追加実験 E01（supports）、監査 pass_with_fixes。残り 2h10m。it03 の査読へ`。そして NN+1 として A へ。ラウンドの間でユーザーに確認しない（D の L3 だけは例外）。

## 3. 終了処理

1. 最後の反復で `r2r.py log <ws> --it NN` → `r2r.py finish <ws> --reason "<status の STOP の理由>"` → `r2r.py summary <ws>`。
   finish は、最も評価の良かった版（Major が最少、同数なら W が最小、同じなら新しい方）を `<論文名>_revised.pdf` と `final_src/` にコピーする。最新の版と違う場合は理由が出力されるので、final_report に書く。ユーザーが最新版を望めば `--pick <NN>` で選び直す。時間切れで最後の改訂版が査読されなかった場合は、それを `<論文名>_revised_unreviewed.pdf` として別にコピーする（成果物ではなく、未査読の参考版として final_report に書く）。
2. 元が .docx なら、§1 の pandoc の手順で `.docx` にも戻す。
3. `<ws>/final_report.md` を書く：

```markdown
# Review2Revise-loop 最終レポート：<論文タイトル>
- 投稿先：<正式名・年度・種別>（aims & scope の要点を1行、出典は venue/venue_profile.md）
- 反復数 / 使用時間 / 終了理由 / 査読の深さ / 実験のモード
- scientific core：人間の確認 済 / 未（core/core.md）

## 改善の推移            （progress.md の表）
## 元の原稿（it01）の主な指摘   （Major を全件、一行ずつ）
## 解決した主な課題         （課題 ID・何をどう変えたか・どの反復で）
## 追加分析・追加実験        （実験 ID・問い・結果の向き・本文への反映。不利な結果も書く）
## 主張の変化               （元の主張 → 最終版の主張、理由）
## 反論した指摘と、その根拠
## 残っている課題
### 人間の判断が必要なもの（human_decisions.md）
### 著者の作業が必要なもの（author_todo.md の上位）
### 時間内に終わらなかったもの・再指摘はないが未対応のもの
## 健全性監査で見つかり修正した問題
## 投稿前に著者が確認すべきこと   （AUTHOR TODO の残り、引用の最終確認、投稿先の AI 利用方針への対応、チェックリスト）
## ファイル一覧
```

4. ユーザーへの返答は短く：反復数と終了理由、Major / Minor の推移、解決した主な課題、追加実験とその結果の向き、残る重要課題（人間の判断・著者の作業の上位3件）、ファイルの場所（`final_report.md`、`<論文名>_revised.pdf`、各反復の `iteration_log.md`、最終の deep-review の `report.html`）。最後に、これは AI による改訂であり、投稿前に著者がすべての変更（特に追加した文献・数値・主張の変更）を確かめる必要があることを一言添える。

## 4. 中断からの再開

`<ws>/state.json` があり `status` が `running` なら、`r2r.py status <ws>` と、最新の `iterations/itNN/` にあるファイルを見て、最後に終わった工程の次から再開する。工程とファイルの対応：`review/findings.json`（A）→ `venue_review.json`（B）→ `triage.json` と ingest 済みの指標（C）→ `changes.json`（E/F）→ `output/paper.pdf` と `changes.diff`（G）→ `audit.json`（H）→ `iteration_log.md` と次の `input/`（I）。deep-review-modoki の途中なら、その SKILL.md の「中断からの再開」に従う。ingest・changes・audit は再実行しても台帳が二重に更新されない（最初の実行の前の状態からやり直す）が、後の工程は実行し直す。`init --force` は全結果を消すので、ユーザーが最初からやり直したいときだけ使う。

**途中で上限を変える**：ユーザーが「あと2時間延ばして」「3反復で止めて」「時間制限をなくして」などと言ったら、`r2r.py limits <ws> --extend 2` / `--max-iter 3` / `--hours 6`（開始からの合計）/ `--no-deadline` で変更し、`r2r.py status <ws>` で新しい締め切りを確かめて1行で伝える。ループはそのまま続ける。

## 5. 原則と、その理由

- **査読 AI を満足させることを目的にしない**：指摘数は手段であり、目標は科学的に正しく、再現でき、主張と証拠が一致した論文である。だから、誤った指摘には根拠を示して反論し（監査が独立に検証する）、不利な結果や Limitations を消さず、言い回しで批判をかわさない。指摘数を減らすためだけの変更は、監査で差し戻す。
- **scientific core を守る**：研究課題・中心的アイデア・主要手法・主要な主張は著者のもの。これらを変える必要が出たら（L3）、自動では変えず人間に確認する。主張を証拠に合わせて狭めるのは core の範囲内（L2）で、記録したうえで自動で行う。
- **捏造しない**：実験結果・数値・データ・引用・証明・著者しか知らない事実を作らない。新しい数値は実際に実行した実験の記録からだけ写し、`provenance` で出所を機械的に調べる。実行できない実験は設計して著者に渡す。作った数値が一つでも混じれば研究不正になり、著者に深刻な害を与える。
- **実験は事前登録してから**：設計と判定の基準を先に固定し（`exp-register`）、結果を見てから条件を選ばず、すべての run を報告する。結果が主張に不利でも同じように反映する。
- **査読の基準を緩めない**：深さと焦点を全反復で同じにし、査読者には紙面だけを見せる。`[AUTHOR TODO]` は未解決として扱われる。評価が良くなるのは、紙面上で問題が解決したときだけ。
- **すべてを記録する**：各反復の査読コメント・対応・追加実験・変更箇所・未解決事項を `iteration_log.md` に、課題の履歴を台帳に残す。後から著者が、なぜその変更をしたのかを追える。
- **時間と収束の判断はスクリプトに任せる**：経過時間や改善の度合いを推測しない。毎回 `r2r.py status` を見る。
- **原稿の機密を守る**：Web 検索のクエリに原稿の文章・未公開のタイトルを入れない。原稿を外部のサービスに送らない。
- **元のファイルを変更しない**：`original/` とユーザーのコード・データは読み取り専用。編集は `src/` と `experiments/` の中だけで行う。
