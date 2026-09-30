"""Combine PFF play-feed exports into one slim play-by-play file plus game results.

PFF Ultimate's "Play Feed CSV" (Base Reports > plays button) exports ~214 columns
and roughly 550MB per FBS+FCS season, so seasons are pulled one export at a time
into data/ncaa/raw/playfeed_<label>.csv. This script stitches those segments
together, keeps only the columns the timeout work needs, drops duplicate plays
(segments may overlap), and attaches each game's final result.

FINAL SCORES
------------
PFF's score columns are the score BEFORE the snap, so the last row of a game
does not include points scored on the final play. Those are added back from the
play itself: a touchdown (+6 to the team PFF credits), a made field goal (+3) or
a made extra point (+1). Games still level after that are ambiguous (an unseen
two-point try, a safety) and get no winner rather than a guessed one.

Usage:
    python build_dataset.py                       # all raw/playfeed_*.csv
    python build_dataset.py --raw ../data/ncaa/raw --out ../data/ncaa
"""

import argparse
import glob
import os

import numpy as np
import pandas as pd

KEEP = [
    "pff_PLAYID", "pff_GAMEID", "pff_GAMEDATE", "pff_GAMESEASON", "pff_WEEK",
    "pff_SORTORDER", "pff_QUARTER", "pff_CLOCK", "pff_PLAYCLOCK",
    "pff_DOWN", "pff_DISTANCE", "pff_YARDS_TO_GOAL_LINE", "pff_FIELDPOSITION",
    "pff_OFFTEAM", "pff_DEFTEAM", "pff_OFFSCORE", "pff_DEFSCORE",
    "pff_SCOREDIFFERENTIAL",
    "pff_OFF_TIMEOUTS_REMAINING", "pff_DEF_TIMEOUTS_REMAINING",
    "pff_SPECIALTEAMSTYPE", "pff_KICKRESULT", "pff_KICKYARDS", "pff_KICKER",
    "pff_RUNPASS", "pff_PASSRESULT", "pff_GAINLOSSNET", "pff_FIRST_DOWN_GAINED",
    "pff_TOUCHDOWN", "pff_TURNOVER", "pff_NOPLAY", "pff_PENALTY",
    "pff_PENALTYYARDS", "pff_NON_TACKLE_TYPE", "pff_INJURED",
    "pff_EXPECTED_POINTS", "pff_EXPECTED_POINTS_ADDED",
    "pff_2MINUTE", "pff_TEMPO", "pff_NOHUDDLE", "pff_GARBAGETIME",
    "pff_DRIVE", "pff_DRIVEENDEVENT", "pff_PLAYENDFIELDPOSITION",
]


def load_segments(raw_dir):
    """Read every playfeed_*.csv segment, keeping only the columns in KEEP."""
    paths = sorted(glob.glob(os.path.join(raw_dir, "playfeed_*.csv")))
    if not paths:
        raise SystemExit(f"no playfeed_*.csv files in {raw_dir}")

    frames = []
    for path in paths:
        header = pd.read_csv(path, nrows=0).columns
        cols = [c for c in KEEP if c in header]
        missing = sorted(set(KEEP) - set(cols))
        frame = pd.read_csv(path, usecols=cols, low_memory=False)
        print(f"  {os.path.basename(path):28s} {len(frame):8,d} plays  "
              f"{frame.pff_GAMEID.nunique():5,d} games"
              + (f"  (missing {missing})" if missing else ""))
        frames.append(frame)

    plays = pd.concat(frames, ignore_index=True)
    before = len(plays)
    plays = plays.drop_duplicates("pff_PLAYID")
    if len(plays) < before:
        print(f"  dropped {before - len(plays):,d} duplicate plays across segments")
    return plays.sort_values(["pff_GAMEID", "pff_SORTORDER"]).reset_index(drop=True)


def _made(kick_result):
    return kick_result.astype(str).str.upper().str.startswith("MADE")


def game_results(plays):
    """One row per game: both teams, final scores, and the winner (or None)."""
    last = plays.groupby("pff_GAMEID").tail(1).set_index("pff_GAMEID")

    off_pts = pd.Series(0, index=last.index)
    def_pts = pd.Series(0, index=last.index)

    # Points scored on the final snap are not in that snap's score columns.
    td_team = last.pff_TOUCHDOWN.dropna().astype(str).str.split().str[0]
    off_pts[td_team[td_team == last.loc[td_team.index, "pff_OFFTEAM"]].index] += 6
    def_pts[td_team[td_team == last.loc[td_team.index, "pff_DEFTEAM"]].index] += 6

    made = _made(last.pff_KICKRESULT)
    off_pts[made & (last.pff_SPECIALTEAMSTYPE == "FIELD GOAL")] += 3
    off_pts[made & (last.pff_SPECIALTEAMSTYPE == "EXTRA POINT")] += 1

    games = pd.DataFrame({
        "season": last.pff_GAMESEASON,
        "week": last.pff_WEEK,
        "team_a": last.pff_OFFTEAM,
        "team_b": last.pff_DEFTEAM,
        "score_a": last.pff_OFFSCORE + off_pts,
        "score_b": last.pff_DEFSCORE + def_pts,
        "n_plays": plays.groupby("pff_GAMEID").size(),
    })
    games["winner"] = np.select(
        [games.score_a > games.score_b, games.score_b > games.score_a],
        [games.team_a, games.team_b],
        default=None,
    )
    return games.reset_index()


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_data = os.path.join(here, "..", "data", "ncaa")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", default=os.path.join(default_data, "raw"))
    parser.add_argument("--out", default=default_data)
    args = parser.parse_args()

    print("reading segments")
    plays = load_segments(args.raw)
    games = game_results(plays)

    plays = plays.merge(
        games[["pff_GAMEID", "winner"]], on="pff_GAMEID", how="left"
    )
    plays["off_won"] = np.where(
        plays.winner.isna(), np.nan, (plays.pff_OFFTEAM == plays.winner).astype(float)
    )

    os.makedirs(args.out, exist_ok=True)
    plays_path = os.path.join(args.out, "pbp.csv.gz")
    games_path = os.path.join(args.out, "games.csv")
    plays.to_csv(plays_path, index=False, compression="gzip")
    games.to_csv(games_path, index=False)

    no_winner = games.winner.isna().sum()
    print(f"\n{len(plays):,d} plays, {len(games):,d} games, "
          f"seasons {sorted(games.season.unique())}")
    print(f"{no_winner} games with no resolvable winner (excluded from WP labels)")
    print(f"wrote {plays_path}\nwrote {games_path}")


if __name__ == "__main__":
    main()
