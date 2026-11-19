"""Preview an extra Ivy conversion marker without changing the plot generator.

Run from the repository root with MPLCONFIGDIR=/private/tmp/evertrue-mpl.
All existing Cornell bars, labels, and Ivy call-share ticks use the current
34analyze_new.py implementation. Only the Ivy overlay and its key are extended.
"""

import importlib.util
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("analyze", ROOT / "scripts/34analyze_new.py")
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)
OUT = ROOT / "output/plots/ivy_comparison_preview"
SOURCE = ROOT / "3rd_4th_down/2026/cornell_26"
original_save = analyze._save


def preview(team, ivy, down, label):
    _, ivy_rates = analyze._ivy_benchmarks(ivy, down)
    bins = list(range(1, 15)) + ["15+"]
    expected = []
    for key, offset in (("pass", 0), ("run", .35)):
        for i, distance in enumerate(bins):
            selection = (team[team.pff_DISTANCE >= 15] if distance == "15+"
                         else team[team.pff_DISTANCE == distance])
            _, p, r, s = analyze._split_plays(selection, down)
            count = len(p if key == "pass" else r)
            total = len(p) + len(r) + len(s)
            rate = ivy_rates[key][i]
            if count and total and np.isfinite(rate):
                # Use Cornell's share, not Ivy's share, to put the expected
                # boundary on the exact same scale as Cornell's solid fill.
                expected.append((i + offset + .35 * .30, 100 * count / total * rate))

    def save_with_overlay(fig_path, out_dir, show, **kwargs):
        ax = plt.gca()
        for x, y in expected:
            ax.plot(x, y, marker="D", markersize=5, markerfacecolor="white",
                    markeredgecolor="#2d2d2d", markeredgewidth=1.3,
                    linestyle="none", zorder=6)
        old = ax.get_legend()
        handles = list(old.legend_handles)
        handles.append(Line2D([], [], marker="D", markersize=5,
                             markerfacecolor="white", markeredgecolor="#2d2d2d",
                             markeredgewidth=1.3, linestyle="none",
                             label="Ivy conversion at Cornell mix"))
        ax.legend(handles=handles, ncol=4, fontsize=8.5, loc="lower center",
                  bbox_to_anchor=(.5, 1.02), frameon=False)
        original_save(fig_path, out_dir, show, **kwargs)

    analyze._save = save_with_overlay
    try:
        analyze.play_mix_and_conversion(team, down, label, str(OUT), ivy_df=ivy)
    finally:
        analyze._save = original_save


for filename, side, seasons in (
    ("cornell_o.csv", "offense", "2024-2026"),
    ("cornell_d26.csv", "defense", "2026"),
    ("cornell_d2325.csv", "defense", "2023-2025"),
):
    raw = pd.read_csv(SOURCE / filename, low_memory=False)
    low, high = (int(seasons.split("-")[0]), int(seasons.split("-")[-1]))
    years = pd.to_numeric(raw.pff_GAMESEASON, errors="coerce")
    raw = raw[years.between(low, high)]
    team = analyze.clean_data(raw)
    ivy_path = analyze.IVY_OFFENSE_PATH if side == "offense" else analyze.IVY_DEFENSE_PATH
    ivy = analyze.clean_data(pd.read_csv(ivy_path, usecols=analyze.REQUIRED_COLUMNS, low_memory=False))
    for down in (3, 4):
        preview(team, ivy, down, f"Cornell {side} ({seasons})")

