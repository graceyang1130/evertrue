# Opponent Scoring Refit (`opp_offense.py`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refit the opponent-scoring model on the population the tool can actually be asked about, and rebuild the three validation gates that could not fail or that rewarded the defect.

**Architecture:** Same three features and same multinomial form — the population was the entire defect. Every out-of-sample gate moves to leave-one-season-out folds computed once and shared, because a single-season holdout is noise at n=720. Anchor bounds become two-sided and are derived from the data at fit time rather than hardcoded.

**Tech Stack:** Python 3, pandas 2.2.3, numpy 2.3.4, scikit-learn 1.7.2, pytest 9.0.3

**Spec:** `end_of_game/DESIGN.md` — read Amendment 2 (and Amendment 1a). Where the body of the document and Amendment 2 disagree, **Amendment 2 wins**.

## Global Constraints

- `statsmodels` is **not installed**. Use scikit-learn. Do not add dependencies.
- `end_of_game/ivy_19t26.csv` and `end_of_game/brown_19t26.csv` are gitignored and total 113MB. **Never `git add` them.**
- Tests run as `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v`. 30 tests pass before this plan starts.
- Seasons are 2019 and 2021–2026. **There is no 2020** — the Ivy League cancelled it.
- Features stay `FEATURE_NAMES == ["log_seconds", "ep_start", "needs_td"]`. **Do not add, remove or re-bucket a feature.** A bucketed score-state feature was tested and is worse out of sample (median LOSO band bias 0.183 against 0.072); the 2-band scheme *is* `needs_td`.
- `timeouts` is not a feature and must not become one (Amendment 1/1a). `load_drives` still returns the column.
- Existing thresholds that must not move: `CALIBRATION_TOLERANCE = 0.10`, `MIN_AUC = 0.60`, `MIN_BIN_N = 30`.
- `git` has no configured identity in this repo and infers it from the hostname, which can break. If a commit fails with "Author identity unknown", prefix it with `GIT_AUTHOR_NAME="Grace Yang" GIT_AUTHOR_EMAIL="graceyang@Graces-MacBook-Air-644.local" GIT_COMMITTER_NAME="Grace Yang" GIT_COMMITTER_EMAIL="graceyang@Graces-MacBook-Air-644.local"` to match the existing history. Do not write to git config.
- Measured facts you may rely on without re-deriving: corrected population n=720 (253 inside 5:00, 122 inside 2:00); LOSO AUC 0.649 all / 0.674 ≤5:00 / 0.665 ≤2:00; LOSO conditional band bias median 0.072, worst 0.116; aggregate decile calibration 0.058; monotonicity `log_seconds` TD +0.315 FG +0.132, `ep_start` TD +0.440 FG +0.127.

---

### Task 1: Corrected population, and anchors that work in it

**Files:**
- Modify: `end_of_game/opp_offense.py`
- Modify: `end_of_game/tests/test_opp_offense.py`

These ship together and cannot be split. Changing the population moves every
anchor prediction, and the old `own 25, 0:20` anchor fails immediately
afterwards (0.154 against its 0.10 ceiling). Splitting them leaves the suite red.

**Interfaces:**
- Consumes: `load_drives(path, quarter=4)` returning columns `drive_id, season, offense, defense, seconds_left, yards_to_goal, ep_start, timeouts, score_diff, deficit, needs_td, end_event, scored_td, scored_fg, scored`; `MIN_BIN_N = 30`; `REQUIRED_FIELDS`
- Produces:
  - `MAX_DEFICIT = 16`
  - `decision_population(drives, max_deficit=MAX_DEFICIT) -> pd.DataFrame`
  - `wilson_interval(successes, n, z=1.96) -> tuple[float, float]`
  - `ANCHOR_SCENARIOS`, `ANCHOR_YARD_TOLERANCE = 10`
  - `anchor_check(model, drives) -> pd.DataFrame` with columns `scenario, n, observed, floor, ceiling, mean_predicted, plausible, tested`

- [ ] **Step 1: Write the failing tests**

Append to `end_of_game/tests/test_opp_offense.py`:

