"""Probability an opponent scores, given when and where they get the ball.

This is the piece every punt-versus-go decision rests on: what does handing the
ball back actually cost? It is estimated first and validated hardest because it
has the thinnest data in the system and the most leverage over the answer.

Drive outcomes are mutually exclusive -- a drive ends in a touchdown, a field
goal, or neither -- so they are fitted as one multinomial model rather than two
binary ones. That makes P(score) = P(TD) + P(FG) exact instead of approximate.

Touchdown and field goal are kept separate because they are not
interchangeable to the team on the field: an offense down 4 cannot settle for a
field goal, and plays accordingly. What they need is a model input, not a
detail.
"""

import argparse

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

# A drive's own scoring plays. FUMBLE-TD and INTERCEPTION-TD are the DEFENSE
# scoring -- counting them here would inflate every estimate this module makes.
TD_EVENTS = {"TOUCHDOWN"}
FG_EVENTS = {"FIELD GOAL"}

# Trailing by more than a field goal means a field goal cannot tie it.
FG_MAX = 3

# Fields a drive must have for the model to use it. Shared by fit() and every
# validation report so they can never drift apart -- a test asserts their row
# counts match, and that test is only meaningful if the subsets are identical.
REQUIRED_FIELDS = ["seconds_left", "ep_start", "score_diff", "end_event"]


def yards_to_goal(field_position):
    """PFF field position to yards from the goal line.

    PFF encodes own territory as a negative own-yard-line and opponent
    territory as positive yards-to-goal, so own 20 is -20 (80 to go) while the
    opponent 20 is +20 (20 to go).
    """
    if field_position > 0:
        return float(field_position)
    return 100.0 + float(field_position)


def _clock_to_seconds(value):
    try:
        minutes, seconds = str(value).split(":")
        return float(int(minutes) * 60 + int(seconds))
    except (ValueError, AttributeError):
        return np.nan


def load_drives(path, quarter=4):
    """One row per drive: the state it started in and how it ended."""
    frame = pd.read_csv(path, low_memory=False)
    frame = frame[frame.pff_QUARTER == quarter]
    frame = frame[frame.pff_DRIVEID.notna()]

    frame = frame.copy()
    frame["seconds"] = frame.pff_CLOCK.map(_clock_to_seconds)

    # The drive's first play is the one with the most clock left.
    frame = frame.sort_values("seconds", ascending=False)
    first = frame.drop_duplicates(subset="pff_DRIVEID", keep="first")

    drives = pd.DataFrame({
        "drive_id": first.pff_DRIVEID,
        "season": first.pff_GAMESEASON,
        "offense": first.pff_OFFTEAM,
        "defense": first.pff_DEFTEAM,
        "seconds_left": first.seconds,
        "yards_to_goal": first.pff_FIELDPOSITION.map(yards_to_goal),
        "ep_start": pd.to_numeric(first.pff_EXPECTED_POINTS, errors="coerce"),
        "timeouts": pd.to_numeric(
            first.pff_OFF_TIMEOUTS_REMAINING, errors="coerce"),
        "score_diff": pd.to_numeric(
            first.pff_SCOREDIFFERENTIAL, errors="coerce"),
        "end_event": first.pff_DRIVEENDEVENT,
    })

    drives["deficit"] = (-drives.score_diff).clip(lower=0)
    drives["needs_td"] = (drives.deficit > FG_MAX).astype(int)
    drives["scored_td"] = drives.end_event.isin(TD_EVENTS).astype(int)
    drives["scored_fg"] = drives.end_event.isin(FG_EVENTS).astype(int)
    drives["scored"] = (drives.scored_td | drives.scored_fg).astype(int)

    drives = drives.dropna(subset=["seconds_left"])

    return drives.reset_index(drop=True)


# The tool is only ever asked about an opponent that trails or is tied -- if
# Brown holds the lead, a leading opponent cannot occur. Beyond this margin the
# game is effectively decided and the behaviour stops being representative.
MAX_DEFICIT = 16


