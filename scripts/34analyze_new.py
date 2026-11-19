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

Ivy reference ticks compare pass/run call share on the combined charts and
pass/run conversion rate on the bucketed charts. Combined charts also show
Ivy conversion diamonds scaled to the team's call share and an aligned strip
of explicit team / Ivy conversion percentages; scrambles have no reference.
References pool all plays in the Ivy exports (independent of the team's season
filters). Override the default exports with --ivy-offense-csv and --ivy-defense-csv.

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
import re
from pathlib import Path

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

IVY_DATA_DIR = Path(__file__).resolve().parents[1] / "3rd_4th_down" / "2025" / "Ivy Averages"
IVY_OFFENSE_PATH = IVY_DATA_DIR / "ivy_offense.csv"
IVY_DEFENSE_PATH = IVY_DATA_DIR / "ivy_defense.csv"


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


def _ivy_benchmarks(ivy_df, desired_down, bucketed=False):
    """Pooled pass/run shares and conversions, with NaN for absent samples.

    Call shares use pass + run + scramble as the denominator, matching the
    team bars. Special teams are excluded; scrambles get no benchmark series.
    """
    plays = ivy_df[ivy_df["pff_DOWN"] == desired_down].copy()
    if bucketed:
        plays["distance_category"] = pd.cut(
            plays["pff_DISTANCE"], bins=[0, 2, 6, 10, np.inf],
            labels=DISTANCE_CATEGORIES, right=True, include_lowest=True,
        )
        bins = DISTANCE_CATEGORIES
    else:
        bins = list(range(1, 15)) + ["15+"]

    shares = {"pass": [], "run": []}
    conversions = {"pass": [], "run": []}
    for distance in bins:
        if bucketed:
            sel = plays[plays["distance_category"] == distance]
        elif distance == "15+":
            sel = plays[plays["pff_DISTANCE"] >= 15]
        else:
            sel = plays[plays["pff_DISTANCE"] == distance]
        _, p, r, s = _split_plays(sel, desired_down)
        total = len(p) + len(r) + len(s)
        for key, frame in (("pass", p), ("run", r)):
            shares[key].append(len(frame) / total * 100 if total else np.nan)
            conversions[key].append(
                (frame["pff_FIRST_DOWN_GAINED"] == 1).mean() if len(frame) else np.nan
            )
    return shares, conversions


def _draw_ivy_ticks(ax, centers, values, bar_width, label, label_pad):
    """Short, outlined ticks across pass/run bars; return one legend handle."""
    import matplotlib.patheffects as pe

    handle = None
    for key in ("pass", "run"):
        for x, value in zip(centers[key], values[key]):
            if not np.isfinite(value):
                continue
            line, = ax.plot(
                [x - bar_width * 0.44, x + bar_width * 0.44], [value, value],
                color="#2d2d2d", linewidth=2.5, solid_capstyle="round",
                label=label if handle is None else "_nolegend_", zorder=5,
                path_effects=[pe.withStroke(linewidth=4.5, foreground="white")],
            )
            if handle is None:
                handle = line
            # Keep count labels readable when a reference sits near a bar top.
            for text in ax.texts:
                tx, ty = text.get_position()
                if (text.get_va() == "bottom" and np.isclose(tx, x)
                        and abs(ty - value) <= label_pad):
                    text.set_y(value + label_pad)
    return handle


def _draw_ivy_conversion_markers(ax, centers, shares, counts, ivy_rates, bar_width, team_name):
    """Mark the expected solid-fill boundary at Ivy conversion, holding team mix fixed."""
    from matplotlib.lines import Line2D

    style = dict(marker="D", markersize=5, markerfacecolor="white",
                 markeredgecolor="#2d2d2d", markeredgewidth=1.3, linestyle="none")
    for key in ("pass", "run"):
        for x, share, count, rate in zip(centers[key], shares[key], counts[key], ivy_rates[key]):
            if count and np.isfinite(rate):
                # Offset toward the bar's edge to keep converted-count labels readable.
                ax.plot(x + bar_width * .30, share * rate, zorder=6, **style)
    return Line2D([], [], label=f"Ivy conversion at {team_name} mix", **style)


def _draw_conversion_strip(ax, centers, team_rates, ivy_rates, school, team_name):
    """Separate explicit conversion percentages from the plot's call-share axis."""
    fig = ax.figure
    fig.set_size_inches(13, 8.7)
    fig.subplots_adjust(left=.065, right=.985, bottom=.26, top=.89)
    strip = fig.add_axes([.065, .035, .92, .105])
    strip.set_xlim(ax.get_xlim())
    strip.set_ylim(0, 2)
    strip.set_axis_off()
    fig.text(.065, .165, _conversion_label(school).upper(), fontsize=9,
             fontweight="bold", color="#222222")
    fig.text(.265, .165, f"{team_name} / Ivy  ·  converted ÷ calls within each play type",
             fontsize=8.5, color="#555555")
    for i, center in enumerate(centers):
        if i % 2 == 0:
            strip.axvspan(center - .5, center + .5, color="#f3f3f3", zorder=0)
    strip.axhline(1, color="#dddddd", linewidth=.6)
    for key, y, color in (("pass", 1.5, PASS_COLOR), ("run", .5, RUN_COLOR)):
        strip.text(-.016, y / 2, key.title(), transform=strip.transAxes,
                   ha="right", va="center", fontsize=8, color=color, fontweight="bold")
        for x, team_rate, ivy_rate in zip(centers, team_rates[key], ivy_rates[key]):
            # NaN means no sample; preserve genuine zero conversion as 0%.
            team_text = f"{team_rate:.0%}" if np.isfinite(team_rate) else "—"
            ivy_text = f"{ivy_rate:.0%}" if np.isfinite(ivy_rate) else "—"
            strip.text(x - .045, y, team_text, ha="right", va="center",
                       fontsize=7.7, fontweight="bold", color="#222222")
            strip.text(x, y, "/", ha="center", va="center", fontsize=7.7, color="#999999")
            strip.text(x + .045, y, ivy_text, ha="left", va="center",
                       fontsize=7.7, color="#666666")
    fig.text(.065, .009, "— = no calls in that sample. Rates rounded to whole percentages.",
             fontsize=7, color="#666666")


