"""Self-scout: what do we do in key situations, and how does it go?

Rows are situations (field position, score, clock, offense tempo). For each:
  - how often the offense threw
  - how often we blitzed their passes
  - yards per play we allowed
  - offense success rate

Tendencies (threw, blitzed) count every snap, including plays a penalty
wiped out, because the call was still made. Results (yards, success) use
plays that stood. scout_common.py says which snaps count.

Writes situations.png and situations.csv in this folder.

Usage:
    python self-scout/situations/situations.py "self-scout/blitz_102926/play_feed (1).csv"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from scout_common import (SMALL_SAMPLE, SUCCESS_RULE, TEAM_CODE, board, footer, games_line,
                          load_snaps, out_dir_for, row, save, start_page)


def situations(snaps):
    """[(heading, [(label, phrase, mask), ...]), ...] in display order."""
    to_goal, lead, clock = snaps["to_goal"], snaps["our_lead"], snaps["pff_2MINUTE"]
    return [
        ("Field position", [
            ("Backed up (their 1-19)", "they're backed up", to_goal >= 81),
            ("Their 20 to their 49", "they're between their 20 and 49", to_goal.between(51, 80)),
            ("Midfield to our 21", "they're between midfield and our 21", to_goal.between(21, 50)),
            ("Red zone (our 11-20)", "they're in the red zone", to_goal.between(11, 20)),
            ("Goal line (our 10 and in)", "they're at our 10 or closer", to_goal <= 10),
        ]),
        ("Score", [
            ("We lead by 9+", "we lead by 9 or more", lead >= 9),
            ("We lead by 1-8", "we lead by 1 to 8", lead.between(1, 8)),
            ("Tied", "it's tied", lead == 0),
            ("We trail by 1-8", "we trail by 1 to 8", lead.between(-8, -1)),
            ("We trail by 9+", "we trail by 9 or more", lead <= -9),
        ]),
        ("Clock", [
            ("Their two-minute drill", "they're in a two-minute drill", clock == 2),
            ("They're killing the clock", "they're killing the clock", clock == 4),
            ("Rest of the game", "it's a normal clock situation", clock == 0),
        ]),
        ("Offense's pace", [
            ("They go tempo", "they go tempo", snaps["pff_TEMPO"].eq(True)),
            ("Normal pace", "they huddle up or go at a normal pace", snaps["pff_TEMPO"].eq(False)),
        ]),
    ]


def situation_table(snaps):
    records = []
    for heading, items in situations(snaps):
        for label, phrase, mask in items:
            picked = snaps[mask]
            passes = picked[picked["is_pass"]]
            stood = picked[picked["counts"]]
            records.append({
                "heading": heading, "situation": label, "phrase": phrase,
                "snaps": len(picked), "passes": len(passes),
                "pass_pct": 100 * picked["is_pass"].mean() if len(picked) else float("nan"),
                "blitz_pct": 100 * passes["blitz"].mean() if len(passes) else float("nan"),
                "yards_per_play": stood["gain"].mean() if len(stood) else float("nan"),
                "success_pct": 100 * stood["off_success"].mean() if len(stood) else float("nan"),
            })
    return pd.DataFrame(records)


def short_answer(table, overall):
    enough = table[table["passes"] >= SMALL_SAMPLE]
    most = enough.loc[enough["blitz_pct"].idxmax()]
    least = enough.loc[enough["blitz_pct"].idxmin()]
    return (f"We blitz most when {most.phrase} ({most.blitz_pct:.0f}% of passes) and least "
            f"when {least.phrase} ({least.blitz_pct:.0f}%). Our average is {overall:.0f}%.")


PANELS = [  # column, title, format, sample-size column
    ("pass_pct", "They threw", "{:.0f}%", "snaps"),
    ("blitz_pct", "We blitzed (of their passes)", "{:.0f}%", "passes"),
    ("yards_per_play", "Yards per play we allowed", "{:.1f}", "snaps"),
    ("success_pct", "Offense success", "{:.0f}%", "snaps"),
]


def draw(snaps, table, path):
    passes = snaps[snaps["is_pass"]]
    overall = 100 * passes["blitz"].mean()
    units = len(table) * 1.0 + 1.3 * table["heading"].nunique()
    width, height = 16, 1.6 + 0.36 * units + 1.25
    fig, top = start_page(width, height, "What do we do in key situations?",
                          short_answer(table, overall),
                          f"{games_line(snaps)} · {len(snaps)} snaps, {len(passes)} passes")

    left, right, gap = 2.6, 0.4, 0.35
    panel_w = (width - left - right - gap * (len(PANELS) - 1)) / len(PANELS)
    for i, (column, title, fmt, n_column) in enumerate(PANELS):
        groups = []
        for heading, rows in table.groupby("heading", sort=False):
            groups.append((heading, [
                row(f"{r.situation}\n{r.snaps} snaps", getattr(r, column), getattr(r, n_column))
                for r in rows.itertuples()]))
        ax = fig.add_axes([(left + i * (panel_w + gap)) / width, 1.25 / height,
                           panel_w / width, (height - top - 0.65 - 1.25) / height])
        board(ax, groups, title=title, fmt=fmt, labels=i == 0,
              ref=overall if column == "blitz_pct" else None,
              ref_label=f"Average {overall:.0f}%" if column == "blitz_pct" else None,
              xmax=table[column].max() * 1.45)
    footer(fig, [
        f"Striped bar: fewer than {SMALL_SAMPLE} plays behind it (passes for the blitz column), "
        "too few to call it. Field position is where the ball was snapped.",
        SUCCESS_RULE,
        "Blitz = PFF's blitz tag (passes only). Plays wiped out by a penalty count for "
        "'They threw' and 'We blitzed' but not for results.",
    ])
    save(fig, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="PFF play-by-play export of our defensive games")
    parser.add_argument("--team", default=TEAM_CODE, help="PFF code of the defense to scout")
    parser.add_argument("--out", help="folder for the outputs (default: this script's folder)")
    args = parser.parse_args()

    snaps = load_snaps(args.csv, args.team)
    out_dir = out_dir_for(__file__, args.out)

    table = situation_table(snaps)
    table.drop(columns="phrase").round(1).to_csv(out_dir / "situations.csv", index=False)
    print(table.drop(columns="phrase").round(1).to_string(index=False))
    draw(snaps, table, out_dir / "situations.png")


if __name__ == "__main__":
    main()
