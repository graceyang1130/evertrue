"""Self-scout: how often our defense blitzes on each down.

Reads a PFF play-by-play export of our defensive games (e.g.
self-scout/blitz_102926/brown_d26.csv) and draws one page:

  left   blitz rate on 1st, 2nd, 3rd and 4th down
  right  the same split by yards to go (1-2, 3-6, 7-10, 11+)

A blitz is PFF's pff_BLITZDOG tag. PFF only charts it on pass plays, so the
rate is blitzes / opponent pass plays. Counted: every scrimmage snap where we
were on defense, including snaps a post-snap penalty wiped out (the call was
still made). Left out: special teams and pre-snap penalties (no snap).

Writes blitz_by_down.png and blitz_by_down.csv next to the input file unless
--out says otherwise.

Usage:
    python self-scout/blitz_by_down.py self-scout/blitz_102926/brown_d26.csv
    python self-scout/blitz_by_down.py path/to/export.csv --out output/plots
"""

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Rectangle

TEAM_CODE = "RIBR"

TEAM = {
    "RIUN": "Rhode Island", "NJPR": "Princeton", "CTYA": "Yale",
    "DCGT": "Georgetown", "RIBT": "Bryant", "MAHA": "Harvard",
    "PAUN": "Penn", "NYCN": "Cornell", "NHDA": "Dartmouth",
    "NYCL": "Columbia", "CTNH": "New Haven", "CTCE": "Central Connecticut",
}

DOWNS = [1, 2, 3, 4]
DOWN_NAMES = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}
# Same buckets as the 3rd/4th-down packets (scripts/34analyze_new.py).
DISTANCE_CATEGORIES = ["1-2", "3-6", "7-10", "11+"]
DISTANCE_EDGES = [0, 2, 6, 10, np.inf]

# Below this many passes a rate is too thin to read as a tendency.
SMALL_SAMPLE = 10

BROWN = "#4b2e23"
INK = "#231f20"
MUTED = "#66615e"
GRID = "#ddd7d1"
PALE = "#f4f0ec"
WHITE = "#ffffff"


def team(code):
    return TEAM.get(code, code)


def load_snaps(path, team_code=TEAM_CODE):
    """Our defensive scrimmage snaps, one row each, with a distance bucket."""
    df = pd.read_csv(path, low_memory=False)
    snaps = df[
        (df["pff_DEFTEAM"] == team_code)
        & df["pff_SPECIALTEAMSTYPE"].isna()
        & df["pff_DOWN"].isin(DOWNS)
        & df["pff_RUNPASS"].isin(["P", "R"])  # X = pre-snap penalty, no snap
    ].copy()
    snaps["is_pass"] = snaps["pff_RUNPASS"].eq("P")
    snaps["blitz"] = snaps["pff_BLITZDOG"].eq(1)
    snaps["distance"] = pd.cut(snaps["pff_DISTANCE"], DISTANCE_EDGES,
                               labels=DISTANCE_CATEGORIES)
    return snaps


def rates(snaps, by):
    """Snaps, passes, blitzes and blitz rate (per pass) for each group in `by`."""
    out = snaps.groupby(by, observed=False).agg(
        snaps=("blitz", "size"),
        passes=("is_pass", "sum"),
        blitzes=("blitz", "sum"),
    )
    out["blitz_pct"] = 100 * out["blitzes"] / out["passes"].replace(0, np.nan)
    return out


def summary_table(snaps):
    """By-down rows (distance 'all') followed by down x distance rows."""
    by_down = rates(snaps, ["pff_DOWN"]).reset_index()
    by_down["distance"] = "all"
    by_cell = rates(snaps, ["pff_DOWN", "distance"]).reset_index()
    table = pd.concat([by_down, by_cell], ignore_index=True)
    table = table.rename(columns={"pff_DOWN": "down"})
    table["down"] = table["down"].map(DOWN_NAMES)
    table["blitz_pct"] = table["blitz_pct"].round(1)
    return table[["down", "distance", "snaps", "passes", "blitzes", "blitz_pct"]]


def games_line(snaps):
    """'6 games, Sep 19 - Oct 24, 2026: New Haven, Harvard, ...' in date order."""
    games = (snaps.drop_duplicates("pff_GAMEID")
             .assign(date=lambda g: pd.to_datetime(g["pff_GAMEDATE"]))
             .sort_values("date"))
    first, last = games["date"].iloc[0], games["date"].iloc[-1]
    span = f"{first:%b} {first.day} – {last:%b} {last.day}, {last.year}"
    names = ", ".join(team(code) for code in games["pff_OFFTEAM"])
    return f"{len(games)} games, {span}: {names}"


def draw_by_down(ax, snaps):
    by_down = rates(snaps, "pff_DOWN").reindex(DOWNS)
    top = by_down["blitz_pct"].max()
    x = np.arange(len(DOWNS))

    for i, down in enumerate(DOWNS):
        row = by_down.loc[down]
        thin = row["passes"] < SMALL_SAMPLE
        ax.bar(x[i], row["blitz_pct"], width=0.56, zorder=2,
               color=WHITE if thin else BROWN, edgecolor=BROWN,
               linewidth=1.4 if thin else 0, hatch="////" if thin else None)
        ax.text(x[i], row["blitz_pct"] + top * 0.025, f"{row['blitz_pct']:.0f}%",
                ha="center", va="bottom", fontsize=16, fontweight="bold", color=INK)

    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"{DOWN_NAMES[d]} down\n{int(by_down.loc[d, 'blitzes'])} of "
         f"{int(by_down.loc[d, 'passes'])} passes" for d in DOWNS],
        fontsize=10, color=INK)
    ax.tick_params(axis="x", length=0, pad=8)
    ax.set_ylim(0, top * 1.18)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%")
    ax.tick_params(axis="y", labelsize=9, colors=MUTED, length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)


