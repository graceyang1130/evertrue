"""Compute every number the timeout decision report shows, into one JSON file.

A timeout is priced as the clock it saves. runoff_model.py measured how many
dead-ball seconds a timeout erases; wp_model.py turns seconds into win
probability. The value of holding your k-th timeout is

    WP(clock + k*S) - WP(clock + (k-1)*S)      (never below zero)

from the point of view of the team spending it, where S is:

  their ball  the dead-ball seconds of a team killing the clock (Ivy kill-regime
              run, ~35s) -- what a defensive timeout takes back
  our ball    Brown's own hurry-up dead-ball seconds (~18s) -- what an offensive
              timeout saves in a two-minute drill

A team that is ahead gains nothing from more clock, so its timeouts have no
clock value here. That is deliberate: their other uses (a bad look, a
substitution mess) are the play_clock question, priced separately.

Writes out/report_data.json with:
  value_grid     timeout value by time left and score, Q4, both sides
  option_value   what a 2nd-half timeout carried into the last 4:00 is worth on
                 average -- the real cost of spending one earlier
  penalty_costs  what 5 yards costs in common spots, to set against it
  audit          where timeouts go per game, Brown vs rest of Ivy vs FBS/FCS
  close_losses   timeouts left unused in one-score losses
  brown_log      each Brown play-clock timeout: 5 yards vs the timeout
  scenario       the Brown-Yale test case, three ways
  calibration    predicted vs actual on the held-out season

Usage:
    python report_data.py
"""

import json
import os

import numpy as np
import pandas as pd

from timeouts import DATA, HERE, load_plays
from wp_model import EP_FEATURES, build_snaps, load, win_prob

OUT = os.path.join(HERE, "out")
RUNOFF = os.path.join(HERE, "..", "end_of_game")
TEAM = "RIBR"
IVY = ["RIBR", "MAHA", "CTYA", "NJPR", "PAUN", "NHDA", "NYCN", "NYCL"]

GRID_CLOCK = list(range(30, 601, 30))     # seconds left in the 4th quarter
GRID_LEAD = list(range(-16, 9))           # our score minus theirs
PENALTY = 5
LATE_WINDOW = 240                         # "the last 4:00"


def seconds_saved(play_time=None):
    """Seconds between plays that one timeout erases.

    From clock_game.play_time (PFF's clock-mode tags): on defense, the average
    time between plays of a team running out the clock with runs (all FBS/FCS);
    on offense, Brown's own two-minute pace. Without play_time it falls back to
    the end-of-game runoff model's parameters.
    """
    if play_time is not None:
        row = lambda group, label: next(r for r in play_time["rows"][group]
                                        if r["label"] == label)
        brown = row("brown", "Two-minute drill: pass")
        ball = brown if brown["n"] >= 30 else row("all", "Two-minute drill: pass")
        return {"def": row("all", "Running out the clock: run")["dead"],
                "ball": ball["dead"]}
    with open(os.path.join(RUNOFF, "params_ivy.json")) as handle:
        ivy = json.load(handle)
    with open(os.path.join(RUNOFF, "params_brown.json")) as handle:
        brown = json.load(handle)
    return {
        "def": float(ivy["runoff"]["kill"]["R"]["dead_ball"]["median"]),
        "ball": float(brown["runoff"]["hurry"]["P"]["dead_ball"]["median"]),
    }


def ep_of(ep_model, down, distance, ytg, half_secs):
    frame = pd.DataFrame({"down": down, "distance": distance, "ytg": ytg,
                          "half_secs": half_secs})
    return ep_model.predict(frame[EP_FEATURES])


def our_wp(params, side, lead, ep, secs, strength=0.0):
    """WP of the team deciding, whether it has the ball or not."""
    if side == "ball":
        return win_prob(params, lead, ep, secs, strength)
    return 1 - win_prob(params, -np.asarray(lead), ep, secs, -np.asarray(strength))


def clock_value(params, side, lead, ep, secs, k, save):
    """WP added by the k-th timeout, priced as k*save seconds of clock."""
    more = our_wp(params, side, lead, ep, secs + k * save)
    less = our_wp(params, side, lead, ep, secs + (k - 1) * save)
    return np.maximum(0.0, more - less)


