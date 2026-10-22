"""Audit and plot possessions producing the final winning lead in Q4.

Run: MPLCONFIGDIR=/private/tmp/evertrue-mpl python3 tos/plot_winning_drives.py
No start-time cutoff is applied by default. Earlier outputs are preserved.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plot_drive_time_distribution import clock_seconds, fcs_codes, fmt

ROOT = Path(__file__).resolve().parents[1]
PLOTS = ROOT / "output/plots"
PDFS = ROOT / "output/pdf"
KEY = ["pff_GAMEID", "pff_OFFTEAM", "pff_DRIVE"]


def load_plays() -> pd.DataFrame:
    columns = [
        "pff_GAMEID", "pff_GAMESEASON", "pff_SORTORDER", "pff_DRIVE", "pff_QUARTER",
        "pff_CLOCK", "pff_OFFTEAM", "pff_DEFTEAM", "pff_OFFSCORE", "pff_DEFSCORE",
        "pff_DOWN", "pff_SPECIALTEAMSTYPE", "pff_2MINUTE", "pff_DRIVEENDEVENT",
        "winner", "pff_TOUCHDOWN", "pff_KICKRESULT", "pff_NOPLAY",
        "pff_YARDS_TO_GOAL_LINE", "pff_OFF_TIMEOUTS_REMAINING",
    ]
    plays = pd.read_csv(ROOT / "data/ncaa/pbp.csv.gz", usecols=columns, low_memory=False)
    plays = plays.sort_values(["pff_GAMEID", "pff_SORTORDER"]).reset_index(drop=True)
    plays["clock"] = clock_seconds(plays.pff_CLOCK)
    return plays


def drive_table(plays: pd.DataFrame) -> pd.DataFrame:
    # Drive numbers are team-specific. Omitting OFFTEAM combines opponents.
    valid = (plays.pff_SPECIALTEAMSTYPE.isna() & plays.pff_DOWN.between(1, 4)
             & ~plays.pff_NOPLAY.eq(1))
    snaps = plays[valid].copy()
    snaps["hurry"] = pd.to_numeric(snaps.pff_2MINUTE, errors="coerce").eq(2)
    drives = snaps.groupby(KEY, sort=False).agg(
        season=("pff_GAMESEASON", "first"), defense=("pff_DEFTEAM", "first"),
        q_first=("pff_QUARTER", "first"), q_last=("pff_QUARTER", "last"),
        c_first=("clock", "first"), c_last=("clock", "last"),
        first_sort=("pff_SORTORDER", "first"), last_sort=("pff_SORTORDER", "last"),
        offscore=("pff_OFFSCORE", "first"), defscore=("pff_DEFSCORE", "first"),
        end=("pff_DRIVEENDEVENT", "last"), snaps=("hurry", "size"),
        hurry=("hurry", "mean"), winner=("winner", "first"),
        yards_to_goal=("pff_YARDS_TO_GOAL_LINE", "first"),
        timeouts=("pff_OFF_TIMEOUTS_REMAINING", "first"),
    ).reset_index().rename(columns={"pff_OFFTEAM": "offense"})
    codes = fcs_codes()
    drives["fcs"] = [team in codes[int(season)]
                     for team, season in zip(drives.offense, drives.season)]
    drives["start_regulation_seconds"] = (4 - drives.q_first) * 900 + drives.c_first
    drives["snap_span_seconds"] = (drives.q_last - drives.q_first) * 900 + drives.c_first - drives.c_last
    return drives


def scoring_snap(row: pd.Series, game: pd.DataFrame) -> pd.Series | None:
    """Find this possession's TD or its immediately following FG attempt.

    Special teams rows usually have no DRIVE, so a FG cannot be joined by
    drive number. Search only until the next possession/kickoff, never beyond it.
    """
    if row.end == "TOUCHDOWN":
        own_td = game.pff_TOUCHDOWN.fillna("").str.split().str[0].eq(row.offense)
        found = game[
            game.pff_SORTORDER.between(row.first_sort, row.last_sort)
            & game.pff_OFFTEAM.eq(row.offense) & own_td & ~game.pff_NOPLAY.eq(1)
        ]
        return found.iloc[-1] if len(found) else None
    after = game[game.pff_SORTORDER.gt(row.last_sort)]
    boundary = after[
        after.pff_DRIVE.notna() | after.pff_SPECIALTEAMSTYPE.eq("KICKOFF")
        | after.pff_QUARTER.ne(4)
    ]
    limit = boundary.pff_SORTORDER.iloc[0] if len(boundary) else np.inf
    kicks = after[
        after.pff_SORTORDER.lt(limit) & after.pff_QUARTER.eq(4)
        & after.pff_OFFTEAM.eq(row.offense)
        & after.pff_SPECIALTEAMSTYPE.eq("FIELD GOAL") & ~after.pff_NOPLAY.eq(1)
    ]
    if kicks.empty:
        return None
    kick = kicks.iloc[0]
    return kick if str(kick.pff_KICKRESULT).startswith("MADE") else None


def scores_for(frame: pd.DataFrame, offense: str) -> tuple[np.ndarray, np.ndarray]:
    own = frame.pff_OFFTEAM.eq(offense)
    return (np.where(own, frame.pff_OFFSCORE, frame.pff_DEFSCORE),
            np.where(own, frame.pff_DEFSCORE, frame.pff_OFFSCORE))


def holds_winning_lead(row: pd.Series, terminal: pd.Series,
                       game: pd.DataFrame, final: pd.Series) -> bool:
    """Check the lead after the try, every remaining Q4 score, and final score."""
    if final.winner != row.offense or game.pff_QUARTER.gt(4).any():
        return False
    after = game[game.pff_SORTORDER.gt(terminal.pff_SORTORDER)]
    # Tries have no drive ID; wait until the kickoff or next actual possession.
    boundary = after[after.pff_SPECIALTEAMSTYPE.eq("KICKOFF") | after.pff_DRIVE.notna()]
    if len(boundary):
        future = after[after.pff_SORTORDER.ge(boundary.pff_SORTORDER.iloc[0])]
        own, other = scores_for(future, row.offense)
        if not np.all(own > other):
            return False
        # Ensure this score actually made the lead; don't attribute a later score.
        points = own[0] - row.offscore
        if points not in ((3,) if row.end == "FIELD GOAL" else (6, 7, 8)):
            return False
    else:
        own = final.score_a if final.team_a == row.offense else final.score_b
        other = final.score_b if final.team_a == row.offense else final.score_a
        points = own - row.offscore
        if own <= other or points not in ((3,) if row.end == "FIELD GOAL" else (6, 7, 8)):
            return False
    return True


def winning_drives(plays: pd.DataFrame, drives: pd.DataFrame,
                   games: pd.DataFrame, window: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    start = drives.start_regulation_seconds.gt(0)
    if window is not None:
        start &= drives.start_regulation_seconds.le(window)
    candidates = drives[
        drives.q_first.between(1, 4) & drives.q_last.eq(4) & start
        & drives.offscore.le(drives.defscore) & drives.offense.eq(drives.winner)
        & drives.end.isin(["TOUCHDOWN", "FIELD GOAL"])
    ].copy()
    candidates["status"] = ""
    candidates["score_snap_clock"] = np.nan
    candidates["score_sort"] = np.nan
    by_game = dict(tuple(plays.groupby("pff_GAMEID", sort=False)))
    for i, row in candidates.iterrows():
        game = by_game[row.pff_GAMEID]
        if game.pff_QUARTER.gt(4).any():
            candidates.at[i, "status"] = "Overtime game"
            continue
        terminal = scoring_snap(row, game)
        if terminal is None:
            candidates.at[i, "status"] = "No verified offensive TD or made FG"
            continue
        candidates.at[i, "score_snap_clock"] = terminal.clock
        candidates.at[i, "score_sort"] = terminal.pff_SORTORDER
        if not holds_winning_lead(row, terminal, game, games.loc[row.pff_GAMEID]):
            candidates.at[i, "status"] = "Lead did not hold or score did not create lead"
        elif not 0 <= row.start_regulation_seconds - terminal.clock <= row.start_regulation_seconds:
            candidates.at[i, "status"] = "Invalid clock interval"
        else:
            candidates.at[i, "status"] = "Included"
    winners = candidates[candidates.status.eq("Included")].copy()
    winners["to_score_snap_seconds"] = winners.start_regulation_seconds - winners.score_snap_clock
    winners["fg_setup_seconds"] = np.where(
        winners.end.eq("FIELD GOAL"), winners.c_last - winners.score_snap_clock, 0)
    if winners.pff_GAMEID.duplicated().any():
        raise ValueError("Multiple drives claim the final winning lead in one game")
    return winners, candidates


def percentile(series: pd.Series, q: float) -> float:
    # An empirical CDF crosses its percentile at an observed value, not an
    # interpolated non-observation (the earlier charts used interpolation).
    return float(series.quantile(q, interpolation="inverted_cdf"))


def plot(winners: pd.DataFrame, window: int | None, stem: str) -> pd.DataFrame:
    navy, rust = "#193a59", "#bb6338"
    groups = [("All offenses in feed", winners, navy, "-"),
              ("FCS offenses", winners[winners.fcs], rust, "--")]
    fig = plt.figure(figsize=(13.5, 8.8), facecolor="white")
    fig.text(.075, .947, "How much clock did Q4 winning drives use?",
             fontsize=22, weight="bold", color=navy)
    fig.text(.075, .903,
             ("No drive-start cutoff | Winning score in Q4 | Offense tied or trailing | Final lead held"
              if window is None else f"First snap in final {fmt(window)} of Q4 | Offense tied or trailing | Final lead held"),
             fontsize=11, color="#4a5d6b")
    grid = fig.add_gridspec(2, 2, left=.075, right=.97, top=.81, bottom=.205,
                            height_ratios=[3.3, 1.2], hspace=.65, wspace=.22)
    summary = []
    for column, (metric, title, xlabel) in enumerate([
        ("to_score_snap_seconds", "Game clock used to reach the scoring snap",
         "First scrimmage snap to TD snap / made-FG snap"),
        ("start_regulation_seconds", "Game clock remaining when the drive began",
         "Time left in regulation at first scrimmage snap"),
    ]):
        ax = fig.add_subplot(grid[0, column])
        xmax = max(60, int(np.ceil(winners[metric].max() / 60)) * 60)
        for name, frame, color, style in groups:
            values = frame[metric].dropna().sort_values().to_numpy()
            if not len(values):
                continue
            y = 100 * np.arange(1, len(values) + 1) / len(values)
            ax.step(np.r_[0, values, xmax], np.r_[0, y, 100], where="post",
                    color=color, linestyle=style, linewidth=2.4,
                    label=f"{name} (n={len(frame)})")
        ax.set(xlim=(0, xmax), ylim=(0, 101), xlabel=xlabel,
               ylabel="Cumulative share of winning drives")
        ax.set_title(title, loc="left", fontsize=12, weight="bold", color=navy, pad=14)
        ticks = np.arange(0, xmax + 1, 60 if xmax <= 600 else 120)
        ax.set_xticks(ticks, [fmt(x) for x in ticks])
        ax.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
        ax.grid(axis="y", color="#e0e6eb", linewidth=.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color("#9eabb5")
        ax.tick_params(colors="#4a5d6b", labelsize=9.5)
        ax.xaxis.label.set(color="#4a5d6b", fontsize=10)
        ax.yaxis.label.set(color="#4a5d6b", fontsize=10)
        ax.xaxis.labelpad = 10
        ax.yaxis.labelpad = 8
        ax.legend(loc="lower right", frameon=False, fontsize=9)
        if column == 0:
            ax.axhline(75, color="#aab6bf", linewidth=.8, linestyle=":")
            for j, (name, frame, color, _) in enumerate(groups):
                if frame.empty:
                    continue
                p75 = percentile(frame[metric], .75)
                share = 100 * frame[metric].le(p75).mean()
                ax.plot(p75, share, "o", color=color, markersize=5)
                ax.annotate(f"75th: {fmt(p75)}", (p75, share), xytext=(8, -23 - j * 17),
                            textcoords="offset points", color=color, fontsize=9.5, weight="bold")

    for population, frame in [("All offenses", winners), ("FCS offenses", winners[winners.fcs]),
                               ("All: TD finish", winners[winners.end.eq("TOUCHDOWN")]),
                               ("All: FG finish", winners[winners.end.eq("FIELD GOAL")])]:
        if frame.empty:
            continue
        summary.append({"population": population, "n": len(frame),
                        "median_start_seconds": percentile(frame.start_regulation_seconds, .5),
                        **{f"used_p{q}_seconds": percentile(frame.to_score_snap_seconds, q / 100)
                           for q in [25, 50, 75, 90]}})
    stats = pd.DataFrame(summary)
    tax = fig.add_subplot(grid[1, :])
    tax.axis("off")
    tax.text(0, 1.2, "Observed winning-drive percentiles", fontsize=12, weight="bold", color=navy)
    rows = [[r.population, str(r.n), fmt(r.median_start_seconds),
             *[fmt(getattr(r, f"used_p{q}_seconds")) for q in [25, 50, 75, 90]]]
            for r in stats.itertuples()]
    table = tax.table(cellText=rows,
                      colLabels=["Population", "Drives", "Median start", "25th used", "Median used", "75th used", "90th used"],
                      cellLoc="center", colWidths=[.25, .085, .145, .13, .13, .13, .13],
                      bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False)
    table.set_fontsize(9.5)
    for (r, c), cell in table.get_celld().items():
        cell.set_edgecolor("#d8e0e7")
        cell.set_linewidth(.5)
        cell.set_text_props(color=navy)
        if r == 0:
            cell.set_facecolor("#eaf0f5")
            cell.set_text_props(weight="bold")
        elif r == 2:
            cell.set_facecolor("#f9eee8")
        elif r % 2:
            cell.set_facecolor("#f7f9fb")
    fig.text(.075, .14, "Timing includes the wait before a field-goal snap; the final play's live-ball seconds are unavailable and excluded.",
             fontsize=9, color="#536370")
    fig.text(.075, .112, "FCS is a subset of all offenses. No hurry-up or minimum-snap filter; OT-forcing ties and return TDs are excluded.",
             fontsize=9, color="#536370")
    fig.text(.075, .084, "These are durations among observed wins, not scoring probabilities. Drives beginning before Q4 are included."
             if window is None else f"These are durations among observed wins, not scoring probabilities. Start cutoff: {fmt(window)} remaining.",
             fontsize=9, color="#536370")
    fig.text(.075, .056, "Source: local PFF feed, 2023-2026 through week 4. Possession key: game + offense + drive. Percentiles use observed ranks.",
             fontsize=9, color="#536370")
    PLOTS.mkdir(parents=True, exist_ok=True)
    PDFS.mkdir(parents=True, exist_ok=True)
    fig.savefig(PLOTS / f"{stem}.png", dpi=190, facecolor="white")
    fig.savefig(PDFS / f"{stem}.pdf", facecolor="white")
    plt.close(fig)
    return stats


def plot_finishes(winners: pd.DataFrame, stem: str) -> None:
    """Show the duration shape and TD/FG mix without discarding the long tail."""
    navy, rust = "#193a59", "#bb6338"
    xmax = max(60, int(np.ceil(winners.to_score_snap_seconds.max() / 60)) * 60)
    bins = np.arange(0, xmax + 30, 30)
    fig, axes = plt.subplots(2, 2, figsize=(13.5, 8.8))
    fig.subplots_adjust(left=.075, right=.97, top=.82, bottom=.17, hspace=.45, wspace=.22)
    fig.text(.075, .947, "Winning-drive durations: frequency and scoring finish",
             fontsize=21, weight="bold", color=navy)
    fig.text(.075, .903, "Winning score in Q4 | Offense tied or trailing at start | No drive-start cutoff",
             fontsize=11, color="#4a5d6b")
    for row, (label, frame) in enumerate([("All offenses", winners), ("FCS offenses", winners[winners.fcs])]):
        left, right = axes[row]
        if frame.empty:
            continue
        left.hist(frame.to_score_snap_seconds, bins=bins,
                  weights=np.full(len(frame), 100 / len(frame)), color=navy,
                  edgecolor="white", linewidth=.65)
        left.set_title(f"{label}: share in each 30-second bin (n={len(frame)})",
                       loc="left", color=navy, weight="bold", fontsize=11)
        left.set_ylabel("Share of winning drives (%)")
        for end, color in [("TOUCHDOWN", navy), ("FIELD GOAL", rust)]:
            values = frame.loc[frame.end.eq(end), "to_score_snap_seconds"].sort_values().to_numpy()
            if not len(values):
                continue
            right.step(np.r_[0, values, xmax],
                       np.r_[0, 100 * np.arange(1, len(values) + 1) / len(values), 100],
                       where="post", color=color, linewidth=2.1,
                       label=f"{'TD' if end == 'TOUCHDOWN' else 'Made FG'} (n={len(values)})")
        right.set_title(f"{label}: cumulative duration by finish", loc="left",
                        color=navy, weight="bold", fontsize=11)
        right.set_ylim(0, 101)
        right.set_yticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
        right.set_ylabel("Cumulative share within finish type")
        right.legend(loc="lower right", frameon=False, fontsize=9)
        for ax in (left, right):
            ax.set_xlim(0, xmax)
            ticks = np.arange(0, xmax + 1, 60 if xmax <= 600 else 120)
            ax.set_xticks(ticks, [fmt(t) for t in ticks])
            ax.set_xlabel("First scrimmage snap to scoring snap")
            ax.grid(axis="y", color="#e0e6eb", linewidth=.7)
            ax.set_axisbelow(True)
            ax.spines[["top", "right"]].set_visible(False)
            ax.tick_params(colors="#4a5d6b", labelsize=9)
            ax.xaxis.label.set(color="#4a5d6b", fontsize=10)
            ax.yaxis.label.set(color="#4a5d6b", fontsize=10)
    fig.text(.075, .095, "FG setup is included. The final play's duration is excluded. Each TD/FG curve has its own denominator.",
             fontsize=9, color="#536370")
    fig.text(.075, .065, "Source: local PFF feed, 2023-2026 through week 4. FCS is a subset of all offenses. Full observed duration range shown.",
             fontsize=9, color="#536370")
    fig.savefig(PLOTS / f"{stem}_finishes.png", dpi=190, facecolor="white")
    fig.savefig(PDFS / f"{stem}_finishes.pdf", facecolor="white")
    plt.close(fig)


def five_percentile_table(winners: pd.DataFrame) -> pd.DataFrame:
    """Observed clock cutoffs for each additional 5% of winning drives."""
    result = pd.DataFrame({"percentile": range(5, 101, 5)})
    for name, frame in [("all", winners), ("fcs", winners[winners.fcs])]:
        seconds = [percentile(frame.to_score_snap_seconds, p / 100) for p in result.percentile]
        result[f"{name}_seconds"] = seconds
        result[f"{name}_m_ss"] = [fmt(value) for value in seconds]
    return result


def plot_percentile_steps(winners: pd.DataFrame, stem: str, window: int | None) -> pd.DataFrame:
    navy, rust = "#193a59", "#bb6338"
    ranks = five_percentile_table(winners)
    fig = plt.figure(figsize=(14, 9.5), facecolor="white")
    fig.text(.07, .945, "Winning-drive clock used: every 5th percentile",
             fontsize=22, weight="bold", color=navy)
    condition = "No drive-start cutoff" if window is None else f"Start in final {fmt(window)}"
    fig.text(.07, .903, f"{condition} | Winning score in Q4 | Offense tied or trailing at start | Final lead held",
             fontsize=10.5, color="#4a5d6b")
    grid = fig.add_gridspec(1, 2, left=.07, right=.96, top=.81, bottom=.255,
                            width_ratios=[1.9, 1], wspace=.22)
    ax = fig.add_subplot(grid[0, 0])
    for label, column, color, style in [
        (f"All offenses (n={len(winners):,})", "all_seconds", navy, "-"),
        (f"FCS offenses (n={int(winners.fcs.sum()):,})", "fcs_seconds", rust, "--"),
    ]:
        ax.plot(ranks.percentile, ranks[column], color=color, linestyle=style,
                marker="o", markersize=4, linewidth=2, label=label)
    ymax = max(60, int(np.ceil(ranks[["all_seconds", "fcs_seconds"]].max().max() / 60)) * 60)
    ax.set_xlim(3, 102)
    ax.set_ylim(0, ymax + 15)
    ax.set_xticks(range(5, 101, 5), [f"{p}%" for p in range(5, 101, 5)], rotation=55)
    ax.set_yticks(range(0, ymax + 1, 60), [fmt(t) for t in range(0, ymax + 1, 60)])
    ax.set_xlabel("Percentile of observed winning-drive duration", labelpad=11, fontsize=10.5)
    ax.set_ylabel("Game clock used to reach the scoring snap (m:ss)", labelpad=10, fontsize=10.5)
    ax.set_title("Time cutoff at each cumulative 5% step", loc="left", color=navy,
                 weight="bold", fontsize=12, pad=14)
    for p in [50, 75, 90, 95]:
        ax.axvline(p, color="#dce2e8", linewidth=.7, linestyle=":", zorder=0)
    ax.grid(axis="y", color="#e0e6eb", linewidth=.75)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#9eabb5")
    ax.tick_params(colors="#4a5d6b", labelsize=9)
    ax.legend(loc="upper left", frameon=False, fontsize=10)
    tax = fig.add_subplot(grid[0, 1])
    tax.axis("off")
    tax.set_title("Clock used at every 5th percentile", loc="left", color=navy,
                  weight="bold", fontsize=12, pad=14)
    cells = [[f"{r.percentile}%", r.all_m_ss, r.fcs_m_ss] for r in ranks.itertuples()]
    table = tax.table(cellText=cells, colLabels=["Percentile", "All offenses", "FCS"],
                      cellLoc="center", bbox=[0, 0, 1, 1], colWidths=[.34, .36, .3])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#d8e0e7")
        cell.set_linewidth(.45)
        cell.set_text_props(color=navy)
        if row == 0:
            cell.set_facecolor("#eaf0f5")
            cell.set_text_props(weight="bold")
        elif row * 5 in [50, 75, 90, 95, 100]:
            cell.set_facecolor("#edf4f7")
            cell.set_text_props(weight="bold")
        elif row % 2 == 0:
            cell.set_facecolor("#f7f9fb")
    p75 = ranks[ranks.percentile.eq(75)].iloc[0]
    fig.text(.07, .132,
             f"Read 75% as: at least 75% of these winning drives reached the scoring snap within {p75.all_m_ss} overall / {p75.fcs_m_ss} for FCS.",
             fontsize=10, color=navy)
    fig.text(.07, .098, "Percentiles describe observed wins, not scoring probabilities. The 100th percentile is the sample maximum.",
             fontsize=9, color="#536370")
    fig.text(.07, .068, "Timing: first scrimmage snap to TD or made-FG snap; FG setup included, final play duration excluded. FCS is a subset of all offenses.",
             fontsize=9, color="#536370")
    fig.text(.07, .038, "Source: local PFF feed, 2023-2026 through week 4. Cutoffs use observed ranks. Lines connect the 5% markers as a visual guide.",
             fontsize=9, color="#536370")
    fig.savefig(PLOTS / f"{stem}_5pct.png", dpi=190, facecolor="white")
    fig.savefig(PDFS / f"{stem}_5pct.pdf", facecolor="white")
    plt.close(fig)
    ranks.to_csv(PLOTS / f"{stem}_5pct.csv", index=False)
    return ranks


def write_review(winners: pd.DataFrame, audit: pd.DataFrame, stem: str, window: int | None) -> None:
    summary = []
    for population, frame in [("All offenses", winners), ("FCS offenses", winners[winners.fcs])]:
        for subgroup, cell in [("All finishes", frame), ("TD", frame[frame.end.eq("TOUCHDOWN")]),
                                ("FG", frame[frame.end.eq("FIELD GOAL")]),
                                ("Tied at start", frame[frame.offscore.eq(frame.defscore)]),
                                ("Trailing at start", frame[frame.offscore.lt(frame.defscore)])]:
            if cell.empty:
                continue
            summary.append({"population": population, "subgroup": subgroup, "n": len(cell),
                            "mean_used_seconds": float(cell.to_score_snap_seconds.mean()),
                            **{f"used_p{q}_seconds": percentile(cell.to_score_snap_seconds, q / 100)
                               for q in [10, 25, 50, 75, 90, 95, 100]},
                            "median_start_seconds": percentile(cell.start_regulation_seconds, .5)})
    stats = pd.DataFrame(summary)
    stats.to_csv(PLOTS / f"{stem}_summary.csv", index=False)
    ranks = pd.DataFrame({"percentile": range(1, 101)})
    for label, frame in [("all", winners), ("fcs", winners[winners.fcs])]:
        for metric in ["to_score_snap_seconds", "start_regulation_seconds"]:
            ranks[f"{label}_{metric}"] = [percentile(frame[metric], p / 100) for p in ranks.percentile]
    ranks.to_csv(PLOTS / f"{stem}_percentiles.csv", index=False)
    comparison = []
    for label, frame in [("All offenses", winners), ("FCS offenses", winners[winners.fcs])]:
        for cohort_label, cell in [("No start cutoff", frame),
                                    ("Prior final 4:00", frame[frame.start_regulation_seconds.le(240)])]:
            if len(cell):
                comparison.append({"population": label, "cohort": cohort_label, "n": len(cell),
                                   **{f"used_p{q}_seconds": percentile(cell.to_score_snap_seconds, q / 100)
                                      for q in [50, 75, 90]}})
    comp = pd.DataFrame(comparison)
    comp.to_csv(PLOTS / f"{stem}_comparison.csv", index=False)
    cutoff_text = "No drive-start cutoff" if window is None else f"Optional start cutoff: {fmt(window)} remaining"
    text = f"""# Q4 winning drives: distribution without a drive-start cutoff

