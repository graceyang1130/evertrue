# Opponent Scoring Model (`opp_offense.py`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estimate the probability an opponent scores (touchdown or field goal) given when and where they get the ball and how many timeouts they hold, and prove it holds up before anything is built on top of it.

**Architecture:** Drive-level aggregation from PFF play rows, then a multinomial logistic regression over three mutually exclusive drive outcomes (touchdown / field goal / no score). Multinomial rather than two separate binary fits so `P(score) = P(TD) + P(FG)` is exact by construction rather than approximate. Five validation gates ship with the module and gate every downstream build.

**Tech Stack:** Python 3, pandas 2.2.3, numpy 2.3.4, scikit-learn 1.7.2, pytest 9.0.3

**Spec:** `end_of_game/DESIGN.md`

## Global Constraints

- `statsmodels` is **not installed**. Use `sklearn.linear_model.LogisticRegression`. Do not add dependencies.
- Plan and spec live in `end_of_game/`, not `docs/`, per the user's instruction that everything for this work goes in that folder.
- Data files: `end_of_game/ivy_19t26.csv` (52,971 plays, 308 games, 42 teams), `end_of_game/brown_19t26.csv` (11,220 plays, 61 games). Both 214-column PFF exports, seasons 2019 and 2021–2026 (**no 2020** — the Ivy League cancelled it).
- `pff_FIELDPOSITION` encoding: negative = own yard line, positive = yards to opponent goal. Convert with `ytg = fp if fp > 0 else 100 + fp`. Verified against `pff_YARDS_TO_GOAL_LINE`.
- `pff_SCOREDIFFERENTIAL` = `pff_OFFSCORE - pff_DEFSCORE`, offense perspective, exact in 100% of rows.
- `pff_DRIVEID` is a string and is null on 16.6% of rows (special teams and untagged plays). Drop nulls before grouping.
- `pff_DRIVEENDEVENT` values: `DOWNS`, `END OF GAME`, `END OF HALF`, `FIELD GOAL`, `FUMBLE`, `FUMBLE-TD`, `INTERCEPTION`, `INTERCEPTION-TD`, `MISSED FG`, `PUNT`, `SAFETY`, `TOUCHDOWN`.
- **`FUMBLE-TD` and `INTERCEPTION-TD` are the DEFENSE scoring, not the drive's offense.** They must count as no-score for the offense. Treating them as scores silently inflates every opponent scoring estimate.
- Clock strings are `MM:SS`. A drive's `seconds_left` is the clock on its **first** play, which is the **maximum** clock within the drive.
- All five validation gates in `DESIGN.md` must pass before Plans 02–04 begin. A monotonicity sign flip is a failure, not a curiosity.

---

### Task 1: Drive-level data loader

**Files:**
- Create: `end_of_game/opp_offense.py`
- Create: `end_of_game/tests/test_opp_offense.py`

**Interfaces:**
- Consumes: nothing (first task)
- Produces:
  - `yards_to_goal(field_position: float) -> float`
  - `load_drives(path: str, quarter: int = 4) -> pd.DataFrame` with columns
    `drive_id, season, offense, defense, seconds_left, yards_to_goal, ep_start,
    timeouts, score_diff, deficit, needs_td, end_event, scored_td, scored_fg, scored`

- [ ] **Step 1: Write the failing test**

Create `end_of_game/tests/test_opp_offense.py`:

```python
import pandas as pd
import pytest

from opp_offense import load_drives, yards_to_goal


@pytest.mark.parametrize("field_position,expected", [
    (-20.0, 80.0),   # own 20
    (-49.0, 51.0),   # own 49
    (-1.0, 99.0),    # own 1, backed up
    (20.0, 20.0),    # opponent 20, red zone edge
    (50.0, 50.0),    # midfield
    (1.0, 1.0),      # goal line
])
def test_yards_to_goal_matches_pff_encoding(field_position, expected):
    assert yards_to_goal(field_position) == expected


def _play(drive_id, clock, event, offense="AAAA", off_score=0, def_score=0,
          field_position=-25.0, ep=0.5, timeouts=3, quarter=4, season=2023):
    """One synthetic PFF play row, only the columns the loader reads."""
    return {
        "pff_DRIVEID": drive_id,
        "pff_GAMESEASON": season,
        "pff_QUARTER": quarter,
        "pff_CLOCK": clock,
        "pff_OFFTEAM": offense,
        "pff_DEFTEAM": "BBBB",
        "pff_OFFSCORE": off_score,
        "pff_DEFSCORE": def_score,
        "pff_SCOREDIFFERENTIAL": off_score - def_score,
        "pff_FIELDPOSITION": field_position,
        "pff_DRIVESTARTFIELDPOSITION": field_position,
        "pff_EXPECTED_POINTS": ep,
        "pff_OFF_TIMEOUTS_REMAINING": timeouts,
        "pff_DRIVEENDEVENT": event,
    }


@pytest.fixture
def synthetic_csv(tmp_path):
    rows = [
        # drive d1: touchdown, starts at 4:00
        _play("d1", "04:00", "TOUCHDOWN"),
        _play("d1", "03:20", "TOUCHDOWN"),
        # drive d2: punt, starts at 2:30
        _play("d2", "02:30", "PUNT"),
        # drive d3: defense returned a fumble for a score -- NOT an offensive score
        _play("d3", "01:40", "FUMBLE-TD"),
        # drive d4: field goal, offense trailing by 6 so it needs a TD
        _play("d4", "01:00", "FIELD GOAL", off_score=14, def_score=20),
        # drive d5: third quarter, must be excluded by the quarter filter
        _play("d5", "05:00", "TOUCHDOWN", quarter=3),
        # a null drive id, must be dropped
        {**_play("x", "00:30", "PUNT"), "pff_DRIVEID": None},
    ]
    path = tmp_path / "synthetic.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return str(path)


def test_load_drives_one_row_per_drive(synthetic_csv):
    drives = load_drives(synthetic_csv, quarter=4)
    assert len(drives) == 4
    assert set(drives.drive_id) == {"d1", "d2", "d3", "d4"}


def test_load_drives_seconds_left_is_first_play_clock(synthetic_csv):
    drives = load_drives(synthetic_csv, quarter=4).set_index("drive_id")
    assert drives.loc["d1", "seconds_left"] == 240.0
    assert drives.loc["d2", "seconds_left"] == 150.0


def test_load_drives_defensive_touchdown_is_not_an_offensive_score(synthetic_csv):
    drives = load_drives(synthetic_csv, quarter=4).set_index("drive_id")
    assert drives.loc["d3", "scored"] == 0
    assert drives.loc["d3", "scored_td"] == 0


def test_load_drives_scoring_flags(synthetic_csv):
    drives = load_drives(synthetic_csv, quarter=4).set_index("drive_id")
    assert drives.loc["d1", "scored_td"] == 1
    assert drives.loc["d1", "scored"] == 1
    assert drives.loc["d4", "scored_fg"] == 1
    assert drives.loc["d4", "scored"] == 1
    assert drives.loc["d2", "scored"] == 0


def test_load_drives_needs_td_when_trailing_by_more_than_three(synthetic_csv):
    drives = load_drives(synthetic_csv, quarter=4).set_index("drive_id")
    assert drives.loc["d4", "deficit"] == 6
    assert drives.loc["d4", "needs_td"] == 1
    assert drives.loc["d1", "needs_td"] == 0


def test_load_drives_yards_to_goal_converted(synthetic_csv):
    drives = load_drives(synthetic_csv, quarter=4)
    assert (drives.yards_to_goal == 75.0).all()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'opp_offense'`

- [ ] **Step 3: Write minimal implementation**

Create `end_of_game/opp_offense.py`:

```python
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
    first = frame.groupby("pff_DRIVEID", as_index=False).first()

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

    return drives.reset_index(drop=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v`
Expected: PASS — 12 passed (6 parametrized conversion cases plus 6 loader tests)

- [ ] **Step 5: Sanity check against real data**

Run:
```bash
cd end_of_game && python3 -c "
from opp_offense import load_drives
d = load_drives('ivy_19t26.csv')
print(len(d), 'Q4 drives')
print(d[d.seconds_left <= 300].scored.mean().round(3), 'score rate inside 5:00')
print(d.end_event.value_counts().head())
"
```
Expected: ~1,982 Q4 drives; score rate inside 5:00 around 0.17; `END OF GAME` the most common end event.

- [ ] **Step 6: Commit**

```bash
cd /Users/graceyang/Desktop/evertrue
git add end_of_game/opp_offense.py end_of_game/tests/test_opp_offense.py
git commit -m "feat(end_of_game): drive-level loader for opponent scoring model"
```

---

### Task 2: Multinomial scoring model

**Files:**
- Modify: `end_of_game/opp_offense.py`
- Modify: `end_of_game/tests/test_opp_offense.py`

