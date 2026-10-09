"""The end-of-game clock game: what the math says, what teams actually do.

Three pieces for the report, all built on the snap-to-snap intervals from
end_of_game/runoff_model.py run over every FBS/FCS play:

PLAY TIME WHEN RUNNING OUT THE CLOCK
    PFF tags each snap with the offense's clock mode (pff_2MINUTE: 4 = four-
    minute offense, 2 = two-minute, 0 = normal). For clock-running snaps we
    split the time into snap-to-whistle (the play) and whistle-to-snap (the
    time between plays), and read how much play clock is left at the snap.

THE TIMEOUT RULE (theory) AND HOW TEAMS FOLLOW IT (reality)
    A timeout saves the same seconds whenever it is used, so on defense the
    only reasons to wait are (a) keeping it in case the offense converts and
    (b) not needing the clock at all. With their next snap on down n, the
    dead-ball periods left before they must punt are 5 - n (before downs n..4).
    If you hold at least that many timeouts you can use one in every period,
    so waiting gains nothing: call it now. Otherwise waiting a snap is free,
    because if they convert you keep the timeout for the new set.

    Reality: every late-4th-quarter snap where the defense trailed by 1-16,
    held a timeout, and the clock kept running after the previous play. Did it
    call timeout before the next snap, and how many seconds ran first?

RECOMMENDATION INPUTS
    Expected points for the down/distance/field-position choices on the
    report's recommendation chart, at every time on its grid. The page does the
    rest of the arithmetic live from the WP formula.

Usage:
    python clock_game.py            # prints the summaries
"""

import json
import os
import sys

import numpy as np
import pandas as pd

from timeouts import DATA, HERE

sys.path.insert(0, os.path.join(HERE, "..", "end_of_game"))
from runoff_model import load_intervals  # noqa: E402

TEAM = "RIBR"
IVY = ["RIBR", "MAHA", "CTYA", "NJPR", "PAUN", "NHDA", "NYCN", "NYCL"]
PLAY_CLOCK = 40
LIVE_BALL = 7            # typical snap-to-whistle seconds (see play_time)
LATE = 300               # "late": last 5:00 of the 4th quarter
MODES = {0: "normal", 2: "two_minute", 4: "four_minute"}

# The recommendation card: down & distance down the side, the ball's spot
# across the top (yards from OUR goal line), laid out like the staff's
# 4th-down decision sheet. Times are seconds left in the 4th quarter.
DOWNS = [(1, 10), (2, 2), (2, 5), (2, 8), (2, 12), (3, 1), (3, 3), (3, 5),
         (3, 8), (3, 12), (4, 1), (4, 3), (4, 6)]
YARDS = list(range(5, 96, 5))               # ball on our 5 ... their 5
GRID_CLOCK = list(range(30, 901, 30))
GRID_LEAD = list(range(-16, 9))


def fcs_codes_by_season():
    """Season-specific FCS team codes matched to ESPN's FCS directory."""
    path = os.path.join(DATA, "fcs_team_codes.json")
    source = json.load(open(path))
    base = set(source["base_codes"])
    return {
        int(season): (base | set(change["add"])) - set(change["remove"])
        for season, change in source["season_adjustments"].items()
    }


def load():
    """Snap-to-snap intervals with PFF's clock mode and the next snap's down."""
    path = os.path.join(DATA, "pbp.csv.gz")
    iv = load_intervals(path)

    plays = pd.read_csv(path, low_memory=False,
                        usecols=["pff_GAMEID", "pff_SORTORDER", "pff_QUARTER",
                                 "pff_DOWN", "pff_SPECIALTEAMSTYPE",
                                 "pff_EXPECTED_POINTS", "pff_YARDS_TO_GOAL_LINE"])
    plays = plays.sort_values(["pff_GAMEID", "pff_SORTORDER"])
    by = plays.groupby(["pff_GAMEID", "pff_QUARTER"])
    plays["next_down"] = by.pff_DOWN.shift(-1)
    plays["next_st"] = by.pff_SPECIALTEAMSTYPE.shift(-1)
    plays["next_ep"] = by.pff_EXPECTED_POINTS.shift(-1)
    plays["next_ytg"] = by.pff_YARDS_TO_GOAL_LINE.shift(-1)
    iv = iv.merge(plays[["pff_GAMEID", "pff_SORTORDER", "next_down", "next_st", "next_ep",
                         "next_ytg"]],
                  on=["pff_GAMEID", "pff_SORTORDER"], how="left")

    iv["mode"] = pd.to_numeric(iv.pff_2MINUTE, errors="coerce").map(MODES)
    iv["play_clock"] = pd.to_numeric(iv.pff_PLAYCLOCK, errors="coerce")
    iv["kneel"] = iv.pff_NON_TACKLE_TYPE.eq("TOOK A KNEE")
    return iv


