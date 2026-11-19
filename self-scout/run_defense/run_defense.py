"""Self-scout: where do teams run on us?

One page, three views of opponent runs:
  top           where the ball went (PFF's point of attack, offense's left
                to right): carries, yards per carry, offense success, 10+ runs
  bottom left   the same results by run play (inside zone, power, ...)
  bottom right  the same results by how many we had in the box

Runs that stood only (no penalty wiped them out); kneel-downs are dropped,
and scrambles are passes, so they aren't here. Jet sweeps, reverses and QB
sneaks have no gap, so they're left off the top chart but count by run play.

Writes run_defense.png and run_defense.csv in this folder.

Usage:
    python self-scout/run_defense/run_defense.py "self-scout/blitz_102926/play_feed (1).csv"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from scout_common import (BIG_RUN, BROWN, GRID, INK, MUTED, SMALL_SAMPLE, SUCCESS_RULE,
                          TEAM_CODE, board, footer, games_line, load_snaps, out_dir_for, row, save,
                          start_page)

# PFF point-of-attack codes, offense's left to right.
GAPS = [("LE", "Left end"), ("LT", "Left tackle"), ("LG", "Left guard"),
        ("ML", "Middle left"), ("MR", "Middle right"), ("RG", "Right guard"),
        ("RT", "Right tackle"), ("RE", "Right end")]


def results(runs):
    return pd.Series({
        "carries": len(runs),
        "yards_per_carry": runs["gain"].mean() if len(runs) else np.nan,
        "success_pct": 100 * runs["off_success"].mean() if len(runs) else np.nan,
        "big_runs": int(runs["explosive"].sum()),
    })


def run_tables(runs):
    gaps = pd.DataFrame([results(runs[runs["pff_POAACTUAL"] == code]).rename(label)
                         for code, label in GAPS])

    concept = runs["pff_RUNCONCEPTPRIMARY"].str.capitalize()
    counts = concept.value_counts()
    named = [c for c in counts.index if counts[c] >= SMALL_SAMPLE
             and c not in ("Undefined", "No video")]
    concepts = pd.DataFrame([results(runs[concept == c]).rename(c) for c in named]
                            + [results(runs[~concept.isin(named)]).rename("Everything else")])

    box = runs["box"]
    boxes = pd.DataFrame([
        results(runs[box <= 5]).rename("5 or fewer"),
        results(runs[box == 6]).rename("6"),
        results(runs[box == 7]).rename("7"),
        results(runs[box >= 8]).rename("8 or more"),
    ])
    return gaps, concepts, boxes


def short_answer(gaps):
    middle = gaps.loc[["Middle left", "Middle right"], "carries"].sum()
    enough = gaps[gaps["carries"] >= SMALL_SAMPLE]
    best = enough["yards_per_carry"].idxmax()
    worst = enough["yards_per_carry"].idxmin()
    return (f"{100 * middle / gaps['carries'].sum():.0f}% of runs go up the middle. Offenses "
            f"average the most at the {best.lower()} ({enough.loc[best, 'yards_per_carry']:.1f} "
            f"yards a carry) and the least at the {worst.lower()} "
            f"({enough.loc[worst, 'yards_per_carry']:.1f}).")


def draw_gaps(fig, rect, gaps):
    """Carries as columns across the line, results in a strip underneath."""
    ax = fig.add_axes(rect)
    x = np.arange(len(gaps))
    top = gaps["carries"].max()
    for i, (label, r) in enumerate(gaps.iterrows()):
        small = r["carries"] < SMALL_SAMPLE
        ax.bar(x[i], r["carries"], width=0.55, zorder=2, color="white" if small else BROWN,
               edgecolor=BROWN, linewidth=1.2 if small else 0, hatch="////" if small else None)
        ax.text(x[i], r["carries"] + top * 0.03, f"{int(r['carries'])}", ha="center",
                va="bottom", fontsize=12, fontweight="bold", color=INK)
    ax.set_xlim(-0.6, len(gaps) - 0.4)
    ax.set_ylim(0, top * 1.25)
    ax.set_xticks(x)
    ax.set_xticklabels(gaps.index, fontsize=10, color=INK)
    ax.tick_params(axis="x", length=0, pad=6)
    ax.set_yticks([])
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.set_title("Carries by where the ball went (offense's left → offense's right)",
                 loc="left", fontsize=11.5, fontweight="bold", color=INK, pad=8)

    # results strip, one line per measure, aligned under each column
    lines = [("Yards per carry", lambda r: f"{r['yards_per_carry']:.1f}"),
             ("Offense success", lambda r: f"{r['success_pct']:.0f}%"),
             (f"Runs of {BIG_RUN}+", lambda r: f"{int(r['big_runs'])}")]
    for j, (name, fmt) in enumerate(lines):
        y = -0.22 - 0.13 * j
        ax.text(-0.6, y, name, transform=ax.get_xaxis_transform(), ha="right", va="center",
                fontsize=9.5, color=MUTED)
        for i, (_, r) in enumerate(gaps.iterrows()):
            ax.text(x[i], y, fmt(r), transform=ax.get_xaxis_transform(), ha="center",
                    va="center", fontsize=10, color=INK)


def board_rows(table):
    return [(None, [row(name, r["yards_per_carry"], int(r["carries"]),
                        text=f"{r['yards_per_carry']:.1f} yds · {r['success_pct']:.0f}% success · "
                             f"{int(r['big_runs'])} of {BIG_RUN}+ · {int(r['carries'])} carries")
                    for name, r in table.iterrows()])]


def draw(runs, gaps, concepts, boxes, path):
    width, height = 14, 11.2
    fig, top = start_page(width, height, "Where do teams run on us?", short_answer(gaps),
                          f"{games_line(runs)} · {len(runs)} opponent runs")
    draw_gaps(fig, [1.9 / width, 6.4 / height, (width - 2.5) / width,
                    (height - 6.4 - top - 0.65) / height], gaps)

    xmax = max(concepts["yards_per_carry"].max(), boxes["yards_per_carry"].max()) * 2.3
    ax = fig.add_axes([1.9 / width, 1.35 / height, 4.0 / width, 2.9 / height])
    board(ax, board_rows(concepts), title="By run play: yards per carry", fmt="{:.0f}",
          xmax=xmax)
    ax = fig.add_axes([9.0 / width, 1.35 / height, 4.0 / width, 2.9 / height])
    board(ax, board_rows(boxes), title="By players in our box: yards per carry", fmt="{:.0f}",
          xmax=xmax)
    footer(fig, [
        SUCCESS_RULE,
        f"Striped: fewer than {SMALL_SAMPLE} carries, too few to call it.",
        "Where the ball went is PFF's point of attack, from the offense's side. Jet sweeps, "
        "reverses and sneaks have no gap and are left off the top chart. Kneel-downs and "
        "plays wiped out by a penalty are left out.",
    ])
    save(fig, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="PFF play-by-play export of our defensive games")
    parser.add_argument("--team", default=TEAM_CODE, help="PFF code of the defense to scout")
    parser.add_argument("--out", help="folder for the outputs (default: this script's folder)")
    args = parser.parse_args()

    snaps = load_snaps(args.csv, args.team)
    runs = snaps[~snaps["is_pass"] & snaps["counts"]]
    out_dir = out_dir_for(__file__, args.out)

    gaps, concepts, boxes = run_tables(runs)
    table = pd.concat([gaps.assign(view="where the ball went"),
                       concepts.assign(view="run play"),
                       boxes.assign(view="players in our box")])
    table.rename_axis("group").reset_index().round(1).to_csv(out_dir / "run_defense.csv",
                                                             index=False)
    print(table.round(1).to_string())
    draw(runs, gaps, concepts, boxes, out_dir / "run_defense.png")


if __name__ == "__main__":
    main()