## Selection and timing

{cutoff_text}. The end-of-game definition is a **winning TD or made field goal in Q4**.
The offense must be **tied or trailing at the first scrimmage snap**, create a positive lead after the scoring play and try,
and keep that lead through the end of regulation. There is one decisive drive per game.
Drives that begin before Q4 are included; earlier-quarter scores that stood as the winning lead are outside this Q4 analysis.
No hurry-up requirement, minimum snap count, starting field-position limit, or deficit limit is applied.
Overtime games, OT-forcing ties, and defensive/special-teams return scores are excluded.

Possessions use game + offense + drive number. No-play rows cannot set the first or last scrimmage snap.
TDs are verified against the offensive scoring-team tag. Made FGs are attached before the next possession/kickoff.
The lead is checked after the try, at subsequent score states, and against the game's final winner.

Elapsed time is **first scrimmage snap to the TD snap or made-FG snap**, including FG setup.
For drives crossing a quarter boundary, remaining regulation time is `(4 - quarter) * 900 + quarter clock`;
subtracting the scoring-snap clock gives the full game-clock interval. Quarter breaks consume no game clock.
The final play's live-ball duration and delays before the first scrimmage snap are unavailable and excluded.
Percentiles use observed ranks (inverse empirical CDF), not interpolation.

Source: local PFF feed, 2023-2026 through week 4. FCS uses the saved season-specific offense code list, regardless of opponent;
FCS is a subset of all offenses. The broader feed is not independently restricted to verified FBS/FCS members.

