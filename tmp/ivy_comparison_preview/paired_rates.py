"""Prototype explicit Cornell/Ivy conversion rates below the call-share plot."""

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
OUT = ROOT / "output/plots/ivy_comparison_preview/paired_rates"
SOURCE = ROOT / "3rd_4th_down/2026/cornell_26"
original_save = analyze._save


def preview(team, ivy, down, label):
    _, ivy_rates = analyze._ivy_benchmarks(ivy, down)
    bins = list(range(1, 15)) + ["15+"]
    rates = {"pass": [], "run": []}
    expected = []
    for i, distance in enumerate(bins):
        selection = (team[team.pff_DISTANCE >= 15] if distance == "15+"
                     else team[team.pff_DISTANCE == distance])
        _, p, r, s = analyze._split_plays(selection, down)
        total = len(p) + len(r) + len(s)
        for key, frame, offset in (("pass", p, 0), ("run", r, .35)):
            rate = (frame.pff_FIRST_DOWN_GAINED == 1).mean() if len(frame) else np.nan
            rates[key].append(rate)
            ivy_rate = ivy_rates[key][i]
            if len(frame) and total and np.isfinite(ivy_rate):
                expected.append((i + offset + .35 * .30,
                                 100 * len(frame) / total * ivy_rate))

    def save_with_strip(fig_path, out_dir, show, **kwargs):
        fig = plt.gcf()
        ax = plt.gca()
        for x, y in expected:
            ax.plot(x, y, marker="D", markersize=5, markerfacecolor="white",
                    markeredgecolor="#2d2d2d", markeredgewidth=1.3,
                    linestyle="none", zorder=6)
        handles = list(ax.get_legend().legend_handles)
        handles.append(Line2D([], [], marker="D", markersize=5,
                             markerfacecolor="white", markeredgecolor="#2d2d2d",
                             markeredgewidth=1.3, linestyle="none",
                             label="Ivy conversion at Cornell mix"))
        ax.legend(handles=handles, ncol=4, fontsize=8.5, loc="lower center",
                  bbox_to_anchor=(.5, 1.02), frameon=False)

        fig.set_size_inches(13, 8.7)
        fig.subplots_adjust(left=.065, right=.985, bottom=.26, top=.89)
        strip = fig.add_axes([.065, .035, .92, .105])
        strip.set_xlim(ax.get_xlim())
        strip.set_ylim(0, 2)
        strip.set_axis_off()
        heading = "CONVERSION RATE ALLOWED" if "defense" in label else "CONVERSION RATE"
        fig.text(.065, .165, heading, fontsize=9, fontweight="bold", color="#222222")
        fig.text(.265, .165, "Cornell / Ivy  ·  converted ÷ calls within each play type",
                 fontsize=8.5, color="#555555")
        for i in range(len(bins)):
            if i % 2 == 0:
                strip.axvspan(i - .325, i + .675, color="#f3f3f3", zorder=0)
        strip.axhline(1, color="#dddddd", linewidth=.6)
        for key, y, color in (("pass", 1.5, analyze.PASS_COLOR),
                              ("run", .5, analyze.RUN_COLOR)):
            strip.text(-.016, y / 2, key.title(), transform=strip.transAxes,
                       ha="right", va="center", fontsize=8, color=color,
                       fontweight="bold")
            for i, (team_rate, ivy_rate) in enumerate(zip(rates[key], ivy_rates[key])):
                x = i + .175
                team_text = f"{team_rate:.0%}" if np.isfinite(team_rate) else "—"
                ivy_text = f"{ivy_rate:.0%}" if np.isfinite(ivy_rate) else "—"
                strip.text(x - .045, y, team_text, ha="right", va="center",
                           fontsize=7.7, fontweight="bold", color="#222222")
                strip.text(x, y, "/", ha="center", va="center", fontsize=7.7,
                           color="#999999")
                strip.text(x + .045, y, ivy_text, ha="left", va="center",
                           fontsize=7.7, color="#666666")
        fig.text(.065, .009, "— = no calls in that sample. Rates rounded to whole percentages.",
                 fontsize=7, color="#666666")
        original_save(fig_path, out_dir, show, tight=False)

    analyze._save = save_with_strip
    try:
        analyze.play_mix_and_conversion(team, down, label, str(OUT), ivy_df=ivy)
    finally:
        analyze._save = original_save


for filename, side, seasons, down in (
    ("cornell_o.csv", "offense", "2024-2026", 3),
    ("cornell_d26.csv", "defense", "2026", 4),
):
    team = analyze.clean_data(pd.read_csv(SOURCE / filename, low_memory=False))
    ivy_path = analyze.IVY_OFFENSE_PATH if side == "offense" else analyze.IVY_DEFENSE_PATH
    ivy = analyze.clean_data(pd.read_csv(ivy_path, usecols=analyze.REQUIRED_COLUMNS, low_memory=False))
    preview(team, ivy, down, f"Cornell {side} ({seasons})")