def decision_population(drives, max_deficit=MAX_DEFICIT):
    """The drives the tool can actually be asked about.

    Trailing or tied, within `max_deficit` points. An earlier version fitted on
    all fourth-quarter drives, 894 of 1,978 of which were leading offenses
    killing clock -- the opposite of the behaviour in question. That understated
    a trailing opponent's scoring probability by up to 15 points while aggregate
    calibration read a healthy 0.028, because the errors offset. See DESIGN.md
    Amendment 2.
    """
    return drives[(drives.score_diff <= 0)
                  & (drives.score_diff >= -max_deficit)].copy()


def wilson_interval(successes, n, z=1.96):
    """Wilson score interval for a binomial rate. (nan, nan) when n is 0.

    Preferred over the normal approximation because the anchor neighbourhoods
    are small enough (n=60, n=81) that the naive interval misbehaves.
    """
    if n == 0:
        return (float("nan"), float("nan"))
    p = successes / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# Feature order is part of the interface -- design_matrix, coefficients() and
# every validation report rely on it.
FEATURE_NAMES = ["log_seconds", "ep_start", "needs_td"]

# Outcome labels for the multinomial fit.
OUTCOME_TD = "TD"
OUTCOME_FG = "FG"
OUTCOME_NONE = "NONE"

# Clock enters as a log because the first 30 seconds of a possession matter far
# more than the thirtieth 30 seconds. Floored so log stays finite at 0:00.
MIN_SECONDS = 5.0

# A quarter is 900 seconds; nothing beyond that is a fourth-quarter question.
MAX_PREDICT_SECONDS = 900.0


def design_matrix(frame):
    """Model features, in FEATURE_NAMES order.

    Requires complete inputs -- callers must filter on REQUIRED_FIELDS first.
    Raises rather than imputing a missing value, so a bad input fails here
    with a clear message instead of surfacing as a cryptic sklearn error.
    """
    matrix = np.column_stack([
        np.log(frame.seconds_left.clip(lower=MIN_SECONDS).to_numpy(float)),
        frame.ep_start.to_numpy(float),
        frame.needs_td.to_numpy(float),
    ])
    if not np.isfinite(matrix).all():
        raise ValueError(
            "design_matrix received non-finite features; a caller passed drives "
            "that were not filtered on REQUIRED_FIELDS")
    return matrix


def _outcomes(frame):
    return np.where(
        frame.scored_td == 1, OUTCOME_TD,
        np.where(frame.scored_fg == 1, OUTCOME_FG, OUTCOME_NONE),
    )


class OppOffenseModel:
    """Fitted multinomial model over drive outcomes."""

    def __init__(self, estimator, n_train):
        self._estimator = estimator
        self.n_train = n_train

    def predict(self, seconds_left, ep_start, needs_td):
        if not MIN_SECONDS <= seconds_left <= MAX_PREDICT_SECONDS:
            raise ValueError(
                f"seconds_left={seconds_left} is outside [{MIN_SECONDS}, "
                f"{MAX_PREDICT_SECONDS}]; the clock is floored at "
                f"{MIN_SECONDS}s internally, so a smaller value would silently "
                f"return the {MIN_SECONDS}s answer")
        frame = pd.DataFrame([{
            "seconds_left": float(seconds_left),
            "ep_start": float(ep_start),
            "needs_td": float(needs_td),
        }])
        return self.predict_frame(frame).iloc[0].to_dict()

    def predict_frame(self, frame):
        """Vectorised prediction. Returns a frame of p_td, p_fg, p_score."""
        probabilities = self._estimator.predict_proba(design_matrix(frame))
        classes = list(self._estimator.classes_)
        p_td = probabilities[:, classes.index(OUTCOME_TD)]
        p_fg = probabilities[:, classes.index(OUTCOME_FG)]
        return pd.DataFrame({
            "p_td": p_td,
            "p_fg": p_fg,
            "p_score": p_td + p_fg,
        }, index=frame.index)

    def coefficients(self):
        return pd.DataFrame(
            self._estimator.coef_,
            index=list(self._estimator.classes_),
            columns=FEATURE_NAMES,
        )


