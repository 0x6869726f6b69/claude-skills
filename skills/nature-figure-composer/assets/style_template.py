"""Display conventions shared by every figure script of the paper (copy to paper_figures/src/style.py).

Everything that must look identical across figures lives here, so that Fig. 1 and Fig. 4 cannot
drift apart: display names, the order of methods, colour limits of maps, axis labels with units.
Colours / markers per method live in figure_style.json (nfig.Palette), not here.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # project root (paper_figures/src/ -> ../..)
RESULTS = ROOT / "results"
OUT = ROOT / "paper_figures"
PALETTE = OUT / "figure_style.json"

# data name -> name printed in figures, legends and tables
DISPLAY = {
    "ours_v3_final": "Ours",
    "baseline_sota": "SOTA-X",
}
# fixed order: comparisons first, proposed method last (drawn on top, read last)
ORDER = ["Base A", "Base B", "SOTA-X", "Ours"]

# one colour range per physical quantity, shared by every map of that quantity in the paper
TEMP_LIM = (300.0, 345.0)        # K
ERR_LIM = (0.0, 6.0)             # K, |prediction - reference|

# axis labels: quantity (unit)
LABELS = {
    "rmse": "Temperature RMSE (K)",
    "time": "Inference time per sample (ms)",
    "n_train": "Training samples",
}


def display(name: str) -> str:
    return DISPLAY.get(name, name)
