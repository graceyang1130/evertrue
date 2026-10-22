"""Compare matched late comeback attempts with the subset that won or forced OT.

Run from the repository root: python3 tos/plot_matched_comeback_drives.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from plot_drive_time_distribution import drive_table, fmt, load


ROOT = Path(__file__).resolve().parents[1]
GAMES = ROOT / "data/ncaa/games.csv"
OUT = ROOT / "output/plots"


def score_after_drive(row, game: pd.DataFrame, final: pd.Series) -> tuple[float, float, float]:
    """Scores after a scoring drive, using kickoff, OT start, or final score."""
    after = game[game.pff_SORTORDER.gt(row.last_sort)]
    kickoff = after[after.pff_SPECIALTEAMSTYPE.eq("KICKOFF") & after.pff_QUARTER.eq(4)].head(1)
    if len(kickoff):
        point = kickoff.iloc[0]
    else:
        overtime = after[after.pff_QUARTER.gt(4)].head(1)
        point = overtime.iloc[0] if len(overtime) else None
    if point is not None:
        if point.pff_OFFTEAM == row.offense:
            return float(point.pff_OFFSCORE), float(point.pff_DEFSCORE), float(point.pff_SORTORDER)
        return float(point.pff_DEFSCORE), float(point.pff_OFFSCORE), float(point.pff_SORTORDER)
    if final.team_a == row.offense:
        return float(final.score_a), float(final.score_b), np.inf
    return float(final.score_b), float(final.score_a), np.inf


def held_result(game: pd.DataFrame, row, from_sort: float, *, lead: bool) -> bool:
    """A winning lead or OT-forcing tie must last through the rest of Q4."""
    future = game[game.pff_SORTORDER.ge(from_sort) & game.pff_QUARTER.eq(4)]
    if future.empty:
        return True
    off = np.where(future.pff_OFFTEAM.eq(row.offense), future.pff_OFFSCORE, future.pff_DEFSCORE)
    defense = np.where(future.pff_OFFTEAM.eq(row.offense), future.pff_DEFSCORE, future.pff_OFFSCORE)
    diff = off - defense
    return bool(np.all(diff > 0 if lead else diff == 0))


def cohort(plays: pd.DataFrame, drives: pd.DataFrame) -> pd.DataFrame:
    """One-score trailing Q4 hurry-up drives that began with <=5:00 left."""
    deficit = drives.defscore - drives.offscore
    attempts = drives[
        drives.q_first.eq(4) & drives.q_last.eq(4)
        & drives.c_first.between(1, 300)
        & deficit.between(1, 8)
        & drives.hurry.ge(.8)
        & drives.duration.ge(0)
    ].copy()
    attempts["deficit"] = deficit.loc[attempts.index].astype(int)
    attempts["outcome"] = "Other result"
    games = pd.read_csv(GAMES).set_index("pff_GAMEID")
    by_game = {key: frame for key, frame in plays.groupby("pff_GAMEID", sort=False)}
    overtime = set(plays.loc[plays.pff_QUARTER.gt(4), "pff_GAMEID"])
    scoring_end = attempts.end.astype(str).str.upper().str.contains("TOUCHDOWN|FIELD GOAL")
    for i, row in attempts[scoring_end].iterrows():
        final = games.loc[row.pff_GAMEID]
        game = by_game[row.pff_GAMEID]
        post_off, post_def, score_sort = score_after_drive(row, game, final)
        own_points = post_off - row.offscore
        if own_points not in (3, 6, 7, 8):
            continue
        if (row.pff_GAMEID in overtime and post_off == post_def
              and held_result(game, row, score_sort, lead=False)):
            attempts.at[i, "outcome"] = "Forced OT"
        elif (row.pff_GAMEID not in overtime and post_off > post_def
              and row.offense == final.winner
              and held_result(game, row, score_sort, lead=True)):
            attempts.at[i, "outcome"] = "Won in regulation"
    # If the lead or tie changed again, only the final decisive drive counts.
    decisive = attempts[attempts.outcome.ne("Other result")]
    if len(decisive):
        keep = set(decisive.sort_values("last_sort").groupby("pff_GAMEID").tail(1).index)
        attempts.loc[decisive.index.difference(list(keep)), "outcome"] = "Other result"
    attempts["success"] = attempts.outcome.ne("Other result")
    return attempts


def summarize(frame: pd.DataFrame) -> dict[str, object]:
    return {
        "n": len(frame),
        "start_mean": round(float(frame.c_first.mean()), 1),
        "start_median": float(frame.c_first.median()),
        "duration_median": float(frame.duration.median()),
        "duration_p75": float(frame.duration.quantile(.75)),
        "fg": int(frame.end.eq("FIELD GOAL").sum()),
    }


def ecdf(ax: plt.Axes, values: pd.Series, *, label: str, color: str) -> None:
    x = np.sort(values.to_numpy(dtype=float))
    y = 100 * np.arange(1, len(x) + 1) / len(x)
    ax.step(np.r_[0, x], np.r_[0, y], where="post", color=color,
            linewidth=2.25, label=f"{label} (n={len(x)})")


def draw(attempts: pd.DataFrame) -> None:
    navy, rust = "#193a59", "#bb6338"
    fig = plt.figure(figsize=(13.3, 10.1), facecolor="white")
    grid = fig.add_gridspec(3, 2, height_ratios=[2.4, 2.4, 1.25],
                            left=.085, right=.97, top=.81, bottom=.16,
                            hspace=.48, wspace=.2)
    fig.suptitle("Final-five-minute comeback drives: matched comparison",
                 x=.085, y=.965, ha="left", fontsize=19, fontweight="bold", color=navy)
    fig.text(.085, .922,
             "Q4 first snap at or below 5:00 · trailing by 1–8 · at least 80% of snaps tagged hurry-up",
             ha="left", fontsize=10.8, color="#4a5d6b")
    fig.text(.085, .887,
             "The orange drives won in regulation or tied the game and forced overtime; they are part of the blue group.",
             ha="left", fontsize=10.2, color="#4a5d6b")
    groups = [("FBS + FCS", attempts), ("FCS only", attempts[attempts.fcs])]
    for row_index, (group_name, frame) in enumerate(groups):
        wins = frame[frame.success]
        for col_index, (field, heading) in enumerate([
            ("c_first", "Clock left at first snap"),
            ("duration", "Time from first to last snap"),
        ]):
            ax = fig.add_subplot(grid[row_index, col_index])
            ecdf(ax, frame[field], label="All attempts", color=navy)
            ecdf(ax, wins[field], label="Won / forced OT", color=rust)
            ax.set_title(f"{group_name}  ·  {heading}", loc="left", fontsize=11.7,
                         fontweight="bold", color=navy, pad=10)
            ax.set_xlim(0, 300)
            ax.set_ylim(0, 100)
            ax.set_xticks(range(0, 301, 60))
            ax.set_xticklabels([fmt(x) for x in range(0, 301, 60)])
            ax.set_yticks([0, 25, 50, 75, 100])
            ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
            ax.grid(axis="y", color="#dce2e8", linewidth=.8)
            ax.spines[["top", "right"]].set_visible(False)
            ax.spines[["left", "bottom"]].set_color("#8a99a6")
            ax.tick_params(colors="#485969", labelsize=9.5)
            ax.set_xlabel("Time remaining (less = later)" if col_index == 0
                          else "Elapsed drive time", fontsize=10.2, color="#394c5d", labelpad=5)
            ax.set_ylabel("Share of drives", fontsize=10.2, color="#394c5d", labelpad=6)
            ax.legend(loc="lower right", frameon=False, fontsize=9, labelcolor="#394c5d")

    table_ax = fig.add_subplot(grid[2, :])
    table_ax.axis("off")
    table_ax.text(0, 1.14, "Same filters, same timing measure", transform=table_ax.transAxes,
                  fontsize=11.8, fontweight="bold", color=navy)
    table_rows = []
    for label, frame in [
        ("FBS + FCS: all attempts", attempts),
        ("FBS + FCS: won / forced OT", attempts[attempts.success]),
        ("FCS: all attempts", attempts[attempts.fcs]),
        ("FCS: won / forced OT", attempts[attempts.fcs & attempts.success]),
    ]:
        stats = summarize(frame)
        table_rows.append([label, str(stats["n"]), fmt(stats["start_mean"]),
                           fmt(stats["start_median"]), fmt(stats["duration_median"]),
                           fmt(stats["duration_p75"])])
    table = table_ax.table(
        cellText=table_rows,
        colLabels=["Group", "Drives", "Average start", "Median start", "Median used", "75th used"],
        cellLoc="center", colLoc="center", loc="upper center", bbox=[0, .05, 1, .92],
        colWidths=[.31, .10, .15, .15, .145, .145],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9.8)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#d8e0e7")
        cell.set_linewidth(.45)
        if row == 0:
            cell.set_facecolor("#eaf0f5")
            cell.set_text_props(weight="bold", color=navy)
        elif row in (2, 4):
            cell.set_facecolor("#f9eee8")
            cell.set_text_props(color="#743c22", weight="bold" if col == 0 else "normal")
        elif row == 3:
            cell.set_facecolor("#f7f9fb")
        if col == 0 and row > 0:
            cell.get_text().set_ha("left")

    fig.text(.085, .105,
             "Source: PFF play feed, 2023–2026 week 4. Drive duration is first to last scrimmage snap;"
             " it excludes the final play and can be 0:00 for a one-snap drive.",
             ha="left", fontsize=8.6, color="#536370")
    fig.text(.085, .079,
             "A win means the drive created a lead that held through regulation. Forced OT means the drive tied the game"
             " and the tie held through Q4. Failed attempts may end quickly.",
             ha="left", fontsize=8.6, color="#536370")
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "matched_comeback_drives.png", dpi=190, facecolor="white")
    fig.savefig(OUT / "matched_comeback_drives.pdf", facecolor="white")
    plt.close(fig)

    detail = attempts[["pff_GAMEID", "season", "offense", "defense", "fcs", "deficit",
                       "c_first", "c_last", "duration", "snaps", "hurry", "end", "outcome"]].copy()
    detail.to_csv(OUT / "matched_comeback_drives.csv", index=False)
    percentiles = pd.DataFrame({"percentile": range(1, 100)})
    for group, frame in [
        ("all_attempts", attempts),
        ("all_won_or_ot", attempts[attempts.success]),
        ("fcs_attempts", attempts[attempts.fcs]),
        ("fcs_won_or_ot", attempts[attempts.fcs & attempts.success]),
    ]:
        for metric, series in [("start", frame.c_first), ("duration", frame.duration)]:
            values = [float(series.quantile(p / 100)) for p in percentiles.percentile]
            percentiles[f"{group}_{metric}_seconds"] = values
            percentiles[f"{group}_{metric}_m_ss"] = [fmt(value) for value in values]
    percentiles.to_csv(OUT / "matched_comeback_percentiles.csv", index=False)

    by_deficit = []
    for population, frame in [("FBS + FCS", attempts), ("FCS", attempts[attempts.fcs])]:
        for band, cell in [("Down 1–3", frame[frame.deficit.le(3)]),
                           ("Down 4–8", frame[frame.deficit.ge(4)])]:
            wins = int(cell.success.sum())
            by_deficit.append({"population": population, "starting_deficit": band,
                               "attempts": len(cell), "won_or_forced_ot": wins,
                               "observed_rate": wins / len(cell)})
    pd.DataFrame(by_deficit).to_csv(OUT / "matched_comeback_by_deficit.csv", index=False)


def main() -> None:
    plays = load()
    drives = drive_table(plays)
    attempts = cohort(plays, drives)
    draw(attempts)
    for name, frame in [
        ("all attempts", attempts),
        ("all successes", attempts[attempts.success]),
        ("FCS attempts", attempts[attempts.fcs]),
        ("FCS successes", attempts[attempts.fcs & attempts.success]),
    ]:
        print(name, summarize(frame))
    print("outcomes", attempts.outcome.value_counts().to_dict())


if __name__ == "__main__":
    main()