# scikit-learn regularises by default. C=1.0 is retained rather than chosen -- it
# is what every gate in this module was measured against -- but the features are
# unstandardised (log_seconds ~1.6-6.8, ep_start ~-3-6, needs_td 0/1), so the
# penalty does not fall evenly across them. Any future refit on more data should
# revisit this deliberately rather than inherit it.
REGULARISATION_C = 1.0


def fit(drives, allow_any_population=False):
    """Fit the outcome model. Drops drives missing a required field.

    Refuses a frame containing leading offenses or deficits beyond MAX_DEFICIT,
    because fitting on those is exactly the defect this model was rebuilt to
    remove -- see DESIGN.md Amendment 2. Pass allow_any_population=True only to
    deliberately reconstruct the broken model, which two tests do in order to
    prove the gates detect it.
    """
    if not allow_any_population:
        outside = drives[(drives.score_diff > 0)
                         | (drives.score_diff < -MAX_DEFICIT)]
        if len(outside):
            raise ValueError(
                f"{len(outside)} of {len(drives)} drives are outside the "
                f"decision population (leading, or trailing by more than "
                f"{MAX_DEFICIT}). Call decision_population() first, or pass "
                f"allow_any_population=True if you intend the broken model.")
    usable = drives.dropna(subset=REQUIRED_FIELDS)
    estimator = LogisticRegression(max_iter=2000, C=REGULARISATION_C)
    estimator.fit(design_matrix(usable), _outcomes(usable))
    return OppOffenseModel(estimator, n_train=len(usable))


# A season needs at least this many drives to be worth holding out as a fold.
MIN_FOLD_N = 20


def loso_folds(drives):
    """Per-season fold status, so a skipped fold leaves a trail.

    A fold is skipped when the held-out season is too small to be worth scoring,
    or when the remaining training data lacks one of the three outcome classes a
    multinomial fit needs. Either silently shrinks the coverage every
    out-of-sample gate rests on, so the reason is recorded rather than left to be
    inferred from a smaller row count.
    """
    usable = drives.dropna(subset=REQUIRED_FIELDS)
    rows = []
    for season in sorted(usable.season.unique()):
        test = usable[usable.season == season]
        train = usable[usable.season != season]
        if len(test) < MIN_FOLD_N:
            reason = (f"held-out fold n={len(test)} below "
                      f"MIN_FOLD_N={MIN_FOLD_N}")
        elif train.empty:
            reason = "no training drives outside this season"
        elif len(set(_outcomes(train))) < 3:
            reason = "training set missing an outcome class"
        else:
            reason = ""
        rows.append({"season": int(season), "n": int(len(test)),
                     "folded": reason == "", "skipped_because": reason})
    return pd.DataFrame(rows)


def loso_predictions(drives):
    """Out-of-fold scoring probabilities, leaving each season out in turn.

    Every out-of-sample gate shares these folds. A single train/test season
    split does not survive this population: the <=5:00 slice of a 2025-26
    holdout is n=56, where AUC reads 0.596 -- against 0.674 for the same model
    scored leave-one-season-out. At n=720 a single holdout measures which
    seasons happened to land in the test fold. See DESIGN.md Amendment 2.
    """
    usable = drives.dropna(subset=REQUIRED_FIELDS).copy()
    usable["predicted"] = np.nan

    folds = loso_folds(drives)
    for season in folds.loc[folds.folded, "season"]:
        test = usable[usable.season == season]
        train = usable[usable.season != season]
        model = fit(train)
        usable.loc[test.index, "predicted"] = (
            model.predict_frame(test).p_score.to_numpy())

    return usable.dropna(subset=["predicted"])