# --------------------------------------------------------------------------
# play time
# --------------------------------------------------------------------------

def _split(frame):
    """Average seconds for clock-running snaps: the play plus the time between.

    Averages, not medians, so the two parts add up to the total a bar shows.
    """
    running = frame[~frame.clock_stopped & frame.next_play_clock.notna()]
    if not len(running):
        return {"n": 0, "total": None, "live": None, "dead": None, "clock_left": None}
    dead = PLAY_CLOCK - running.next_play_clock
    live = (running.elapsed - dead).clip(0, 20)
    return {
        "n": int(len(running)),
        "live": round(float(live.mean()), 1),
        "dead": round(float(dead.mean()), 1),
        "total": round(float(live.mean() + dead.mean()), 1),
        "clock_left": float(running.next_play_clock.median()),
    }


def play_time(iv):
    """Seconds per snap by clock mode and play type, for three groups."""
    groups = {"all": iv, "ivy": iv[iv.pff_OFFTEAM.isin(IVY)],
              "brown": iv[iv.pff_OFFTEAM == TEAM]}
    rows = [("normal", "R", "Normal run"), ("normal", "P", "Normal pass"),
            ("four_minute", "R", "Running out the clock: run"),
            ("four_minute", "P", "Running out the clock: pass"),
            ("two_minute", "R", "Two-minute drill: run"),
            ("two_minute", "P", "Two-minute drill: pass")]
    out = {}
    for name, frame in groups.items():
        table = []
        for mode, call, label in rows:
            cell = frame[(frame["mode"] == mode) & (frame.call == call) & ~frame.kneel]
            table.append({"label": label, "mode": mode, "call": call, **_split(cell)})
        table.append({"label": "Kneel-down", "mode": "kneel", "call": "K",
                      **_split(frame[frame.kneel])})
        out[name] = table

    # how much play clock is left at the snap, clock-running snaps only
    running = iv[~iv.clock_stopped & iv.next_play_clock.notna()]
    hist = {}
    for mode in ["normal", "four_minute"]:
        left = running[running["mode"] == mode].next_play_clock.clip(0, 40)
        counts = left.round().value_counts().reindex(range(0, 41), fill_value=0)
        hist[mode] = (counts / counts.sum()).round(4).tolist()
    four = running[running["mode"] == "four_minute"]
    brown_four = four[four.pff_OFFTEAM == TEAM]
    return {
        "rows": out,
        "clock_left_hist": hist,
        "four_minute_share_3s": round(float((four.next_play_clock <= 3).mean()), 3),
        "four_minute_clock_left": float(four.next_play_clock.median()),
        "brown_four_minute_n": int(len(brown_four)),
        "brown_four_minute_clock_left": float(brown_four.next_play_clock.median())
            if len(brown_four) else None,
        "pass_share": {m: round(float((iv[(iv["mode"] == m) & iv.call.notna()].call == "P").mean()), 3)
                       for m in MODES.values()},
    }


# --------------------------------------------------------------------------
# theory vs reality: late defensive timeouts
# --------------------------------------------------------------------------

