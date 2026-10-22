# 査読の出力形式

査読者は毎ラウンド2つのファイルを書く。

- `review.md`：人が読む査読レポート（下のテンプレート）
- `issues.json`：同じ内容を機械可読にしたもの。ラウンドをまたいで指摘を追跡し、`loop_state.py summary` が評価の推移表を作るのに使う

両者の ID（W1, Q1, …）と評価値は一致させる。

---

## review.md テンプレート

見出しと順序はこのとおりにする。`< >` は置き換える。

```markdown
# 査読レポート — Round <NN>

- **論文**：<タイトル>
- **分野**：<例：Federated Learning / 分散最適化>
- **評価尺度**：<例：国際会議型 1–6>

## 0. 前回指摘の対応状況（Round 2 以降のみ）

| ID | 重大度 | 指摘 | 今回の状態 | 根拠（PDF の該当箇所と内容） |
|---|---|---|---|---|
| W1 | Major | <要約> | 解決 / 一部解決 / 未解決 / 著者対応待ち | <例：Sec. 5.2 に α∈{0.1,0.5,1.0} の結果（Table 3）が追加された> |

**改訂で新たに生じた問題**：<なければ「なし」>
**前回からの評価の変化**：<例：3 → 4。W2・W5 が解決されたため>

## 1. Paper Summary

- **目的**：<何の問題を、なぜ解くのか>
- **提案手法**：<手法の概要>
- **主要な技術的アイデア**：<既存手法との違いの核>
- **主張されている貢献**：
  - 理論：<例：非凸・partial participation 下で O(1/√(NKT)) の収束>
  - 実験：<例：CIFAR-10 / FEMNIST で FedAvg 比 +3〜8 pt>

（著者の主張を正確かつ中立に書く。評価はここに混ぜない）

## 2. Strengths

- **S1［新規性・独創性］** <何が、なぜ優れているかを具体的に>
- **S2［技術的妥当性］** <…>
- **S3［問題設定の重要性］** <…>

（観点：新規性・独創性 / 技術的妥当性 / 理論的貢献 / 実験結果の有効性 / 問題設定の重要性 / 既存研究に対する位置づけ。該当するものを根拠とともに）

## 3. Weaknesses

### Major

**W1［Major｜<カテゴリ>］<一行要約>**
- 該当箇所：<Sec. / 式 / 表 / 図>
- 問題：<具体的に、根拠つきで>
- 重要な理由：<どの主張・判断に影響するか>
- 改善案：<追加実験・分析・理論的説明を具体的に>
- 改訂での対応：<本文修正で可 / 一部可 / 新規の結果が必要>

### Minor

**W5［Minor｜<カテゴリ>］<一行要約>**
- 該当箇所 / 問題 / 改善案 / 改訂での対応（簡潔に）

### その他の細かい点（誤字・表記・図表）

- <p.3 l.12：…>

### 確認観点

| 観点 | 判定 | 関連する指摘 |
|---|---|---|
| 既存研究との差異・新規性 | 十分 / 一部不足 / 不十分 | W… |
| 提案手法を支持する実験の十分性 | | |
| 実験設定の現実性 | | |
| より大規模なモデル・データでの有効性 | | |
| 計算量・メモリ・通信量のスケーラビリティ | | |
| 理論の仮定の現実的な妥当性 | | |
| FL：non-IID・クライアント異質性・partial participation | （FL でなければ「該当なし」） | |
| Privacy / Security の主張と制約 | （主張がなければ「該当なし」） | |

## 4. Justification of Recommendation

- **判断を決めている論点**（最大3つ）：<どの Weakness が評価を決めているか、なぜか>
- **長所がどこまで短所を補うか**：<…>
- **現在の位置づけ**：<例：手法の着想は有望だが、中心的主張 C2 を支える実験が欠けているため、現時点では Borderline Reject>

（要約の繰り返しではなく、採択判断に効く論点を明確にする）

## 5. Specific Points of Feedback for Rebuttal

優先度の高い順。追加実験・追加分析・理論的説明で答えられる形で書く。

**Q1（優先度：高｜関連：W1）** <質問>
- 期待する回答・追加実験：<…>
- 評価への影響：<例：十分に示されれば W1 は解決とみなし、総合評価を 3→4 に上げうる>

**Q2（優先度：高｜関連：W2）** <…>

## 6. Rating

- **総合評価**：<3> / 6（<Borderline Reject>）
- **内訳**：Quality <2>/4、Clarity <3>/4、Significance <3>/4、Originality <2>/4
- **採択側に変わる条件**：<例：W1 と W3 が解決されれば 4（Borderline Accept）、さらに W2 も解決されれば 5>

## 7. Confidence

- **<4> / 5**：<根拠。何を確認し、何を確認していないか。例：主定理の鍵補題は確認したが、付録 B の証明全体は追っていない>
```

---

## issues.json

```json
{
  "round": 2,
  "paper_title": "FedAlign: ...",
  "field": "Federated Learning",
  "rating": {
    "scale": "国際会議型 1-6",
    "overall": 3,
    "overall_label": "Borderline Reject",
    "quality": 2,
    "clarity": 3,
    "significance": 3,
    "originality": 2,
    "confidence": 4
  },
  "accept_conditions": "W1 と W3 が解決されれば 4、さらに W2 で 5",
  "issues": [
    {
      "id": "W1",
      "severity": "major",
      "category": "experiments",
      "title": "非IIDの強さが1設定のみ",
      "location": "Sec. 5.1, Table 2",
      "problem": "Dirichlet α=0.5 のみで、異質性への頑健性 (C2) を検証できない",
      "suggestion": "α∈{0.1,0.3,1.0} と FEMNIST で FedAvg/FedProx/SCAFFOLD と比較",
      "fixable_by_revision": "no",
      "status": "needs_author",
      "first_round": 1,
      "status_note": "Sec. 5.1 に [AUTHOR TODO] として明記。C2 の記述は α=0.5 に限定された"
    }
  ],
  "questions": [
    {"id": "Q1", "related": ["W1"], "priority": "high", "text": "α を変えたとき FedProx との差はどう変化するか"}
  ]
}
```

| フィールド | 値 |
|---|---|
| `severity` | `major` / `minor` |
| `category` | `novelty` / `related_work` / `technical` / `theory` / `experiments` / `scalability` / `fl_setting` / `privacy_security` / `clarity` / `reproducibility` / `other` |
| `fixable_by_revision` | `yes`（本文修正で解決可）/ `partial` / `no`（新しい結果が必要） |
| `status` | `open` / `partially_resolved` / `resolved` / `needs_author` |
| `first_round` | その指摘が最初に出たラウンド |
| `status_note` | ラウンド2以降：状態の根拠（PDF のどこに何が書かれたか） |

- 前ラウンドの指摘は、解決済みのものも含めてすべて残す（推移表を作るため）
- 誤字などの「その他の細かい点」は issues.json に入れなくてよい
- JSON として正しいこと（末尾カンマなし、コメントなし）を確認する
