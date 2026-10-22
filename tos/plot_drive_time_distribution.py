"""Plot successful late game-winning drives and the report's scoring-drive benchmark.

Run from the repository root: python3 tos/plot_drive_time_distribution.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/ncaa/pbp.csv.gz"
GAMES = ROOT / "data/ncaa/games.csv"
FCS = ROOT / "data/ncaa/fcs_team_codes.json"
OUT = ROOT / "output/plots"


def clock_seconds(clock: pd.Series) -> pd.Series:
    parts = clock.astype(str).str.extract(r"^(\d+):(\d{2})$")
    return pd.to_numeric(parts[0], errors="coerce") * 60 + pd.to_numeric(parts[1], errors="coerce")


def fcs_codes() -> dict[int, set[str]]:
    source = json.loads(FCS.read_text())
    base = set(source["base_codes"])
    return {
        int(season): (base | set(change["add"])) - set(change["remove"])
        for season, change in source["season_adjustments"].items()
    }


def fmt(seconds: float) -> str:
    whole = int(round(seconds))
    return f"{whole // 60}:{whole % 60:02d}"


def ecdf(ax: plt.Axes, values: pd.Series, *, color: str, label: str, linestyle: str = "-") -> None:
    x = np.sort(values.to_numpy(dtype=float))
    y = 100 * np.arange(1, len(x) + 1) / len(x)
    ax.step(np.r_[0, x], np.r_[0, y], where="post", color=color,
            linewidth=2.4, linestyle=linestyle, label=f"{label}  (n={len(x)})")


def draw(groups: dict[str, pd.Series]) -> None:
    navy, rust = "#193a59", "#bb6338"
    fig = plt.figure(figsize=(13.2, 8.6), facecolor="white")
    grid = fig.add_gridspec(2, 2, height_ratios=[3.3, 1.75],
                            left=.075, right=.975, top=.82, bottom=.15,
                            wspace=.19, hspace=.38)
    panels = [fig.add_subplot(grid[0, 0]), fig.add_subplot(grid[0, 1])]
    fig.suptitle("How long did scoring and winning drives take?", x=.075, y=.96,
                 ha="left", fontsize=21, fontweight="bold", color=navy)
    fig.text(.075, .911,
             "Each curve shows the share of drives completed within the time on the horizontal axis.",
             ha="left", fontsize=11.5, color="#485969")

    settings = [
        ("Report's 430-drive hurry-up benchmark", groups["benchmark_all"],
         groups["benchmark_fcs"], 360),
        ("Actual winning drives starting in final 4:00", groups["winner_all"],
         groups["winner_fcs"], 240),
    ]
    for ax, (title, all_values, fcs_values, xmax) in zip(panels, settings):
        ecdf(ax, all_values, color=navy, label="FBS + FCS")
        ecdf(ax, fcs_values, color=rust, label="FCS only", linestyle="--")
        ax.set_title(title, loc="left", fontsize=12.5, fontweight="bold", color=navy, pad=13)
        ax.set_xlim(0, xmax)
        ax.set_ylim(0, 100)
        ax.set_xticks(np.arange(0, xmax + 1, 60))
        ax.set_xticklabels([fmt(x) for x in np.arange(0, xmax + 1, 60)])
        ax.set_yticks([0, 25, 50, 75, 100])
        ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax.grid(axis="y", color="#dce2e8", linewidth=.8)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color("#8a99a6")
        ax.tick_params(colors="#485969", labelsize=10)
        ax.set_xlabel("First snap to last snap", fontsize=10.5, color="#394c5d", labelpad=7)
        ax.legend(loc="lower right", frameon=False, fontsize=9.5, labelcolor="#394c5d")
        p75 = all_values.quantile(.75)
        ax.plot([p75], [75], "o", color=navy, markersize=6, zorder=5)
        ax.annotate(f"75th: {fmt(p75)}", (p75, 75), xytext=(7, -25),
                    textcoords="offset points", fontsize=10, fontweight="bold", color=navy)
    panels[0].set_ylabel("Share completed by this time", fontsize=10.5,
                         color="#394c5d", labelpad=9)
    panels[1].set_ylabel("Share completed by this time", fontsize=10.5,
                         color="#394c5d", labelpad=9)
    tail = (groups["benchmark_all"] > 360).mean()
    panels[0].text(.02, .97, f"{tail:.1%} lasted over 6:00", transform=panels[0].transAxes,
                   va="top", fontsize=9.5, color="#667582")

    table_ax = fig.add_subplot(grid[1, :])
    table_ax.axis("off")
    table_ax.text(0, 1.12, "Percentile cutoffs", transform=table_ax.transAxes,
                  fontsize=12.5, fontweight="bold", color=navy)
    percentiles = [5, 10, 25, 50, 75, 90, 95, 99]
    columns = ["Percentile", "Benchmark: all", "Benchmark: FCS",
               "Winners: all", "Winners: FCS"]
    names = ["benchmark_all", "benchmark_fcs", "winner_all", "winner_fcs"]
    rows = [[f"{p}th"] +
            [fmt(groups[name].quantile(p / 100)) for name in names]
            for p in percentiles]
    table = table_ax.table(cellText=rows, colLabels=columns, loc="upper center",
                           cellLoc="center", colLoc="center", bbox=[0, 0, 1, 1.02],
                           colWidths=[.13, .215, .215, .22, .22])
    table.auto_set_font_size(False)
    table.set_fontsize(9.8)
    for (r, c), cell in table.get_celld().items():
        cell.set_linewidth(.4)
        cell.set_edgecolor("#d8e0e7")
        if r == 0:
            cell.set_facecolor("#eaf0f5")
            cell.set_text_props(weight="bold", color=navy)
        elif r == 5:  # 75th percentile
            cell.set_facecolor("#edf4f7")
            cell.set_text_props(weight="bold", color=navy)
        elif r % 2 == 0:
            cell.set_facecolor("#f7f9fb")
    fig.text(.075, .103,
             "Source: PFF play feed, 2023–2026 week 4. Benchmark: ≥3 snaps, ≥80% two-minute tag, TD/FG drive, any quarter."
             " Winning: final go-ahead TD/FG drive, first snap at or below 4:00 Q4, regulation wins.",
             ha="left", fontsize=8.4, color="#536370")
    fig.text(.075, .078,
             "Time runs from first to last snap; the scoring play is excluded. The original benchmark includes 2 blocked FG attempts;"
             " removing them changes its 75th percentile from 2:31 to 2:30.",
             ha="left", fontsize=8.4, color="#536370")
    fig.text(.075, .053,
             "The panels select different drives. Neither curve shows the chance of scoring; failed attempts are absent.",
             ha="left", fontsize=8.4, color="#536370")
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "endgame_drive_time_distribution.png", dpi=190, facecolor="white")
    fig.savefig(OUT / "endgame_drive_time_distribution.pdf", facecolor="white")
    plt.close(fig)

    full = pd.DataFrame({"percentile": range(1, 100)})
    for name, values in groups.items():
        seconds = [values.quantile(p / 100) for p in full.percentile]
        full[f"{name}_seconds"] = seconds
        full[f"{name}_m_ss"] = [fmt(s) for s in seconds]
    full.to_csv(OUT / "endgame_drive_time_percentiles.csv", index=False)


def load() -> pd.DataFrame:
    cols = [
        "pff_GAMEID", "pff_GAMESEASON", "pff_SORTORDER", "pff_DRIVE", "pff_QUARTER",
        "pff_CLOCK", "pff_OFFTEAM", "pff_DEFTEAM", "pff_OFFSCORE", "pff_DEFSCORE",
        "pff_DOWN", "pff_SPECIALTEAMSTYPE", "pff_2MINUTE", "pff_DRIVEENDEVENT",
        "winner", "pff_TOUCHDOWN", "pff_KICKRESULT",
    ]
    plays = pd.read_csv(SOURCE, usecols=cols, low_memory=False)
    plays = plays.sort_values(["pff_GAMEID", "pff_SORTORDER"]).reset_index(drop=True)
    plays["clock"] = clock_seconds(plays.pff_CLOCK)
    return plays


def drive_table(plays: pd.DataFrame) -> pd.DataFrame:
    snaps = plays[plays.pff_SPECIALTEAMSTYPE.isna() & plays.pff_DOWN.between(1, 4)].copy()
    snaps["hurry"] = pd.to_numeric(snaps.pff_2MINUTE, errors="coerce").eq(2)
    drives = snaps.groupby(["pff_GAMEID", "pff_DRIVE"], sort=False).agg(
        season=("pff_GAMESEASON", "first"),
        offense=("pff_OFFTEAM", "first"),
        defense=("pff_DEFTEAM", "first"),
        winner=("winner", "first"),
        q_first=("pff_QUARTER", "first"),
        q_last=("pff_QUARTER", "last"),
        c_first=("clock", "first"),
        c_last=("clock", "last"),
        first_sort=("pff_SORTORDER", "first"),
        last_sort=("pff_SORTORDER", "last"),
        offscore=("pff_OFFSCORE", "first"),
        defscore=("pff_DEFSCORE", "first"),
        end=("pff_DRIVEENDEVENT", "last"),
        hurry=("hurry", "mean"),
        snaps=("hurry", "size"),
    ).reset_index()
    drives["duration"] = drives.c_first - drives.c_last
    codes = fcs_codes()
    drives["fcs"] = [
        team in codes.get(int(season), set())
        for team, season in zip(drives.offense, drives.season)
    ]
    return drives


def winning_drives(plays: pd.DataFrame, drives: pd.DataFrame) -> pd.DataFrame:
    games = pd.read_csv(GAMES).set_index("pff_GAMEID")
    overtime = set(plays.loc[plays.pff_QUARTER.gt(4), "pff_GAMEID"])
    scored = drives.end.astype(str).str.upper().str.contains("TOUCHDOWN|FIELD GOAL")
    candidates = drives[
        scored & drives.q_first.eq(4) & drives.q_last.eq(4)
        & drives.c_first.le(240) & drives.c_first.gt(0)
        & drives.offscore.le(drives.defscore)
        & drives.offense.eq(drives.winner)
        & ~drives.pff_GAMEID.isin(overtime)
        & drives.duration.ge(0)
    ].copy()
    accepted = []
    for row in candidates.itertuples(index=False):
        game = plays[plays.pff_GAMEID.eq(row.pff_GAMEID)]
        after = game[game.pff_SORTORDER.gt(row.last_sort)]
        # A post-score kickoff carries the updated score, including the try.
        # The feed's score on a scoring snap itself is the pre-snap score.
        kickoff = after[
            after.pff_SPECIALTEAMSTYPE.eq("KICKOFF") & after.pff_QUARTER.eq(4)
        ].head(1)
        if len(kickoff):
            k = kickoff.iloc[0]
            post_off = k.pff_OFFSCORE if k.pff_OFFTEAM == row.offense else k.pff_DEFSCORE
            post_def = k.pff_DEFSCORE if k.pff_OFFTEAM == row.offense else k.pff_OFFSCORE
            post_lead = post_off - post_def
            own_points = post_off - row.offscore
        else:
            final = games.loc[row.pff_GAMEID]
            off_final = final.score_a if final.team_a == row.offense else final.score_b
            def_final = final.score_b if final.team_a == row.offense else final.score_a
            post_lead = off_final - def_final
            own_points = off_final - row.offscore
        if post_lead > 0 and own_points in (3, 6, 7, 8):
            accepted.append(row.pff_GAMEID)
        else:
            accepted.append(None)
    candidates = candidates.assign(accepted=accepted)
    candidates = candidates[candidates.accepted.notna()]
    # The last go-ahead drive is the one that produced the final winning lead.
    return candidates.sort_values("last_sort").groupby("pff_GAMEID").tail(1).copy()


def main() -> None:
    plays = load()
    drives = drive_table(plays)
    scored = drives.end.astype(str).str.upper().str.contains("TOUCHDOWN|FIELD GOAL")
    benchmark = drives[
        scored & drives.q_first.eq(drives.q_last)
        & drives.hurry.ge(0.8) & drives.snaps.ge(3)
    ].copy()
    winners = winning_drives(plays, drives)
    groups = {
        "benchmark_all": benchmark.duration,
        "benchmark_fcs": benchmark.loc[benchmark.fcs, "duration"],
        "winner_all": winners.duration,
        "winner_fcs": winners.loc[winners.fcs, "duration"],
    }
    draw(groups)
    for name, values in groups.items():
        print(name, "n", len(values), "max", values.max(),
              "percentiles", {p: fmt(values.quantile(p / 100)) for p in [5, 10, 25, 50, 75, 90, 95, 99]})


if __name__ == "__main__":
    main()
