---
name: deep-review-modoki
description: Google の Deep Review（旧 Paper Assistant Tool, PAT）を模した、論文・技術文書の深い検証レビュー。文書を論理セグメントに分け、情報密度に応じて検証の深さ（Light/Medium/High）を配分し、セグメントごとに観点の異なる検証サブエージェントを並列に走らせる（証明の逐行検証・反例探索・数値の再計算・実験設計・主張と証拠の対応・新規性の文献確認）。候補は逐語引用で照合・重複排除し、反証検証で誤検出を落としたうえで、Overall Feedback と Detailed Feedback（Major concerns / Minor corrections / Suggestions）の Markdown・HTML レポートにまとめる。スコアは付けない。「Deep Reviewして」「ディープレビュー」「PATみたいに」「論文の誤りや証明の穴を徹底的に探して」「投稿前に技術的なミスを洗い出して」「数式・証明・実験を検証して」などと頼まれたら、スキル名が出ていなくても使うこと。設計書・技術報告など論文以外の技術文書にも使える。採点つきの会議形式の査読や、査読→改訂のループは paper-review-loop を使う。Use for deep, agentic error-finding review of a paper or technical document in the style of Google's Deep Review / PAT.
---

# Deep Review もどき：分割 → 並列検証 → 反証 → 統合

Google の Deep Review（STOC・ICML・NeurIPS・ICLR で著者向けに試行された Paper Assistant Tool の後継）の公開されている設計を、Claude のサブエージェントで再現する。目的は、投稿前の著者が自分では気づけない**本物の誤り**（証明の穴、計算違い、数値の不一致、証拠より強い主張、欠けている比較）を、確かめられる形で優先度順に示すこと。点数は付けない。

工程と、それぞれを置く理由：

| 工程 | 担当 | 理由 |
|---|---|---|
| 1 取り込み | スクリプト | テキストとページ画像の両方を用意する。抽出テキストは数式・表が崩れるので画像が要る |
| 2 セグメント分割・予算配分 | あなた | 証明の密な部分に計算を集中し、導入や関連研究は軽く見る |
| 3 並列の深い検証 | サブエージェント（セグメント×観点、レンズ） | 一度に深く読む範囲を絞り、観点の違う独立な目で網羅性を上げる |
| 4 照合・重複排除 | スクリプト | 逐語引用が論文に実在するかを機械的に確かめ、同じ問題をまとめる |
| 5 反証検証 | サブエージェント | 誤り探しは試行を重ねるほど誤検出が増える。疑ってかかる別の目で精度を取り戻す |
| 6 統合 | サブエージェント | 重大度の決定、優先順位、長さの制御、Overall Feedback |
| 7 レポート | スクリプト → あなた | report.md / report.html を作り、要点を短く伝える |

設計の根拠（どの文献のどの知見から来たか）は `references/research_basis.md` にある。

以下、`<skill_dir>` はこの SKILL.md があるディレクトリ、`<ws>` は作業フォルダ、`deep_review.py` は `python <skill_dir>/scripts/deep_review.py` の略。`python` が無ければ `python3` を使う。

## 0. 最初に：深さと焦点を確認する

1. 対象の文書を特定する。PDF が最良（ページ画像が作れる）。.md / .txt / .tex も受け付けるが、その場合は図や数式の画像確認ができない。LaTeX ソースしか無く、ビルドできるなら PDF にしてから使う。
2. 深さと焦点を、AskUserQuestion などの質問ツールで一度に聞く（無ければチャットで聞く）。起動メッセージで既に分かっている項目は聞かない。「すぐやって」「任せる」なら standard・焦点なしで始める。
   - 質問1「深さ」：`Standard（推奨）` / `Quick` / `Deep`（下の表の目安を説明に添える）
   - 質問2「重点的に見てほしいところ」（複数選択可）：`特になし` / `証明・数式` / `実験・統計` / `新規性・関連研究`（その他で投稿先や自由記述も可）

| 深さ | セグメント数 | 1セグメントのトレース数 | レンズ | 反証検証の対象 | エージェント数の目安 | 時間の目安 |
|---|---|---|---|---|---|---|
| quick | 2〜4 | 1 | L0（統合） | Major と所在不明のもの | 4〜8 | 10〜20分 |
| standard | 4〜8 | High 2、他 1 | L1・L2・L3 | Major と所在不明のもの | 10〜20 | 20〜45分 |
| deep | 5〜12 | High 3、Medium 2、Light 1 | L1・L2・L3 | ＋数式・統計・数値系の Minor、批評担当 | 20〜40 | 45〜90分 |

時間は論文の長さで大きく変わる。

