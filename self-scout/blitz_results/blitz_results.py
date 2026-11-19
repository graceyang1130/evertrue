"""Self-scout: does blitzing work for us?

Compares what happened on opponent passes by how we rushed: 3-man rush,
4-man rush, 4-man rush with a stunt, sim pressure (4 rushers, one of them a
blitzer), 5-man blitz, 6+ man blitz.

Two pages:
  rush_results.png      pressure, sacks, yards, offense success and big
                        passes for each rush, all downs
  third_down_rush.png   3rd-down conversions allowed by rush and yards to go,
                        so blitzes are compared with four-man rushes in the
                        same situations

Results use plays that stood (no penalty wiped them out); scrambles count as
dropbacks. scout_common.py says which snaps count.

Usage:
    python self-scout/blitz_results/blitz_results.py "self-scout/blitz_102926/play_feed (1).csv"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from matplotlib.transforms import blended_transform_factory

from scout_common import (BIG_PASS, DISTANCE_CATEGORIES, INK, MUTED, RUSH_ORDER, SMALL_SAMPLE,
                          SUCCESS_RULE, TEAM_CODE, board, footer, games_line, heat_grid,
                          load_snaps, out_dir_for, row, save, start_page)

BLITZES = ["Sim pressure", "5-man blitz", "6+ man blitz"]
ALL_BLITZES = "All blitzes"
# Rows on the results page: each rush, then the blitzes pooled (so those plays show twice).
RESULT_GROUPS = [("No blitz", [(r, [r]) for r in RUSH_ORDER if r not in BLITZES]),
                 ("Blitz", [(r, [r]) for r in BLITZES]),
                 (None, [(ALL_BLITZES, BLITZES)])]
# 3rd-down rows: blitzes pooled so each box has enough plays.
THIRD_DOWN_RUSHES = [("4-man rush", ["4-man rush"]),
                     ("4-man rush + stunt", ["4-man rush + stunt"]),
                     (ALL_BLITZES, BLITZES)]

METRICS = [  # column, panel title, format, how to get it from a group of dropbacks
    ("pressure_pct", "QB pressured", "{:.0f}%", lambda g: 100 * g["pressure"].mean()),
    ("sack_pct", "Sacks", "{:.0f}%", lambda g: 100 * g["sack"].mean()),
    ("yards", "Yards per dropback", "{:.1f}", lambda g: g["gain"].mean()),
    ("success_pct", "Offense success", "{:.0f}%", lambda g: 100 * g["off_success"].mean()),
    ("big_pct", f"Passes of {BIG_PASS}+ yards", "{:.0f}%", lambda g: 100 * g["explosive"].mean()),
]
# Sack rates all round to 5%, so their bar labels carry two decimals (the axis stays whole).
LABEL_FORMATS = {"sack_pct": "{:.2f}%"}


def rush_table(dropbacks):
    records = []
    for heading, rows in RESULT_GROUPS:
        for label, rushes in rows:
            group = dropbacks[dropbacks["rush"].isin(rushes)]
            record = {"group": heading or "", "rush": label, "dropbacks": len(group)}
            for column, _, _, stat in METRICS:
                record[column] = stat(group) if len(group) else float("nan")
            records.append(record)
    return pd.DataFrame(records)


def summary(dropbacks, rushes):
    group = dropbacks[dropbacks["rush"].isin(rushes)]
    return group["gain"].mean(), 100 * group["pressure"].mean(), len(group)


def sample_column(fig, ax, counts, x, header="Dropbacks", header_y=-0.75):
    """Plays behind each row, in their own column at the far left of the page."""
    place = blended_transform_factory(fig.transFigure, ax.transData)
    ax.text(x, header_y, header, transform=place, ha="right", va="bottom", fontsize=8.5,
            fontweight="bold", color=MUTED)
    for y, n in zip(ax.get_yticks(), counts):
        ax.text(x, y, f"{n}", transform=place, ha="right", va="center", fontsize=9.5, color=INK)


def draw_results(dropbacks, table, path):
    b_yds, b_pr, _ = summary(dropbacks, BLITZES)
    f_yds, f_pr, _ = summary(dropbacks, ["4-man rush"])
    answer = (f"When we blitz: {b_yds:.1f} yards per dropback, QB pressured {b_pr:.0f}% of the "
              f"time. Plain four-man rush: {f_yds:.1f} yards, pressured {f_pr:.0f}%.")
    width, height = 16, 8.0
    fig, top = start_page(width, height, "Does blitzing work for us?", answer,
                          f"{games_line(dropbacks)} · {len(dropbacks)} opponent dropbacks")

    left, right, gap = 2.6, 0.4, 0.35
    panel_w = (width - left - right - gap * (len(METRICS) - 1)) / len(METRICS)
    for i, (column, title, fmt, _) in enumerate(METRICS):
        label_fmt = LABEL_FORMATS.get(column)
        groups = [(heading or None, [
            row("All blitzes\n(3 rows above)" if r.rush == ALL_BLITZES else r.rush,
                getattr(r, column), r.dropbacks,
                text=label_fmt.format(getattr(r, column)) if label_fmt else None)
            for r in rows.itertuples()])
            for heading, rows in table.groupby("group", sort=False)]
        ax = fig.add_axes([(left + i * (panel_w + gap)) / width, 1.35 / height,
                           panel_w / width, (height - top - 0.7 - 1.35) / height])
        board(ax, groups, title=title, fmt=fmt, labels=i == 0,
              xmax=table[column].max() * 1.5)
        if i == 0:
            sample_column(fig, ax, table["dropbacks"], 1.05 / width)
    footer(fig, [
        f"Striped bar: fewer than {SMALL_SAMPLE} dropbacks, too few to call it. Blitzes are "
        "called more on 3rd down, so the next page compares rushes on 3rd down only.",
        SUCCESS_RULE,
        "Blitz = PFF's blitz tag. Sim pressure = 4 rushers, one of them a blitzer. All blitzes "
        "pools the three blitz rows, so those plays appear twice. Plays wiped out by a penalty "
        "are left out.",
    ])
    save(fig, path)


def third_down_table(dropbacks):
    third = dropbacks[dropbacks["pff_DOWN"] == 3]
    records = []
    for label, rushes in THIRD_DOWN_RUSHES:
        group = third[third["rush"].isin(rushes)]
        for bucket in DISTANCE_CATEGORIES + ["all"]:
            cell = group if bucket == "all" else group[group["distance"] == bucket]
            records.append({"rush": label, "distance": bucket, "dropbacks": len(cell),
                            "converted": int(cell["converted"].sum()),
                            "converted_pct": 100 * cell["converted"].mean() if len(cell)
                            else float("nan")})
    return pd.DataFrame(records)


def draw_third_down(dropbacks, table, path):
    totals = table[table["distance"] == "all"].set_index("rush")
    blitz, four = totals.loc[ALL_BLITZES], totals.loc["4-man rush"]
    stunt = totals.loc["4-man rush + stunt"]
    answer = (f"3rd-down passes converted: {blitz.converted_pct:.0f}% against our blitz "
              f"({blitz.converted} of {blitz.dropbacks}), {four.converted_pct:.0f}% against a "
              f"plain four-man rush ({four.converted} of {four.dropbacks}), "
              f"{stunt.converted_pct:.0f}% against four with a stunt "
              f"({stunt.converted} of {stunt.dropbacks}).")
    width, height = 11, 6.9
    fig, top = start_page(width, height, "On 3rd down, does the blitz get us off the field?",
                          answer, games_line(dropbacks))

    cells = table.set_index(["rush", "distance"])
    rows = [label for label, _ in THIRD_DOWN_RUSHES]

    def cell(r, c):
        record = cells.loc[(rows[r], DISTANCE_CATEGORIES[c])]
        n = int(record["dropbacks"])
        return (record["converted_pct"], f"{record['converted_pct']:.0f}%" if n else "",
                f"{int(record['converted'])} of {n} converted", n)

    ax = fig.add_axes([2.7 / width, 1.0 / height, 6.2 / width,
                       (height - top - 0.5 - 1.0) / height])
    heat_grid(ax, rows, [f"3rd & {b}" for b in DISTANCE_CATEGORIES], cell, ceiling=70,
              note_small=10)
    ax.set_aspect("auto")
    sample_column(fig, ax, [int(totals.loc[r, "dropbacks"]) for r in rows], 1.2 / width,
                  header="Passes", header_y=-0.05)
    footer(fig, [
        "Each box: share of 3rd-down passes the offense converted, then the count. Darker = "
        "they converted more. White box: fewer than 10 passes.",
        "All blitzes = sim pressure, 5-man and 6+ man blitzes together. 3-man rushes are left "
        "off (too few). Plays wiped out by a penalty are left out.",
    ])
    save(fig, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="PFF play-by-play export of our defensive games")
    parser.add_argument("--team", default=TEAM_CODE, help="PFF code of the defense to scout")
    parser.add_argument("--out", help="folder for the outputs (default: this script's folder)")
    args = parser.parse_args()

    snaps = load_snaps(args.csv, args.team)
    dropbacks = snaps[snaps["is_pass"] & snaps["counts"]]
    out_dir = out_dir_for(__file__, args.out)

    table = rush_table(dropbacks)
    table.round(1).assign(sack_pct=table["sack_pct"].round(2)).to_csv(
        out_dir / "rush_results.csv", index=False)
    print(table.round(1).to_string(index=False))
    third = third_down_table(dropbacks)
    third.round(1).to_csv(out_dir / "third_down_rush.csv", index=False)
    print(third.round(1).to_string(index=False))

    draw_results(dropbacks, table, out_dir / "rush_results.png")
    draw_third_down(dropbacks, third, out_dir / "third_down_rush.png")


if __name__ == "__main__":
    main()