def value_grid(params, ep_model, save):
    """Q4 value of the 1st/2nd/3rd timeout: 1st & 10 at the 25, either side."""
    clock, lead = np.meshgrid(GRID_CLOCK, GRID_LEAD)
    ep = ep_of(ep_model, np.ones(clock.size), np.full(clock.size, 10),
               np.full(clock.size, 75), clock.ravel()).reshape(clock.shape)
    out = {}
    for side in ["ball", "def"]:
        out[f"{side}|wp"] = np.round(our_wp(params, side, lead, ep, clock) * 100, 1).tolist()
        for k in range(1, 4):
            v = clock_value(params, side, lead, ep, clock, k, save[side])
            out[f"{side}|{k}"] = np.round(v * 100, 2).tolist()

    # With the ball, the alternative to a play-clock timeout is 5 yards:
    # 1st & 10 at our 25 becomes 1st & 15 at our 20.
    ep_pen = ep_of(ep_model, np.ones(clock.size), np.full(clock.size, 10 + PENALTY),
                   np.full(clock.size, 75 + PENALTY), clock.ravel()).reshape(clock.shape)
    pen = win_prob(params, lead, ep, clock) - win_prob(params, lead, ep_pen, clock)
    out["ball|penalty"] = np.round(pen * 100, 2).tolist()
    return out


def option_value(params, snaps, save):
    """Average value of one timeout for a team reaching the last 4:00 with it."""
    late = snaps[snaps.game_secs <= LATE_WINDOW]
    first = late.sort_values("pff_SORTORDER").groupby("pff_GAMEID").head(1)

    rows = []
    for side, lead, strength in [("ball", first.lead, first.strength),
                                 ("def", -first.lead, -first.strength)]:
        v = clock_value(params, side, lead, first.ep, first.game_secs, 1, save[side])
        rows.append(pd.DataFrame({"value": v, "close": lead.abs() <= 8}))
    both = pd.concat(rows)
    return {
        "all_games": round(float(both.value.mean()) * 100, 2),
        "one_score": round(float(both[both.close].value.mean()) * 100, 2),
        "share_one_score": round(float(both.close.mean()), 3),
    }


SPOTS = [
    ("1st & 10, own 25", 1, 10, 75),
    ("2nd & 6, own 40", 2, 6, 60),
    ("3rd & 2, midfield", 3, 2, 50),
    ("3rd & 6, own 45", 3, 6, 55),
    ("3rd & 4, opp 30", 3, 4, 30),
    ("4th & 1, opp 40", 4, 1, 40),
    ("1st & goal, opp 5", 1, 5, 5),
    ("3rd & goal, opp 3", 3, 3, 3),
]


def penalty_costs(params, ep_model, game_secs=1350, lead=0):
    """WP lost to a 5-yard delay of game in common spots (3rd qtr, tied)."""
    half_secs = game_secs
    rows = []
    for label, down, dist, ytg in SPOTS:
        yards = min(PENALTY, (100 - ytg) / 2)
        before = ep_of(ep_model, [down], [dist], [ytg], [half_secs])[0]
        after = ep_of(ep_model, [down], [dist + yards], [ytg + yards], [half_secs])[0]
        cost = (win_prob(params, lead, before, game_secs)
                - win_prob(params, lead, after, game_secs))
        rows.append({"spot": label, "ep_before": round(float(before), 2),
                     "ep_after": round(float(after), 2),
                     "cost": round(float(cost) * 100, 2)})
    return rows


def audit(events, left, games):
    def n_games(teams):
        return int(games.team_a.isin(teams).sum() + games.team_b.isin(teams).sum())

    everyone = sorted(set(games.team_a) | set(games.team_b))
    groups = {
        "Brown": [TEAM],
        "Rest of Ivy": [t for t in IVY if t != TEAM],
        "All FBS/FCS": everyone,
    }
    purposes = ["clock", "defense", "play_clock", "fourth_down", "pre_punt",
                "pre_kick", "offense"]
    rates, unused = {}, {}
    for label, teams in groups.items():
        games_played = n_games(teams)
        mine = events[events.team.isin(teams)]
        per = mine.groupby("purpose").n.sum() / games_played
        rates[label] = {p: round(float(per.get(p, 0.0)), 3) for p in purposes}
        rates[label]["total"] = round(float(mine.n.sum() / games_played), 2)
        rates[label]["games"] = games_played
        held = left[left.team.isin(teams)]
        unused[label] = {
            "half": round(float(held[held.half == 1].unused.mean()), 2),
            "game": round(float(held[held.half == 2].unused.mean()), 2),
        }
    return {"purposes": purposes, "rates": rates, "unused": unused}


def close_losses(left, games):
    """Timeouts still in the pocket at the final whistle of one-score losses."""
    end = left[left.half == 2].merge(games, left_on="game", right_on="pff_GAMEID")
    mine = np.where(end.team == end.team_a, end.score_a, end.score_b)
    theirs = np.where(end.team == end.team_a, end.score_b, end.score_a)
    end["margin"] = mine - theirs
    lost = end[(end.margin < 0) & (end.margin >= -8)]
    brown = lost[lost.team == TEAM].copy()
    brown["opponent"] = np.where(brown.team == brown.team_a, brown.team_b, brown.team_a)
    return {
        "brown_games": brown[["season", "week", "opponent", "margin", "unused"]]
            .sort_values(["season", "week"]).to_dict("records"),
        "brown_share_with_unused": round(float((brown.unused > 0).mean()), 3),
        "ncaa_share_with_unused": round(float((lost.unused > 0).mean()), 3),
    }