3. ユーザーが**他人の原稿を査読者として**見ようとしている様子なら、投稿先の AI 利用方針（多くの出版社・会議が、査読中の原稿を AI ツールに入力することを禁じている）を確認するよう一言添える。著者が自分の原稿を見る場合は不要。

## 1. 取り込み

```bash
python <skill_dir>/scripts/deep_review.py init <文書のパス> --depth standard --focus "<焦点。なければ省略>" --venue "<投稿先。なければ省略>" --lang ja
```

- 作業フォルダは `<文書のあるフォルダ>/<文書名>_deep_review/`（書けなければカレントディレクトリ配下、`--ws` で指定も可）
- `paper.txt`（`=== Page N ===` 区切り）、`pages/page_NNN.png`（150 dpi）、`pages.json`、`config.json` ができる
- 出力されるページごとのアウトライン（語数、数式記号の割合、式番号の数、定理・証明の数、見出し、図表キャプション）を次の工程で使う
- `WARN` が出たら読む。スキャン PDF などでテキストが乏しければ、各担当にページ画像中心で読むよう依頼文に書き足す
- レポートの言語は `--lang`（`ja` / `en`）。ユーザーの言語に合わせる。引用は原文のまま

## 2. セグメント分割と予算配分

アウトラインを見て `<ws>/segments.json` を書く。見出しだけで内容が分からないページは `paper.txt` の該当ページを覗く（全文を読む必要はない）。

規則：
- **論理的なまとまりで分ける**（理論、手法、実験、導入など）。重なってもよく、連続していなくてもよい。例えば「Sec. 3 の定理の主張」と「付録 B のその証明」は同じセグメントにする
- **全ページをどれかのセグメントに含める**（`plan` が検査する）
- **トラック（深さ）を情報密度で決める**：
  - `high`：主定理とその証明、中心的な導出、正しさを主張するアルゴリズムの核心。論文の主要な主張が実験結果そのものなら、主要な結果の表・図の節も
  - `medium`：手法の説明、実験、付録の追加実験
  - `light`：導入、関連研究、考察・結論
  - `none`：参考文献・謝辞など（`reason` 必須。参考文献はレンズ L3 が見る）
- `high` のセグメントは 8〜10 ページ以内にする（長ければ分ける）
- `theme`：`intro` / `related_work` / `discussion` / `other` / `method` / `algorithm` / `system` / `theory` / `appendix_proofs` / `experiments` / `analysis` / `appendix_experiments` / `references`
- `notes` に、担当に伝えたいこと（このセグメントが支える主張、依存する定義の場所など）を一行で書いてよい

```json
{
  "segments": [
    {"id": "S1", "title": "導入と貢献", "pages": "1-2", "theme": "intro", "track": "light",
     "notes": "貢献 C1–C3 は p.2 の箇条書き"},
    {"id": "S2", "title": "主定理とその証明", "pages": "4-5,13-16", "theme": "theory", "track": "high",
     "notes": "定理2（p.5）の証明は付録B（p.13–16）。仮定は p.3 の Assumption 1–3"},
    {"id": "S3", "title": "提案アルゴリズム", "pages": "3-4", "theme": "algorithm", "track": "medium"},
    {"id": "S4", "title": "実験", "pages": "6-9", "theme": "experiments", "track": "medium"},
    {"id": "S5", "title": "関連研究・結論", "pages": "9-10", "theme": "related_work", "track": "light"},
    {"id": "S6", "title": "参考文献", "pages": "11-12", "theme": "references", "track": "none",
     "reason": "参考文献はレンズ L3 が抜き取り検査する"}
  ]
}
```

次に計画を作る：

```bash
python <skill_dir>/scripts/deep_review.py plan <ws>
```

`plan.json` に、起動するエージェント（タスク ID、担当セグメント、トラック、トレース＝観点、ページ、出力先、推奨 effort）が並ぶ。エラーが出たら segments.json を直して再実行する。

ユーザーへ1行：`分割完了：6セグメント（High 1・Medium 2・Light 2）、検証エージェント 9 を並列で起動します`

## 3. 並列の深い検証

`plan.json` の全タスクを、**一つのメッセージで並列に** Agent ツールで起動する（10を超えるなら 8 程度ずつの波に分ける）。各タスクに `effort` があり、Agent ツールに effort の指定があれば、その値で起動する（High トラックに推論を厚く配分するため）。

**セグメント検証担当への依頼文**（`kind: segment`）