## Results

**{len(winners):,} winning drives**, including **{int(winners.fcs.sum()):,} by FCS offenses**.
Added beyond the prior final-4:00 cohort: **{int(winners.start_regulation_seconds.gt(240).sum()):,} drives**.
Drives beginning before Q4: **{int(winners.q_first.lt(4).sum())}**.
Drives longer than 4:00 to reach the scoring snap: **{int(winners.to_score_snap_seconds.gt(240).sum())}**.

| Population | Start / finish | Drives | Median used | 75th | 90th | 95th | Longest |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
"""
    for r in stats.itertuples():
        text += f"| {r.population} | {r.subgroup} | {r.n} | {fmt(r.used_p50_seconds)} | {fmt(r.used_p75_seconds)} | {fmt(r.used_p90_seconds)} | {fmt(r.used_p95_seconds)} | {fmt(r.used_p100_seconds)} |\n"
    text += "\n## Clock used at every 5th percentile\n\nEach cutoff is the shortest observed duration at which at least that percentage of winning drives is included. The 100th percentile is the sample maximum, not a guarantee for future drives.\n\n| Percentile | All offenses | FCS offenses |\n| --- | ---: | ---: |\n"
    for r in five_percentile_table(winners).itertuples():
        text += f"| {r.percentile}% | {r.all_m_ss} | {r.fcs_m_ss} |\n"
    text += "\n## Effect of removing the four-minute start cutoff\n\n| Population | Cohort | Drives | Median used | 75th | 90th |\n| --- | --- | ---: | ---: | ---: | ---: |\n"
    for r in comp.itertuples():
        text += f"| {r.population} | {r.cohort} | {r.n} | {fmt(r.used_p50_seconds)} | {fmt(r.used_p75_seconds)} | {fmt(r.used_p90_seconds)} |\n"
    text += "\nThe earlier restriction preferentially selected drives that had little clock available. Removing it admits longer possessions and a broader range of offensive tempo. The expanded percentiles describe this broader winning-drive population; they are not required time to score or the probability of success given a clock budget.\n"
    text += "\n## Cohort audit\n\nCandidates already require a Q4 scoring-end label, a tied/trailing start, and the eventual winning offense.\n\n"
    for status, count in audit.status.value_counts().items():
        text += f"- {status}: {count}\n"
    text += "\nSeason coverage among included drives:\n\n"
    for season, cell in winners.groupby("season"):
        text += f"- {season}: {len(cell)} total, {int(cell.fcs.sum())} FCS\n"
    text += f"""