# Clock regions to report. Gate 2 is scored on the <=5:00 slice: 42.8% of
# fourth-quarter drives start outside the card's range entirely, and including
# them flatters discrimination (0.705 overall against 0.669 inside 5:00 on the
# model this replaces).
REGIONS = [(None, "all"), (600, "<=10:00"), (300, "<=5:00"), (120, "<=2:00")]
GATE_REGION_SECONDS = 300

# A bias localised in the clock passes every other gate: AUC is rank-based and so
# blind to monotone miscalibration, and pooling clocks lets an early-game
# overstatement cancel a late-game understatement exactly. The shipped model's
# signed bias runs -0.027 inside 5:00 and +0.033 inside 2:00, cancelling to 0.000
# overall. This is the original population defect's mechanism one dimension over.
REGION_CALIBRATION_MAX = 0.06
GATE_REGIONS_SECONDS = [300, 120]

# What the opponent needs. GATE_BANDS are the sub-populations gate 6 is measured
# within; DIAGNOSTIC_BANDS are printed for a human to read but never gated.
#
# Only two bands are stable enough to gate on. Measured leave-one-season-out on
# the corrected population: two bands give median 0.072 / worst 0.116; three give
# 0.103 / 0.198; four give 0.104 / 0.234; five give 0.139 / 0.234. Three and above
# fail the thresholds this document commits to, so gating on them would mean
# shipping a gate that fails on arrival.
#
# The two-band split is deliberately the same cut as `needs_td`.
GATE_BANDS = [("needs 3 or fewer", 0, 3), ("needs a TD", 4, MAX_DEFICIT)]

# Finer structure, printed as a diagnostic. Gating on these is not an option
# (see above) but a human reading the report should still see where the error
# concentrates -- at two bands a problem confined to tied games alone would be
# diluted below the threshold and missed.
DIAGNOSTIC_BANDS = [("tied", 0, 0), ("down 1-3", 1, 3),
                    ("down 4-7", 4, 7), ("down 8-16", 8, MAX_DEFICIT)]

# A band cell thinner than this in a single season is noise, not evidence.
MIN_BAND_CELL_N = 5

CONDITIONAL_MEDIAN_MAX = 0.10
CONDITIONAL_WORST_MAX = 0.20

# Gate 6 needs this many seasons with at least one usable band cell before its
# median means anything. Fewer than this and the gate is measuring noise.
MIN_SCORED_SEASONS = 5


def regional_performance(out_of_fold):
    """Out-of-sample discrimination and calibration by clock region."""
    rows = []
    for limit, label in REGIONS:
        region = (out_of_fold if limit is None
                  else out_of_fold[out_of_fold.seconds_left <= limit])
        if len(region) < MIN_BIN_N or region.scored.nunique() < 2:
            continue
        rows.append({
            "region": label,
            "seconds_limit": limit,
            "n": int(len(region)),
            "auc": round(float(roc_auc_score(
                region.scored.to_numpy(), region.predicted.to_numpy())), 3),
            "calibration": round(float(abs(
                region.predicted.mean() - region.scored.mean())), 3),
        })
    return pd.DataFrame(rows)


def score_band(drives, bands=GATE_BANDS):
    """Label each drive by what the opponent needs."""
    deficit = -drives.score_diff
    labels = pd.Series("other", index=drives.index, dtype=object)
    for name, low, high in bands:
        labels[(deficit >= low) & (deficit <= high)] = name
    return labels


