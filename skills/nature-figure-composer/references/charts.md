# グラフ形式の選び方と nfig レシピ

目次: 1. 主張の型 → グラフ / 2. 不確実性と統計 / 3. 軸・目盛り・ラベル / 4. 凡例と直接ラベル /
5. レシピ集（コード） / 6. nfig API 早見表

前提: `import nfig, numpy as np; nfig.use_style(); pal = nfig.Palette.load("paper_figures/figure_style.json")`

---

## 1. 主張の型 → グラフ

| 言いたいこと | 第一候補 | 避けるもの |
|---|---|---|
| A は B より良い（少数条件） | 個々の点＋平均±SD（`points_summary`） | 点のない棒グラフ |
| 多数の条件・データセットで一貫して良い | 横向きドットプロット（条件 × 手法）、改善量の heatmap | データセットごとの別グラフの羅列 |
| 条件ごとの対応のある改善 | slopegraph（baseline → ours を線で結ぶ） | 2本の棒を並べるだけ |
| 精度とコストの両立 | 散布図（コストは対数軸）＋パレート前線 | 2つの別々の棒グラフ |
| スケーリング・桁違いの差 | log–log の折れ線＋傾き | 線形軸で潰れた曲線 |
| 時間・反復による変化 | 平均線＋帯（`line_band`） | 全反復のスパゲッティ |
| 分布の違い | box＋全点（`box_strip`）、violin、ECDF | 平均だけの棒 |
| 予測と真値の一致 | parity plot（`scatter_identity`、点が多ければ hexbin） | 2系列の折れ線 |
| 2要因のパターン | heatmap（基準値があれば発散カラーマップを基準で中心化） | 3D 棒 |
| 各要素の寄与（アブレーション） | 完全モデルとの差 Δ の横向きドット＋CI、ゼロ線、効果順に並べる | 絶対値の棒の羅列 |
| 構成比 | 横向き積み上げ棒 | 円グラフ（多項目）、3D |
| 定性的な違い | 同じ切り出し・同じスケールの画像グリッド（GT / 従来 / 提案 / 誤差マップ） | 都合のよい1例だけ |

## 2. 不確実性と統計

- 平均だけを示さない。誤差棒の定義（SD / s.e.m. / 95% CI）を選び、Caption に書く。
  ばらつきの大きさを見せたいなら SD、平均の推定精度なら 95% CI。s.e.m. は小さく見えるので慎重に。
- n が ~30 以下なら個々のデータ点を重ねる。n は「何の反復か」（独立な試料、乱数シード、
  被験者、データセット）を明記する。技術的反復を独立反復として数えない。
- 検定の目安: 2群の独立比較 → Welch の t 検定 / Mann–Whitney U、対応あり → 対応のある t 検定 /
  Wilcoxon 符号順位、複数データセットにわたる手法比較 → データセット単位の Wilcoxon（Demšar 2006）、
  多重比較 → Holm または Benjamini–Hochberg。両側/片側を明記し、P 値は正確な値で（`nfig.fmt_p`）。
- 生データがなく統計を計算できないときは、値を作らず `[AUTHOR TODO: n と検定を確認]` を残す。

## 3. 軸・目盛り・ラベル

- 軸ラベルは「量 (単位)」: `Time (s)`, `Error (%)`, `Concentration (µM)`。無次元なら単位なし。
- 目盛りは 3–5 本。目盛りの数値は短く（0.80 より 0.8、1000000 より 10⁶ や単位の変更）。
- 棒グラフは必ず 0 から。点や線のグラフはデータ範囲に合わせてよいが、差を誇張しない範囲で。
- 2 桁以上にわたる量（時間、メモリ、誤差、データ量）は対数軸。
- 同じ指標は Figure 内・Figure 間で同じ範囲にする（`sharey=True` や `set_ylim` を共通化）。
- 回転した目盛りラベルは最後の手段。ラベルを短くする、横向きグラフにする、略語を Caption で定義する。
- グラフ内のタイトルは原則なし（Caption に書く）。小さな条件名（"CIFAR-10" 等）は可。

## 4. 凡例と直接ラベル

- 手法の凡例は Figure 全体で1つ: `nfig.shared_legend(fig, pal.handles([...]))`（最上段に横一列）。
- 線が 5 本以下なら線の端に黒文字で直接ラベル: `nfig.end_labels(ax, [(x_end, y_end, "Ours"), ...])`。
- 色付き文字は使わない（Nature の方針）。色の説明は図中の凡例で行い、Caption に色名だけで頼らない。