```python
from opp_offense import (ANCHOR_SCENARIOS, MAX_DEFICIT, anchor_check,
                          decision_population, wilson_interval)


def test_decision_population_excludes_leading_offenses(real_drives):
    pop = decision_population(real_drives)
    assert (pop.score_diff <= 0).all()


def test_decision_population_caps_the_deficit(real_drives):
    pop = decision_population(real_drives)
    assert (pop.score_diff >= -MAX_DEFICIT).all()


def test_decision_population_size_matches_the_spec(real_drives):
    # DESIGN.md Amendment 2 records n=720 after dropping incomplete rows
    pop = decision_population(real_drives).dropna(subset=REQUIRED_FIELDS)
    assert len(pop) == 720


def test_wilson_interval_brackets_the_point_estimate():
    low, high = wilson_interval(20, 100)
    assert low < 0.20 < high


def test_wilson_interval_is_wider_on_less_data():
    narrow = wilson_interval(20, 100)
    wide = wilson_interval(2, 10)
    assert (wide[1] - wide[0]) > (narrow[1] - narrow[0])


def test_wilson_interval_handles_zero_n():
    low, high = wilson_interval(0, 0)
    assert np.isnan(low) and np.isnan(high)


def test_anchor_check_is_two_sided(real_drives):
    pop = decision_population(real_drives)
    model = fit(pop)
    anchors = anchor_check(model, pop)
    tested = anchors[anchors.tested]
    assert len(tested) >= 1
    # a two-sided anchor has both bounds, and they bracket the observed rate
    for row in tested.itertuples():
        assert row.floor <= row.observed <= row.ceiling


def test_anchor_check_skips_anchors_the_data_cannot_support(real_drives):
    pop = decision_population(real_drives)
    model = fit(pop)
    anchors = anchor_check(model, pop)
    # every tested anchor must clear the support floor
    for row in anchors[anchors.tested].itertuples():
        assert row.n >= MIN_BIN_N


def test_anchor_bounds_are_wide_enough_to_be_a_coarse_check_only(real_drives):
    """Anchors are a backstop, not the primary defence, and the plan says so.
    At n=60 a Wilson interval spans about 0.21, so a 15-point bias fits inside
    it -- the model fitted on the WRONG population passes every anchor here.
    This test pins that fact so nobody later mistakes an anchor pass for
    evidence of calibration. Gate 6 is what catches population-level bias."""
    pop = decision_population(real_drives)
    anchors = anchor_check(fit(pop), pop)
    tested = anchors[anchors.tested]
    widths = tested.ceiling - tested.floor
    assert (widths > 0.12).all(), (
        "an anchor interval is narrow enough to be mistaken for a precise "
        "check; re-read the SCOPE note on anchor_check")
```

Also add `REQUIRED_FIELDS` and `MIN_BIN_N` to the existing `from opp_offense import (...)` block if not already present.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v -k "decision_population or wilson or anchor"`
Expected: FAIL — `ImportError: cannot import name 'decision_population'`

- [ ] **Step 3: Write the implementation**

In `end_of_game/opp_offense.py`, add near the other constants:

```python
# The tool is only ever asked about an opponent that trails or is tied -- if
# Brown holds the lead, a leading opponent cannot occur. Beyond this margin the
# game is effectively decided and the behaviour stops being representative.
MAX_DEFICIT = 16
```

Add after `load_drives`:

```python
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
```

Replace `anchor_check` entirely, and delete the now-unused `ANCHOR_CEILING`:

```python
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
```

In `run_gates`, change gate 4's reporting line to show both bounds:

```python
    anchors = anchor_check(model, drives)
    tested = anchors[anchors.tested]
    ok = bool(tested.plausible.all()) and len(tested) >= 1
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 4. anchors          " +
                 ", ".join(f"{r.scenario} -> {r.mean_predicted:.2f} "
                           f"in [{r.floor:.2f},{r.ceiling:.2f}]"
                           for r in tested.itertuples()))
```

In `main`, apply the population filter immediately after loading, and say so:

```python
    all_drives = load_drives(args.csv, quarter=args.quarter)
    drives = decision_population(all_drives)
    print(f"{len(all_drives)} Q{args.quarter} drives loaded; "
          f"{len(drives)} in the decision population "
          f"(trailing or tied, within {MAX_DEFICIT})")