def conditional_calibration(out_of_fold, bands=GATE_BANDS):
    """Worst per-band calibration bias, per held-out season.

    This is the gate the original five could not provide. The model this
    replaces read 0.028 on aggregate decile calibration while understating a
    trailing opponent's scoring probability by 15 points, because the errors
    offset inside the deciles. **Aggregate calibration is not conditional
    calibration.**

    Measured out of sample deliberately. In-sample conditional calibration is
    near-unfailable (0.0298 on a bucketed fit) because the model fits band means
    by construction -- the same flaw that made the original bin-count gate
    incapable of failing.

    LIMITATION: with GATE_BANDS the model this replaces reads a worst band bias
    of 0.107 against a 0.10 threshold -- detected, but by a 7% margin, and only
    because the affected band is a third of the population. A bias confined to a
    narrower slice would be diluted below the threshold. Call this with
    DIAGNOSTIC_BANDS to see the finer structure; do not gate on that result.

    A season with no usable cell reports NaN, never 0.0. Reporting zero would
    enter the gate as a perfectly calibrated season and pull the median down --
    a season with no evidence is not a season that passed. `cells_skipped`
    records what was dropped so the loss is visible rather than inferred.
    """
    frame = out_of_fold.assign(band=score_band(out_of_fold, bands))
    rows = []
    for season, block in frame.groupby("season"):
        worst = 0.0
        used = 0
        skipped = 0
        for _, cell in block.groupby("band", observed=True):
            if len(cell) < MIN_BAND_CELL_N:
                skipped += 1
                continue
            used += 1
            worst = max(worst, abs(cell.predicted.mean() - cell.scored.mean()))
        rows.append({"season": int(season), "n": int(len(block)),
                     "cells_used": used, "cells_skipped": skipped,
                     "worst_band_bias": round(worst, 3) if used else np.nan})
    return pd.DataFrame(rows)


# Monotonicity: more clock and better field position must never reduce
# scoring probability. A negative coefficient on either of these means the
# fit is chasing noise, and the spec treats that as a failure.
#
# Amendment 1: timeouts was dropped from the regression entirely (see
# DESIGN.md). It is not a monotone-up feature here because it is not a
# feature at all.
MONOTONE_UP = ["log_seconds", "ep_start"]

# A calibration bin thinner than this is too thin to trust -- the gate
# refuses it rather than let a handful of drives pass for a validated rate.
MIN_BIN_N = 30

# Where trailing teams actually start fourth-quarter drives: the median is 75
# yards out (own 25) and the distribution concentrates between 65 and 85, since
# a team getting the ball back has just received a punt or a kickoff. An earlier
# card used [80, 65, 50, 35, 20], whose two nearest columns were backed by 0-1
# drives -- it asked about field positions that do not occur. [90, 80, 75, 70,
# 60] still printed "--" in its 90 and 60 columns at every clock: support is
# 14/25 either way, so narrowing to [85, 80, 75, 70, 65] buys no extra
# supported cells -- it spreads the same 14 across five usable columns instead
# of three, so a sideline card stops carrying two permanently blank ones.
CARD_YARDS_TO_GOAL = [85, 80, 75, 70, 65]
CARD_CLOCKS = [30, 60, 120, 180, 300]

# Below this share of printable cells the card is mostly blanks and the model is
# being asked about situations its population does not contain.
MIN_SUPPORTED_CELL_FRACTION = 0.50


def median_ep_at(drives, yards_to_goal_target, tolerance=5,
                 seconds_left=None, seconds_tolerance=120, min_n=1):
    """Typical expected points from a given distance, for building scenarios.

    `pff_EXPECTED_POINTS` embeds time remaining as well as field position, so
    pass `seconds_left` whenever the caller is asking about a specific clock --
    otherwise the all-clock median is combined with a specific clock and the
    time effect is counted twice.

    Raises LookupError when fewer than `min_n` drives support the cell, rather
    than returning a number no data stands behind.
    """
    near = drives[
        (drives.yards_to_goal - yards_to_goal_target).abs() <= tolerance]
    if seconds_left is not None:
        near = near[(near.seconds_left - seconds_left).abs() <= seconds_tolerance]
    if len(near) < min_n:
        raise LookupError(
            f"only {len(near)} drives within {tolerance} yards of "
            f"{yards_to_goal_target} (clock {seconds_left}); need {min_n}")
    return float(near.ep_start.median())