---

## 5. レシピ集

### 5.1 少数群の比較（点＋平均±SD）
```python
data = {"Base A": a, "SOTA-X": s, "Ours": o}           # 各群の観測値（n 個）
nfig.points_summary(ax, data, pal=pal, summary="mean_sd")
ax.set_ylabel("Accuracy (%)")
nfig.sig_bracket(ax, 1, 2, y=o.max() + 0.5, text=nfig.fmt_p(p))
```

### 5.2 多数データセット × 手法（横向きドットプロット）
```python
datasets = list(df.Dataset.unique())
methods = ["Base B", "Base A", "SOTA-X", "Ours"]        # 下から描くと Ours が最前面
off = np.linspace(-0.24, 0.24, len(methods))
for k, m in enumerate(methods):
    d = df[df.Method == m].set_index("Dataset").loc[datasets]
    ax.errorbar(d.acc_mean, np.arange(len(datasets)) + off[k], xerr=d.acc_std,
                fmt=pal[m]["marker"], color=pal.color(m), ms=3.5, mec="white", mew=0.4,
                elinewidth=0.6, capsize=0, zorder=pal[m]["zorder"], label=m)
ax.set_yticks(range(len(datasets)), datasets)
ax.invert_yaxis()
ax.set_xlabel("Accuracy (%)")
nfig.shared_legend(fig, pal.handles(methods[::-1], kind="marker"))   # 線なし・マーカーだけの凡例
```

### 5.3 対応のある改善（slopegraph）
```python
for ds, b, o in zip(datasets, base_vals, ours_vals):
    ax.plot([0, 1], [b, o], color=nfig.GREYS[2], lw=0.6, zorder=1)
ax.scatter(np.zeros(len(base_vals)), base_vals, **pal.scatter("SOTA-X"))
ax.scatter(np.ones(len(ours_vals)), ours_vals, **pal.scatter("Ours"))
ax.set_xticks([0, 1], ["SOTA-X", "Ours"]); ax.set_xlim(-0.3, 1.3)
```

### 5.4 精度–コストのトレードオフ
```python
for m in methods:
    ax.scatter(cost[m], acc[m], **pal.scatter(m, s=18))
ax.set_xscale("log")
ax.set_xlabel("Inference time per sample (ms)"); ax.set_ylabel("Accuracy (%)")
# パレート前線（任意）: コスト昇順に累積最大精度を結ぶ
```

### 5.5 学習曲線・時系列（平均＋帯）
```python
for m in ["Base A", "SOTA-X", "Ours"]:
    nfig.line_band(ax, epochs, curves[m], band="sd", style=pal.line(m, marker=None))
ax.axhline(upper_bound, **pal.line("Oracle"))
nfig.end_labels(ax, [(epochs[-1], curves[m].mean(0)[-1], m) for m in ["Base A", "SOTA-X", "Ours"]])
```

### 5.6 スケーリング（log–log と傾き）
```python
ax.loglog(n, err, **pal.line("Ours"))
k, c = np.polyfit(np.log10(n), np.log10(err), 1)
ax.loglog(n, 10 ** c * n ** k, color="black", lw=0.6, ls="--")
ax.text(0.95, 0.9, f"slope = {k:.2f}", transform=ax.transAxes, ha="right")
```

### 5.7 アブレーション（完全モデルとの差）
```python
order = np.argsort(delta)                                # 影響の大きい順
y = np.arange(len(order))
ax.errorbar(delta[order], y, xerr=ci[order], fmt="o", color=nfig.COLORS["accent"],
            ms=3.5, elinewidth=0.6, capsize=0)
ax.axvline(0, color="black", lw=0.5)
ax.set_yticks(y, [names[i] for i in order]); ax.set_xlabel("Δ accuracy vs full model (pt)")
```

### 5.8 分布（box＋全点）
```python
nfig.box_strip(ax, {"Control": c, "Treated": t}, pal=pal)
ax.set_ylabel("Expression (a.u.)")
```

### 5.9 予測 vs 真値
```python
nfig.scatter_identity(ax, y_true, y_pred, metrics=("r2", "mae"), unit="K")
ax.set_xlabel("Measured temperature (K)"); ax.set_ylabel("Predicted temperature (K)")
```

### 5.10 heatmap（基準からの差）
```python
nfig.heatmap(ax, delta_matrix, row_labels, col_labels, center=0, annotate=True,
             fmt="{:.1f}", cbar_label="Δ accuracy (pt)")
```
基準のない量は `center=None`（viridis）。値の注釈は 5×10 程度まで、それ以上はカラーバーのみ。

