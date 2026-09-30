"""Inputs for the 4th-down card: go, punt or kick, by chance of winning.

The card compares three options on every 4th down, each scored by our chance
of winning afterwards (the same win-probability formula as tos/wp_model.py):

    GO    = convert% x WP(first down at the sticks, or a touchdown)
          + (1 - convert%) x WP(they take over here)
    PUNT  = WP(they take over where our punt usually lands)
    FG    = make% x WP(up 3 more, they receive the kickoff)
          + (1 - make%) x WP(they take over at the spot of the kick, or their 20)

This script fits the rates behind those formulas from every FBS/FCS play we
have (2023 on) and writes them, plus an expected-points table, for the page to
do the arithmetic live when the filters change:

  conversion   logistic fit on 3rd- and 4th-down snaps: log(distance), and a
               goal-line term (inside the 5 is harder)
  field goal   logistic fit on every attempt: kick distance (yards to goal + 17)
  punt         where the receiving team starts, by where we punt from (median
               regression, floored at the short-field start from clock_game)
  Brown        the same three, shifted to match Brown's own results since 2023
               (a single adjustment each, so small samples can't reshape curves)

Usage:
    python fourth_data.py
"""

import json
import os
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tos"))

from clock_game import punt_model  # noqa: E402
from report_data import ep_of  # noqa: E402
from timeouts import DATA, load_plays  # noqa: E402
from wp_model import load as load_models  # noqa: E402

TEAM = "RIBR"
OUT = os.path.join(HERE, "out")
QUARTER_CLOCKS = [900, 720, 600, 480, 300, 180, 120, 60, 30]   # time-left choices
KICKOFF_YTG = 75                                               # start after a kickoff


def logit(p):
    return np.log(p / (1 - p))


def shift_to_match(prob, observed):
    """Log-odds shift that makes mean(prob) equal the observed rate."""
    lo, hi = -3.0, 3.0
    base = logit(np.clip(prob, 1e-6, 1 - 1e-6))
    for _ in range(60):
        mid = (lo + hi) / 2
        if (1 / (1 + np.exp(-(base + mid)))).mean() < observed:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 3)


def conversion_model(plays):
    snaps = plays[plays.pff_SPECIALTEAMSTYPE.isna() & plays.pff_DOWN.isin([3, 4])]
    snaps = snaps[~snaps.pff_NON_TACKLE_TYPE.eq("TOOK A KNEE")
                  & ~snaps.pff_PASSRESULT.eq("SPIKE")
                  & (pd.to_numeric(snaps.pff_NOPLAY, errors="coerce").fillna(0) == 0)]
    converted = ((pd.to_numeric(snaps.pff_FIRST_DOWN_GAINED, errors="coerce") == 1)
                 | snaps.pff_TOUCHDOWN.notna()).astype(int)
    X = pd.DataFrame({
        "log_dist": np.log(snaps.pff_DISTANCE.clip(1, 20)),
        "goal_line": (snaps.pff_YARDS_TO_GOAL_LINE <= 5).astype(int),
    })
    fit = LogisticRegression(C=1e6, max_iter=1000).fit(X, converted)
    prob = fit.predict_proba(X)[:, 1]
    mine = (snaps.pff_OFFTEAM == TEAM).values
    table = (pd.DataFrame({"d": snaps.pff_DISTANCE.clip(1, 15), "c": converted, "p": prob})
             .groupby("d").agg(n=("c", "size"), actual=("c", "mean"), fitted=("p", "mean")))
    return {
        "b0": round(float(fit.intercept_[0]), 4),
        "b_log_dist": round(float(fit.coef_[0][0]), 4),
        "b_goal_line": round(float(fit.coef_[0][1]), 4),
        "n": int(len(snaps)),
        "brown_shift": shift_to_match(prob[mine], converted[mine].mean()),
        "brown_n": int(mine.sum()),
        "by_distance": [{"distance": int(d), "n": int(r.n), "actual": round(float(r.actual), 3),
                         "fitted": round(float(r.fitted), 3)} for d, r in table.iterrows()],
    }


def field_goal_model(plays):
    kicks = plays[plays.pff_SPECIALTEAMSTYPE.eq("FIELD GOAL")]
    dist = kicks.pff_YARDS_TO_GOAL_LINE + 17
    made = kicks.pff_KICKRESULT.astype(str).str.upper().str.startswith("MADE").astype(int)
    fit = LogisticRegression(C=1e6, max_iter=1000).fit(dist.to_frame(), made)
    prob = fit.predict_proba(dist.to_frame())[:, 1]
    mine = (kicks.pff_OFFTEAM == TEAM).values
    bins = pd.cut(dist, [0, 30, 35, 40, 45, 50, 55, 60])
    table = pd.DataFrame({"m": made, "p": prob}).groupby(bins, observed=True).agg(
        n=("m", "size"), actual=("m", "mean"), fitted=("p", "mean"))
    return {
        "b0": round(float(fit.intercept_[0]), 4),
        "b_dist": round(float(fit.coef_[0][0]), 4),
        "n": int(len(kicks)),
        "brown_shift": shift_to_match(prob[mine], made[mine].mean()),
        "brown_n": int(mine.sum()),
        "by_distance": [{"range": str(b), "n": int(r.n), "actual": round(float(r.actual), 3),
                         "fitted": round(float(r.fitted), 3)} for b, r in table.iterrows()],
    }