```

Every later use of `drives` in `main` then operates on the filtered frame. Leave
the existing score-rate print, gates call and grid call reading `drives`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v`
Expected: PASS — 39 tests.

Note what Task 1 does *not* claim: anchors are a coarse backstop only. The
model fitted on the wrong population passes every anchor defined here, because a
Wilson interval at n=60 spans about 0.20. Gate 6 in Task 3 is the gate that
catches population-level bias, and it carries the test that proves it.

- [ ] **Step 5: Run the CLI on both datasets**

```bash
cd end_of_game
python3 opp_offense.py ivy_19t26.csv --gates; echo "ivy exit: $?"
python3 opp_offense.py brown_19t26.csv --gates; echo "brown exit: $?"
```

Record both. Gate 1 is expected to read about 0.058 (up from 0.028 — the model no
longer has the easy leading-offense mass) and must still be under 0.10. If an Ivy
gate fails, stop and report BLOCKED with its numbers; do not tune.

- [ ] **Step 6: Commit**

```bash
cd /Users/graceyang/Desktop/evertrue
git add end_of_game/opp_offense.py end_of_game/tests/test_opp_offense.py
git commit -m "fix(end_of_game): fit on the decision population, two-sided anchors"
```

---

### Task 2: Leave-one-season-out folds, computed once

**Files:**
- Modify: `end_of_game/opp_offense.py`
- Modify: `end_of_game/tests/test_opp_offense.py`

**Interfaces:**
- Consumes: `fit(drives)`, `OppOffenseModel.predict_frame(frame)`, `_outcomes(frame)`, `REQUIRED_FIELDS`, `decision_population`
- Produces:
  - `MIN_FOLD_N = 20`
  - `loso_predictions(drives) -> pd.DataFrame` — the input rows that received an out-of-fold prediction, plus a `predicted` column

- [ ] **Step 1: Write the failing tests**

```python
from opp_offense import MIN_FOLD_N, loso_predictions


def test_loso_predictions_covers_most_of_the_population(real_drives):
    pop = decision_population(real_drives)
    out = loso_predictions(pop)
    usable = pop.dropna(subset=REQUIRED_FIELDS)
    # every season with enough drives gets folded; allow a little loss to
    # seasons too thin to hold out
    assert len(out) > 0.85 * len(usable)


def test_loso_predictions_are_probabilities(real_drives):
    out = loso_predictions(decision_population(real_drives))
    assert out.predicted.between(0.0, 1.0).all()
    assert out.predicted.notna().all()


def test_loso_predictions_are_out_of_sample(real_drives):
    """An out-of-fold prediction must be worse than an in-sample one. If they
    match, a fold is leaking its own season into training."""
    pop = decision_population(real_drives)
    out = loso_predictions(pop)
    in_sample = fit(pop).predict_frame(out).p_score.to_numpy()
    assert not np.allclose(out.predicted.to_numpy(), in_sample)


def test_loso_predictions_keeps_season_and_outcome_columns(real_drives):
    out = loso_predictions(decision_population(real_drives))
    for column in ["season", "scored", "seconds_left", "score_diff"]:
        assert column in out.columns
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v -k loso`
Expected: FAIL — `ImportError: cannot import name 'loso_predictions'`

- [ ] **Step 3: Write the implementation**

Add after `fit`:

```python
# A season needs at least this many drives to be worth holding out as a fold.
MIN_FOLD_N = 20


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

    for season in sorted(usable.season.unique()):
        test = usable[usable.season == season]
        train = usable[usable.season != season]
        if len(test) < MIN_FOLD_N or train.empty:
            continue
        # a multinomial fit needs all three outcomes present in training
        if len(set(_outcomes(train))) < 3:
            continue
        model = fit(train)
        usable.loc[test.index, "predicted"] = (
            model.predict_frame(test).p_score.to_numpy())

    return usable.dropna(subset=["predicted"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v`