**Interfaces:**
- Consumes: `load_drives` from Task 1
- Produces:
  - `design_matrix(frame: pd.DataFrame) -> np.ndarray` — 4 columns, order `[log_seconds, ep_start, timeouts, needs_td]`
  - `fit(drives: pd.DataFrame) -> OppOffenseModel`
  - `OppOffenseModel.predict(seconds_left: float, ep_start: float, timeouts: int, needs_td: int) -> dict` with keys `p_td`, `p_fg`, `p_score`
  - `OppOffenseModel.n_train: int`
  - `OppOffenseModel.coefficients() -> pd.DataFrame` indexed by outcome, columns the feature names

- [ ] **Step 1: Write the failing test**

Append to `end_of_game/tests/test_opp_offense.py`:

```python
import numpy as np

from opp_offense import FEATURE_NAMES, design_matrix, fit


@pytest.fixture
def real_drives():
    """Real Q4 drives. The model needs genuine covariance to fit sensibly."""
    return load_drives("ivy_19t26.csv")


def test_design_matrix_shape_and_order(real_drives):
    matrix = design_matrix(real_drives.head(10))
    assert matrix.shape == (10, len(FEATURE_NAMES))
    assert FEATURE_NAMES == ["log_seconds", "ep_start", "timeouts", "needs_td"]


def test_design_matrix_has_no_nan_or_inf(real_drives):
    matrix = design_matrix(real_drives)
    assert np.isfinite(matrix).all()


def test_predict_returns_probabilities_that_sum_correctly(real_drives):
    model = fit(real_drives)
    out = model.predict(seconds_left=120, ep_start=0.5, timeouts=2, needs_td=1)
    assert 0.0 <= out["p_td"] <= 1.0
    assert 0.0 <= out["p_fg"] <= 1.0
    assert out["p_score"] == pytest.approx(out["p_td"] + out["p_fg"])


def test_more_time_never_lowers_scoring_probability(real_drives):
    model = fit(real_drives)
    probs = [
        model.predict(seconds_left=t, ep_start=0.5, timeouts=2, needs_td=1)["p_score"]
        for t in [30, 60, 120, 240, 480]
    ]
    assert probs == sorted(probs), f"P(score) fell as time rose: {probs}"


def test_better_field_position_never_lowers_scoring_probability(real_drives):
    model = fit(real_drives)
    probs = [
        model.predict(seconds_left=180, ep_start=ep, timeouts=2, needs_td=1)["p_score"]
        for ep in [-1.0, 0.0, 1.0, 2.0, 3.0]
    ]
    assert probs == sorted(probs), f"P(score) fell as position improved: {probs}"


def test_coefficients_are_reported_per_outcome(real_drives):
    model = fit(real_drives)
    coefs = model.coefficients()
    assert list(coefs.columns) == FEATURE_NAMES
    assert "TD" in coefs.index and "FG" in coefs.index
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v -k "design_matrix or predict or never_lowers or coefficients"`
Expected: FAIL — `ImportError: cannot import name 'FEATURE_NAMES'`

- [ ] **Step 3: Write minimal implementation**

Append to `end_of_game/opp_offense.py`:

```python
from sklearn.linear_model import LogisticRegression

# Feature order is part of the interface -- design_matrix, coefficients() and
# every validation report rely on it.
FEATURE_NAMES = ["log_seconds", "ep_start", "timeouts", "needs_td"]

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
        frame.timeouts.fillna(3.0).to_numpy(float),
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

    def predict(self, seconds_left, ep_start, timeouts, needs_td):
        frame = pd.DataFrame([{
            "seconds_left": float(seconds_left),
            "ep_start": float(ep_start),
            "timeouts": float(timeouts),
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
        subset=["seconds_left", "ep_start", "timeouts", "end_event"])
    estimator = LogisticRegression(max_iter=2000)
    estimator.fit(design_matrix(usable), _outcomes(usable))
    return OppOffenseModel(estimator, n_train=len(usable))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v`
Expected: PASS — all tests, including both monotonicity tests.

**If either monotonicity test fails, stop.** That is validation gate 3 from the spec failing, not a bug to paper over. Report the coefficient signs and do not proceed to Task 3.

- [ ] **Step 5: Commit**

```bash
cd /Users/graceyang/Desktop/evertrue
git add end_of_game/opp_offense.py end_of_game/tests/test_opp_offense.py
git commit -m "feat(end_of_game): multinomial drive-outcome model"
```

---

### Task 3: The five validation gates

