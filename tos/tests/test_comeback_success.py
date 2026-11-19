"""Checks for which late drives are counted and how each outcome is scored."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plot_comeback_success import (behind_pace, late_drives, scored_then_lost_windows,
                                   shade_top, timeout_grid, timeout_vs_time, two_bands, windows)


def drive(**changes):
    values = dict(pff_GAMEID=1, offense="RIBR", season=2024, q_first=4, c_first=120.0,
                  c_last=40.0, offscore=10, defscore=10, end="FIELD GOAL", fcs=True,
                  yards_to_goal=75, timeouts=3)
    values.update(changes)
    return values


def counted(rows, winners=None, ot_games=()):
    winners = pd.Series(winners or {1: "RIBR", 2: "CTYA", 3: "RIBR"})
    return late_drives(pd.DataFrame(rows), winners, set(ot_games))


class CohortTests(unittest.TestCase):
    def test_keeps_only_fourth_quarter_fcs_drives_tied_or_down_one_to_eight(self):
        rows = [drive(), drive(offscore=2), drive(offscore=1), drive(offscore=13),
                drive(q_first=3), drive(fcs=False), drive(c_first=0.0)]
        out = counted(rows)
        self.assertEqual(sorted(out.margin.tolist()), [-8, 0])

    def test_score_state_labels(self):
        out = counted([drive(), drive(offscore=7), drive(offscore=6), drive(offscore=2)])
        self.assertEqual(out.state.tolist(), ["Tied", "Down 1-3", "Down 4-8", "Down 4-8"])


class OutcomeTests(unittest.TestCase):
    def test_field_goal_is_enough_when_tied_or_down_three(self):
        out = counted([drive(), drive(offscore=7)])
        self.assertTrue(out.got_score.all())

    def test_field_goal_is_not_enough_when_down_four_or_more(self):
        out = counted([drive(offscore=6), drive(offscore=6, end="TOUCHDOWN")])
        self.assertEqual(out.got_score.tolist(), [False, True])

    def test_missed_field_goal_and_punt_do_not_count(self):
        out = counted([drive(end="MISSED FG"), drive(end="PUNT")])
        self.assertFalse(out.got_score.any())

    def test_won_comes_from_the_final_result_and_overtime_is_flagged(self):
        rows = [drive(pff_GAMEID=1), drive(pff_GAMEID=2), drive(pff_GAMEID=3)]
        out = counted(rows, ot_games={3})
        self.assertEqual(out.won.tolist(), [True, False, True])
        self.assertEqual(out.overtime.tolist(), [False, False, True])

    def test_scored_but_lost(self):
        out = counted([drive(pff_GAMEID=2), drive(pff_GAMEID=1)])
        self.assertEqual(out.scored_then_lost.tolist(), [True, False])


class WindowTests(unittest.TestCase):
    def test_fifteen_second_windows_count_drives_and_successes(self):
        rows = [drive(c_first=120.0), drive(c_first=106.0, end="PUNT"), drive(c_first=105.0),
                drive(offscore=7, c_first=110.0)]
        out = windows(counted(rows), "got_score", 15, top=120)
        tied = out[out.state.eq("Tied")].set_index("starts_by")
        self.assertEqual(tied.loc["2:00", ["drives", "worked"]].tolist(), [2, 1])
        self.assertEqual(tied.loc["1:45", ["drives", "worked"]].tolist(), [1, 1])
        self.assertAlmostEqual(tied.loc["2:00", "share"], 0.5)
        self.assertEqual(out[out.state.eq("Down 1-3")].drives.sum(), 1)
        self.assertEqual(len(tied), 8)

    def test_window_midpoints(self):
        out = windows(counted([drive()]), "won", 15, top=30)
        self.assertEqual(out[out.state.eq("Tied")].mid.tolist(), [7.5, 22.5])


class PaceTests(unittest.TestCase):
    def test_cell_is_behind_pace_when_most_drives_have_under_a_second_per_yard(self):
        tbins, ybins = [0, 60, 120], [0, 50, 99]
        secs = np.array([30, 30, 30, 65, 70, 100])
        yards = np.array([75, 75, 20, 95, 90, 75])
        out = behind_pace(secs, yards, tbins, ybins)
        # rows = yards bins (near, far); columns = time bins (short, long). The far/long
        # cell's middle (90 s, 75 yd) is on pace, but 2 of its 3 drives were behind.
        self.assertEqual(out.tolist(), [[False, False], [True, True]])

    def test_empty_cell_falls_back_to_its_middle(self):
        out = behind_pace(np.array([]), np.array([]), [0, 30, 120], [0, 50, 99])
        self.assertEqual(out.tolist(), [[True, False], [True, False]])


class ScoredThenLostTests(unittest.TestCase):
    def test_fifteen_second_windows_by_clock_when_the_drive_scored(self):
        rows = [drive(pff_GAMEID=2, c_last=0.0), drive(pff_GAMEID=1, c_last=15.0),
                drive(pff_GAMEID=2, c_last=16.0), drive(pff_GAMEID=2, c_last=40.0, end="PUNT"),
                drive(pff_GAMEID=2, offscore=4, c_last=10.0, end="TOUCHDOWN")]
        out = scored_then_lost_windows(counted(rows), 15, top=60).set_index("starts_by")
        self.assertEqual(out.loc["0:15", ["scored", "still_lost"]].tolist(), [2, 1])
        self.assertEqual(out.loc["0:30", ["scored", "still_lost"]].tolist(), [1, 1])
        self.assertAlmostEqual(out.loc["0:15", "share_lost"], 0.5)
        self.assertEqual(out.scored.sum(), 3)  # punt and the down-4-8 drive are left out
        self.assertEqual(len(out), 4)


class TimeoutGridTests(unittest.TestCase):
    def test_counts_by_timeouts_left_and_minute(self):
        rows = [drive(timeouts=3, c_first=30.0), drive(timeouts=3, c_first=50.0, end="PUNT"),
                drive(timeouts=0, c_first=60.0), drive(timeouts=1, c_first=61.0),
                drive(timeouts=2, c_first=250.0)]
        out = timeout_grid(counted(rows), "got_score").set_index(["timeouts", "time_left"])
        self.assertEqual(out.loc[(3, "Last minute"), ["drives", "worked"]].tolist(), [2, 1])
        self.assertEqual(out.loc[(0, "Last minute"), "drives"], 1)
        self.assertEqual(out.loc[(1, "1:00-2:00"), "drives"], 1)
        self.assertEqual(out.drives.sum(), 4)  # the drive starting at 4:10 is past the grid
        self.assertEqual(len(out), 16)


class IvyTests(unittest.TestCase):
    def test_two_bands_counts_inside_two_minutes_against_two_to_four(self):
        rows = [drive(c_first=30.0), drive(c_first=120.0, end="PUNT"), drive(c_first=121.0),
                drive(c_first=240.0), drive(c_first=241.0), drive(offscore=7, c_first=60.0)]
        text = two_bands(counted(rows), "got_score")
        self.assertEqual(text, "tied 1 of 2 vs 2 of 2; down 1-3 1 of 1 vs no drives; "
                               "down 4-8 no drives vs no drives")

    def test_shade_scale_keeps_small_counts_exact(self):
        self.assertEqual([shade_top(n) for n in (0, 3, 7, 10, 23)], [1, 3, 7, 10, 30])


class TimeoutCheckTests(unittest.TestCase):
    def synthetic(self, per_timeout):
        rng = np.random.default_rng(7)
        n = 20000
        d = pd.DataFrame(dict(secs=rng.uniform(1, 240, n), timeouts=rng.integers(0, 4, n),
                              yards_to_goal=rng.integers(20, 99, n),
                              state=rng.choice(["Tied", "Down 1-3", "Down 4-8"], n)))
        logit = -1 + 0.5 * d.secs / 60 + per_timeout * d.timeouts - 0.3 * d.yards_to_goal / 10
        d["got_score"] = rng.random(n) < 1 / (1 + np.exp(-logit))
        return d

    def test_recovers_time_and_timeout_effects(self):
        out = timeout_vs_time(self.synthetic(0.25), "got_score")
        self.assertAlmostEqual(out["per_minute"], 0.5, delta=0.05)
        self.assertAlmostEqual(out["per_timeout"], 0.25, delta=0.05)
        self.assertGreater(out["per_timeout_low"], 0)
        self.assertAlmostEqual(out["timeout_in_seconds"], 30, delta=6)

    def test_no_timeout_effect_has_a_range_through_zero(self):
        out = timeout_vs_time(self.synthetic(0.0), "got_score")
        self.assertLess(out["per_timeout_low"], 0)
        self.assertGreater(out["per_timeout_high"], 0)


if __name__ == "__main__":
    unittest.main()
