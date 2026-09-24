"""
3rd & 4th down breakdown charts from PFF play-by-play exports.

Generic version: pass CSV paths and a school name instead of editing the file.
This replaces the per-opponent copies (yale_breakdown.py, dartmouth_breakdown.py,
better34analysis.py, ...) which were identical apart from three lines.

Usage (command line):
    python 34analyze.py OFFENSE.csv DEFENSE.csv "Brown" --out-dir charts

Usage (import):
    from importlib import import_module
    run_all_plots("brown_o.csv", "brown_d.csv", "Brown", out_dir="charts")

Analysis definitions match the 2025 opponent packets exactly so output stays
comparable: a play counts as successful when pff_FIRST_DOWN_GAINED == 1, and
plays negated by penalty (pff_NOPLAY) and garbage-time plays are both kept in.
"""

import argparse
import os

import matplotlib
import numpy as np
import pandas as pd

# Columns the charts actually need out of the ~212 PFF exports.
REQUIRED_COLUMNS = [
    "pff_DOWN",
    "pff_DISTANCE",
    "pff_QBSCRAMBLE",
    "pff_RUNPASS",
    "pff_FIRST_DOWN_GAINED",
]

PASS_COLOR = "blue"
RUN_COLOR = "green"
SCRAMBLE_COLOR = "orange"

DISTANCE_CATEGORIES = ["1-2", "3-6", "7-10", "11+"]


def _save(fig_path, out_dir, show, dpi=150, tight=True):
    """Lay out, save under out_dir, then either show or close the figure."""
    import matplotlib.pyplot as plt

    if tight:
        plt.tight_layout()
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, fig_path)
    plt.savefig(path, dpi=dpi, bbox_inches="tight")
    print(f"[saved] {path}")
    if show:
        plt.show()
    plt.close()


def _label_bars(bars, counts, offset, stacked=False):
    """Write the play count above each bar, skipping empty ones."""
    import matplotlib.pyplot as plt

    for i, rect in enumerate(bars):
        n = counts[i]
        if n <= 0:
            continue
        top = rect.get_y() + rect.get_height() if stacked else rect.get_height()
        plt.text(
            rect.get_x() + rect.get_width() / 2,
            top + offset,
            f"{int(n)}",
            ha="center",
            va="bottom",
            fontsize=8,
        )


def apply_season_filter(df, min_season=None, recent_years=None):
    """
    Optionally narrow a raw export to recent seasons.

    min_season   -- keep seasons >= this year (e.g. 2022)
    recent_years -- keep the last N seasons present in the file (e.g. 3)

    Opponent exports span anywhere from one season (New Haven 2025) to eight
    (Cornell 2018-2025), so this is how you put them on equal footing.
    """
    if "pff_GAMESEASON" not in df.columns:
        return df

    out = df.copy()
    seasons = pd.to_numeric(out["pff_GAMESEASON"], errors="coerce")

    if min_season is not None:
        out = out[seasons >= int(min_season)]
        seasons = pd.to_numeric(out["pff_GAMESEASON"], errors="coerce")

    if recent_years is not None and not seasons.isna().all():
        cutoff = int(seasons.max()) - int(recent_years) + 1
        out = out[seasons >= cutoff]

    return out


def clean_data(unclean):
    """Keep the five columns the charts use and normalise their blanks."""
    missing = [c for c in REQUIRED_COLUMNS if c not in unclean.columns]
    if missing:
        raise ValueError(f"Dataframe is missing required column(s): {missing}")

    clean = unclean[REQUIRED_COLUMNS].copy()
    clean["pff_FIRST_DOWN_GAINED"] = clean["pff_FIRST_DOWN_GAINED"].fillna(0)
    clean["pff_QBSCRAMBLE"] = clean["pff_QBSCRAMBLE"].fillna("N")
    return clean


def _split_plays(df, desired_down):
    """Pass / run / scramble for one down. Scrambles are pulled out of pass."""
    plays = df[df["pff_DOWN"] == desired_down]
    pass_plays = plays[(plays["pff_RUNPASS"] == "P") & (plays["pff_QBSCRAMBLE"] == "N")]
    run_plays = plays[(plays["pff_RUNPASS"] == "R") & (plays["pff_QBSCRAMBLE"] == "N")]
    scramble_plays = plays[plays["pff_QBSCRAMBLE"] != "N"]
    return plays, pass_plays, run_plays, scramble_plays