def card_cells(model, drives):
    """One row per printed card cell: its support, and its probability.

    A cell is printed only when at least MIN_BIN_N comparable drives stand
    behind it. DESIGN.md has always required refusing to print a cell the data
    cannot support; this is where that is enforced.
    """
    rows = []
    for seconds in CARD_CLOCKS:
        for ytg in CARD_YARDS_TO_GOAL:
            near = drives[
                (drives.needs_td == 1)
                & ((drives.yards_to_goal - ytg).abs() <= 5)
                & ((drives.seconds_left - seconds).abs() <= 120)]
            if len(near) < MIN_BIN_N:
                rows.append({"seconds": seconds, "yards_to_goal": ytg,
                             "n": int(len(near)), "supported": False,
                             "p_score": np.nan})
                continue
            ep = median_ep_at(drives[drives.needs_td == 1], ytg,
                              seconds_left=seconds, min_n=MIN_BIN_N)
            rows.append({"seconds": seconds, "yards_to_goal": ytg,
                         "n": int(len(near)), "supported": True,
                         "p_score": round(
                             model.predict(seconds, ep, 1)["p_score"], 3)})
    return pd.DataFrame(rows)


def calibration_table(model, drives, bins=10):
    """Predicted against observed scoring rate, by predicted-probability bin."""
    usable = drives.dropna(subset=REQUIRED_FIELDS).copy()
    usable["predicted"] = model.predict_frame(usable).p_score.to_numpy()
    usable["bin"] = pd.qcut(
        usable.predicted, bins, labels=False, duplicates="drop")
    grouped = usable.groupby("bin", observed=True).agg(
        n=("scored", "size"),
        predicted=("predicted", "mean"),
        observed=("scored", "mean"),
    ).reset_index()
    return grouped[["bin", "n", "predicted", "observed"]]


def monotonicity_check(model):
    """Every must-rise feature must have a non-negative scoring coefficient.

    The multinomial fit gives one coefficient per outcome, so the effect on
    P(score) is read as each scoring outcome's coefficient net of the
    no-score outcome's -- an exact log-odds derivative. Both the TD effect
    and the FG effect must be individually non-negative for P(score) to be
    provably non-decreasing in the feature; averaging them would let a large
    positive TD effect mask a genuinely negative FG effect.
    """
    coefs = model.coefficients()
    td = coefs.loc[OUTCOME_TD]
    fg = coefs.loc[OUTCOME_FG]
    none = coefs.loc[OUTCOME_NONE]
    rows = []
    for feature in MONOTONE_UP:
        td_effect = float(td[feature] - none[feature])
        fg_effect = float(fg[feature] - none[feature])
        rows.append({
            "feature": feature,
            "direction": round(min(td_effect, fg_effect), 4),
            "td_effect": round(td_effect, 4),
            "fg_effect": round(fg_effect, 4),
            "passed": td_effect >= 0 and fg_effect >= 0,
        })
    return pd.DataFrame(rows)


# Anchor neighbourhoods: (label, yards to goal, min seconds, max seconds).
# Bounds are DERIVED from each neighbourhood's own observed rate rather than
# hardcoded, so they cannot go stale when the population or seasons change.
# `own 25, 0:20` was retired: it is backed by 12 drives, whose Wilson interval
# [0.015, 0.354] could never discriminate between a good model and a bad one.
ANCHOR_SCENARIOS = [
    ("own 25, under 3:00, needs TD", 75, 0, 180),
    ("own 25, 3:00-7:00, needs TD", 75, 180, 420),
    ("own 40, over 4:00, needs TD", 60, 240, 900),
    ("own 10-20, any clock, needs TD", 88, 0, 900),
]
ANCHOR_YARD_TOLERANCE = 10

# Fewer than this many surviving anchors and the gate is nearly meaningless --
# len(tested) >= 1 let three of four anchors drop out silently.
MIN_TESTED_ANCHORS = 3


