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

import numpy as np
import pandas as pd

# A drive's own scoring plays. FUMBLE-TD and INTERCEPTION-TD are the DEFENSE
# scoring -- counting them here would inflate every estimate this module makes.
TD_EVENTS = {"TOUCHDOWN"}
FG_EVENTS = {"FIELD GOAL"}

# Trailing by more than a field goal means a field goal cannot tie it.
FG_MAX = 3

# Columns the loader reads. Kept explicit so a changed export fails loudly
# instead of silently producing NaNs.
DRIVE_COLUMNS = [
    "pff_DRIVEID", "pff_GAMESEASON", "pff_QUARTER", "pff_CLOCK",
    "pff_OFFTEAM", "pff_DEFTEAM", "pff_OFFSCORE", "pff_DEFSCORE",
    "pff_SCOREDIFFERENTIAL", "pff_FIELDPOSITION", "pff_EXPECTED_POINTS",
    "pff_OFF_TIMEOUTS_REMAINING", "pff_DRIVEENDEVENT",
]


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


from sklearn.linear_model import LogisticRegression

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
    """Model features, in FEATURE_NAMES order."""
    return np.column_stack([
        np.log(frame.seconds_left.clip(lower=MIN_SECONDS).to_numpy(float)),
        frame.ep_start.fillna(0.0).to_numpy(float),
        frame.needs_td.to_numpy(float),
    ])


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
    usable = drives.dropna(
        subset=["seconds_left", "ep_start", "end_event"])
    estimator = LogisticRegression(max_iter=2000)
    estimator.fit(design_matrix(usable), _outcomes(usable))
    return OppOffenseModel(estimator, n_train=len(usable))


from sklearn.metrics import roc_auc_score

# Monotonicity: more clock and better field position must never reduce
# scoring probability. A negative coefficient on either of these means the
# fit is chasing noise, and the spec treats that as a failure.
#
# Amendment 1: timeouts was dropped from the regression entirely (see
# DESIGN.md). It is not a monotone-up feature here because it is not a
# feature at all.
MONOTONE_UP = ["log_seconds", "ep_start"]

# An offense at its own 25 with a minute left, needing a touchdown, scores
# rarely. A model that disagrees is wrong whatever its AUC.
ANCHOR_CEILING = 0.25


def median_ep_at(drives, yards_to_goal_target, tolerance=5):
    """Typical expected points from a given distance, for building scenarios."""
    near = drives[
        (drives.yards_to_goal - yards_to_goal_target).abs() <= tolerance]
    return float(near.ep_start.median())


def calibration_table(model, drives, bins=10):
    """Predicted against observed scoring rate, by predicted-probability bin."""
    usable = drives.dropna(
        subset=["seconds_left", "ep_start", "end_event"]).copy()
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
        subset=["seconds_left", "ep_start", "end_event"])
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
    P(score) is read as the scoring outcomes' coefficients net of the
    no-score outcome's.
    """
    coefs = model.coefficients()
    scoring = coefs.loc[[OUTCOME_TD, OUTCOME_FG]].mean()
    none = coefs.loc[OUTCOME_NONE]
    rows = []
    for feature in MONOTONE_UP:
        effect = float(scoring[feature] - none[feature])
        rows.append({
            "feature": feature,
            "direction": round(effect, 4),
            "passed": effect >= 0,
        })
    return pd.DataFrame(rows)


def anchor_check(model, drives):
    """Scenarios whose answers are known well enough to falsify the model."""
    ep_own_25 = median_ep_at(drives, 75)
    ep_own_40 = median_ep_at(drives, 60)
    scenarios = [
        ("own 25, 1:00, needs TD", 60, ep_own_25, 1, ANCHOR_CEILING),
        ("own 25, 0:20, needs TD", 20, ep_own_25, 1, 0.10),
        ("own 40, 5:00, needs TD", 300, ep_own_40, 1, 0.80),
    ]
    rows = []
    for label, seconds, ep, needs_td, ceiling in scenarios:
        p = model.predict(seconds, ep, needs_td)["p_score"]
        rows.append({
            "scenario": label,
            "p_score": round(p, 3),
            "plausible": p < ceiling,
        })
    return pd.DataFrame(rows)