def drive_time(plays):
    """How long successful hurry-up scoring drives take (TD or FG).

    Drives where at least 80% of snaps were two-minute offense, in one quarter,
    ending in a touchdown or field goal: seconds from first to last snap. The
    75th percentile is what "enough time for a scoring drive" means on the card.
    """
    snaps = plays[plays.pff_SPECIALTEAMSTYPE.isna() & plays.pff_DOWN.between(1, 4)].copy()
    snaps["two_minute"] = pd.to_numeric(snaps.pff_2MINUTE, errors="coerce") == 2
    drives = snaps.groupby(["pff_GAMEID", "pff_DRIVE"]).agg(
        q_first=("pff_QUARTER", "first"), q_last=("pff_QUARTER", "last"),
        c_first=("clock", "first"), c_last=("clock", "last"),
        ytg_first=("pff_YARDS_TO_GOAL_LINE", "first"), ytg_last=("pff_YARDS_TO_GOAL_LINE", "last"),
        end=("pff_DRIVEENDEVENT", "last"), hurry=("two_minute", "mean"),
        n=("two_minute", "size"))
    drives = drives[(drives.q_first == drives.q_last) & (drives.hurry >= 0.8) & (drives.n >= 3)]
    scored = drives[drives.end.astype(str).str.upper().str.contains("TOUCHDOWN|FIELD GOAL")]
    secs = scored.c_first - scored.c_last
    yards = scored.ytg_first - scored.ytg_last

    # time needed by distance: the line three out of four drives beat
    from sklearn.linear_model import QuantileRegressor
    long = yards >= 20
    fit = QuantileRegressor(quantile=0.75, alpha=0, solver="highs").fit(
        yards[long].to_frame(), secs[long])
    return {"n": int(len(secs)), "median": float(secs.median()),
            "p75": float(secs.quantile(0.75)),
            "a": round(float(fit.intercept_), 1), "b": round(float(fit.coef_[0]), 3)}


def time_needed(drive, lead, ytg):
    """Seconds a hurry-up drive needs from `ytg` yards out to get the score it must.

    Down 1-3 or tied: reach field-goal range (about the 30). Down 4-8: a
    touchdown. Down 9+: a touchdown, then a short second drive after an onside
    kick. Under 20 yards the fitted line is ramped down to 30 seconds at 0.
    """
    def by_yards(y):
        y = np.asarray(y, dtype=float)
        at20 = drive["a"] + 20 * drive["b"]
        return np.where(y >= 20, drive["a"] + drive["b"] * y, 30 + (at20 - 30) * y / 20)

    lead = np.asarray(lead)
    fg = by_yards(np.maximum(0, np.asarray(ytg) - 30))
    td = by_yards(ytg)
    return np.where(lead <= -9, td + by_yards(20), np.where(lead <= -4, td, fg))


FG_RANGE = 35       # yards to goal inside which a stop is assumed to still give up 3


def punt_model(plays):
    """Where the receiving team starts after a punt, from every punt we have.

    net: median yards between the punt spot and the receiver's first snap, for
    punts from 55+ yards out. floor: the receiver's median start when the punt
    comes from 40-54 yards out (short fields end in touchbacks and fair catches).
    """
    plays = plays.sort_values(["pff_GAMEID", "pff_SORTORDER"])
    nxt = plays.groupby("pff_GAMEID").pff_YARDS_TO_GOAL_LINE.shift(-1)
    punts = plays[plays.pff_SPECIALTEAMSTYPE.eq("PUNT")].assign(next_ytg=nxt)
    punts = punts[punts.next_ytg.between(1, 99)]
    start = 100 - punts.next_ytg                # receiver's yards from its own goal
    spot = punts.pff_YARDS_TO_GOAL_LINE
    return {"net": float((spot - start)[spot >= 55].median()),
            "floor": float(start[spot.between(40, 54)].median())}


def ball_back(punt, their_ytg, lead):
    """(our lead, our yards to goal) when we next get the ball after a stop.

    Inside FG_RANGE a stop still gives up a field goal and we start at our 25
    after the kickoff; otherwise they punt and we start where punts land.
    """
    their_ytg, lead = np.asarray(their_ytg, dtype=float), np.asarray(lead)
    kicked = their_ytg <= FG_RANGE
    start = np.maximum(punt["floor"], their_ytg - punt["net"])
    return (np.where(kicked, lead - 3, lead), np.where(kicked, 75, 100 - start))