def draw_by_distance(ax, snaps):
    cells = rates(snaps, ["pff_DOWN", "distance"])
    shade = LinearSegmentedColormap.from_list("brown", [PALE, BROWN])
    # Fill darkens up to 50%; anything above is as dark as it gets.
    ceiling = 50
    gap = 0.04

    for r, down in enumerate(DOWNS):
        for c, bucket in enumerate(DISTANCE_CATEGORIES):
            passes, blitzes, pct = cells.loc[(down, bucket), ["passes", "blitzes", "blitz_pct"]]
            x0, y0 = c + gap, r + gap
            size = 1 - 2 * gap
            if passes == 0:
                ax.add_patch(Rectangle((x0, y0), size, size, facecolor=WHITE,
                                       edgecolor=GRID, linewidth=1))
                ax.text(c + 0.5, r + 0.5, "no passes", ha="center", va="center",
                        fontsize=8.5, color=MUTED)
                continue
            if passes < SMALL_SAMPLE:
                face, edge, ink, sub = WHITE, GRID, INK, MUTED
            else:
                level = min(pct, ceiling) / ceiling
                face, edge = shade(level), None
                ink = WHITE if level > 0.45 else INK
                sub = WHITE if level > 0.45 else MUTED
            ax.add_patch(Rectangle((x0, y0), size, size, facecolor=face,
                                   edgecolor=edge or face, linewidth=1))
            ax.text(c + 0.5, r + 0.42, f"{pct:.0f}%", ha="center", va="center",
                    fontsize=15, fontweight="bold", color=ink)
            ax.text(c + 0.5, r + 0.72, f"{int(blitzes)} of {int(passes)}",
                    ha="center", va="center", fontsize=9, color=sub)

    ax.set_xlim(0, len(DISTANCE_CATEGORIES))
    ax.set_ylim(len(DOWNS), 0)
    ax.set_xticks(np.arange(len(DISTANCE_CATEGORIES)) + 0.5)
    ax.set_xticklabels([f"{b} yds" for b in DISTANCE_CATEGORIES], fontsize=10, color=INK)
    ax.xaxis.tick_top()
    ax.set_yticks(np.arange(len(DOWNS)) + 0.5)
    ax.set_yticklabels([f"{DOWN_NAMES[d]} down" for d in DOWNS], fontsize=10, color=INK)
    ax.tick_params(length=0, pad=6)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_aspect("equal")


def panel_title(fig, ax, title, note):
    """Bold heading and a muted line under it, both just above the axes box."""
    ax.apply_aspect()
    box = ax.get_position()
    fig.text(box.x0, 0.835, title, fontsize=12.5, fontweight="bold", color=INK, va="bottom")
    fig.text(box.x0, 0.83, note, fontsize=9, color=MUTED, va="top")


def draw_page(snaps, path):
    plt.rcParams["font.family"] = ["Arial", "DejaVu Sans"]
    fig = plt.figure(figsize=(13, 7.2), facecolor=WHITE)
    grid = fig.add_gridspec(1, 2, width_ratios=[1.1, 1], wspace=0.22,
                            left=0.05, right=0.97, top=0.72, bottom=0.16)
    by_down, by_distance = fig.add_subplot(grid[0]), fig.add_subplot(grid[1])
    draw_by_down(by_down, snaps)
    draw_by_distance(by_distance, snaps)

    passes, blitzes = int(snaps["is_pass"].sum()), int(snaps["blitz"].sum())
    fig.text(0.05, 0.955, "How often do we blitz on each down?", fontsize=20,
             fontweight="bold", color=INK, va="top")
    fig.text(0.05, 0.90,
             f"Brown defense · {games_line(snaps)}",
             fontsize=10, color=MUTED, va="top")
    panel_title(fig, by_down, "Blitz rate by down",
                f"All downs: {100 * blitzes / passes:.0f}% ({blitzes} blitzes on {passes} passes)")
    panel_title(fig, by_distance, "Same thing, split by yards to go",
                "Each box: blitz rate, then blitzes / passes. Darker = more blitzing.")
    fig.text(0.05, 0.055,
             f"Striped bar or white box: fewer than {SMALL_SAMPLE} passes, too few plays "
             "to call it a tendency.",
             fontsize=9, color=INK, va="top")
    fig.text(0.05, 0.03,
             "Blitz rate = opponent passes where we sent a blitz (PFF's blitz tag), out of all "
             "opponent passes. PFF doesn't tag blitzes on runs, so runs aren't counted. "
             "Special teams and pre-snap penalties are left out; plays called back by a "
             "post-snap penalty count.",
             fontsize=8, color=MUTED, va="top")

    fig.savefig(path, dpi=200, facecolor=WHITE)
    plt.close(fig)
    print(f"[saved] {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="PFF play-by-play export of our defensive games")
    parser.add_argument("--team", default=TEAM_CODE, help="PFF code of the defense to scout")
    parser.add_argument("--out", type=Path, help="folder for the outputs (default: next to the csv)")
    args = parser.parse_args()

    snaps = load_snaps(args.csv, args.team)
    out_dir = args.out or args.csv.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    table = summary_table(snaps)
    table.to_csv(out_dir / "blitz_by_down.csv", index=False)
    print(table[table["distance"] == "all"].to_string(index=False))
    print(f"[saved] {out_dir / 'blitz_by_down.csv'}")

    draw_page(snaps, out_dir / "blitz_by_down.png")


if __name__ == "__main__":
    main()