Expected: PASS — 43 tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/graceyang/Desktop/evertrue
git add end_of_game/opp_offense.py end_of_game/tests/test_opp_offense.py
git commit -m "feat(end_of_game): leave-one-season-out folds for out-of-sample gates"
```

---

### Task 3: Gate 2 measured where the tool operates, and gate 6

**Files:**
- Modify: `end_of_game/opp_offense.py`
- Modify: `end_of_game/tests/test_opp_offense.py`

**Interfaces:**
- Consumes: `loso_predictions(drives)`, `MIN_BIN_N`, `MIN_AUC`
- Produces:
  - `REGIONS`, `GATE_REGION_SECONDS = 300`
  - `regional_performance(out_of_fold) -> pd.DataFrame` with columns `region, seconds_limit, n, auc, calibration`
  - `GATE_BANDS`, `DIAGNOSTIC_BANDS`, `MIN_BAND_CELL_N = 5`, `CONDITIONAL_MEDIAN_MAX = 0.10`, `CONDITIONAL_WORST_MAX = 0.20`
  - `score_band(drives, bands=GATE_BANDS) -> pd.Series`
  - `conditional_calibration(out_of_fold, bands=GATE_BANDS) -> pd.DataFrame` with columns `season, n, worst_band_bias`

- [ ] **Step 1: Write the failing tests**

```python
from opp_offense import (CONDITIONAL_MEDIAN_MAX, CONDITIONAL_WORST_MAX,
                          DIAGNOSTIC_BANDS, GATE_BANDS, GATE_REGION_SECONDS,
                          conditional_calibration, regional_performance,
                          score_band)


def test_regional_performance_reports_every_populated_region(real_drives):
    out = loso_predictions(decision_population(real_drives))
    table = regional_performance(out)
    assert list(table.columns) == ["region", "seconds_limit", "n", "auc",
                                   "calibration"]
    assert "<=5:00" in set(table.region)


def test_regional_auc_clears_the_bar_where_the_tool_operates(real_drives):
    out = loso_predictions(decision_population(real_drives))
    table = regional_performance(out).set_index("region")
    assert table.loc["<=5:00", "auc"] > MIN_AUC


def test_score_band_labels_every_drive_in_the_population(real_drives):
    pop = decision_population(real_drives)
    bands = score_band(pop)
    assert (bands != "other").all()


def test_score_band_splits_on_what_the_opponent_needs(real_drives):
    pop = decision_population(real_drives)
    bands = score_band(pop)
    assert (bands[pop.score_diff == 0] == "needs 3 or fewer").all()
    assert (bands[pop.score_diff == -3] == "needs 3 or fewer").all()
    assert (bands[pop.score_diff == -4] == "needs a TD").all()


def test_diagnostic_bands_are_finer_than_gate_bands(real_drives):
    pop = decision_population(real_drives)
    assert score_band(pop, DIAGNOSTIC_BANDS).nunique() > score_band(pop).nunique()
    assert (score_band(pop, DIAGNOSTIC_BANDS) != "other").all()


def test_finer_bands_would_fail_the_gate_which_is_why_they_are_not_gated(real_drives):
    """Pins the reason GATE_BANDS is only two wide. The diagnostic bands are
    genuinely less stable out of sample, so gating on them would ship a gate
    that fails on arrival."""
    out = loso_predictions(decision_population(real_drives))
    coarse = conditional_calibration(out)
    fine = conditional_calibration(out, DIAGNOSTIC_BANDS)
    assert fine.worst_band_bias.median() > coarse.worst_band_bias.median()


def test_gate_bands_still_detect_the_original_defect(real_drives):
    """The gate must be coarse enough to be stable AND fine enough to catch the
    defect it exists for. Two bands threads that by a 7% margin; verify it."""
    old_model = fit(real_drives)
    pop = decision_population(real_drives).dropna(subset=REQUIRED_FIELDS)
    scored = pop.assign(
        predicted=old_model.predict_frame(pop).p_score.to_numpy(),
        band=score_band(pop))
    worst = max(abs(cell.predicted.mean() - cell.scored.mean())
                for _, cell in scored.groupby("band", observed=True))
    assert worst > CONDITIONAL_MEDIAN_MAX, (
        f"two-band gate misses the original defect (worst bias {worst:.3f}); "
        f"the gate is stable but blind and must be reconsidered")


def test_conditional_calibration_reports_per_season(real_drives):
    out = loso_predictions(decision_population(real_drives))
    table = conditional_calibration(out)
    assert list(table.columns) == ["season", "n", "worst_band_bias"]
    assert len(table) >= 5


