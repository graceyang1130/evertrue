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


import numpy as np

from opp_offense import FEATURE_NAMES, design_matrix, fit


@pytest.fixture
def real_drives():
    """Real Q4 drives. The model needs genuine covariance to fit sensibly."""
    return load_drives("ivy_19t26.csv")


def test_design_matrix_shape_and_order(real_drives):
    matrix = design_matrix(real_drives.head(10))
    assert matrix.shape == (10, len(FEATURE_NAMES))
    assert FEATURE_NAMES == ["log_seconds", "ep_start", "needs_td"]


def test_design_matrix_has_no_nan_or_inf(real_drives):
    matrix = design_matrix(real_drives)
    assert np.isfinite(matrix).all()


def test_predict_returns_probabilities_that_sum_correctly(real_drives):
    model = fit(real_drives)
    out = model.predict(seconds_left=120, ep_start=0.5, needs_td=1)
    assert 0.0 <= out["p_td"] <= 1.0
    assert 0.0 <= out["p_fg"] <= 1.0
    assert out["p_score"] == pytest.approx(out["p_td"] + out["p_fg"])


def test_more_time_never_lowers_scoring_probability(real_drives):
    model = fit(real_drives)
    probs = [
        model.predict(seconds_left=t, ep_start=0.5, needs_td=1)["p_score"]
        for t in [30, 60, 120, 240, 480]
    ]
    assert probs == sorted(probs), f"P(score) fell as time rose: {probs}"


def test_better_field_position_never_lowers_scoring_probability(real_drives):
    model = fit(real_drives)
    probs = [
        model.predict(seconds_left=180, ep_start=ep, needs_td=1)["p_score"]
        for ep in [-1.0, 0.0, 1.0, 2.0, 3.0]
    ]
    assert probs == sorted(probs), f"P(score) fell as position improved: {probs}"


def test_coefficients_are_reported_per_outcome(real_drives):
    model = fit(real_drives)
    coefs = model.coefficients()
    assert list(coefs.columns) == FEATURE_NAMES
    assert "TD" in coefs.index and "FG" in coefs.index


from opp_offense import (MIN_BIN_N, REQUIRED_FIELDS, anchor_check,
                         calibration_table, holdout_evaluation, median_ep_at,
                         monotonicity_check)


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
    assert set(checks.feature) == {"log_seconds", "ep_start"}
    assert checks.passed.all(), f"sign flip: {checks.to_dict('records')}"


def test_median_ep_at_own_25_is_low(real_drives):
    ep = median_ep_at(real_drives, yards_to_goal_target=75)
    assert -2.0 < ep < 2.0


def test_anchor_check_own_25_one_minute_needing_a_touchdown(real_drives):
    pop = decision_population(real_drives)
    model = fit(pop)
    checks = anchor_check(model, pop)
    row = checks.set_index("scenario").loc["own 25, under 3:00, needs TD"]
    assert row.tested
    assert bool(row.plausible)


def test_no_calibration_bin_is_thinner_than_the_floor(real_drives):
    model = fit(real_drives)
    table = calibration_table(model, real_drives, bins=10)
    assert table.n.min() >= MIN_BIN_N, f"thinnest bin n={table.n.min()}"


import subprocess
import sys


def test_cli_gates_exit_zero_on_real_data():
    result = subprocess.run(
        [sys.executable, "opp_offense.py", "ivy_19t26.csv", "--gates"],
        capture_output=True, text=True, cwd=".")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
    assert "FAIL" not in result.stdout


def test_median_ep_at_raises_when_too_few_drives_support_the_cell(real_drives):
    with pytest.raises(LookupError):
        median_ep_at(real_drives, yards_to_goal_target=500)


def test_median_ep_at_respects_the_min_n_floor(real_drives):
    # the red-zone band at a tight clock is backed by single digits of drives
    with pytest.raises(LookupError):
        median_ep_at(real_drives, yards_to_goal_target=20, seconds_left=30,
                     min_n=MIN_BIN_N)


def test_clock_matched_ep_differs_from_all_clock_ep(real_drives):
    # pff_EXPECTED_POINTS embeds time, so ignoring the clock double-counts it
    all_clock = median_ep_at(real_drives, yards_to_goal_target=50)
    late = median_ep_at(real_drives, yards_to_goal_target=50, seconds_left=30)
    assert all_clock != late


def test_design_matrix_raises_on_non_finite_features(real_drives):
    broken = real_drives.head(20).copy()
    broken.loc[broken.index[0], "ep_start"] = np.nan
    with pytest.raises(ValueError):
        design_matrix(broken)


def test_required_fields_is_shared_by_fit_and_calibration(real_drives):
    model = fit(real_drives)
    table = calibration_table(model, real_drives, bins=10)
    assert table.n.sum() == model.n_train


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


from opp_offense import MIN_FOLD_N, loso_folds, loso_predictions


def test_loso_predictions_folds_every_qualifying_season(real_drives):
    """The invariant is not a coverage percentage -- it is that no qualifying
    season goes missing. At 85% a silently dropped 2019 (9.3% of drives) or 2026
    (6.7%) would still have passed."""
    pop = decision_population(real_drives)
    folds = loso_folds(pop)
    out = loso_predictions(pop)
    expected = set(folds.loc[folds.folded, "season"])
    assert set(out.season.unique()) == expected
    assert len(expected) >= 5


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


def test_loso_folds_accounts_for_every_season(real_drives):
    pop = decision_population(real_drives)
    folds = loso_folds(pop)
    usable = pop.dropna(subset=REQUIRED_FIELDS)
    assert set(folds.season) == set(usable.season.astype(int))
    assert folds.n.sum() == len(usable)


def test_loso_folds_records_why_it_skipped(real_drives):
    """A skipped fold must say why. Force one by keeping a single season plus a
    token slice of another, so the small season fails MIN_FOLD_N."""
    pop = decision_population(real_drives)
    big = pop[pop.season == 2023]
    tiny = pop[pop.season == 2019].head(3)
    folds = loso_folds(pd.concat([big, tiny]))
    skipped = folds[~folds.folded]
    assert len(skipped) >= 1
    assert (skipped.skipped_because.str.len() > 0).all()