def playcall_by_distance(df, desired_down, school="Brown offense", out_dir=".", show=False):
    """Raw play counts by distance, 1-14 and 15+."""
    import matplotlib.pyplot as plt

    _, pass_plays, run_plays, scramble_plays = _split_plays(df, desired_down)

    rates_pass, rates_run, rates_scramble = [], [], []
    for distance in range(1, 15):
        rates_pass.append(len(pass_plays[pass_plays["pff_DISTANCE"] == distance]))
        rates_run.append(len(run_plays[run_plays["pff_DISTANCE"] == distance]))
        rates_scramble.append(len(scramble_plays[scramble_plays["pff_DISTANCE"] == distance]))

    rates_pass.append(len(pass_plays[pass_plays["pff_DISTANCE"] >= 15]))
    rates_run.append(len(run_plays[run_plays["pff_DISTANCE"] >= 15]))
    rates_scramble.append(len(scramble_plays[scramble_plays["pff_DISTANCE"] >= 15]))

    distances = list(range(1, 15)) + ["15+"]
    bar_width = 0.35
    index = np.arange(len(distances))

    plt.figure(figsize=(12, 7))
    pass_bars = plt.bar(index, rates_pass, bar_width, label="Pass Plays", color=PASS_COLOR)
    scramble_bars = plt.bar(
        index, rates_scramble, bar_width, bottom=rates_pass,
        label="Scramble Plays", color=SCRAMBLE_COLOR,
    )
    run_bars = plt.bar(index + bar_width, rates_run, bar_width, label="Run Plays", color=RUN_COLOR)

    _label_bars(pass_bars, rates_pass, 0.5)
    _label_bars(scramble_bars, rates_scramble, 0.5, stacked=True)
    _label_bars(run_bars, rates_run, 0.5)

    plt.xlabel("Distance (Yards)")
    plt.ylabel("# of Plays")
    plt.title(f"{school} Down #{desired_down}: # of Plays by Distance")
    plt.xticks(index + bar_width / 2, distances)
    plt.legend()
    plt.grid(axis="y")

    _save(f"{school}_{desired_down}_#plays.png", out_dir, show)


def play_percentage_by_distance(df, desired_down, school="Brown offense", out_dir=".", show=False):
    """Play-type mix as a percentage of plays at each distance, 1-14 and 15+."""
    import matplotlib.pyplot as plt

    plays, pass_plays, run_plays, scramble_plays = _split_plays(df, desired_down)

    distance_bins = list(range(1, 15)) + ["15+"]
    percentages_pass, percentages_run, percentages_scramble = [], [], []
    counts_pass, counts_run, counts_scramble = [], [], []

    for d in distance_bins:
        if d == "15+":
            p_sel = pass_plays[pass_plays["pff_DISTANCE"] >= 15]
            r_sel = run_plays[run_plays["pff_DISTANCE"] >= 15]
            s_sel = scramble_plays[scramble_plays["pff_DISTANCE"] >= 15]
            total_sel = plays[plays["pff_DISTANCE"] >= 15]
        else:
            p_sel = pass_plays[pass_plays["pff_DISTANCE"] == d]
            r_sel = run_plays[run_plays["pff_DISTANCE"] == d]
            s_sel = scramble_plays[scramble_plays["pff_DISTANCE"] == d]
            total_sel = plays[plays["pff_DISTANCE"] == d]

        cp, cr, cs = len(p_sel), len(r_sel), len(s_sel)
        counts_pass.append(cp)
        counts_run.append(cr)
        counts_scramble.append(cs)

        total = len(total_sel)
        if total > 0:
            pp, pr, ps = cp / total, cr / total, cs / total
            # Renormalise: the down/distance total also contains special teams
            # and other non run/pass snaps, which we don't chart.
            s = pp + pr + ps
            if s > 0:
                pp, pr, ps = pp / s, pr / s, ps / s
        else:
            pp = pr = ps = 0.0

        percentages_pass.append(pp * 100.0)
        percentages_run.append(pr * 100.0)
        percentages_scramble.append(ps * 100.0)

    bar_width = 0.35
    x = np.arange(len(distance_bins))

    plt.figure(figsize=(12, 7))
    pass_bars = plt.bar(x, percentages_pass, bar_width, label="Pass Plays", color=PASS_COLOR)
    scramble_bars = plt.bar(
        x, percentages_scramble, bar_width, bottom=percentages_pass,
        label="Scramble Plays", color=SCRAMBLE_COLOR,
    )
    run_bars = plt.bar(x + bar_width, percentages_run, bar_width, label="Run Plays", color=RUN_COLOR)

    _label_bars(pass_bars, counts_pass, 2)
    _label_bars(scramble_bars, counts_scramble, 2, stacked=True)
    _label_bars(run_bars, counts_run, 2)

    plt.xlabel("Distance (Yards)")
    plt.ylabel("Percentage of Plays (%)")
    plt.ylim(0, 105)  # headroom for labels over a 100% stack
    plt.title(f"{school} Down #{desired_down}: % of Plays by Distance")
    plt.xticks(x + bar_width / 2, distance_bins)
    plt.legend()
    plt.grid(axis="y")

    _save(f"{school}_{desired_down}_%plays.png", out_dir, show)