def anchor_check(model, drives):
    """Two-sided sanity checks on specific, recognisable situations.

    Bounds are Wilson 95% intervals on the observed rate in each neighbourhood,
    derived at fit time. The model's MEAN PREDICTION OVER THE NEIGHBOURHOOD'S
    ACTUAL DRIVES is compared against them -- not a point prediction at an
    invented centre. Predicting at a nominal clock the neighbourhood does not
    average to was tried and rejected: widening a neighbourhood to reach the
    support floor drags its centre away from the scenario (the "own 25, ~1:00"
    band has a median clock of 1:49), so the model gets asked about a situation
    the observed rate does not describe.

    The previous version was one-sided -- every anchor an upper bound -- so a
    model UNDERSTATING opponent scoring passed more easily, which is the
    dangerous direction for a punt decision.

    SCOPE, and this is a real limitation: these catch gross errors, not subtle
    ones. A Wilson interval at n=60 spans about 0.20, and the model fitted on
    the wrong population -- 15 points biased against trailing opponents --
    passes every anchor defined here. Gate 6 (conditional calibration) is the
    primary defence against population-level bias. An anchor pass is not
    evidence of calibration.
    """
    rows = []
    for label, ytg, min_seconds, max_seconds in ANCHOR_SCENARIOS:
        near = drives[
            ((drives.yards_to_goal - ytg).abs() <= ANCHOR_YARD_TOLERANCE)
            & drives.seconds_left.between(min_seconds, max_seconds)
            & (drives.needs_td == 1)]

        if len(near) < MIN_BIN_N:
            # Not a test. Recorded so its absence is visible rather than silent.
            rows.append({"scenario": label, "n": len(near),
                         "observed": np.nan, "floor": np.nan,
                         "ceiling": np.nan, "mean_predicted": np.nan,
                         "plausible": np.nan, "tested": False})
            continue

        floor, ceiling = wilson_interval(int(near.scored.sum()), len(near))
        mean_predicted = float(model.predict_frame(near).p_score.mean())
        rows.append({"scenario": label, "n": len(near),
                     "observed": round(float(near.scored.mean()), 3),
                     "floor": round(floor, 3), "ceiling": round(ceiling, 3),
                     "mean_predicted": round(mean_predicted, 3),
                     "plausible": bool(floor <= mean_predicted <= ceiling),
                     "tested": True})
    return pd.DataFrame(rows)


CALIBRATION_TOLERANCE = 0.10
MIN_AUC = 0.60


