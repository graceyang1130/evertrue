"""Reconstruct every charged timeout from PFF play-by-play and tag its purpose.

PFF has no timeout rows, but every snap carries both teams' timeouts remaining.
A team's count dropping between two consecutive snaps of the same half means it
called a timeout in that dead-ball period. Counts are mapped to TEAMS, not to
offense/defense, so a timeout taken across a change of possession (before a
punt return, after a turnover) is still charged to the right team.

WHAT EACH TIMEOUT WAS FOR
-------------------------
Purpose is inferred from the situation, since the export does not record it.
Checked in this order, first match wins:

  clock        inside the last 2:00 of a half -- stopping or saving the clock
  pre_kick     the next snap is a field goal or extra point (icing, or the
               kicking team settling its unit)
  pre_punt     the next snap is a punt
  fourth_down  the caller's offense snaps on 4th down next (deciding to go)
  play_clock   the caller is on offense and 20+ game-clock seconds ran after
               the previous play -- the play clock was burned down first, the
               signature of a substitution or play-call problem
  defense      the caller is on defense, anywhere else (to see a look, stop a
               drive, rest)
  offense      any other offensive timeout

The 20s play-clock cut uses game clock between snaps, so it only applies when
both snaps sit in the same quarter and the clock was running. It is a proxy:
a timeout called late in the play clock and one called after a long injury
stoppage look the same.

Usage:
    python timeouts.py                       # all NCAA plays -> timeouts.csv
    python timeouts.py --team RIBR           # print one team's audit summary
"""

import argparse
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "ncaa")

PLAY_CLOCK_BURN = 20     # seconds of game clock between snaps -> play-clock timeout
LATE = 120               # "last two minutes" of a half, in seconds


def _clock_to_seconds(value):
    """'14:33' -> 873. Returns NaN on anything unparseable."""
    try:
        minutes, seconds = str(value).split(":")
        return int(minutes) * 60 + int(seconds)
    except (ValueError, AttributeError):
        return np.nan


def load_plays(path=None):
    path = path or os.path.join(DATA, "pbp.csv.gz")
    plays = pd.read_csv(path, low_memory=False)
    plays["clock"] = plays.pff_CLOCK.map(_clock_to_seconds)
    plays["half"] = np.where(plays.pff_QUARTER <= 2, 1,
                             np.where(plays.pff_QUARTER <= 4, 2, 3))
    return plays.sort_values(["pff_GAMEID", "pff_SORTORDER"]).reset_index(drop=True)


def _team_counts(plays):
    """Long form: one row per (snap, team) with that team's timeouts remaining."""
    base = ["pff_GAMEID", "pff_SORTORDER", "half"]
    off = plays[base + ["pff_OFFTEAM", "pff_OFF_TIMEOUTS_REMAINING"]].set_axis(
        base + ["team", "to"], axis=1)
    dfn = plays[base + ["pff_DEFTEAM", "pff_DEF_TIMEOUTS_REMAINING"]].set_axis(
        base + ["team", "to"], axis=1)
    return pd.concat([off, dfn], ignore_index=True)


