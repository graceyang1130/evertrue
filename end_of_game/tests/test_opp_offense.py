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