def run_gates(drives):
    """All six spec gates. Returns (passed, lines) for printing."""
    model = fit(drives)
    lines = []
    passed = True

    calibration = calibration_table(model, drives)
    gap = float((calibration.predicted - calibration.observed).abs().mean())
    ok = gap < CALIBRATION_TOLERANCE
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 1. calibration      "
                 f"mean |predicted-observed| = {gap:.3f}")

    out_of_fold = loso_predictions(drives)
    regional = regional_performance(out_of_fold)
    gated = regional[regional.seconds_limit.isin(GATE_REGIONS_SECONDS)]
    ok = len(gated) == len(GATE_REGIONS_SECONDS)
    detail = []
    for row in gated.itertuples():
        auc_ok = row.auc > MIN_AUC
        calib_ok = row.calibration <= REGION_CALIBRATION_MAX
        ok = ok and auc_ok and calib_ok
        detail.append(f"{row.region} AUC {row.auc:.3f} calib {row.calibration:.3f}")
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 2. discrimination   "
                 + ", ".join(detail)
                 + f" (AUC>{MIN_AUC}, calib<={REGION_CALIBRATION_MAX})")

    monotone = monotonicity_check(model)
    ok = bool(monotone.passed.all())
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 3. monotonicity     " +
                 ", ".join(f"{r.feature}={r.direction:+.3f}"
                           for r in monotone.itertuples()))

    anchors = anchor_check(model, drives)
    tested = anchors[anchors.tested]
    ok = bool(tested.plausible.all()) and len(tested) >= MIN_TESTED_ANCHORS
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 4. anchors          " +
                 ", ".join(f"{r.scenario} -> {r.mean_predicted:.2f} "
                           f"in [{r.floor:.2f},{r.ceiling:.2f}]"
                           for r in tested.itertuples()))

    cells = card_cells(model, drives)
    fraction = float(cells.supported.mean())
    ok = fraction >= MIN_SUPPORTED_CELL_FRACTION
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 5. card support     "
                 f"{cells.supported.sum()}/{len(cells)} cells backed by "
                 f">={MIN_BIN_N} drives ({fraction:.0%})")

    conditional = conditional_calibration(out_of_fold)
    scored = conditional.dropna(subset=["worst_band_bias"])
    median_bias = float(scored.worst_band_bias.median()) if len(scored) else float("nan")
    worst_bias = float(scored.worst_band_bias.max()) if len(scored) else float("nan")
    ok = (len(scored) >= MIN_SCORED_SEASONS
          and median_bias < CONDITIONAL_MEDIAN_MAX
          and worst_bias < CONDITIONAL_WORST_MAX)
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 6. cond. calibration "
                 f"median {median_bias:.3f} (<{CONDITIONAL_MEDIAN_MAX}), "
                 f"worst {worst_bias:.3f} (<{CONDITIONAL_WORST_MAX}), "
                 f"{len(scored)}/{len(conditional)} seasons scored, "
                 f"{int(conditional.cells_skipped.sum())} cells skipped")

    return passed, lines, model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="PFF play-by-play export")
    parser.add_argument("--quarter", type=int, default=4)
    parser.add_argument("--gates", action="store_true",
                        help="run the six validation gates and exit nonzero on failure")
    args = parser.parse_args()

    all_drives = load_drives(args.csv, quarter=args.quarter)
    drives = decision_population(all_drives)
    print(f"{len(all_drives)} Q{args.quarter} drives loaded; "
          f"{len(drives)} in the decision population "
          f"(trailing or tied, within {MAX_DEFICIT})")
    print(f"{len(drives)} Q{args.quarter} drives, "
          f"seasons {int(drives.season.min())}-{int(drives.season.max())}")
    print(f"score rate: {drives.scored.mean():.3f} overall, "
          f"{drives[drives.seconds_left <= 300].scored.mean():.3f} inside 5:00")

    folds = loso_folds(drives)
    print("\nLEAVE-ONE-SEASON-OUT FOLDS")
    print(folds.to_string(index=False))

    passed, lines, model = run_gates(drives)

    print("\nFITTED COEFFICIENTS")
    print(model.coefficients().round(4).to_string())

    print("\nVALIDATION GATES")
    for line in lines:
        print("  " + line)

    cells = card_cells(model, drives)
    print("\nP(score) BY TIME LEFT AND FIELD POSITION (opponent needs a TD)")
    header = "".join(f"{y:>8d}" for y in CARD_YARDS_TO_GOAL)
    print(f"  {'clock':>7s}{header}   <- yards to goal")
    for seconds in CARD_CLOCKS:
        row = f"  {seconds // 60}:{seconds % 60:02d}".rjust(9)
        for ytg in CARD_YARDS_TO_GOAL:
            cell = cells[(cells.seconds == seconds)
                         & (cells.yards_to_goal == ytg)].iloc[0]
            row += f"{'--':>8}" if not cell.supported else f"{cell.p_score:>8.2f}"
        print(row)
    print(f"  -- = fewer than {MIN_BIN_N} comparable drives; no number printed")

    out_of_fold = loso_predictions(drives)

    print("\nOUT-OF-SAMPLE PERFORMANCE BY REGION (leave-one-season-out)")
    print(regional_performance(out_of_fold).to_string(index=False))

    print("\nCALIBRATION BY SCORE BAND, finer than the gate (diagnostic only)")
    print(conditional_calibration(out_of_fold, DIAGNOSTIC_BANDS)
          .to_string(index=False))
    scored = conditional_calibration(out_of_fold).dropna(
        subset=["worst_band_bias"])
    print(f"  uncertainty: per-score-band calibration bias runs "
          f"{scored.worst_band_bias.median():.2f} typical / "
          f"{scored.worst_band_bias.max():.2f} worst season across "
          f"{len(scored)} scored seasons. Read these as bands, not point "
          f"estimates.")

    if args.gates and not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