def extract(plays):
    """One row per charged timeout, with the situation it was called in."""
    counts = _team_counts(plays).sort_values(["pff_GAMEID", "team", "pff_SORTORDER"])
    counts["next_to"] = counts.groupby(["pff_GAMEID", "team", "half"]).to.shift(-1)
    counts["next_sort"] = counts.groupby(["pff_GAMEID", "team", "half"]).pff_SORTORDER.shift(-1)
    used = counts[counts.next_to < counts.to].copy()
    used["n"] = (used.to - used.next_to).astype(int)

    # the snap before and after the dead-ball period the timeout was taken in
    snaps = plays.set_index(["pff_GAMEID", "pff_SORTORDER"])
    before = snaps.loc[list(zip(used.pff_GAMEID, used.pff_SORTORDER))].reset_index()
    after = snaps.loc[list(zip(used.pff_GAMEID, used.next_sort))].reset_index()

    events = pd.DataFrame({
        "game": used.pff_GAMEID.values,
        "snap_sort": used.next_sort.values,      # the snap the timeout preceded
        "season": after.pff_GAMESEASON.values,
        "week": after.pff_WEEK.values,
        "team": used.team.values,
        "n": used.n.values,
        "quarter": after.pff_QUARTER.values,
        "clock": after.clock.values,
        "half": after.half.values,
        "to_left_after": used.next_to.values.astype(int),
        "on_offense": (after.pff_OFFTEAM.values == used.team.values),
        "next_down": after.pff_DOWN.values,
        "next_distance": after.pff_DISTANCE.values,
        "next_st": after.pff_SPECIALTEAMSTYPE.values,
        "next_ytg": after.pff_YARDS_TO_GOAL_LINE.values,
        "next_play_clock": after.pff_PLAYCLOCK.values,
        "prev_result": before.pff_PASSRESULT.values,
        "prev_st": before.pff_SPECIALTEAMSTYPE.values,
    })
    events["opponent"] = np.where(events.on_offense, after.pff_DEFTEAM.values,
                                  after.pff_OFFTEAM.values)
    diff = after.pff_SCOREDIFFERENTIAL.values
    events["lead"] = np.where(events.on_offense, diff, -diff)

    same_quarter = before.pff_QUARTER.values == after.pff_QUARTER.values
    events["elapsed"] = np.where(same_quarter, before.clock.values - after.clock.values, np.nan)

    events["purpose"] = classify(events)
    return events


def classify(events):
    late = events.quarter.isin([2, 4]) & (events.clock <= LATE)
    kick = events.next_st.isin(["FIELD GOAL", "EXTRA POINT"])
    punt = events.next_st.eq("PUNT")
    fourth = events.on_offense & events.next_st.isna() & (events.next_down == 4)
    burned = events.on_offense & (events.elapsed >= PLAY_CLOCK_BURN)
    return np.select(
        [late, kick, punt, fourth, burned, ~events.on_offense],
        ["clock", "pre_kick", "pre_punt", "fourth_down", "play_clock", "defense"],
        default="offense",
    )


def unused(plays):
    """Timeouts each team still held at the last snap of each half."""
    counts = _team_counts(plays)
    last = counts.sort_values("pff_SORTORDER").groupby(["pff_GAMEID", "team", "half"]).tail(1)
    last = last[last.half <= 2]
    return last.rename(columns={"pff_GAMEID": "game", "to": "unused"})[
        ["game", "team", "half", "unused"]]


def team_summary(events, left, games, team):
    team_games = games[(games.team_a == team) | (games.team_b == team)]
    n = len(team_games)
    ev = events[events.team == team]
    print(f"{team}: {n} games, {ev.n.sum()} timeouts ({ev.n.sum() / n:.2f}/game)")
    print(ev.groupby("purpose").n.sum().div(n).round(2).sort_values(ascending=False).to_string())
    lh = left[left.team == team].groupby("half").unused.mean().round(2)
    print(f"unused at end of 1st half {lh.get(1, np.nan)}, end of game {lh.get(2, np.nan)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", default=None)
    args = parser.parse_args()

    plays = load_plays()
    events = extract(plays)
    left = unused(plays)
    events.to_csv(os.path.join(DATA, "timeouts.csv"), index=False)
    left.to_csv(os.path.join(DATA, "timeouts_unused.csv"), index=False)
    print(f"{events.n.sum():,d} timeouts in {events.game.nunique():,d} games")
    print(events.groupby("purpose").n.sum().sort_values(ascending=False).to_string())

    if args.team:
        games = pd.read_csv(os.path.join(DATA, "games.csv"))
        print()
        team_summary(events, left, games, args.team)


if __name__ == "__main__":
    main()
