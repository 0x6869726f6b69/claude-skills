# Figure plan — <論文の仮タイトル>

- Thesis (1 sentence): <この論文が示すこと>
- Target journal / column width: <Nature, 2-column 183 mm>
- Palette roles (paper_figures/figure_style.json): proposed = <Ours>; highlight = <最強の比較手法>;
  baselines = <...>; references = <oracle / chance / theory>
- Decided by: <ユーザー指定 / おまかせ（Claude が設計）>

## Story arc

| Fig. | Role (What/How/Why/Performance/Impact) | Claim (= caption title sentence) |
|---|---|---|
| 1 | What | <...> |
| 2 | How / Why | <...> |
| 3 | Performance | <...> |
| 4 | Impact / limits | <...> |

## Fig. N — <claim sentence>

- Size: <183> × <120> mm, mosaic `"aab;cde"`, width_ratios <...>, height_ratios <...>
- Hero: panel <a> — <なぜこれが主張を最も直接に証明するか>

| Panel | Content | Chart type | Data source | Role | Notes |
|---|---|---|---|---|---|
| a | <...> | <line + band> | <results/curves.npz> | hero | <sharey with b> |
| b | <...> | <points + mean ± s.d.> | <results/benchmark.csv> | support | <P value: Welch t-test> |

- Shared legend: <Ours, SOTA-X, Base A, Base B, Oracle>（上段に横一列）
- Concrete example paired with the numbers: <panel e: example reconstructions>
- Limitations shown: <panel / SI Fig. x>

## Moved to Supplementary (and why)

| Result | Destination | Reason |
|---|---|---|
| <#7 hyper-parameter sweep> | <Supplementary Fig. 2> | <主張の証拠ではなく実装詳細> |

## Open items

- [AUTHOR TODO] <n とその単位（シード/試料）を確認>
- [AUTHOR TODO] <誤差棒は SD か 95% CI か>
- <再描画できなかった図と必要な元データ>