def play_mix_and_conversion(df, desired_down, school="Brown offense", out_dir=".", show=False,
                            ivy_df=None):
    """
    One chart carrying all three numbers, per distance 1-14 and 15+:

        bar height    -> % of calls at that distance
        label above   -> # of calls
        solid / faded -> conversion rate within that play type

    Layout matches the old %plays chart: pass with scramble stacked on top,
    run beside it. Each segment is split into the part that converted (solid)
    and the part that did not (tinted), separated by a thin white gap.
    With Ivy data, diamonds mark the expected solid boundary at Ivy conversion;
    a separate strip lists team / Ivy conversion rates for pass and run.
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
    if ivy_df is not None:
        ivy_shares, ivy_rates = _ivy_benchmarks(ivy_df, desired_down)
        team_name = re.split(r"\s+(?:offense|defense)\b", school, maxsplit=1, flags=re.I)[0]
        centers = {"pass": x, "run": x + bar_width}
        reference = _draw_ivy_ticks(
            plt.gca(), centers, ivy_shares,
            bar_width, "Ivy avg call share (pass/run)", label_pad=2,
        )
        if reference is not None:
            handles.append(reference)
        handles.append(_draw_ivy_conversion_markers(
            plt.gca(), centers, pct, counts, ivy_rates, bar_width, team_name,
        ))

    plt.xlabel("Distance (Yards)")
    plt.ylabel("Percentage of Calls (%)")
    plt.ylim(0, 108)  # headroom for labels over a 100% stack
    verb = "Allowed " if "defense" in school.lower() else ""
    plt.title(f"{school} Down #{desired_down}: Play Mix & Conversion {verb}by Distance",
              pad=48 if ivy_df is not None else 42)
    plt.xticks(x + bar_width / 2, distance_bins)
    plt.legend(handles=handles, ncol=4 if ivy_df is not None else 5,
               fontsize=8.5 if ivy_df is not None else 9, loc="lower center",
               bbox_to_anchor=(0.5, 1.02), frameon=False)
    plt.grid(axis="y", alpha=0.3)
    plt.gca().set_axisbelow(True)

    if ivy_df is not None:
        team_rates = {
            key: [converted[key][i] / n if n else np.nan for i, n in enumerate(counts[key])]
            for key in ("pass", "run")
        }
        _draw_conversion_strip(plt.gca(), x + bar_width / 2, team_rates, ivy_rates, school, team_name)

    # The conversion strip uses explicit axes positions, so retain its layout.
    _save(f"{school}_{desired_down}_mix_conversion.png", out_dir, show, tight=ivy_df is None)


def conversion_by_distance_category(df, desired_down, school="Brown offense", out_dir=".", show=False,
                                    ivy_df=None):
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

    if ivy_df is not None:
        _, ivy_conversions = _ivy_benchmarks(ivy_df, desired_down, bucketed=True)
        _draw_ivy_ticks(
            plt.gca(), {"pass": index, "run": index + bar_width}, ivy_conversions,
            bar_width, "Ivy avg conversion (pass/run)", label_pad=0.02,
        )

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
    ivy_offense_csv=IVY_OFFENSE_PATH,
    ivy_defense_csv=IVY_DEFENSE_PATH,
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

    ivy_o = clean_data(pd.read_csv(ivy_offense_csv, usecols=REQUIRED_COLUMNS, low_memory=False))
    ivy_d = clean_data(pd.read_csv(ivy_defense_csv, usecols=REQUIRED_COLUMNS, low_memory=False))

    print_summary(f"{school_name} - OFFENSE", offense_raw, o_clean)
    print_summary(f"{school_name} - DEFENSE", defense_raw, d_clean)
    print()

    for clean, side_name, ivy in ((o_clean, "offense", ivy_o), (d_clean, "defense", ivy_d)):
        side = f"{school_name} {side_name}"
        for down in (3, 4):
            play_mix_and_conversion(clean, down, side, out_dir, show, ivy_df=ivy)
            conversion_by_distance_category(clean, down, side, out_dir, show, ivy_df=ivy)


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
    parser.add_argument("--ivy-offense-csv", default=IVY_OFFENSE_PATH,
                        help="Ivy offense reference export (default: repository Ivy Averages file)")
    parser.add_argument("--ivy-defense-csv", default=IVY_DEFENSE_PATH,
                        help="Ivy defense reference export (default: repository Ivy Averages file)")
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
        ivy_offense_csv=args.ivy_offense_csv,
        ivy_defense_csv=args.ivy_defense_csv,
    )


if __name__ == "__main__":
    main()