def defense_reality(iv, kill_cycle, drive, punt):
    """How trailing defenses use timeouts in the last 5:00, against the rule.

    Only spots where time is tight count: if the offense ran the clock on every
    snap left before its punt (kill_cycle seconds each), the defense would get
    the ball back (see ball_back) with less time than time_needed() says its
    drive needs, the same test the recommendation card uses. Beginning in 2024,
    any otherwise flagged sequence expected to cross 2:00 before the punt is
    set aside because the automatic timeout changes the number and placement
    of useful charged timeouts. A no-timeout interval under 15 seconds means
    the clock stopped on its own (a push out of bounds PFF did not flag), so it
    is not a missed chance.
    """
    late_q4 = (iv.pff_QUARTER == 4) & (iv.clock <= LATE)
    trailing_d = iv.score_diff.between(1, 16)          # offense leads by 1-16
    same = iv.pff_OFFTEAM == iv.next_offense
    next_scrimmage = iv.next_st.isna() & iv.next_down.between(1, 4)
    natural = (iv.incomplete | iv.pff_TOUCHDOWN.notna()
               | (pd.to_numeric(iv.pff_NOPLAY, errors="coerce") == 1)
               | (pd.to_numeric(iv.pff_TURNOVER, errors="coerce") == 1)
               | ((pd.to_numeric(iv.pff_FIRST_DOWN_GAINED, errors="coerce") == 1)
                  & (iv.clock <= 120)))
    spots = iv[late_q4 & trailing_d & same & next_scrimmage & ~natural
               & (iv.def_to >= 1) & iv.next_ytg.notna()].copy()

    spots["called"] = spots.next_def_to < spots.def_to
    spots = spots[spots.called | (spots.elapsed >= 15)]

    # is time tight? the ball back after they run the clock on every snap left
    snaps_left = 5 - spots.next_down
    time_back = (spots.clock - LIVE_BALL) - snaps_left * kill_cycle
    lead_after, ytg_after = ball_back(punt, spots.next_ytg, -spots.score_diff)
    need = time_needed(drive, lead_after, ytg_after)
    spots = spots[time_back < need]

    # The 2024 rule stops a running dead-ball clock at exactly 2:00. If the
    # ball is live then, the stop comes when that play ends. We conservatively
    # hold out the whole decision whenever the average no-timeout path starts
    # above 2:00 and reaches it before the expected punt. Those rows require a
    # separate optimization with one free stop; they are not labeled misses.
    spots["two_minute_affected"] = (
        (spots.pff_GAMESEASON >= 2024)
        & (spots.clock > 120)
        & (time_back <= 120)
    )
    spots["two_minute_direct"] = (
        (spots.pff_GAMESEASON >= 2024)
        & (spots.clock > 120)
        & (spots.next_clock <= 120)
        & ~spots.called
    )
    spots["rule_call_raw"] = spots.def_to >= 5 - spots.next_down
    spots["rule_call"] = spots.rule_call_raw & ~spots.two_minute_affected
    spots["lost"] = (spots.elapsed - LIVE_BALL).clip(lower=0)

    def summary(frame):
        raw_should = frame[frame.rule_call_raw]
        should = frame[frame.rule_call]
        wait = frame[~frame.rule_call]
        missed = should[~should.called]
        made = should[should.called]
        return {
            "snaps": int(len(frame)),
            "raw_should_call": int(len(raw_should)),
            "two_minute_excluded": int(raw_should.two_minute_affected.sum()),
            "direct_two_minute_stops": int(raw_should.two_minute_direct.sum()),
            "should_call": int(len(should)),
            "called_when_should": round(float(should.called.mean()), 3) if len(should) else None,
            "seconds_lost_when_missed": round(float(missed.lost.mean()), 1) if len(missed) else None,
            "seconds_lost_total": round(float(missed.lost.sum()), 1),
            "missed_with_three_timeouts": int((missed.def_to == 3).sum()),
            "delay_when_called": round(float(made.lost.median()), 1) if len(made) else None,
            "called_when_could_wait": round(float(wait.called.mean()), 3) if len(wait) else None,
            "seconds_lost_per_game": round(float(missed.lost.sum() / frame.pff_GAMEID.nunique()), 1)
                if len(frame) else None,
        }

    brown = spots[spots.pff_DEFTEAM == TEAM]
    missed = brown[brown.rule_call & ~brown.called].sort_values(["pff_GAMESEASON", "pff_WEEK"])
    brown_missed = [{
        "season": int(r.pff_GAMESEASON), "opponent": r.pff_OFFTEAM,
        "clock": int(max(0, r.clock - LIVE_BALL)), "lead": int(-r.score_diff),
        "next_down": int(r.next_down), "timeouts": int(r.def_to),
        "lost": round(float(r.lost)),
    } for r in missed.itertuples()]

    brown_two_minute = brown[brown.rule_call_raw & brown.two_minute_affected].sort_values(
        ["pff_GAMESEASON", "pff_WEEK", "pff_GAMEID", "clock"]
    )
    brown_two_minute = [{
        "season": int(r.pff_GAMESEASON), "opponent": r.pff_OFFTEAM,
        "snap_clock": int(r.clock), "next_snap_clock": int(r.next_clock),
        "next_down": int(r.next_down), "timeouts": int(r.def_to),
        "called": bool(r.called), "lost": round(float(r.lost)),
    } for r in brown_two_minute.itertuples()]

    fcs = fcs_codes_by_season()
    fcs_defense = pd.Series([
        team in fcs.get(int(season), set())
        for team, season in zip(spots.pff_DEFTEAM, spots.pff_GAMESEASON)
    ], index=spots.index)

    return {"all": summary(spots),
            "fcs": summary(spots[fcs_defense]),
            "ivy": summary(spots[spots.pff_DEFTEAM.isin(IVY)]),
            "brown": summary(brown),
            "brown_missed": brown_missed,
            "brown_two_minute_excluded": brown_two_minute,
            "two_minute_assumption": (
                "For 2024 onward, set aside any raw flag that starts above 2:00 "
                "and whose average no-timeout path reaches 2:00 before the expected punt."
            )}