```
あなたは Deep Review の「セグメント検証担当」です。まず次を最後まで読み、手順と出力形式に従ってください。
  <skill_dir>/references/segment_reviewer.md
  <skill_dir>/references/checklists.md（担当テーマに関係する節）
  <skill_dir>/references/schemas.md の §1 と §4

- 論文の全文: <ws>/paper.txt（=== Page N === がページ番号）  ページ画像: <ws>/pages/page_NNN.png
- 元の文書: <ws>/<config.json の input_copy>
- タスク: <T03>   セグメント: <S2>「<タイトル>」  ページ: <4-5,13-16>  テーマ: <theory（proof）>
- トラック: <high>   トレース: <B — 反例・境界・仮定>
- セグメントのメモ: <notes。無ければ「なし」>
- ユーザー指定の焦点: <focus または「なし」>   投稿先: <venue または「なし」>
- 出力: <ws>/<candidates/T03_S2_B.json>
- 補助: python <skill_dir>/scripts/pdf_tools.py（crop・render --grid で図や式を拡大）

全文は文脈として読み、指摘は担当ページに集中してください。同じセグメントを別の観点の担当も見ています。
```

Light トラックで複数セグメントを束ねたタスクは、セグメント欄に全部を並べる。

**レンズ担当への依頼文**（`kind: lens`）

```
あなたは Deep Review の「レンズ担当（<L2 新規性・重要性>）」です。まず次を最後まで読み、担当レンズの節の手順と出力形式に従ってください。
  <skill_dir>/references/lens_reviewers.md
  <skill_dir>/references/checklists.md（§6〜§8）
  <skill_dir>/references/schemas.md の §1 と §4

- 論文の全文: <ws>/paper.txt   ページ画像: <ws>/pages/page_NNN.png
- タスク: <T08>   レンズ: <L2>
- ユーザー指定の焦点: <…>   投稿先: <…>
- 出力: <ws>/<candidates/T08_L2.json>（overall_notes も書くこと）

論文全体を、担当レンズの観点で横断して見てください。範囲ごとの深い検証は別の担当が行っています。
```

全員の完了を待ったら `plan` を再実行し、全タスクに `[done]` が付いたか確かめる。欠けたタスクは一度だけ起動し直す。それでも欠けたら先へ進み、統合担当に伝えて limitations に書かせる。

ユーザーへ1行：`検証 9/9 完了`

## 4. 照合と重複排除

```bash
python <skill_dir>/scripts/deep_review.py merge <ws>
```

- 各候補の逐語引用が論文に実在するか（`exact` / `fuzzy` / `not_found`）とそのページを調べ、近い候補を cluster（K01, …）にまとめて `merged.json` に書く
- `support` は、同じ問題を独立に見つけたタスクの数。複数のトレースが独立に見つけた問題ほど本物である可能性が高い
- 反証検証のバッチ（V01, …）が出力される。`invalid` や `missing outputs` の警告があれば、該当ファイルを書いた担当の問題として記録しておく

ユーザーへ1行：`候補 64 件 → 38 件に統合、うち 9 件を反証検証にかけます`

## 5. 反証検証

`merged.json` の `verify_tasks` を、一つのメッセージで並列に起動する。

**反証検証担当への依頼文**

```
あなたは Deep Review の「反証検証担当」です。まず <skill_dir>/references/verifier.md と
<skill_dir>/references/schemas.md の §2 を最後まで読んでください。

- 論文の全文: <ws>/paper.txt   ページ画像: <ws>/pages/page_NNN.png
- 検証対象: <ws>/merged.json の clusters のうち <K01, K04, K07>（関係ページ: <…>）
- 出力: <ws>/verdicts/<V01>.json

各候補について、まず「論文が正しい」という立場で反証を試み、そのうえで自分で独立に再現できたもの
（再計算・反例・矛盾する二箇所の引用など具体的な根拠があるもの）だけを confirmed にしてください。
```

完了したら：

```bash
python <skill_dir>/scripts/deep_review.py collate <ws>
```

検証結果を cluster に結びつけた `collated.json` ができる。`refuted` / `cannot_locate` は削除推奨になる。

ユーザーへ1行：`反証検証完了：確認 5・妥当 2・誤検出 2`

## 6. 統合

**統合担当への依頼文**

```
あなたは Deep Review の「統合担当」です。まず <skill_dir>/references/synthesis.md と
<skill_dir>/references/schemas.md の §3 と §4 を最後まで読んでください。

- 入力: <ws>/collated.json（候補・検証結果・レンズの所見・観点の分布）、<ws>/paper.txt、
        <ws>/pages/、<ws>/config.json（深さ・焦点・投稿先・言語）
- 出力: <ws>/findings.json
- 書き終えたら python <skill_dir>/scripts/deep_review.py render <ws> --check を実行し、
  エラーがなくなるまで直すこと
- レポートの言語: <日本語>   ユーザー指定の焦点: <…>   投稿先: <…>
- 補足: <欠けたタスクなど、limitations に書くべきこと。無ければ「なし」>
```

