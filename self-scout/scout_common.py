"""Shared loading and drawing for the defensive self-scout pages.

Each study lives in its own folder (blitz_tells/, blitz_results/, run_defense/,
situations/, explosives/) and imports this module. They all read the same PFF
play-by-play export of our defensive games, e.g.
self-scout/blitz_102926/play_feed (1).csv (2025 + 2026).

Which snaps count:
  - our scrimmage snaps on defense, downs 1-4 (no special teams)
  - kneel-downs, spikes and pre-snap penalties (no snap) are dropped
  - snaps wiped out by a post-snap penalty stay in for tendencies (the call
    was made) but are left out of results (yards, success, big plays), using
    the `counts` column
"""

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle
from matplotlib.transforms import blended_transform_factory

TEAM_CODE = "RIBR"

TEAM = {
    "RIUN": "Rhode Island", "NJPR": "Princeton", "CTYA": "Yale",
    "DCGT": "Georgetown", "RIBT": "Bryant", "MAHA": "Harvard",
    "PAUN": "Penn", "NYCN": "Cornell", "NHDA": "Dartmouth",
    "NYCL": "Columbia", "CTNH": "New Haven", "CTCE": "Central Connecticut",
}

DOWN_NAMES = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}
# Same buckets as the 3rd/4th-down packets (scripts/34analyze_new.py).
DISTANCE_CATEGORIES = ["1-2", "3-6", "7-10", "11+"]
DISTANCE_EDGES = [0, 2, 6, 10, np.inf]

RUSH_ORDER = ["3-man rush", "4-man rush", "4-man rush + stunt",
              "Sim pressure", "5-man blitz", "6+ man blitz"]

# A big play: a run of 10+ yards or a pass (scrambles included) of 20+.
BIG_RUN, BIG_PASS = 10, 20

# PFF's success grade (pff_OFFSUCCESS), checked against every play in the export:
# 40% of the yards to go on 1st down, 50% on 2nd, all of it on 3rd/4th; turnovers
# are never a success and penalty yards don't count.
SUCCESS_RULE = ("Offense success = the play gained at least 40% of the yards to go on 1st down "
                "(4 on 1st & 10), half on 2nd, or all of it on 3rd and 4th. Turnovers never "
                "count, and penalty yards don't count (PFF's grade).")

# Rows built from fewer plays than this are striped: too few to call a tendency.
SMALL_SAMPLE = 20

BROWN = "#4b2e23"
TAN = "#b9a08f"
INK = "#231f20"
MUTED = "#66615e"
GRID = "#ddd7d1"
PALE = "#f4f0ec"
WHITE = "#ffffff"


def team(code):
    return TEAM.get(code, code)


def player(code):
    """'RIBR D23' -> '#23'."""
    if not isinstance(code, str):
        return ""
    return "#" + code.split()[-1].lstrip("D")


def load_snaps(path, team_code=TEAM_CODE):
    """Our defensive scrimmage snaps, one row each, with the columns the studies use."""
    df = pd.read_csv(path, low_memory=False)
    snaps = df[
        (df["pff_DEFTEAM"] == team_code)
        & df["pff_SPECIALTEAMSTYPE"].isna()
        & df["pff_DOWN"].isin(DOWN_NAMES)
        & df["pff_RUNPASS"].isin(["P", "R"])  # X = pre-snap penalty, no snap
        & df["pff_POAACTUAL"].ne("QB KNEEL")
        & df["pff_PASSRESULT"].ne("SPIKE")
    ].copy()

    snaps["season"] = snaps["pff_GAMESEASON"]
    snaps["date"] = pd.to_datetime(snaps["pff_GAMEDATE"])
    snaps["opponent"] = snaps["pff_OFFTEAM"].map(team)
    snaps["is_pass"] = snaps["pff_RUNPASS"].eq("P")
    snaps["counts"] = snaps["pff_NOPLAY"].eq(0)
    snaps["gain"] = snaps["pff_GAINLOSSNET"]

    snaps["blitz"] = snaps["pff_BLITZDOG"].eq(1)
    snaps["stunt"] = snaps["pff_STUNT"].eq(1)
    snaps["rushers"] = pd.to_numeric(snaps["pff_PASSRUSHPLAYERS"].str.split(";").str[0],
                                     errors="coerce")
    snaps["rush"] = np.select(
        [~snaps["is_pass"],
         snaps["blitz"] & (snaps["rushers"] <= 4),
         snaps["blitz"] & (snaps["rushers"] == 5),
         snaps["blitz"],
         snaps["rushers"] <= 3,
         snaps["stunt"]],
        [None, "Sim pressure", "5-man blitz", "6+ man blitz", "3-man rush",
         "4-man rush + stunt"],
        default="4-man rush")

    snaps["box"] = pd.to_numeric(snaps["pff_BOXPLAYERS"].str.split(";").str[0], errors="coerce")
    snaps["press"] = snaps["pff_PRESS"].notna()
    # PFF's DB depths are fixed by label: FS* sits deep (12), SS* rolled down (8).
    db_labels = snaps["pff_DBDEPTH"].fillna("").str.findall(r"(\w+) \(")
    snaps["deep_safeties"] = db_labels.map(lambda labels: sum(l.startswith("FS") for l in labels))
    snaps["rolled_safety"] = db_labels.map(lambda labels: any(l.startswith("SS") for l in labels))
    snaps["front"] = (snaps["pff_DEFENSIVE_FRONT_NAME"].str.replace(" FAMILY", "")
                      .str.title())

    snaps["sack"] = snaps["pff_PASSRESULT"].eq("SACK")
    snaps["pressure"] = snaps["pff_QBPRESSURE"].notna() | snaps["sack"]
    snaps["off_success"] = snaps["pff_DEFSUCCESS"].eq("F")
    big = np.where(snaps["is_pass"], snaps["gain"] >= BIG_PASS, snaps["gain"] >= BIG_RUN)
    snaps["explosive"] = big & snaps["counts"]
    snaps["converted"] = snaps["pff_FIRST_DOWN_GAINED"].eq(1)

    snaps["distance"] = pd.cut(snaps["pff_DISTANCE"], DISTANCE_EDGES,
                               labels=DISTANCE_CATEGORIES)
    snaps["to_goal"] = snaps["pff_YARDS_TO_GOAL_LINE"]
    # pff_SCOREDIFFERENTIAL is offense minus defense.
    snaps["our_lead"] = -snaps["pff_SCOREDIFFERENTIAL"]
    return snaps


