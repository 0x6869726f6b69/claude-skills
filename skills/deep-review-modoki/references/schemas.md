# ファイル形式

Deep Review もどきの各エージェントが書く JSON の形式。`deep_review.py` がこの形式を前提に検証・集計するので、フィールド名と値はこのとおりにする。JSON は末尾カンマなし・コメントなしで、UTF-8 で書く。

目次：1 candidates（セグメント検証担当・レンズ担当）/ 2 verdicts（反証検証担当）/ 3 findings（統合担当）/ 4 共通の値

---

## 1. candidates/<task>.json

セグメント検証担当とレンズ担当が書く。ファイル名は plan.json の `output` のとおり。

```json
{
  "task_id": "T03",
  "segments": ["S2"],
  "trace": "B",
  "overall_notes": "（レンズ担当のみ・任意）Overall Feedback に使ってほしい所見。新規性の評価、主張と証拠の対応の総評など",
  "coverage_note": "担当範囲のうち確認できなかった箇所（例：付録Cの証明は時間内に追えなかった）",
  "candidates": [
    {
      "id": "c1",
      "type": "major",
      "kind": "error",
      "category": "proof",
      "title": "補題3.4の不等式の向きが逆で、定理2の上界が成り立たない",
      "location": {"page": 6, "section": "Sec. 3.2", "anchor": "Lemma 3.4, Eq. (12)"},
      "quote": "Applying Jensen's inequality to the concave function",
      "explanation": "何が誤りで、なぜそう言えるのか。具体的に。",
      "evidence": "どう確かめたか：再計算、反例（数値）、他の節の記述の引用など",
      "impact": "どの主張に影響するか（例：定理2、Abstract の『O(1/T) で収束』）",
      "suggestion": "どう直せばよいか。具体的に",
      "confidence": "high",
      "self_check": "反証を試みた結果：付録Bに別の導出がないか確認したが、同じ不等式を使っていた"
    }
  ]
}
```

| フィールド | 必須 | 内容 |
|---|---|---|
| `id` | ○ | ファイル内で一意（`c1`, `c2`, …） |
| `type` | ○ | `major` / `minor` / `suggestion`（提案する重大度。最終決定は統合担当） |
| `kind` | | `error`（誤り）/ `gap`（論証・根拠の欠落）/ `absence`（あるべきものが無い）/ `overclaim`（証拠より強い主張）/ `inconsistency`（記述どうしの不一致）/ `improvement`（改善提案）/ `typo` |
| `category` | ○ | §4 の値 |
| `title` | ○ | 一行要約。何が問題かが分かるように |
| `location` | ○ | `page`（整数・リスト・"5-6" のいずれか。paper.txt の `=== Page N ===` の番号）、`section`、`anchor`（式・定理・表の番号） |
| `quote` | △ | 論文からの**逐語引用**（200字以内）。`absence` のときだけ空文字でよい |
| `explanation` | ○ | 問題の内容と理由 |
| `evidence` | | 確認の方法と結果 |
| `impact` | | 影響する主張 |
| `suggestion` | △ | 直し方。`major` / `minor` では必須 |
| `confidence` | | `high` / `medium` / `low` |
| `self_check` | | 自分で反証を試みた内容 |
| `out_of_scope` | | 担当外の範囲の問題に気づいたとき `true`（1件程度に留める） |

**quote の規則**：`paper.txt` からそのままコピーする。言い換え・要約・翻訳をしない。スクリプトは空白・改行・ハイフン・記号の違いを無視して照合するので、PDF抽出で崩れた数式部分を避け、式の直前直後の文や「Lemma 3.4 states that …」のような地の文を引用する。照合できない引用は誤検出として扱われる。

---

## 2. verdicts/<V..>.json

反証検証担当が書く。

```json
{
  "task_id": "V01",
  "verdicts": [
    {
      "cluster": "K03",
      "verdict": "confirmed",
      "type": "major",
      "reason": "判定の理由",
      "evidence": "独立に確かめた内容：再計算の式と値、反例、該当箇所の引用",
      "corrected_location": {"page": 6, "section": "Sec. 3.2", "anchor": "Eq. (12)"},
      "quote": "位置や引用を直した場合のみ、paper.txt からの逐語引用",
      "fix_hint": "直し方についての補足（任意）"
    }
  ]
}
```