**deep のみ：批評担当**。統合担当が書き終えたら、別のサブエージェントに次を依頼する。

```
あなたは Deep Review の「批評担当」です。<ws>/findings.json（統合担当の草稿）を、<ws>/paper.txt と
<ws>/pages/ に照らして点検してください。<skill_dir>/references/synthesis.md の §8 の観点
（引用と位置の正確さ、具体性、重大度の妥当性、外部文献の実在、口調、長さ）で全件を見て、
すべての Major は自分で確かめてください。新しい指摘は探しません。
結果を <ws>/critique.md に「ID・問題・直し方」の箇条書きで書いてください。
```

critique.md ができたら、統合担当に SendMessage で「critique.md を読み、妥当な点を findings.json に反映して render --check を通す」よう依頼する（SendMessage が無ければ、同じ依頼で統合担当を新しく起動する）。

最後に：

```bash
python <skill_dir>/scripts/deep_review.py render <ws>
```

`report.md` と `report.html` ができる。HTML は Major / Minor / Suggestions の絞り込みと、レポート順／ページ順の切り替えができる。

## 7. ユーザーへの報告

`findings.json` を読み、短くまとめる。レポート全文は貼らない。

- 件数（Major / Minor / Suggestions）と、反証検証で除外した誤検出の数
- Major concerns を全件、一行ずつ（ID、場所、要点）
- 総括（bottom_line）を1〜2文
- ファイル：`report.html`（ブラウザで開く）、`report.md`、作業フォルダ
- 注意を一言：AI の指摘であり、原稿を変える前に各指摘を確かめてほしいこと

次の一手を提案する：特定の指摘の深掘り、直した後の再レビュー、採点つきの査読と改訂ループ（paper-review-loop）。

## フォローアップ

- **深掘り**（「MJ2 をもっと詳しく」）：その指摘の箇所を担当範囲とし、high トラック・トレース B（反例）で検証担当を一人起動して、結果を findings.json に反映 → render
- **改訂版の再レビュー**：新しい PDF で 1 から通す（`init` は新しい作業フォルダで）。統合担当の依頼文に前回の `findings.json` のパスを加え、`previous` に対応状況を書かせる
- **中断からの再開**：作業フォルダにあるファイル（segments.json → plan.json の `[done]` → merged.json → verdicts/ → collated.json → findings.json）を見て、最後に完了した工程の次から続ける。`init --force` は前回の結果を消すので、やり直したいときだけ使う

## 他のスキルから呼ばれたとき

review2revise-loop などが、反復の中の査読工程としてこのスキルを呼ぶことがある。呼び出し側が入力・作業フォルダ（`--ws`）・深さ・焦点・投稿先・前回の findings.json を指定していれば：

- §0 の質問はしない。指定された値を使う
- §1〜§6 をそのまま行い、`findings.json`・`report.md`・`report.html` を作る。前回の findings.json が指定されていれば、統合担当の依頼文に加えて `previous` を書かせる
- §7 の報告は「Major / Minor / Suggestions の件数」の一行だけにして呼び出し側に戻る。次の一手の提案はしない
- 査読の基準・深さ・件数の上限は通常と同じ。呼び出し側の都合で緩めない

## サブエージェントが使えない環境

工程は同じで、各タスクを自分で順に行う。独立性が落ちるので次を守る。
- 深さは quick を勧める（ユーザーが望めば standard）
- 各タスクの前に、担当ページを `paper.txt` とページ画像から読み直し、記憶に頼らない
- タスクごとに、そのタスクのガイド（segment_reviewer.md など）の観点だけで見る
- 反証検証は、候補を書いたときの推論を見ずに、論文の該当箇所だけから判断し直す

## 原則と、その理由

- **確かめられない指摘は出さない**：引用は逐語、数式・表は画像で確認、計算はコードで再現、外部文献は実在を確かめたものだけ。誤検出の混じったレポートは著者の時間を奪い、本物の指摘まで信用を失う。
- **量より優先順位**：Major は主要な主張に効くものだけ。件数の上限を守る。細部へのこだわりと長すぎるレポートは、AI レビューで最も嫌われる。
- **点数を付けない**：Deep Review は誤りと改善点に集中し、主観的な点数を出さない。LLM の点数は楽観に偏り、不安定でもある。点数が欲しいときは paper-review-loop を使う。
- **判断は人に残す**：これは投稿前の著者向けの道具であり、査読の代わりではない。最終的な判断は著者と査読者が行う。
- **原稿の機密を守る**：Web 検索のクエリに原稿の文章や未公開のタイトルを入れない。原稿を外部のサービスに送らない。
- **元のファイルを変更しない**：作業はすべて `<ws>` の中で行う。
