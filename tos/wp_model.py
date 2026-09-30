"""Win probability, smooth enough to price a timeout.

PFF's play feed has expected points but no win probability, and PFF's own
In-Game Decision Maker gave numbers far below what actually happened in
comparable Ivy games. So we fit our own, on every FBS/FCS scrimmage snap we
have (2023+, one clock-rule regime).

THE MODEL
---------
The final margin is treated as the current margin plus what this possession
is expected to produce, plus noise that shrinks as the clock runs out:

    z  = (lead + a*EP + b*strength*t) / (sigma*sqrt(t) + c)
    WP = Phi(z)                       t = fraction of regulation left

  lead      offense score minus defense score
  EP        PFF expected points of the offense's current snap
  strength  offense minus defense season points-per-game margin
  sigma     how far the final margin wanders over a full game (fitted)
  c         floor, so a one-score game is never quite decided before 0:00

Four parameters, fitted by maximum likelihood. On the held-out 2025 season it
beats a 400-tree gradient-boosted model we tried first (log loss 0.335 vs
0.352; last five minutes of one-score games 0.442 vs 0.476).

WHY NOT THE TREES
-----------------
The tree model put timeouts-remaining in as a feature, and it learned the
wrong thing: early in games, teams already down a timeout win 43% vs 53%,
because burning one early marks a disorganised afternoon, not because the
timeout mattered. It priced a 1st-quarter timeout at ~6 WP points. Its
seconds-to-WP slope was also jagged (30 extra seconds sometimes "hurt" a
trailing team). A smooth, few-parameter model cannot learn either artefact.

TIMEOUTS
--------
Timeouts are not a model input. A timeout's clock value is the WP of the
dead-ball seconds it erases, and those seconds come from runoff_model.py (see
report_data.py). That keeps the value causal: a timeout is worth what the
clock it saves is worth.

EXPECTED POINTS FOR HYPOTHETICAL SNAPS
--------------------------------------
Pricing "what if we take the 5 yards" needs EP for snaps that did not happen.
A small regressor reproduces PFF's EP from down, distance, yards to goal and
time left in the half (R^2 0.91 on 2025).

Usage:
    python wp_model.py            # fit on 2023-24, test on 2025, refit all, save
"""

import argparse
import json
import os
import pickle

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import brier_score_loss, log_loss

from timeouts import DATA, load_plays

PARAMS_PATH = os.path.join(DATA, "wp_params.json")
EP_PATH = os.path.join(DATA, "ep_model.pkl")
EP_FEATURES = ["down", "distance", "ytg", "half_secs"]
FIT_SAMPLE = 250_000


def team_strength(games):
    """Season points-per-game margin for every team."""
    a = games[["season", "team_a", "score_a", "score_b"]].set_axis(
        ["season", "team", "pf", "pa"], axis=1)
    b = games[["season", "team_b", "score_b", "score_a"]].set_axis(
        ["season", "team", "pf", "pa"], axis=1)
    both = pd.concat([a, b])
    both["margin"] = both.pf - both.pa
    return both.groupby(["season", "team"]).margin.mean()


def build_snaps(plays, games):
    """Regulation scrimmage snaps with a known winner, in model terms."""
    strength = team_strength(games)
    snaps = plays[
        plays.pff_SPECIALTEAMSTYPE.isna()
        & plays.pff_DOWN.between(1, 4)
        & plays.pff_QUARTER.between(1, 4)
    ].copy()

    q = snaps.pff_QUARTER
    snaps["lead"] = snaps.pff_SCOREDIFFERENTIAL
    snaps["ep"] = snaps.pff_EXPECTED_POINTS
    snaps["game_secs"] = (4 - q) * 900 + snaps.clock
    snaps["half_secs"] = np.where(q.isin([1, 3]), 900 + snaps.clock, snaps.clock)
    snaps["down"] = snaps.pff_DOWN
    snaps["distance"] = snaps.pff_DISTANCE.clip(upper=30)
    snaps["ytg"] = snaps.pff_YARDS_TO_GOAL_LINE
    snaps["off_to"] = snaps.pff_OFF_TIMEOUTS_REMAINING
    snaps["def_to"] = snaps.pff_DEF_TIMEOUTS_REMAINING

    key_off = list(zip(snaps.pff_GAMESEASON, snaps.pff_OFFTEAM))
    key_def = list(zip(snaps.pff_GAMESEASON, snaps.pff_DEFTEAM))
    snaps["strength"] = (strength.reindex(key_off).values
                         - strength.reindex(key_def).values)
    return snaps.dropna(subset=["lead", "ep", "game_secs", "strength", "off_won"])