## Reproduction and files

Run `MPLCONFIGDIR=/private/tmp/evertrue-mpl python3 tos/plot_winning_drives.py`.
`--window-minutes 4` optionally reproduces a capped comparison under a separate output prefix.
The earlier four-minute plots and report are preserved.

- `{stem}.png` / PDF: cumulative duration and starting-clock distributions.
- `{stem}_finishes.png` / PDF: duration histograms and separate TD/FG curves, for all offenses and FCS.
- `{stem}_5pct.png` / PDF: duration cutoffs plotted and tabulated at every 5th percentile.
- `{stem}_5pct.csv`: the 5%-increment table, in seconds and m:ss.
- `{stem}_drives.csv`: each included drive, scores, quarters, clock values, field position, timeouts, and timing definitions.
- `{stem}_candidate_audit.csv`: every candidate and inclusion/exclusion status.
- `{stem}_summary.csv`, `{stem}_percentiles.csv`, `{stem}_comparison.csv`: numerical results.

The earlier methodology review documents the possession-key defect in the legacy analyses; this run uses the corrected key.
"""
    (PLOTS / f"{stem}_report.md").write_text(text)
    print(stats.to_string(index=False))
    print("Comparison:\n", comp.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-minutes", type=int, default=None, choices=range(1, 16),
                        help="Optional start-time restriction; omitted by default")
    args = parser.parse_args()
    window = args.window_minutes * 60 if args.window_minutes is not None else None
    stem = ("winning_drive_distribution_uncapped" if window is None
            else f"winning_drive_distribution_last_{args.window_minutes}m")
    plays = load_plays()
    drives = drive_table(plays)
    games = pd.read_csv(ROOT / "data/ncaa/games.csv").set_index("pff_GAMEID")
    winners, audit = winning_drives(plays, drives, games, window)
    if winners.empty:
        raise ValueError("No verified winning possessions for this window")
    plot(winners, window, stem)
    plot_finishes(winners, stem)
    plot_percentile_steps(winners, stem, window)
    winners.to_csv(PLOTS / f"{stem}_drives.csv", index=False)
    audit.to_csv(PLOTS / f"{stem}_candidate_audit.csv", index=False)
    write_review(winners, audit, stem, window)
    print("Audit:", audit.status.value_counts().to_dict())


if __name__ == "__main__":
    main()