| `verdict` | 意味 |
|---|---|
| `confirmed` | 独立に再現できた（再計算・反例・明白な記述の矛盾など、具体的な根拠がある） |
| `plausible` | おそらく問題だが確定できない（例：省略された導出が埋められるか判断できない） |
| `refuted` | 誤検出。論文は正しい／候補側の読み違い／別の場所で定義・証明されている |
| `cannot_locate` | 指摘された箇所や引用が論文中に見つからない |

`type` には検証後に妥当と考える重大度を入れる（例：誤りは本物だが局所的なら `minor`）。

---

## 3. findings.json

統合担当が書く最終結果。`deep_review.py render` がこれを検証し、report.md と report.html を作る。

```json
{
  "title": "論文タイトル",
  "field": "分野（例：分散最適化 / 理論計算機科学）",
  "overall": {
    "summary": "論文の貢献の要約（中立に。評価を混ぜない。1〜2段落）",
    "strengths": ["具体的な根拠つきの長所", "…"],
    "concerns": ["最重要の懸念（MJ1）", "…"],
    "bottom_line": "投稿前に必ず対処すべきこと、対処すれば何が強くなるか。点数は付けない"
  },
  "findings": [
    {
      "id": "MJ1",
      "type": "major",
      "category": "proof",
      "title": "補題3.4の不等式の向きが逆で、定理2の上界が成り立たない",
      "location": {"page": 6, "section": "Sec. 3.2", "anchor": "Lemma 3.4"},
      "quote": "Applying Jensen's inequality to the concave function",
      "explanation": "…",
      "evidence": "…",
      "impact": "…",
      "suggestion": "…",
      "confidence": "high",
      "verification": "confirmed",
      "support": 2,
      "sources": ["K03"]
    }
  ],
  "previous": [
    {"id": "MJ2", "title": "前回レビューの指摘", "status": "resolved", "note": "Sec. 4 に反例への対処が追加された"}
  ],
  "method_notes": "（任意）今回のレビュー固有の注記",
  "limitations": ["このレビューで確認できなかったこと（例：付録Dの証明は追っていない）"]
}
```

| フィールド | 内容 |
|---|---|
| `id` | `major` → `MJ1, MJ2…`、`minor` → `MN1…`、`suggestion` → `SG1…`。重要な順に番号を振る |
| `type` | `major`（Major concern）/ `minor`（Minor correction）/ `suggestion` |
| `confidence` | `high` / `medium` / `low` |
| `verification` | `confirmed` / `plausible` / `unverified` |
| `support` | 独立に同じ問題を見つけたエージェントの数（cluster の `support`） |
| `sources` | 元になった cluster ID |
| `previous` | 改訂版の再レビューのときだけ。`status` は `resolved` / `partially_resolved` / `open` |

`quote` があれば render が論文中での所在を再確認し、見つからなければエラーにする。

---

## 4. 共通の値

**category**

| 値 | 対象 |
|---|---|
| `proof` | 証明の誤り・飛躍、補題の誤用、量化子・条件の誤り |
| `math` | 計算・式変形・定数・次元・記号の数学的な誤り |
| `claim_evidence` | 主張と証拠の対応（証拠のない主張、証拠より強い主張、Abstract と本文の食い違い） |
| `experiment` | 実験設計（ベースライン、比較の公平性、交絡、リーク、評価指標、ablation） |
| `statistics` | 統計の報告と解釈（seed数、誤差、検定、有意性、効果量） |
| `data_consistency` | 数値どうしの不一致（表と本文、表と図、合計・平均・割合の再計算） |
| `novelty` | 新規性・重要性の主張と、その根拠 |
| `related_work` | 最近接研究との比較・欠けている関連研究 |
| `citation` | 引用の誤り（存在しない・内容が違う・書誌情報の誤り） |
| `notation` | 記法の不統一・未定義の記号・記号の多重定義 |
| `clarity` | 説明の分かりにくさ、定義の曖昧さ |
| `presentation` | 図表の読みやすさ、相互参照の誤り、体裁 |
| `reproducibility` | 再現に必要な情報の欠落（ハイパーパラメータ、データ、コード、計算資源） |
| `other` | 上記以外 |