def games_line(snaps):
    """'Brown defense · 16 games (10 in 2025, 6 in 2026)'."""
    games = snaps.drop_duplicates("pff_GAMEID")
    by_season = games["season"].value_counts().sort_index()
    seasons = ", ".join(f"{n} in {season}" for season, n in by_season.items())
    return f"Brown defense · {len(games)} games ({seasons})"


def share(mask, base=None):
    """Percent of `base` rows (default: all) where mask is true."""
    base = mask.index if base is None else base
    picked = mask.loc[base]
    return 100 * picked.mean() if len(picked) else np.nan


# --- page layout ---------------------------------------------------------------

def start_page(width, height, title, answer, context):
    """Figure with the question, its short answer, and what data it covers.

    The answer is written from the data, so its length changes; it wraps to
    the page width. Returns the figure and how far down the header reaches
    (inches from the top), so charts can start below it.
    """
    plt.rcParams["font.family"] = ["Arial", "DejaVu Sans"]
    fig = plt.figure(figsize=(width, height), facecolor=WHITE)
    left = 0.6 / width
    fig.text(left, 1 - 0.35 / height, title, fontsize=20, fontweight="bold",
             color=INK, va="top")
    text = fig.text(left, 1 - 0.8 / height, answer, fontsize=12, color=INK, va="top",
                    linespacing=1.35)
    renderer = fig.canvas.get_renderer()
    room = (width - 1.2) * fig.dpi
    chars = len(answer)
    while text.get_window_extent(renderer).width > room and chars > 20:
        chars -= 2
        text.set_text(textwrap.fill(answer, chars))
    lines = text.get_text().count("\n") + 1
    context_top = 0.8 + 0.27 * lines + 0.03
    fig.text(left, 1 - context_top / height, context, fontsize=9.5, color=MUTED, va="top")
    return fig, context_top + 0.15


def footer(fig, lines):
    """Notes along the bottom edge, first line darkest."""
    width, height = fig.get_size_inches()
    for i, line in enumerate(reversed(lines)):
        fig.text(0.6 / width, (0.25 + 0.22 * i) / height, line, fontsize=8.5,
                 color=INK if i == len(lines) - 1 else MUTED, va="bottom")


def save(fig, path):
    fig.savefig(path, dpi=200, facecolor=WHITE)
    plt.close(fig)
    print(f"[saved] {path}")


def row(label, value, n, text=None, small=None, strong=False):
    """One bar on a board. `small` defaults to n < SMALL_SAMPLE."""
    return {"label": label, "value": value, "n": n, "text": text,
            "small": n < SMALL_SAMPLE if small is None else small, "strong": strong}


