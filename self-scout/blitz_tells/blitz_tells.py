"""Self-scout: can offenses see our blitz coming?

For each look a quarterback can read at the snap (press, box count, deep
safeties, our front) and each look the offense gives us (formation,
personnel), the share of their passes where we blitzed. A look that comes
with a blitz rate well above our average is a tell.

The answer at the top is the box count (7+ in the box vs 6 or fewer), the
tell a quarterback can read every snap; it says whether that held in each
season and on 1st, 2nd and 3rd down, and its group on the chart is starred.

Pass plays only: PFF tags blitzes on passes, not runs. Looks are as PFF
charted them at the snap. scout_common.py says which snaps count.

Writes blitz_tells.png and blitz_tells.csv in this folder.

Usage:
    python self-scout/blitz_tells/blitz_tells.py "self-scout/blitz_102926/play_feed (1).csv"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from scout_common import (SMALL_SAMPLE, TEAM_CODE, board, footer, games_line, load_snaps,
                          out_dir_for, row, save, start_page)

# A look is a tell when we blitz at least this many points more than usual with it.
TELL_LIFT = 10
# The page's takeaway is the box count: this many or more in the box vs fewer.
LOADED_BOX = 7
BOX_HEADING = "Players in our box"


def looks(passes):
    """[(heading, [(label, phrase, mask), ...]), ...] in display order."""
    box, deep = passes["box"], passes["deep_safeties"]
    fronts = passes["front"].value_counts()
    main_fronts = [f for f in fronts.index if fronts[f] >= SMALL_SAMPLE]
    formation = passes["pff_OFFFORMATIONGROUP"]
    personnel = passes["pff_OFF_PERSONNEL_GROUP"].astype(str).str.rstrip("H")
    named_formations = ["2x2", "3x1", "1x3", "3x2", "2x3"]
    return [
        ("We press a receiver", [
            ("Press", "we press a receiver", passes["press"]),
            ("No press", "we don't press", ~passes["press"]),
        ]),
        (BOX_HEADING, [
            ("5 or fewer", "we have 5 or fewer in the box", box <= 5),
            ("6", "we have 6 in the box", box == 6),
            ("7", "we have 7 in the box", box == 7),
            ("8 or more", "we have 8 or more in the box", box >= 8),
        ]),
        ("Deep safeties at the snap", [
            ("Two deep", "we show two deep safeties", deep >= 2),
            ("One deep", "we show one deep safety", deep == 1),
            ("None deep", "we show no deep safety", deep == 0),
        ]),
        ("Safety rolled down", [
            ("Yes", "a safety is rolled down", passes["rolled_safety"]),
            ("No", "no safety is rolled down", ~passes["rolled_safety"]),
        ]),
        ("Our front", [(f, f"we're in our {f} front", passes["front"] == f) for f in main_fronts]
         + [("Other fronts", "we're in another front", ~passes["front"].isin(main_fronts))]),
        ("Their formation", [
            ("2x2", "they line up 2x2", formation == "2x2"),
            ("Trips (3x1)", "they line up in trips", formation.isin(["3x1", "1x3"])),
            ("Empty", "they go empty", formation.isin(["3x2", "2x3"])),
            ("Other", "they're in another formation", ~formation.isin(named_formations)),
        ]),
        ("Their personnel", [
            ("10 personnel", "they're in 10 personnel", personnel == "10"),
            ("11 personnel", "they're in 11 personnel", personnel == "11"),
            ("12 personnel", "they're in 12 personnel", personnel == "12"),
            ("Other", "they're in other personnel", ~personnel.isin(["10", "11", "12"])),
        ]),
    ]


def tell_table(passes):
    overall = 100 * passes["blitz"].mean()
    records = []
    for heading, items in looks(passes):
        for label, phrase, mask in items:
            picked = passes[mask]
            pct = 100 * picked["blitz"].mean() if len(picked) else float("nan")
            records.append({"heading": heading, "look": label, "phrase": phrase,
                            "passes": len(picked), "blitzes": int(picked["blitz"].sum()),
                            "blitz_pct": pct, "vs_average": pct - overall})
    table = pd.DataFrame(records)
    # "Other ..." rows are catch-alls, not a look anyone can read.
    table["tell"] = ((table["passes"] >= SMALL_SAMPLE) & (table["vs_average"] >= TELL_LIFT)
                     & ~table["look"].str.startswith("Other"))
    return table, overall


def box_rates(passes):
    """Blitz rate with a loaded box and with a light one."""
    loaded = passes["box"] >= LOADED_BOX
    return 100 * passes.loc[loaded, "blitz"].mean(), 100 * passes.loc[~loaded, "blitz"].mean()


def box_is_tell(passes):
    loaded, light = box_rates(passes)
    return loaded - light >= TELL_LIFT


def short_answer(passes):
    """The takeaway, and whether the box count is a tell (so its group gets the star)."""
    loaded, light = box_rates(passes)
    if loaded - light < TELL_LIFT:
        return (f"Not by counting our box: we blitz {loaded:.0f}% of passes with {LOADED_BOX} "
                f"or more in it and {light:.0f}% with fewer."), False
    answer = (f"★ Yes, if they count our box. With {LOADED_BOX} or more in the box we blitz "
              f"{loaded:.0f}% of passes; with {LOADED_BOX - 1} or fewer, {light:.0f}%.")
    seasons = passes.groupby("season")
    downs = passes[passes["pff_DOWN"] <= 3].groupby("pff_DOWN")
    if all(box_is_tell(g) for _, g in seasons) and all(box_is_tell(g) for _, g in downs):
        answer += (f" Same story in {' and '.join(str(s) for s in seasons.groups)}, and on "
                   "1st, 2nd and 3rd down.")
    return answer, True


def draw(passes, table, overall, path):
    groups = []
    for heading, rows in table.groupby("heading", sort=False):
        groups.append((heading, [
            row(r.look, r.blitz_pct, r.passes, strong=r.tell,
                text=f"{r.blitz_pct:.0f}%   {r.blitzes} of {r.passes}")
            for r in rows.itertuples()]))

    answer, box_tell = short_answer(passes)
    units = len(table) + 1.3 * len(groups)
    width, height = 11, 1.5 + 0.27 * units + 1.0
    fig, top = start_page(width, height, "Can offenses see our blitz coming?", answer,
                          f"{games_line(passes)} · {int(passes['blitz'].sum())} blitzes "
                          f"on {len(passes)} opponent passes")
    ax = fig.add_axes([2.7 / width, 1.0 / height, (width - 2.7 - 0.6) / width,
                       (height - top - 0.25 - 1.0) / height])
    board(ax, groups, ref=overall, ref_label=f"Our average {overall:.0f}%",
          highlight=True, xmax=max(table["blitz_pct"].max(), overall) * 1.35,
          starred=BOX_HEADING if box_tell else None)
    footer(fig, [
        f"Dark bar: we blitz at least {TELL_LIFT} points more than our average with that look "
        f"(and it happened {SMALL_SAMPLE}+ times). Striped bar: fewer than {SMALL_SAMPLE} passes, "
        "too few to call it.",
        "Blitz rate = opponent passes where we sent a blitz (PFF's blitz tag). PFF doesn't tag "
        "blitzes on runs, so runs are left out. Looks are as PFF charted them at the snap.",
    ])
    save(fig, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="PFF play-by-play export of our defensive games")
    parser.add_argument("--team", default=TEAM_CODE, help="PFF code of the defense to scout")
    parser.add_argument("--out", help="folder for the outputs (default: this script's folder)")
    args = parser.parse_args()

    snaps = load_snaps(args.csv, args.team)
    passes = snaps[snaps["is_pass"]]
    out_dir = out_dir_for(__file__, args.out)

    table, overall = tell_table(passes)
    table.drop(columns="phrase").round(1).to_csv(out_dir / "blitz_tells.csv", index=False)
    print(table[["heading", "look", "passes", "blitz_pct", "tell"]].round(1).to_string(index=False))
    print(f"[saved] {out_dir / 'blitz_tells.csv'}")
    draw(passes, table, overall, out_dir / "blitz_tells.png")


if __name__ == "__main__":
    main()