def win_prob(params, lead, ep, game_secs, strength=0.0):
    """Offense win probability. Arguments broadcast like numpy arrays."""
    t = np.asarray(game_secs, dtype=float) / 3600
    z = (np.asarray(lead) + params["a"] * np.asarray(ep)
         + params["b"] * np.asarray(strength) * t)
    z = z / (params["sigma"] * np.sqrt(t) + params["c"])
    return norm.cdf(z)


def fit_wp(snaps):
    sample = snaps.sample(min(FIT_SAMPLE, len(snaps)), random_state=0)

    def nll(x):
        params = dict(zip(["a", "b", "sigma", "c"], x))
        p = np.clip(win_prob(params, sample.lead, sample.ep, sample.game_secs,
                             sample.strength), 1e-6, 1 - 1e-6)
        return -np.mean(sample.off_won * np.log(p) + (1 - sample.off_won) * np.log(1 - p))

    result = minimize(nll, x0=[1.0, 1.0, 15.0, 1.0], method="Nelder-Mead",
                      options={"maxiter": 2000, "xatol": 1e-4, "fatol": 1e-7})
    return {k: round(float(v), 4) for k, v in zip(["a", "b", "sigma", "c"], result.x)}


def fit_ep(snaps):
    return HistGradientBoostingRegressor(max_iter=300, random_state=0).fit(
        snaps[EP_FEATURES], snaps.ep)


def validate(snaps, test_season):
    train = snaps[snaps.pff_GAMESEASON < test_season]
    test = snaps[snaps.pff_GAMESEASON == test_season]
    params = fit_wp(train)
    p = win_prob(params, test.lead, test.ep, test.game_secs, test.strength)
    base = np.full(len(test), train.off_won.mean())

    print(f"params {params}")
    print(f"train {len(train):,d} snaps, test {len(test):,d} snaps ({test_season})")
    print(f"  log loss  model {log_loss(test.off_won, p):.4f}   "
          f"baseline {log_loss(test.off_won, base):.4f}")
    print(f"  Brier     model {brier_score_loss(test.off_won, p):.4f}   "
          f"baseline {brier_score_loss(test.off_won, base):.4f}")

    bins = pd.cut(p, np.linspace(0, 1, 11), include_lowest=True)
    table = (pd.DataFrame({"pred": p, "won": test.off_won.values})
             .groupby(bins, observed=True)
             .agg(n=("won", "size"), predicted=("pred", "mean"), actual=("won", "mean")))
    print("  calibration by decile:")
    print(table.round(3).to_string())

    late = test[(test.game_secs <= 300) & (test.lead.abs() <= 8)]
    pl = win_prob(params, late.lead, late.ep, late.game_secs, late.strength)
    print(f"  last 5:00, one-score games: n={len(late):,d}  "
          f"log loss {log_loss(late.off_won, pl):.4f}  "
          f"mean predicted {pl.mean():.3f} vs actual {late.off_won.mean():.3f}")

    ep = fit_ep(train)
    resid = test.ep - ep.predict(test[EP_FEATURES])
    print(f"  EP lookup R^2 {1 - resid.var() / test.ep.var():.3f}, MAE {resid.abs().mean():.2f}")
    return table


def load():
    """(wp params, EP regressor) as saved by main()."""
    with open(PARAMS_PATH) as handle:
        params = json.load(handle)
    with open(EP_PATH, "rb") as handle:
        ep_model = pickle.load(handle)
    return params, ep_model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-season", type=int, default=2025)
    args = parser.parse_args()

    plays = load_plays()
    games = pd.read_csv(os.path.join(DATA, "games.csv"))
    snaps = build_snaps(plays, games)
    print(f"{len(snaps):,d} scrimmage snaps with a known winner")

    table = validate(snaps, args.test_season)
    table.to_csv(os.path.join(DATA, "wp_calibration.csv"))

    params = fit_wp(snaps)
    with open(PARAMS_PATH, "w") as handle:
        json.dump(params, handle, indent=2)
    with open(EP_PATH, "wb") as handle:
        pickle.dump(fit_ep(snaps), handle)
    print(f"refit on all seasons: {params}\nwrote {PARAMS_PATH}\nwrote {EP_PATH}")


if __name__ == "__main__":
    main()
