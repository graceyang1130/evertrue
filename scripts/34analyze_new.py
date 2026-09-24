"""
3rd & 4th down breakdown charts from PFF play-by-play exports -- NEW chart set.

This is the leaner redesign: 8 charts per team instead of 16. It sits alongside
34analyze.py, which still produces the original four chart types, so the two can
be run and compared independently.

Per side (offense, defense) and per down (3, 4):
  - play mix & conversion (per-yard)  -- one bar carries % of calls (height),
    # of calls (label above) and conversion rate (solid vs faded fraction).
    Replaces the old #plays, %plays and %success charts.
  - conversion rate (bucketed)        -- the old %success_category chart,
    relabelled from "Success" to "Conversion".

Generic version: pass CSV paths and a school name instead of editing the file.
This replaces the per-opponent copies (yale_breakdown.py, dartmouth_breakdown.py,
better34analysis.py, ...) which were identical apart from three lines.

Usage (command line):
    python 34analyze_new.py OFFENSE.csv DEFENSE.csv "Brown" --out-dir charts

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


def _tint(color, amount=0.62):
    """Blend a series color toward white. Used for the not-converted fill."""
    from matplotlib.colors import to_rgb

    r, g, b = to_rgb(color)
    return (r + (1 - r) * amount, g + (1 - g) * amount, b + (1 - b) * amount)


def _conversion_label(school):
    """Defense charts are reading conversions the opponent got, so say so."""
    return "Conversion Rate Allowed" if "defense" in school.lower() else "Conversion Rate"


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


def play_mix_and_conversion(df, desired_down, school="Brown offense", out_dir=".", show=False):
    """
    One chart carrying all three numbers, per distance 1-14 and 15+:

        bar height    -> % of calls at that distance
        label above   -> # of calls
        solid / faded -> conversion rate within that play type

    Layout matches the old %plays chart: pass with scramble stacked on top,
    run beside it. Each segment is split into the part that converted (solid)
    and the part that did not (tinted), separated by a thin white gap.
    """
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    plays, pass_plays, run_plays, scramble_plays = _split_plays(df, desired_down)
    distance_bins = list(range(1, 15)) + ["15+"]

    frames = {"pass": pass_plays, "run": run_plays, "scramble": scramble_plays}
    counts = {k: [] for k in frames}
    converted = {k: [] for k in frames}
    pct = {k: [] for k in frames}

    for d in distance_bins:
        sel = {}
        for key, frame in frames.items():
            sel[key] = (frame[frame["pff_DISTANCE"] >= 15] if d == "15+"
                        else frame[frame["pff_DISTANCE"] == d])
        total_sel = (plays[plays["pff_DISTANCE"] >= 15] if d == "15+"
                     else plays[plays["pff_DISTANCE"] == d])

        for key in frames:
            counts[key].append(len(sel[key]))
            converted[key].append(int((sel[key]["pff_FIRST_DOWN_GAINED"] == 1).sum()))

        # Same renormalisation as the old %plays chart: the down/distance total
        # also holds special teams and other non run/pass snaps, which we drop.
        total = len(total_sel)
        if total > 0:
            shares = {k: counts[k][-1] / total for k in frames}
            s = sum(shares.values())
            if s > 0:
                shares = {k: v / s for k, v in shares.items()}
        else:
            shares = {k: 0.0 for k in frames}
        for key in frames:
            pct[key].append(shares[key] * 100.0)

    # Split each play type's share into the converted and non-converted parts.
    solid, faded = {}, {}
    for key in frames:
        solid[key] = [pct[key][i] * (converted[key][i] / counts[key][i]) if counts[key][i] else 0.0
                      for i in range(len(distance_bins))]
        faded[key] = [pct[key][i] - solid[key][i] for i in range(len(distance_bins))]

    bar_width = 0.35
    x = np.arange(len(distance_bins))
    gap = {"edgecolor": "white", "linewidth": 1.0}

    plt.figure(figsize=(13, 7))

    # Left group: pass, with scramble stacked on top (unchanged grouping).
    pass_base = [0.0] * len(distance_bins)
    plt.bar(x, solid["pass"], bar_width, bottom=pass_base, color=PASS_COLOR, **gap)
    plt.bar(x, faded["pass"], bar_width, bottom=solid["pass"], color=_tint(PASS_COLOR), **gap)

    scr_base = list(pct["pass"])
    plt.bar(x, solid["scramble"], bar_width, bottom=scr_base, color=SCRAMBLE_COLOR, **gap)
    plt.bar(x, faded["scramble"], bar_width,
            bottom=[scr_base[i] + solid["scramble"][i] for i in range(len(x))],
            color=_tint(SCRAMBLE_COLOR), **gap)

    # Right group: run.
    plt.bar(x + bar_width, solid["run"], bar_width, color=RUN_COLOR, **gap)
    plt.bar(x + bar_width, faded["run"], bar_width, bottom=solid["run"],
            color=_tint(RUN_COLOR), **gap)

    # Call counts above each bar. The pass label used to sit at the top of the
    # pass segment, which put it inside the scramble cap whenever one existed;
    # both now go above the whole stack as "pass + scramble".
    for i in range(len(distance_bins)):
        n_pass, n_scr, n_run = counts["pass"][i], counts["scramble"][i], counts["run"][i]
        if n_pass or n_scr:
            if n_pass and n_scr:
                label = f"{n_pass} + {n_scr}"
            else:
                label = str(n_pass or n_scr)
            plt.text(x[i], pct["pass"][i] + pct["scramble"][i] + 2, label,
                     ha="center", va="bottom", fontsize=8)
        if n_run > 0:
            plt.text(x[i] + bar_width, pct["run"][i] + 2, str(n_run),
                     ha="center", va="bottom", fontsize=8)

    # Converted count inside each solid segment, where there is room for it.
    bases = {"pass": pass_base, "scramble": scr_base, "run": [0.0] * len(distance_bins)}
    offsets = {"pass": 0.0, "scramble": 0.0, "run": bar_width}
    for key in ("pass", "scramble", "run"):
        for i in range(len(distance_bins)):
            if solid[key][i] >= 8 and converted[key][i] > 0:
                plt.text(x[i] + offsets[key], bases[key][i] + solid[key][i] / 2,
                         str(converted[key][i]), ha="center", va="center",
                         fontsize=7, color="white", fontweight="bold")

    handles = [
        Patch(facecolor=PASS_COLOR, label="Pass Plays"),
        Patch(facecolor=SCRAMBLE_COLOR, label="Scramble Plays"),
        Patch(facecolor=RUN_COLOR, label="Run Plays"),
        Patch(facecolor="#6b6b6b", label="Converted (solid)"),
        Patch(facecolor=_tint("#6b6b6b"), label="Not converted (faded)"),
    ]

    plt.xlabel("Distance (Yards)")
    plt.ylabel("Percentage of Calls (%)")
    plt.ylim(0, 108)  # headroom for labels over a 100% stack
    verb = "Allowed " if "defense" in school.lower() else ""
    plt.title(f"{school} Down #{desired_down}: Play Mix & Conversion {verb}by Distance", pad=42)
    plt.xticks(x + bar_width / 2, distance_bins)
    plt.legend(handles=handles, ncol=5, fontsize=9, loc="lower center",
               bbox_to_anchor=(0.5, 1.02), frameon=False)
    plt.grid(axis="y", alpha=0.3)
    plt.gca().set_axisbelow(True)

    _save(f"{school}_{desired_down}_mix_conversion.png", out_dir, show)


def conversion_by_distance_category(df, desired_down, school="Brown offense", out_dir=".", show=False):
    """Conversion rate on a true 0-100% axis, bucketed into 1-2 / 3-6 / 7-10 / 11+."""
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
    pass_bars = plt.bar(index, success_rates_pass, bar_width, label="Pass", color=PASS_COLOR)
    run_bars = plt.bar(index + bar_width, success_rates_run, bar_width, label="Run", color=RUN_COLOR)
    scramble_bars = plt.bar(
        index + 2 * bar_width, success_rates_scramble, bar_width,
        label="Scramble", color=SCRAMBLE_COLOR,
    )

    _label_bars(pass_bars, counts_pass, 0.02)
    _label_bars(run_bars, counts_run, 0.02)
    _label_bars(scramble_bars, counts_scramble, 0.02)

    plt.xlabel("Distance Category")
    plt.ylabel(_conversion_label(school))
    plt.title(f"{school} Down #{desired_down}: {_conversion_label(school)} by Distance Category")
    plt.xticks(index + bar_width, DISTANCE_CATEGORIES)
    plt.legend()
    plt.grid(axis="y", alpha=0.3)
    plt.gca().set_axisbelow(True)

    _save(f"{school}_{desired_down}_conversion_category.png", out_dir, show)


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
):
    """
    Generate the 3rd/4th down packet for one team: 8 charts.

    Per side (offense, defense) and per down (3, 4):
      - play mix & conversion, per-yard distance
      - conversion rate, bucketed distance
    """
    offense_raw = pd.read_csv(offense_csv, low_memory=False)
    defense_raw = pd.read_csv(defense_csv, low_memory=False)

    offense_raw = apply_season_filter(offense_raw, min_season, recent_years)
    defense_raw = apply_season_filter(defense_raw, min_season, recent_years)

    o_clean = clean_data(offense_raw)
    d_clean = clean_data(defense_raw)

    print_summary(f"{school_name} - OFFENSE", offense_raw, o_clean)
    print_summary(f"{school_name} - DEFENSE", defense_raw, d_clean)
    print()

    for clean, side_name in ((o_clean, "offense"), (d_clean, "defense")):
        side = f"{school_name} {side_name}"
        for down in (3, 4):
            play_mix_and_conversion(clean, down, side, out_dir, show)
            conversion_by_distance_category(clean, down, side, out_dir, show)


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
    )


if __name__ == "__main__":
    main()