**Files:**
- Modify: `end_of_game/opp_offense.py`
- Modify: `end_of_game/tests/test_opp_offense.py`

**Interfaces:**
- Consumes: `fit`, `load_drives`, `OppOffenseModel` from Tasks 1–2
- Produces:
  - `calibration_table(model, drives, bins=10) -> pd.DataFrame` with columns `bin, n, predicted, observed`
  - `holdout_evaluation(drives, train_seasons, test_seasons) -> dict` with keys `auc, n_train, n_test, calibration`
  - `monotonicity_check(model) -> pd.DataFrame` with columns `feature, direction, passed`
  - `anchor_check(model, drives) -> pd.DataFrame` with columns `scenario, p_score, plausible`
  - `median_ep_at(drives, yards_to_goal_target, tolerance=5) -> float`

- [ ] **Step 1: Write the failing test**

Append to `end_of_game/tests/test_opp_offense.py`:

```python
from opp_offense import (anchor_check, calibration_table, holdout_evaluation,
                         median_ep_at, monotonicity_check)


def test_calibration_table_bins_and_totals(real_drives):
    model = fit(real_drives)
    table = calibration_table(model, real_drives, bins=10)
    assert list(table.columns) == ["bin", "n", "predicted", "observed"]
    assert table.n.sum() == model.n_train
    # a usable model tracks the diagonal: mean absolute gap under 10 points
    assert (table.predicted - table.observed).abs().mean() < 0.10


def test_holdout_evaluation_trains_and_tests_on_disjoint_seasons(real_drives):
    result = holdout_evaluation(
        real_drives, train_seasons=[2019, 2021, 2022, 2023, 2024],
        test_seasons=[2025, 2026])
    assert result["n_train"] > 1000
    assert result["n_test"] > 100
    # beating a coin flip out of sample is the bar for using this at all
    assert result["auc"] > 0.60, f"out-of-sample AUC {result['auc']}"


def test_monotonicity_check_reports_every_feature(real_drives):
    model = fit(real_drives)
    checks = monotonicity_check(model)
    assert set(checks.feature) == {"log_seconds", "ep_start", "timeouts"}
    assert checks.passed.all(), f"sign flip: {checks.to_dict('records')}"


def test_median_ep_at_own_25_is_low(real_drives):
    ep = median_ep_at(real_drives, yards_to_goal_target=75)
    assert -2.0 < ep < 2.0


def test_anchor_check_own_25_one_minute_needing_a_touchdown(real_drives):
    model = fit(real_drives)
    checks = anchor_check(model, real_drives)
    row = checks.set_index("scenario").loc["own 25, 1:00, 1 TO, needs TD"]
    assert row.p_score < 0.25, f"implausibly high: {row.p_score}"
    assert bool(row.plausible)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v -k "calibration or holdout or monotonicity or median_ep or anchor"`
Expected: FAIL — `ImportError: cannot import name 'anchor_check'`

- [ ] **Step 3: Write minimal implementation**

Append to `end_of_game/opp_offense.py`:

```python
from sklearn.metrics import roc_auc_score

# Monotonicity: more clock, better field position and more timeouts must never
# reduce scoring probability. A negative coefficient on any of these means the
# fit is chasing noise, and the spec treats that as a failure.
MONOTONE_UP = ["log_seconds", "ep_start", "timeouts"]

# An offense at its own 25 with a minute left and one timeout, needing a
# touchdown, scores rarely. A model that disagrees is wrong whatever its AUC.
ANCHOR_CEILING = 0.25


def median_ep_at(drives, yards_to_goal_target, tolerance=5):
    """Typical expected points from a given distance, for building scenarios."""
    near = drives[
        (drives.yards_to_goal - yards_to_goal_target).abs() <= tolerance]
    return float(near.ep_start.median())


def calibration_table(model, drives, bins=10):
    """Predicted against observed scoring rate, by predicted-probability bin."""
    usable = drives.dropna(
        subset=["seconds_left", "ep_start", "timeouts", "end_event"]).copy()
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
        subset=["seconds_left", "ep_start", "timeouts", "end_event"])
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
        ("own 25, 1:00, 1 TO, needs TD", 60, ep_own_25, 1, 1, ANCHOR_CEILING),
        ("own 25, 0:20, 0 TO, needs TD", 20, ep_own_25, 0, 1, 0.10),
        ("own 40, 5:00, 3 TO, needs TD", 300, ep_own_40, 3, 1, 0.80),
    ]
    rows = []
    for label, seconds, ep, timeouts, needs_td, ceiling in scenarios:
        p = model.predict(seconds, ep, timeouts, needs_td)["p_score"]
        rows.append({
            "scenario": label,
            "p_score": round(p, 3),
            "plausible": p < ceiling,
        })
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v`
Expected: PASS — all tests.