### 5.11 場のマップと定性比較（GT / 比較手法 / 提案 / 誤差）
```python
from style import TEMP_LIM, ERR_LIM            # 全Figureで共通の色範囲（paper_figures/src/style.py）
fig, axd = nfig.figure("double", 75, mosaic="bcd;efg")   # 同種の行は1つのグリッドで列を揃える
ext = (0, 1.5, 0, 1.0)                          # 物理座標 (x0, x1, y0, y1) → 縦横比が正しくなる
for k, (name, Z) in zip("bcd", [("CFD", gt), ("SOTA-X", sota), ("Ours", ours)]):
    imT = nfig.field(axd[k], Z, extent=ext, vmin=TEMP_LIM[0], vmax=TEMP_LIM[1], title=name)
nfig.colorbar(imT, [axd[k] for k in "bcd"], "Temperature (K)")      # 同じ量には1本
for k, Z in zip("efg", [abs(sota - gt), abs(ours - gt), abs(base - gt)]):
    imE = nfig.field(axd[k], Z, extent=ext, vmin=ERR_LIM[0], vmax=ERR_LIM[1], cmap="magma")
nfig.colorbar(imE, [axd[k] for k in "efg"], "|Error| (K)")
```
- マップだけの行が並ぶなら1つの mosaic（列が揃う）。模式図やグラフの行と混ざるときだけ
  `rows=` で行を分ける（そうしないとグラフの余白がマップの列に入り込んでマップが潰れる）。
- 同じ量のマップは Figure 内でも Figure 間でも同じ `vmin/vmax`（style.py に定義）。比較が公平になる。
- 符号付きの量（予測 − 真値）は `center=0`（発散カラーマップ）、大きさ（|誤差|、密度）は順序カラーマップ。
- `field` は `imshow(interpolation="nearest")`: PDF では 600 dpi に再標本化されセルがくっきり出る。
  不規則格子で `pcolormesh` が必要なときは `rasterized=True`（ベクターのままだとセル間に白い筋が出る）。
- データの格子は 300 dpi に満たなくてよい（300 dpi 規定は写真用）。写真・顕微鏡像は `nfig.image_panel`。
- 列見出し（CFD / SOTA-X / Ours）は `title=` で短く。例の選び方（ランダム、誤差の中央値付近など）を
  Caption に書き、都合のよい1例だけを選ばない。

### 5.12 拡大インセット
```python
axin = ax.inset_axes([0.55, 0.12, 0.4, 0.4])
axin.plot(x, y, **pal.line("Ours", label=False)); axin.set_xlim(x0, x1); axin.set_ylim(y0, y1)
ax.indicate_inset_zoom(axin, edgecolor="black", linewidth=0.5)
```

---

## 6. nfig API 早見表

| 関数 | 用途 |
|---|---|
| `use_style(base_pt=7, small_pt=6)` | rcParams 一式（Arial、0.5 pt 軸、TrueType 42、グリッドなし） |
| `figure(width, height_mm, mosaic=..., width_ratios=..., height_ratios=...)` | 最終サイズの Figure（constrained layout） |
| `figure(width, height_mm, rows=[(mosaic, share[, kw]), ...])` | 行ごとに独立したレイアウト（種類の違うパネルが混在する図） |
| `Palette.load_or_build(path, proposed, highlight, baselines, references)` | 意味固定の配色。`pal.line(m)`, `pal.scatter(m)`, `pal.color(m)`, `pal.handles([...], kind="line"/"marker"/"patch", **override)` |
| `points_summary`, `box_strip`, `line_band`, `scatter_identity`, `heatmap` | 主要グラフ |
| `field(ax, Z, extent=, vmin=, vmax=, center=)` / `colorbar(im, axes, label)` | 場のマップと共通カラーバー |
| `image_panel(ax, path, crop=, scalebar=)` | 写真・外部図の埋め込み |
| `pipeline(ax, stages, highlight=, y=, lane_label=)` | 概要図の箱と矢印 |
| `end_labels`, `shared_legend`, `sig_bracket`, `fmt_p`, `tint` | 注釈・凡例 |
| `label_panels(fig, axd)` | パネルラベル（最後に呼ぶ） |
| `save(fig, stem)` / `qa(fig)` | 保存と自動QA |
| `cvd_report(colors)` | 色の組の色覚シミュレーション下での最小色差 |