def test_conditional_calibration_meets_the_gate(real_drives):
    out = loso_predictions(decision_population(real_drives))
    table = conditional_calibration(out)
    assert table.worst_band_bias.median() < CONDITIONAL_MEDIAN_MAX
    assert table.worst_band_bias.max() < CONDITIONAL_WORST_MAX


def test_conditional_calibration_would_catch_the_original_defect(real_drives):
    """The gate exists to catch a model fitted on the wrong population. Score
    the old population's model on the decision population's bands and confirm
    the bias it produces exceeds what the gate tolerates."""
    old_model = fit(real_drives)
    pop = decision_population(real_drives).dropna(subset=REQUIRED_FIELDS)
    scored = pop.assign(
        predicted=old_model.predict_frame(pop).p_score.to_numpy(),
        band=score_band(pop))
    worst = 0.0
    for band, cell in scored.groupby("band", observed=True):
        worst = max(worst, abs(cell.predicted.mean() - cell.scored.mean()))
    assert worst > CONDITIONAL_MEDIAN_MAX, (
        f"old model's worst band bias {worst:.3f} does not exceed the gate")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v -k "regional or score_band or conditional"`
Expected: FAIL — `ImportError: cannot import name 'regional_performance'`

- [ ] **Step 3: Write the implementation**

Add after `loso_predictions`:

```python
# Clock regions to report. Gate 2 is scored on the <=5:00 slice: 42.8% of
# fourth-quarter drives start outside the card's range entirely, and including
# them flatters discrimination (0.705 overall against 0.669 inside 5:00 on the
# model this replaces).
REGIONS = [(None, "all"), (600, "<=10:00"), (300, "<=5:00"), (120, "<=2:00")]
GATE_REGION_SECONDS = 300

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
    """
    frame = out_of_fold.assign(band=score_band(out_of_fold, bands))
    rows = []
    for season, block in frame.groupby("season"):
        worst = 0.0
        for _, cell in block.groupby("band", observed=True):
            if len(cell) < MIN_BAND_CELL_N:
                continue
            worst = max(worst, abs(cell.predicted.mean() - cell.scored.mean()))
        rows.append({"season": int(season), "n": int(len(block)),
                     "worst_band_bias": round(worst, 3)})
    return pd.DataFrame(rows)
```

In `run_gates`, replace gate 2 and append gate 6. Compute the folds once:

```python
    out_of_fold = loso_predictions(drives)
    regional = regional_performance(out_of_fold)
    region_row = regional[regional.seconds_limit == GATE_REGION_SECONDS]
    ok = (not region_row.empty
          and float(region_row.iloc[0].auc) > MIN_AUC)
    passed &= ok
    detail = ("no <=5:00 region" if region_row.empty else
              f"LOSO AUC = {region_row.iloc[0].auc:.3f} "
              f"(n={int(region_row.iloc[0].n)})")
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 2. discrimination   "
                 f"{detail}, scored inside 5:00")
```

and, after gate 5:

```python
    conditional = conditional_calibration(out_of_fold)
    median_bias = float(conditional.worst_band_bias.median())
    worst_bias = float(conditional.worst_band_bias.max())
    ok = (median_bias < CONDITIONAL_MEDIAN_MAX
          and worst_bias < CONDITIONAL_WORST_MAX)
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 6. cond. calibration "
                 f"median {median_bias:.3f} (<{CONDITIONAL_MEDIAN_MAX}), "
                 f"worst {worst_bias:.3f} (<{CONDITIONAL_WORST_MAX})")
```

Update `run_gates`'s docstring from "All five spec gates" to "All six spec gates".

Delete `holdout_evaluation`, `HOLDOUT_TRAIN` and `HOLDOUT_TEST`, and the test
`test_holdout_evaluation_trains_and_tests_on_disjoint_seasons` — the single-split
estimator is superseded and keeping it invites someone to gate on it again.

In `main`, replace the hand-rolled regional reporting block with the table:

```python
    print("\nOUT-OF-SAMPLE PERFORMANCE BY REGION (leave-one-season-out)")
    print(regional_performance(loso_predictions(drives)).to_string(index=False))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v`
Expected: PASS — 51 tests (43 + 9 new − 1 deleted).

`test_conditional_calibration_would_catch_the_original_defect` is the one that
matters: it proves gate 6 detects the failure it was built for. If it fails, gate
6 is decoration — stop and report rather than loosening the thresholds.

- [ ] **Step 5: Commit**

```bash
cd /Users/graceyang/Desktop/evertrue
git add end_of_game/opp_offense.py end_of_game/tests/test_opp_offense.py
git commit -m "feat(end_of_game): region-scored discrimination and conditional calibration gates"
```

---

### Task 4: A card axis that matches where drives actually start

**Files:**
- Modify: `end_of_game/opp_offense.py`
- Modify: `end_of_game/tests/test_opp_offense.py`

**Interfaces:**
- Consumes: `median_ep_at`, `MIN_BIN_N`, `decision_population`, `OppOffenseModel.predict`
- Produces:
  - `CARD_YARDS_TO_GOAL = [90, 80, 75, 70, 60]`, `CARD_CLOCKS = [30, 60, 120, 180, 300]`, `MIN_SUPPORTED_CELL_FRACTION = 0.50`
  - `card_cells(model, drives) -> pd.DataFrame` with columns `seconds, yards_to_goal, n, supported, p_score`

- [ ] **Step 1: Write the failing tests**

```python
from opp_offense import (CARD_CLOCKS, CARD_YARDS_TO_GOAL,
                          MIN_SUPPORTED_CELL_FRACTION, card_cells)


def test_card_axis_matches_where_drives_actually_start(real_drives):
    """The median trailing-team drive starts 75 yards out. An axis reaching
    into the red zone describes drives that do not happen."""
    pop = decision_population(real_drives)
    median_start = pop.yards_to_goal.median()
    assert min(CARD_YARDS_TO_GOAL) <= median_start <= max(CARD_YARDS_TO_GOAL)


def test_card_cells_covers_the_whole_grid(real_drives):
    pop = decision_population(real_drives)
    cells = card_cells(fit(pop), pop)
    assert len(cells) == len(CARD_CLOCKS) * len(CARD_YARDS_TO_GOAL)


def test_card_cells_marks_thin_cells_unsupported(real_drives):
    pop = decision_population(real_drives)
    cells = card_cells(fit(pop), pop)
    for row in cells.itertuples():
        if not row.supported:
            assert np.isnan(row.p_score)
        else:
            assert row.n >= MIN_BIN_N
            assert 0.0 <= row.p_score <= 1.0


def test_enough_card_cells_are_supported_to_be_useful(real_drives):
    pop = decision_population(real_drives)
    cells = card_cells(fit(pop), pop)
    fraction = cells.supported.mean()
    assert fraction >= MIN_SUPPORTED_CELL_FRACTION, (
        f"only {fraction:.0%} of card cells are supported")


def test_the_old_card_axis_would_now_fail_the_support_gate(real_drives):
    """Evidence the axis change was necessary, not cosmetic: the previous axis
    reached into the red zone, where trailing teams essentially never start."""
    pop = decision_population(real_drives)
    model = fit(pop)
    supported = 0
    total = 0
    for seconds in CARD_CLOCKS:
        for ytg in [80, 65, 50, 35, 20]:
            total += 1
            try:
                median_ep_at(pop, ytg, seconds_left=seconds, min_n=MIN_BIN_N)
                supported += 1
            except LookupError:
                pass
    assert supported / total < MIN_SUPPORTED_CELL_FRACTION
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v -k card`
Expected: FAIL — `ImportError: cannot import name 'card_cells'`

- [ ] **Step 3: Write the implementation**

Add near the other constants:

```python
# Where trailing teams actually start fourth-quarter drives: the median is 75
# yards out (own 25) and the distribution concentrates between 65 and 85, since
# a team getting the ball back has just received a punt or a kickoff. An earlier
# card used [80, 65, 50, 35, 20], whose two nearest columns were backed by 0-1
# drives -- it asked about field positions that do not occur.
CARD_YARDS_TO_GOAL = [90, 80, 75, 70, 60]
CARD_CLOCKS = [30, 60, 120, 180, 300]

# Below this share of printable cells the card is mostly blanks and the model is
# being asked about situations its population does not contain.
MIN_SUPPORTED_CELL_FRACTION = 0.50
```

Add after `card`-adjacent helpers (anywhere after `median_ep_at`):

```python
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
                ((drives.yards_to_goal - ytg).abs() <= 5)
                & ((drives.seconds_left - seconds).abs() <= 120)]
            if len(near) < MIN_BIN_N:
                rows.append({"seconds": seconds, "yards_to_goal": ytg,
                             "n": int(len(near)), "supported": False,
                             "p_score": np.nan})
                continue
            ep = median_ep_at(drives, ytg, seconds_left=seconds,
                              min_n=MIN_BIN_N)
            rows.append({"seconds": seconds, "yards_to_goal": ytg,
                         "n": int(len(near)), "supported": True,
                         "p_score": round(
                             model.predict(seconds, ep, 1)["p_score"], 3)})
    return pd.DataFrame(rows)
```

Replace gate 5 in `run_gates` — the old version compared `pd.qcut` decile sizes
against a floor, and deciles are equal-count by construction, so it could not
fail below a total n of 300 and was checking the wrong object:

```python
    cells = card_cells(model, drives)
    fraction = float(cells.supported.mean())
    ok = fraction >= MIN_SUPPORTED_CELL_FRACTION
    passed &= ok
    lines.append(f"[{'PASS' if ok else 'FAIL'}] 5. card support     "
                 f"{cells.supported.sum()}/{len(cells)} cells backed by "
                 f">={MIN_BIN_N} drives ({fraction:.0%})")
```

Rewrite the grid in `main` to print from `card_cells`:

```python
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
```

Then print the residual uncertainty directly beneath the card, so it travels with
the numbers instead of living only in a design document:

```python
    out_of_fold = loso_predictions(drives)
    print("\nCALIBRATION BY SCORE BAND, finer than the gate (diagnostic only)")
    print(conditional_calibration(out_of_fold, DIAGNOSTIC_BANDS)
          .to_string(index=False))
    conditional = conditional_calibration(out_of_fold)
    print(f"  uncertainty: per-score-band calibration bias runs "
          f"{conditional.worst_band_bias.median():.2f} typical / "
          f"{conditional.worst_band_bias.max():.2f} worst season. Read these "
          f"as bands, not point estimates.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd end_of_game && python3 -m pytest tests/test_opp_offense.py -v`
Expected: PASS — 56 tests.

- [ ] **Step 5: Run the CLI on both datasets and record the output**

```bash
cd end_of_game
python3 opp_offense.py ivy_19t26.csv --gates; echo "ivy exit: $?"
python3 opp_offense.py brown_19t26.csv --gates; echo "brown exit: $?"
```

Ivy must exit 0 with all six gates PASS and roughly 15 of 25 card cells
supported. Brown has 406 drives before filtering and far fewer after, so a Brown
gate failure here is informative rather than blocking — record it and change
nothing. If an **Ivy** gate fails, stop and report BLOCKED with its numbers.

- [ ] **Step 6: Commit**

```bash
cd /Users/graceyang/Desktop/evertrue
git add end_of_game/opp_offense.py end_of_game/tests/test_opp_offense.py
git commit -m "feat(end_of_game): card axis matching real drive starts, cell-support gate"
```

---

## Gate before Plans 03–04

`python3 opp_offense.py ivy_19t26.csv --gates` must exit 0 with **all six** gates
passing, and the three "would catch the defect" tests must be green:

- `test_gate_bands_still_detect_the_original_defect`
- `test_the_old_card_axis_would_now_fail_the_support_gate`
- `test_finer_bands_would_fail_the_gate_which_is_why_they_are_not_gated`
- `test_anchor_bounds_are_wide_enough_to_be_a_coarse_check_only`

The first two are what separate this from the first attempt, where five gates
passed a model that was 15 points wrong. A gate nobody has demonstrated can fail
is not evidence of anything. The third pins the opposite: anchors are *known* to
be too blunt to catch this, and that limitation is recorded rather than papered
over.

The printed packet must carry the residual band uncertainty (worst-case ~0.12)
rather than implying point-estimate precision, and any cell the data cannot
support prints nothing at all.