def playcall_success_by_distance(df, desired_down, school="Brown offense", out_dir=".", show=False):
    """Conversion rate by distance, 1-10 and 11+."""
    import matplotlib.pyplot as plt

    _, pass_plays, run_plays, scramble_plays = _split_plays(df, desired_down)

    success_rates_pass, success_rates_run, success_rates_scramble = [], [], []
    counts_pass, counts_run, counts_scramble = [], [], []

    def _at(frame, distance):
        if distance == "11+":
            return frame[frame["pff_DISTANCE"] >= 11]
        return frame[frame["pff_DISTANCE"] == distance]

    for distance in list(range(1, 11)) + ["11+"]:
        p, r, s = _at(pass_plays, distance), _at(run_plays, distance), _at(scramble_plays, distance)

        cp, cr, cs = len(p), len(r), len(s)
        counts_pass.append(cp)
        counts_run.append(cr)
        counts_scramble.append(cs)

        sp = (p["pff_FIRST_DOWN_GAINED"] == 1).sum()
        sr = (r["pff_FIRST_DOWN_GAINED"] == 1).sum()
        ss = (s["pff_FIRST_DOWN_GAINED"] == 1).sum()

        success_rates_pass.append(sp / cp if cp > 0 else 0.0)
        success_rates_run.append(sr / cr if cr > 0 else 0.0)
        success_rates_scramble.append(ss / cs if cs > 0 else 0.0)

    distances = list(range(1, 11)) + ["11+"]
    bar_width = 0.25
    index = np.arange(len(distances))

    plt.figure(figsize=(10, 6))
    pass_bars = plt.bar(index, success_rates_pass, bar_width, label="Pass Success Rate", color=PASS_COLOR)
    run_bars = plt.bar(index + bar_width, success_rates_run, bar_width, label="Run Success Rate", color=RUN_COLOR)
    scramble_bars = plt.bar(
        index + 2 * bar_width, success_rates_scramble, bar_width,
        label="Scramble Success Rate", color=SCRAMBLE_COLOR,
    )

    _label_bars(pass_bars, counts_pass, 0.02)
    _label_bars(run_bars, counts_run, 0.02)
    _label_bars(scramble_bars, counts_scramble, 0.02)

    plt.xlabel("Distance (Yards)")
    plt.ylabel("Success Rate")
    plt.ylim(0, 1.06)
    plt.title(f"{school} Down #{desired_down}: Conversion % by Distance")
    plt.xticks(index + bar_width, distances)
    plt.legend()
    plt.grid(True)

    _save(f"{school}_{desired_down}_%success.png", out_dir, show)


def playcall_success_by_distance_category(df, desired_down, school="Brown offense", out_dir=".", show=False):
    """Conversion rate bucketed into 1-2 / 3-6 / 7-10 / 11+."""
    import matplotlib.pyplot as plt

    df = df[df["pff_DOWN"] == desired_down].copy()
    df["distance_category"] = pd.cut(
        df["pff_DISTANCE"],
        bins=[0, 2, 6, 10, np.inf],
        labels=DISTANCE_CATEGORIES,
        right=True,
        include_lowest=True,
    )

    _, pass_plays, run_plays, scramble_plays = _split_plays(df, desired_down)

    success_rates_pass, success_rates_run, success_rates_scramble = [], [], []
    counts_pass, counts_run, counts_scramble = [], [], []

    for category in DISTANCE_CATEGORIES:
        p = pass_plays[pass_plays["distance_category"] == category]
        r = run_plays[run_plays["distance_category"] == category]
        s = scramble_plays[scramble_plays["distance_category"] == category]

        cp, cr, cs = len(p), len(r), len(s)
        counts_pass.append(cp)
        counts_run.append(cr)
        counts_scramble.append(cs)

        success_rates_pass.append(len(p[p["pff_FIRST_DOWN_GAINED"] == 1]) / cp if cp > 0 else 0)
        success_rates_run.append(len(r[r["pff_FIRST_DOWN_GAINED"] == 1]) / cr if cr > 0 else 0)
        success_rates_scramble.append(len(s[s["pff_FIRST_DOWN_GAINED"] == 1]) / cs if cs > 0 else 0)

    bar_width = 0.25
    index = np.arange(len(DISTANCE_CATEGORIES))

    plt.figure(figsize=(10, 6))
    pass_bars = plt.bar(index, success_rates_pass, bar_width, label="Pass Success Rate", color=PASS_COLOR)
    run_bars = plt.bar(index + bar_width, success_rates_run, bar_width, label="Run Success Rate", color=RUN_COLOR)
    scramble_bars = plt.bar(
        index + 2 * bar_width, success_rates_scramble, bar_width,
        label="Scramble Success Rate", color=SCRAMBLE_COLOR,
    )

    _label_bars(pass_bars, counts_pass, 0.02)
    _label_bars(run_bars, counts_run, 0.02)
    _label_bars(scramble_bars, counts_scramble, 0.02)

    plt.xlabel("Distance Category")
    plt.ylabel("Success Rate")
    plt.title(f"{school} Down #{desired_down}: Conversion % by Distance Category")
    plt.xticks(index + bar_width, DISTANCE_CATEGORIES)
    plt.legend()
    plt.grid(True)

    _save(f"{school}_{desired_down}_%success_category.png", out_dir, show)