def board(ax, groups, title=None, ref=None, ref_label=None, xmax=None,
          fmt="{:.0f}%", labels=True, highlight=False, starred=None):
    """Horizontal bars in labelled groups.

    groups     [(heading or None, [row(...), ...]), ...]
    ref        value for a dashed reference line (e.g. the overall rate)
    highlight  only rows with strong=True are dark brown, the rest tan
    labels     False for a second panel that reuses the first panel's rows
    starred    heading of the group the page's answer is about: it gets a star
               and a pale band from the page edge across the chart
    """
    y, ticks, names = 0.0, [], []
    for heading, rows in groups:
        start = y
        if heading:
            if labels:
                star = heading == starred
                ax.text(-0.01, y, ("★ " if star else "") + heading.upper(),
                        transform=blended_transform_factory(ax.transAxes, ax.transData),
                        ha="right", va="center", fontsize=8.5, fontweight="bold",
                        color=INK if star else MUTED)
            y += 0.85
        for r in rows:
            ticks.append(y)
            names.append(r["label"])
            if pd.notna(r["value"]):
                color = BROWN if (r["strong"] or not highlight) else TAN
                ax.barh(y, r["value"], height=0.62, zorder=2,
                        color=WHITE if r["small"] else color, edgecolor=color,
                        linewidth=1.2 if r["small"] else 0,
                        hatch="////" if r["small"] else None)
            y += 1
        if heading and heading == starred:
            fig = ax.figure
            edge = 0.45 / fig.get_size_inches()[0]
            ax.add_patch(Rectangle((edge, start - 0.5), ax.get_position().x1 - edge,
                                   y - start + 0.05, facecolor=PALE, edgecolor="none",
                                   zorder=0.1, clip_on=False, transform=blended_transform_factory(
                                       fig.transFigure, ax.transData)))
        y += 0.45

    values = [r["value"] for _, rows in groups for r in rows if pd.notna(r["value"])]
    top = xmax or max(values + ([ref] if ref is not None else [])) * 1.45
    i = 0
    for heading, rows in groups:
        backing = PALE if heading and heading == starred else WHITE
        for r in rows:
            value = r["value"]
            text = r["text"] if r["text"] is not None else (
                fmt.format(value) if pd.notna(value) else "—")
            # backing so a reference line passing behind stays readable
            ax.text((value if pd.notna(value) else 0) + top * 0.012, ticks[i], text,
                    va="center", fontsize=9, color=INK, zorder=4,
                    bbox={"facecolor": backing, "edgecolor": "none", "pad": 1})
            i += 1

    if ref is not None:
        ax.axvline(ref, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=3)
        if ref_label:
            ax.text(ref, -0.9, ref_label, ha="center", va="bottom", fontsize=8.5,
                    color=MUTED)

    ax.set_ylim(y - 0.2, -1.0)
    ax.set_xlim(0, top)
    ax.set_yticks(ticks)
    ax.set_yticklabels(names if labels else [""] * len(names), fontsize=9.5, color=INK)
    ax.tick_params(axis="y", length=0, pad=6)
    ax.tick_params(axis="x", labelsize=8.5, colors=MUTED, length=0)
    ax.xaxis.set_major_formatter(lambda v, _: fmt.format(v))
    ax.grid(axis="x", color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    if title:
        ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold", color=INK, pad=8)


def heat_grid(ax, row_labels, col_labels, cell, ceiling, note_small=SMALL_SAMPLE):
    """Boxes shaded light->brown by value. cell(r, c) -> (value, top_text, sub_text, n)."""
    from matplotlib.colors import LinearSegmentedColormap
    from matplotlib.patches import Rectangle

    shade = LinearSegmentedColormap.from_list("brown", [PALE, BROWN])
    gap = 0.04
    for r in range(len(row_labels)):
        for c in range(len(col_labels)):
            value, top_text, sub_text, n = cell(r, c)
            x0, y0, size = c + gap, r + gap, 1 - 2 * gap
            if n == 0 or pd.isna(value):
                ax.add_patch(Rectangle((x0, y0), size, size, facecolor=WHITE,
                                       edgecolor=GRID, linewidth=1))
                ax.text(c + 0.5, r + 0.5, "none", ha="center", va="center",
                        fontsize=8.5, color=MUTED)
                continue
            if n < note_small:
                face, edge, ink, sub = WHITE, GRID, INK, MUTED
            else:
                level = min(value, ceiling) / ceiling
                face = edge = shade(level)
                dark = level > 0.45
                ink, sub = (WHITE, WHITE) if dark else (INK, MUTED)
            ax.add_patch(Rectangle((x0, y0), size, size, facecolor=face,
                                   edgecolor=edge, linewidth=1))
            ax.text(c + 0.5, r + 0.42, top_text, ha="center", va="center",
                    fontsize=14, fontweight="bold", color=ink)
            ax.text(c + 0.5, r + 0.72, sub_text, ha="center", va="center",
                    fontsize=8.5, color=sub)
    ax.set_xlim(0, len(col_labels))
    ax.set_ylim(len(row_labels), 0)
    ax.set_xticks(np.arange(len(col_labels)) + 0.5)
    ax.set_xticklabels(col_labels, fontsize=10, color=INK)
    ax.xaxis.tick_top()
    ax.set_yticks(np.arange(len(row_labels)) + 0.5)
    ax.set_yticklabels(row_labels, fontsize=10, color=INK)
    ax.tick_params(length=0, pad=6)
    for spine in ax.spines.values():
        spine.set_visible(False)


def out_dir_for(script_file, override=None):
    """Outputs go next to the study's script unless --out says otherwise."""
    out = Path(override) if override else Path(script_file).resolve().parent
    out.mkdir(parents=True, exist_ok=True)
    return out