# --------------------------------------------------------------------------
# recommendation inputs
# --------------------------------------------------------------------------

def recommendation_inputs(ep_model):
    """Expected points behind the recommendation card, at every grid time.

    Three tables, each indexed [row][ytg][time], where row is a DOWNS entry and
    ytg is yards to the goal line of whichever team has the ball (5..95):
      ep       the snap as it stands
      ep_pen   after a 5-yard delay of game (half the distance near our goal)
      ep_spike one down later, same distance and spot (a spike); None on 4th
    The page does the rest of the arithmetic live from the WP formula.
    """
    from report_data import ep_of
    ytgs = YARDS
    rows = [(i, down, dist, ytg, t) for i, (down, dist) in enumerate(DOWNS)
            for ytg in ytgs for t in GRID_CLOCK]
    frame = pd.DataFrame(rows, columns=["row", "down", "distance", "ytg", "t"])
    # goal to go: the distance can't be longer than the field left
    dist = np.minimum(frame.distance, frame.ytg)
    frame["ep"] = ep_of(ep_model, frame.down, dist, frame.ytg, frame.t)
    yards = np.minimum(5, (100 - frame.ytg) / 2)
    frame["ep_pen"] = ep_of(ep_model, frame.down, dist + yards, frame.ytg + yards, frame.t)
    frame["ep_spike"] = ep_of(ep_model, np.minimum(frame.down + 1, 4), dist,
                              frame.ytg, frame.t)

    def cube(column, skip_fourth=False):
        out = []
        for i, (down, _) in enumerate(DOWNS):
            block = frame[frame.row == i]
            grid = block.pivot(index="ytg", columns="t", values=column).loc[ytgs, GRID_CLOCK]
            out.append(None if skip_fourth and down == 4
                       else np.round(grid.values, 2).tolist())
        return out

    return {"downs": [{"down": d, "distance": s} for d, s in DOWNS],
            "yards": YARDS, "ytgs": ytgs,
            "grid_clock": GRID_CLOCK, "grid_lead": GRID_LEAD,
            "ep": cube("ep"), "ep_pen": cube("ep_pen"),
            "ep_spike": cube("ep_spike", skip_fourth=True)}


def main():
    iv = load()
    pt = play_time(iv)
    print("PLAY TIME (clock-running snaps, medians): total / play / between plays / play clock left")
    for group in ["all", "ivy", "brown"]:
        print(f"  {group}")
        for r in pt["rows"][group]:
            print(f"    {r['label']:30s} n={r['n']:7,d}  {r['total']}  {r['live']}  {r['dead']}  {r['clock_left']}")
    print(f"  four-minute snaps with <=3s left: {pt['four_minute_share_3s']:.0%}; "
          f"median left {pt['four_minute_clock_left']}s (Brown {pt['brown_four_minute_clock_left']}s, "
          f"n={pt['brown_four_minute_n']})")

    from timeouts import load_plays
    plays = load_plays()
    drive = drive_time(plays)
    punt = punt_model(plays)
    print(f"PUNTS: {punt}")
    kill = next(r for r in pt["rows"]["all"] if r["label"] == "Running out the clock: run")
    dr = defense_reality(iv, kill["total"], drive, punt)
    print(f"\nHURRY-UP SCORING DRIVES: {drive}")
    print("\nLATE DEFENSIVE TIMEOUTS vs THE RULE (time tight)")
    for group, s in dr.items():
        print(f"  {group}: {s}")


if __name__ == "__main__":
    main()