**Any failure here is a spec gate failing.** Record which gate, and switch to the `DESIGN.md` fallback (a coarse time × field-position lookup table, labelled coarse on the cards) rather than tuning until the test goes green.

- [ ] **Step 5: Commit**

```bash
cd /Users/graceyang/Desktop/evertrue
git add end_of_game/opp_offense.py end_of_game/tests/test_opp_offense.py
git commit -m "feat(end_of_game): five validation gates for opponent scoring model"
```

---

### Task 4: CLI gate report

**Files:**
- Modify: `end_of_game/opp_offense.py`

**Interfaces:**
- Consumes: everything from Tasks 1–3
- Produces: `python3 opp_offense.py <csv> [--gates]` printing drive counts, the fitted coefficients, all five gates with PASS/FAIL, and a scoring-probability grid. Exit code 1 if any gate fails, so the gate is machine-checkable and not a thing a human has to remember to read.

- [ ] **Step 1: Write the failing test**

Append to `end_of_game/tests/test_opp_offense.py`:

```python
import subprocess
import sys


def test_cli_gates_exit_zero_on_real_data():
    result = subprocess.run(
        [sys.executable, "opp_offense.py", "ivy_19t26.csv", "--gates"],
        capture_output=True, text=True, cwd=".")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
    assert "FAIL" not in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py::test_cli_gates_exit_zero_on_real_data -v`
Expected: FAIL — no `__main__` block, so the script produces no `PASS` output.

- [ ] **Step 3: Write minimal implementation**

Append to `end_of_game/opp_offense.py`:

```python
import argparse

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
    ok = bool(anchors.plausible.all())
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 4. anchors          " +
                 ", ".join(f"{r.scenario} -> {r.p_score:.2f}"
                           for r in anchors.itertuples()))

    thin = calibration[calibration.n < 30]
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

    drives = load_drives(args.csv, quarter=args.quarter)
    print(f"{len(drives)} Q{args.quarter} drives, "
          f"seasons {int(drives.season.min())}-{int(drives.season.max())}")
    print(f"score rate: {drives.scored.mean():.3f} overall, "
          f"{drives[drives.seconds_left <= 300].scored.mean():.3f} inside 5:00")

    passed, lines, model = run_gates(drives)
    print("\nVALIDATION GATES")
    for line in lines:
        print("  " + line)

    print("\nP(score) BY TIME LEFT AND FIELD POSITION (needs TD, 2 TO)")
    header = "".join(f"{y:>8d}" for y in [80, 65, 50, 35, 20])
    print(f"  {'clock':>7s}{header}   <- yards to goal")
    for seconds in [30, 60, 120, 180, 300]:
        row = f"  {seconds // 60}:{seconds % 60:02d}".rjust(9)
        for ytg in [80, 65, 50, 35, 20]:
            ep = median_ep_at(drives, ytg)
            p = model.predict(seconds, ep, 2, 1)["p_score"]
            row += f"{p:>8.2f}"
        print(row)

    if args.gates and not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v`
Expected: PASS — all tests including the CLI gate.

- [ ] **Step 5: Run the gates on both datasets and record the result**

Run:
```bash
cd end_of_game
python3 opp_offense.py ivy_19t26.csv --gates; echo "ivy exit: $?"
python3 opp_offense.py brown_19t26.csv --gates; echo "brown exit: $?"
```

The Ivy run is the one that gates Plans 02–04. The Brown run is expected to be
noisier on far fewer drives; a failure there is informative, not blocking,
because the spec fits opponent scoring on the league and shrinks toward it.

- [ ] **Step 6: Commit**

```bash
cd /Users/graceyang/Desktop/evertrue
git add end_of_game/opp_offense.py end_of_game/tests/test_opp_offense.py
git commit -m "feat(end_of_game): CLI gate report for opponent scoring model"
```

---

## Gate before Plans 02–04

`python3 opp_offense.py ivy_19t26.csv --gates` must exit 0.

If it does not, `DESIGN.md` already commits us to the fallback: a coarse
time × field-position lookup table, labelled as coarse wherever it reaches a
printed card. Take that path rather than tuning the model until the gate goes
green — a gate that has been adjusted until it passes is not a gate.
