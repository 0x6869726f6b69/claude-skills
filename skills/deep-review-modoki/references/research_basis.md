# 設計の根拠

このスキルは、Google の **Deep Review**（旧称 Paper Assistant Tool, PAT）の公開情報と、自動論文レビューに関する研究をもとに、Claude のサブエージェントで再現できる範囲で組み立てたものである。Google の実装（Gemini Deep Think の推論スケーリング、内部のプロンプト）は公開されていないので、「もどき」である。エージェントがこのファイルを読む必要はない。設計を見直すときの参照用。

## 参照した文献

1. Lin, J., Song, J., Zhou, Z., Chen, Y., & Shi, X. (2023). Automated scholarly paper review: Concepts, technologies, and challenges. *Information Fusion, 98*, 101830. https://doi.org/10.1016/j.inffus.2023.101830
2. Zhou, R., Chen, L., & Yu, K. (2024). Is LLM a reliable reviewer? A comprehensive evaluation of LLM on automatic paper reviewing tasks. *LREC-COLING 2024*, 9340–9351.
3. Shin, H., Tang, J., Lee, Y., Kim, N., Lim, H., Cho, J. Y., Hong, H., Lee, M., & Kim, J. (2025). Automatically evaluating the paper reviewing capability of large language models. arXiv:2502.17086（現行版の題名は "Mind the Blind Spots: A Focus-Level Evaluation Framework for LLM Reviews"）
4. Son, G., et al. (2025). When AI co-scientists fail: SPOT — A benchmark for automated verification of scientific research. arXiv:2505.11855
5. Zhuang, Z., Chen, J., Xu, H., Jiang, Y., & Lin, J. (2025). Large language models for automated scholarly paper review: A survey. *Information Fusion, 124*, 103332.
6. Biswas, J., et al. (2026). AI-assisted peer review at scale: The AAAI-26 AI review pilot. arXiv:2604.13940
7. Jayaram, R., Tyler, D., Woodruff, D. P., Cortes, C., Matias, Y., Mirrokni, V., & Cohen-Addad, V. (2026). Towards automating scientific review with Google's Paper Assistant Tool. arXiv:2606.28277
- Google Research Blog: "Analyzing technical documents with Deep Review"、"Gemini provides automated feedback for theoretical computer scientists at STOC 2026"

## 文献の知見 → このスキルの設計

| 知見 | 出典 | 設計 |
|---|---|---|
| 4段構成：セグメント分割 → 情報密度に応じた計算予算（Light / Medium / High）→ セグメントごとの並列の深い検証（各エージェントは全文を文脈に持ち、担当範囲に集中）→ 全体の統合（重複排除・重大度の確認・検索による根拠づけ） | 7, Deep Review ブログ | §2〜§6 の工程そのもの。`segments.json` の `track`、`plan` によるトレース数の配分 |
| 単発の呼び出しより推論スケーリングの方が深い誤りを見つける（SPOT の数学の誤りで 55.2% → 89.7%）。ただし単純な pass@k は再現率を上げる代わりに適合率を下げる | 7 | High トラックに観点の異なる複数トレース（A/B/C）を割り当てる。精度は反証検証で取り戻す |
| 最良モデルでも再現率 21.1%・適合率 6.1%。複数回の実行で同じ誤りを再発見することはまれ。専門家から見ると学生レベルの誤解が混じる | 4 | 反証検証担当（`verifier.md`）。独立に複数トレースが見つけたもの（support≥2）を信頼度の手がかりにする |
| 失敗例：正しい証明を誤りと主張する、PDF の解析ミス、日付・知識の古さ。根拠づけられていると感じた回答者は 6 割程度 | 7 | ページ画像での確認の義務化、逐語引用とスクリプトによる照合（grounding）、外部文献は検索で確認したものだけ |
| レポート形式：Overall Feedback（貢献の要約と強み・弱みの評価）と Detailed Feedback（Major concerns / Minor corrections / Suggestions、該当ページ・節つき）。スコアは付けない。custom context で焦点を指定できる | Deep Review ブログ・解説、7 | `findings.json` と report.md / report.html の構成。HTML のフィルタと「ページ順」表示。`--focus` |
| PDF を markdown 化したテキストと PDF 画像の両方をモデルに渡す。5つの観点（story / presentation / evaluations / correctness / significance）。評価と正しさにはコード実行、重要性には（公刊研究に限った）Web 検索。初稿 → 自己批評 → 改訂 | 6 | paper.txt と pages/ の両方を渡す。セグメント担当にコード実行、L2 に文献検索、L1 にストーリー。統合担当の自己点検、deep の批評担当 |
| AI レビューの強み：技術的誤りの発見、人が考えなかった論点。弱み：細部への過度なこだわり、長すぎる、式・表の読み違い、新規性・重要性の判断が弱い。出力の長さの制御と優先順位づけが課題 | 6 | 件数の上限、Major の基準、重大度は迷ったら低く、Minor の簡潔な形式 |
| LLM のレビューは技術的妥当性に注目が偏り、新規性の評価を大きく見落とす | 3 | 新規性専用のレンズ L2、統合時の観点分布の確認（`focus_profile`） |
| LLM は長い論文の処理と、批判的なフィードバックが苦手 | 2 | セグメント分割で一度に深く読む範囲を絞る |
| 課題：文書の解析と表現の不完全さ、深い論理推論の弱さ、人と計算機の対話の弱さ | 1 | 解析品質の警告（`init`）、深い検証の分業、レポート後の深掘り・再レビューの対話 |
| 課題：知識不足、楽観的な評価への偏り、幻覚・著者の主張の無批判な受け入れ、評価の不安定さ、データの機密性、投稿先に合わせた調整の難しさ | 5 | 反証検証、スコアを付けない、検索クエリに原稿の文章を入れない、`--venue` / `--focus` |
| AI と人の協働の4段階（著者向けツール → 査読者向けツール → 補助査読者 → 完全自動化）。パイロットは著者向けの投稿前ツールとして、公式の査読から切り離して実施 | 7 | 著者の投稿前チェックを主な用途とし、最終判断は人に残す。他人の原稿を査読者として扱う場合は投稿先の AI 方針の確認を促す |

## 再現していないもの

- Gemini Deep Think の並列思考そのもの（観点の異なる複数のサブエージェントと反証検証で近似している）
- 学習データや内部プロンプトに依存する部分
- 多ファイル入力、コメント表示の UI（HTML レポートの「ページ順」表示で簡易的に代替）