def brown_log(params, ep_model, events, snaps, option):
    """Each Brown play-clock timeout: the 5 yards it avoided vs what it was worth."""
    mine = events[(events.team == TEAM) & (events.purpose == "play_clock")]
    indexed = snaps.set_index(["pff_GAMEID", "pff_SORTORDER"])
    rows = []
    for ev in mine.itertuples():
        key = (ev.game, ev.snap_sort)
        if key not in indexed.index:
            continue
        s = indexed.loc[key]
        yards = min(PENALTY, (100 - s.ytg) / 2)
        after = ep_of(ep_model, [s.down], [s.distance + yards], [s.ytg + yards],
                      [s.half_secs])[0]
        cost = (win_prob(params, s.lead, s.ep, s.game_secs, s.strength)
                - win_prob(params, s.lead, after, s.game_secs, s.strength))
        rows.append({
            "season": int(ev.season), "week": str(ev.week), "opponent": ev.opponent,
            "quarter": int(ev.quarter), "clock": int(ev.clock),
            "down": int(s.down), "distance": int(s.distance), "ytg": int(s.ytg),
            "lead": int(s.lead), "left_after": int(ev.to_left_after),
            "penalty_cost": round(float(cost) * 100, 2),
            "timeout_value": option["one_score"] if ev.half == 2 else None,
        })
    return rows


def scenario(params, ep_model, save, games):
    """Down 3, 1st & 10 at own 25, 2:00 left, with 0-3 timeouts.

    PFF's In-Game Decision Maker numbers were read off its UI for Brown vs Yale
    (2026 week 4 ratings); the Ivy history is every 2019-26 Ivy snap in that
    spot (see pff-ultimate notes). Ours is shown even and with 2025 ratings.
    """
    from wp_model import team_strength
    strength = team_strength(games)
    matchup = float(strength.get((2025, TEAM)) - strength.get((2025, "CTYA")))
    ep = ep_of(ep_model, [1], [10], [75], [120])[0]

    def line(s):
        return [round(float(win_prob(params, -3, ep, 120 + k * save["ball"], s)) * 100, 1)
                for k in range(4)]

    return {"even_teams": line(0.0), "brown_vs_yale": line(matchup),
            "pff": [2.5, 2.8, 3.2, 3.6], "ivy_history": {"won": 5, "n": 16}}


def main():
    import clock_game
    params, ep_model = load()
    intervals = clock_game.load()
    play_time = clock_game.play_time(intervals)
    save = seconds_saved(play_time)

    plays = load_plays()
    games = pd.read_csv(os.path.join(DATA, "games.csv"))
    events = pd.read_csv(os.path.join(DATA, "timeouts.csv"), low_memory=False)
    left = pd.read_csv(os.path.join(DATA, "timeouts_unused.csv"))
    snaps = build_snaps(plays, games)
    calib = pd.read_csv(os.path.join(DATA, "wp_calibration.csv"))
    option = option_value(params, snaps, save)
    drive = clock_game.drive_time(plays)
    punt = clock_game.punt_model(plays)
    kill_cycle = next(r for r in play_time["rows"]["all"]
                      if r["label"] == "Running out the clock: run")["total"]

    report = {
        "grid_clock": GRID_CLOCK,
        "grid_lead": GRID_LEAD,
        "seconds_saved": save,
        "value_grid": value_grid(params, ep_model, save),
        "option_value": option,
        "penalty_costs": penalty_costs(params, ep_model),
        "audit": audit(events, left, games),
        "close_losses": close_losses(left, games),
        "brown_log": brown_log(params, ep_model, events, snaps, option),
        "scenario": scenario(params, ep_model, save, games),
        "calibration": calib[["n", "predicted", "actual"]].round(4).to_dict("records"),
        "play_time": play_time,
        "drive_time": drive,
        "punt": {**punt, "fg_range": clock_game.FG_RANGE},
        "defense_reality": clock_game.defense_reality(intervals, kill_cycle, drive, punt),
        "recommend": clock_game.recommendation_inputs(ep_model),
        "wp_params": params,
        "meta": {
            "last_week": int(pd.to_numeric(
                games[games.season == games.season.max()].week, errors="coerce").max()),
            "seasons": sorted(int(s) for s in games.season.unique()),
            "games": int(len(games)),
            "snaps": int(len(snaps)),
            "timeouts": int(events.n.sum()),
        },
    }

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "report_data.json")
    with open(path, "w") as handle:
        json.dump(report, handle, separators=(",", ":"))
    print(f"wrote {path} ({os.path.getsize(path) / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