def punt_line(plays):
    """Where the other team starts after our punt, by where we punt from.

    Punts from deep in our own end go farther than punts from midfield, so a
    single net distance is too pessimistic deep and too generous short. Median
    regression over punts from 50+ yards out:

        their start (yards from their own goal) = a + b * our yards to goal

    floored at the league's short-field start, fitted as a count-weighted line
    through the median start in each 5-yard band (a full median regression on
    40,000+ punts is too slow). Brown's line keeps the slope and moves the
    intercept to Brown's median miss from the league line.
    """
    plays = plays.sort_values(["pff_GAMEID", "pff_SORTORDER"])
    nxt = plays.groupby("pff_GAMEID").pff_YARDS_TO_GOAL_LINE.shift(-1)
    punts = plays[plays.pff_SPECIALTEAMSTYPE.eq("PUNT")].assign(next_ytg=nxt)
    punts = punts[punts.next_ytg.between(1, 99) & (punts.pff_YARDS_TO_GOAL_LINE >= 50)]
    spot = punts.pff_YARDS_TO_GOAL_LINE
    start = 100 - punts.next_ytg
    bands = (spot // 5) * 5 + 2.5
    med = start.groupby(bands).agg(["median", "size"])
    b, a = np.polyfit(med.index.values, med["median"].values, 1, w=np.sqrt(med["size"].values))
    a, b = float(a), float(b)
    mine = punts.pff_OFFTEAM == TEAM
    shift = float((start[mine] - (a + b * spot[mine])).median()) if mine.any() else 0.0
    return {"a": round(a, 2), "b": round(b, 3), "brown_shift": round(shift, 2),
            "brown_n": int(mine.sum()), "n": int(len(punts))}


def ep_table(ep_model):
    """EP of a 1st & 10 (or goal) at every yard line, for every time choice.

    Keys are seconds left in the half; the page picks the one its filters give.
    The EP lookup is a tree model with small bumps between neighbouring yard
    lines, and those bumps flip close 4th-down calls back and forth. A 1st & 10
    can only be worth more the closer it is to the goal line, so each row is
    forced to rise toward the goal (isotonic fit) and then lightly smoothed.
    """
    from sklearn.isotonic import IsotonicRegression
    half_secs = sorted({c for c in QUARTER_CLOCKS} | {900 + c for c in QUARTER_CLOCKS})
    ytg = np.arange(1, 100)
    out = {}
    for hs in half_secs:
        raw = ep_of(ep_model, np.ones(len(ytg)), np.minimum(10, ytg), ytg, np.full(len(ytg), hs))
        mono = IsotonicRegression(increasing=False).fit_transform(ytg, raw)
        smooth = pd.Series(mono).rolling(7, center=True, min_periods=1).mean().values
        out[str(hs)] = np.round(smooth, 3).tolist()
    return out


def main():
    params, ep_model = load_models()
    plays = load_plays()
    games = pd.read_csv(os.path.join(DATA, "games.csv"))

    punt = punt_model(plays)
    data = {
        "wp_params": params,
        "conversion": conversion_model(plays),
        "field_goal": field_goal_model(plays),
        "punt": {"floor": punt["floor"], **punt_line(plays)},
        "ep_first_down": ep_table(ep_model),
        "quarter_clocks": QUARTER_CLOCKS,
        "kickoff_ytg": KICKOFF_YTG,
        "meta": {"games": int(len(games)),
                 "seasons": sorted(int(s) for s in games.season.unique())},
    }

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "fourth_data.json")
    with open(path, "w") as handle:
        json.dump(data, handle, separators=(",", ":"))

    c, f = data["conversion"], data["field_goal"]
    print(f"conversion fit on {c['n']:,} snaps: b0 {c['b0']}, log(dist) {c['b_log_dist']}, "
          f"goal line {c['b_goal_line']}; Brown shift {c['brown_shift']} (n={c['brown_n']})")
    for r in c["by_distance"]:
        print(f"   4th & {r['distance']:2d}: actual {r['actual']:.3f}  fitted {r['fitted']:.3f}  (n={r['n']:,})")
    print(f"field goal fit on {f['n']:,} kicks: b0 {f['b0']}, dist {f['b_dist']}; "
          f"Brown shift {f['brown_shift']} (n={f['brown_n']})")
    for r in f["by_distance"]:
        print(f"   {r['range']:10s} actual {r['actual']:.3f}  fitted {r['fitted']:.3f}  (n={r['n']:,})")
    pl = data["punt"]
    print(f"punt: start = {pl['a']} + {pl['b']} x spot (floor {pl['floor']}), Brown shift {pl['brown_shift']} "
          f"(n={pl['brown_n']}); from our 5 they start at their {pl['a'] + pl['b'] * 95:.0f}, "
          f"from our 30 at their {pl['a'] + pl['b'] * 70:.0f}")
    print(f"wrote {path} ({os.path.getsize(path) / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
