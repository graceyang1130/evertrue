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


def fit(drives):
    """Fit the outcome model. Drops drives missing a required field."""
    usable = drives.dropna(subset=REQUIRED_FIELDS)
    estimator = LogisticRegression(max_iter=2000)
    estimator.fit(design_matrix(usable), _outcomes(usable))
    return OppOffenseModel(estimator, n_train=len(usable))


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


def holdout_evaluation(drives, train_seasons, test_seasons):
    """Fit on one set of seasons, score on another. Out-of-sample or bust."""
    train = drives[drives.season.isin(train_seasons)]
    test = drives[drives.season.isin(test_seasons)].dropna(
        subset=REQUIRED_FIELDS)
    model = fit(train)
    predicted = model.predict_frame(test).p_score.to_numpy()
    return {
        "auc": float(roc_auc_score(test.scored.to_numpy(), predicted)),
        "n_train": int(model.n_train),
        "n_test": int(len(test)),
        "calibration": calibration_table(model, test, bins=5),
    }


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
                         "plausible": True, "tested": False})
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


HOLDOUT_TRAIN = [2019, 2021, 2022, 2023, 2024]
HOLDOUT_TEST = [2025, 2026]
CALIBRATION_TOLERANCE = 0.10
MIN_AUC = 0.60


def run_gates(drives):
    """All five spec gates. Returns (passed, lines) for printing."""
    model = fit(drives)
    lines = []
    passed = True

    calibration = calibration_table(model, drives)
    gap = float((calibration.predicted - calibration.observed).abs().mean())
    ok = gap < CALIBRATION_TOLERANCE
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 1. calibration      "
                 f"mean |predicted-observed| = {gap:.3f}")

    holdout = holdout_evaluation(drives, HOLDOUT_TRAIN, HOLDOUT_TEST)
    ok = holdout["auc"] > MIN_AUC
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 2. season holdout   "
                 f"AUC = {holdout['auc']:.3f} "
                 f"(train {holdout['n_train']}, test {holdout['n_test']})")

    monotone = monotonicity_check(model)
    ok = bool(monotone.passed.all())
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 3. monotonicity     " +
                 ", ".join(f"{r.feature}={r.direction:+.3f}"
                           for r in monotone.itertuples()))

    anchors = anchor_check(model, drives)
    tested = anchors[anchors.tested]
    ok = bool(tested.plausible.all()) and len(tested) >= 1
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 4. anchors          " +
                 ", ".join(f"{r.scenario} -> {r.mean_predicted:.2f} "
                           f"in [{r.floor:.2f},{r.ceiling:.2f}]"
                           for r in tested.itertuples()))

    thin = calibration[calibration.n < MIN_BIN_N]
    ok = thin.empty
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 5. sample floor     "
                 f"{len(thin)} calibration bins under n=30")

    return passed, lines, model


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="PFF play-by-play export")
    parser.add_argument("--quarter", type=int, default=4)
    parser.add_argument("--gates", action="store_true",
                        help="run the five validation gates and exit nonzero on failure")
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

    passed, lines, model = run_gates(drives)

    print("\nFITTED COEFFICIENTS")
    print(model.coefficients().round(4).to_string())

    print("\nVALIDATION GATES")
    for line in lines:
        print("  " + line)

    print("\nP(score) BY TIME LEFT AND FIELD POSITION (needs TD)")
    header = "".join(f"{y:>8d}" for y in [80, 65, 50, 35, 20])
    print(f"  {'clock':>7s}{header}   <- yards to goal")
    for seconds in [30, 60, 120, 180, 300]:
        row = f"  {seconds // 60}:{seconds % 60:02d}".rjust(9)
        for ytg in [80, 65, 50, 35, 20]:
            try:
                ep = median_ep_at(drives, ytg, seconds_left=seconds,
                                  min_n=MIN_BIN_N)
            except LookupError:
                row += f"{'--':>8}"
                continue
            p = model.predict(seconds, ep, 1)["p_score"]
            row += f"{p:>8.2f}"
        print(row)
    print(f"  -- = fewer than {MIN_BIN_N} comparable drives; no number printed")

    print("\nWHERE THE TOOL ACTUALLY OPERATES (reporting only, not a gate)")
    print(f"  {'region':>10s} {'n':>6s} {'AUC':>7s} {'calib':>7s}")
    usable = drives.dropna(subset=REQUIRED_FIELDS).copy()
    usable["predicted"] = model.predict_frame(usable).p_score.to_numpy()
    for limit, label in [(None, "all Q4"), (600, "<=10:00"),
                         (300, "<=5:00"), (120, "<=2:00")]:
        region = usable if limit is None else usable[usable.seconds_left <= limit]
        if region.scored.nunique() < 2:
            continue
        auc = roc_auc_score(region.scored.to_numpy(),
                            region.predicted.to_numpy())
        calib = abs(region.predicted.mean() - region.scored.mean())
        print(f"  {label:>10s} {len(region):6d} {auc:7.3f} {calib:7.3f}")

    if args.gates and not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