def print_summary(label, raw, cleaned):
    """Sanity check on what actually made it into the charts."""
    print(f"\n=== {label} ===")
    print(f"raw rows: {len(raw):,}")
    if "pff_GAMESEASON" in raw.columns:
        seasons = sorted(
            pd.to_numeric(raw["pff_GAMESEASON"], errors="coerce").dropna().unique().astype(int)
        )
        print(f"seasons present: {seasons}")
    if "pff_GAMEDATE" in raw.columns and len(raw):
        print(f"date range: {raw['pff_GAMEDATE'].min()} -> {raw['pff_GAMEDATE'].max()}")
    for down in (3, 4):
        _, p, r, s = _split_plays(cleaned, down)
        print(f"  down {down}: {len(p)} pass, {len(r)} run, {len(s)} scramble "
              f"({len(p) + len(r) + len(s)} charted)")


def run_all_plots(
    offense_csv,
    defense_csv,
    school_name,
    out_dir=".",
    min_season=None,
    recent_years=None,
    show=False,
    defense_pct_plays=True,
):
    """Generate the full 3rd/4th down packet for one team."""
    offense_raw = pd.read_csv(offense_csv, low_memory=False)
    defense_raw = pd.read_csv(defense_csv, low_memory=False)

    offense_raw = apply_season_filter(offense_raw, min_season, recent_years)
    defense_raw = apply_season_filter(defense_raw, min_season, recent_years)

    o_clean = clean_data(offense_raw)
    d_clean = clean_data(defense_raw)

    print_summary(f"{school_name} - OFFENSE", offense_raw, o_clean)
    print_summary(f"{school_name} - DEFENSE", defense_raw, d_clean)
    print()

    for down in (3, 4):
        side = f"{school_name} offense"
        playcall_by_distance(o_clean, down, side, out_dir, show)
        play_percentage_by_distance(o_clean, down, side, out_dir, show)
        playcall_success_by_distance(o_clean, down, side, out_dir, show)
        playcall_success_by_distance_category(o_clean, down, side, out_dir, show)

    for down in (3, 4):
        side = f"{school_name} defense"
        playcall_by_distance(d_clean, down, side, out_dir, show)
        if defense_pct_plays:
            play_percentage_by_distance(d_clean, down, side, out_dir, show)
        playcall_success_by_distance(d_clean, down, side, out_dir, show)
        playcall_success_by_distance_category(d_clean, down, side, out_dir, show)


def main():
    parser = argparse.ArgumentParser(
        description="3rd & 4th down breakdown charts from PFF exports."
    )
    parser.add_argument("offense_csv", help="Path to the offense play-by-play export")
    parser.add_argument("defense_csv", help="Path to the defense play-by-play export")
    parser.add_argument("school_name", help='Team label used in titles and filenames, e.g. "Brown"')
    parser.add_argument("--out-dir", default=".", help="Where to write the PNGs (default: cwd)")
    parser.add_argument("--min-season", type=int, default=None, help="Keep seasons >= this year")
    parser.add_argument("--recent-years", type=int, default=None, help="Keep the last N seasons in the file")
    parser.add_argument("--show", action="store_true", help="Open each chart in a window as it is made")
    parser.add_argument(
        "--no-defense-pct-plays",
        action="store_true",
        help="Skip the defense %%plays charts (matches the 2025 packets)",
    )
    args = parser.parse_args()

    if not args.show:
        matplotlib.use("Agg")

    run_all_plots(
        offense_csv=args.offense_csv,
        defense_csv=args.defense_csv,
        school_name=args.school_name,
        out_dir=args.out_dir,
        min_season=args.min_season,
        recent_years=args.recent_years,
        show=args.show,
        defense_pct_plays=not args.no_defense_pct_plays,
    )


if __name__ == "__main__":
    main()
