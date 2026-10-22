"""Regression checks for possession identity and decisive-score attribution."""

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plot_winning_drives import drive_table, percentile, winning_drives


def play(order, clock, **changes):
    values = dict(pff_GAMEID=1, pff_GAMESEASON=2024, pff_SORTORDER=order,
                  pff_DRIVE=1., pff_QUARTER=4, clock=clock, pff_OFFTEAM="RIBR",
                  pff_DEFTEAM="CTYA", pff_OFFSCORE=10, pff_DEFSCORE=10,
                  pff_DOWN=1, pff_SPECIALTEAMSTYPE=np.nan, pff_2MINUTE=2,
                  pff_DRIVEENDEVENT="FIELD GOAL", winner="RIBR",
                  pff_TOUCHDOWN=np.nan, pff_KICKRESULT=np.nan, pff_NOPLAY=0,
                  pff_YARDS_TO_GOAL_LINE=75, pff_OFF_TIMEOUTS_REMAINING=2)
    values.update(changes)
    return values


def final():
    return pd.DataFrame([dict(pff_GAMEID=1, team_a="RIBR", team_b="CTYA",
                              score_a=13, score_b=10, winner="RIBR")]).set_index("pff_GAMEID")


class WinningDriveTests(unittest.TestCase):
    def extract(self, rows, window=240):
        frame = pd.DataFrame(rows)
        return winning_drives(frame, drive_table(frame), final(), window)

    def test_uncapped_includes_early_q4_winning_drive(self):
        rows = [play(1, 700), play(2, 360),
                play(3, 350, pff_DRIVE=np.nan, pff_SPECIALTEAMSTYPE="FIELD GOAL",
                     pff_KICKRESULT="MADE - M", pff_DOWN=4)]
        winners, _ = self.extract(rows, window=None)
        self.assertEqual(len(winners), 1)
        self.assertEqual(winners.to_score_snap_seconds.iloc[0], 350)
        self.assertTrue(self.extract(rows, window=240)[0].empty)

    def test_uncapped_keeps_full_drive_across_quarter_boundary(self):
        rows = [play(1, 45, pff_QUARTER=3), play(2, 855),
                play(3, 852, pff_DRIVE=np.nan, pff_SPECIALTEAMSTYPE="FIELD GOAL",
                     pff_KICKRESULT="MADE - M", pff_DOWN=4)]
        winners, _ = self.extract(rows, window=None)
        self.assertEqual(len(winners), 1)
        self.assertEqual(winners.start_regulation_seconds.iloc[0], 945)
        self.assertEqual(winners.snap_span_seconds.iloc[0], 90)
        self.assertEqual(winners.to_score_snap_seconds.iloc[0], 93)
        self.assertTrue(self.extract(rows, window=900)[0].empty)

    def test_q3_winning_score_remains_outside_q4_analysis(self):
        winners, _ = self.extract([play(1, 120, pff_QUARTER=3)], window=None)
        self.assertTrue(winners.empty)

    def test_team_specific_drive_numbers_do_not_merge(self):
        frame = pd.DataFrame([
            play(1, 200),
            play(2, 170, pff_OFFTEAM="CTYA", pff_DEFTEAM="RIBR"),
        ])
        drives = drive_table(frame)
        self.assertEqual(len(drives), 2)
        self.assertEqual(drives.snaps.tolist(), [1, 1])
        self.assertEqual(drives.c_first.tolist(), [200, 170])

    def test_no_play_cannot_set_first_snap(self):
        frame = pd.DataFrame([play(1, 250, pff_NOPLAY=1), play(2, 230)])
        self.assertEqual(drive_table(frame).c_first.iloc[0], 230)

    def test_field_goal_without_drive_id_includes_setup_wait(self):
        winners, _ = self.extract([
            play(1, 120), play(2, 40),
            play(3, 3, pff_DRIVE=np.nan, pff_SPECIALTEAMSTYPE="FIELD GOAL",
                 pff_KICKRESULT="MADE - M", pff_DOWN=4),
        ])
        self.assertEqual(len(winners), 1)
        self.assertEqual(winners.to_score_snap_seconds.iloc[0], 117)
        self.assertEqual(winners.fg_setup_seconds.iloc[0], 37)

    def test_blocked_field_goal_not_counted_from_end_label(self):
        winners, audit = self.extract([
            play(1, 120),
            play(2, 3, pff_DRIVE=np.nan, pff_SPECIALTEAMSTYPE="FIELD GOAL",
                 pff_KICKRESULT="BLOCKED", pff_DOWN=4),
        ])
        self.assertTrue(winners.empty)
        self.assertIn("No verified", audit.status.iloc[0])

    def test_cannot_attach_kick_from_later_possession(self):
        winners, _ = self.extract([
            play(1, 120),
            play(2, 100, pff_DRIVE=2, pff_OFFTEAM="CTYA", pff_DEFTEAM="RIBR",
                 pff_DRIVEENDEVENT="PUNT"),
            play(3, 3, pff_DRIVE=np.nan, pff_SPECIALTEAMSTYPE="FIELD GOAL",
                 pff_KICKRESULT="MADE - M", pff_DOWN=4),
        ])
        self.assertTrue(winners.empty)

    def test_temporary_lead_does_not_count_as_decisive(self):
        winners, audit = self.extract([
            play(1, 120),
            play(2, 100, pff_DRIVE=np.nan, pff_SPECIALTEAMSTYPE="FIELD GOAL",
                 pff_KICKRESULT="MADE - M", pff_DOWN=4),
            play(3, 96, pff_DRIVE=np.nan, pff_SPECIALTEAMSTYPE="KICKOFF",
                 pff_OFFSCORE=13),
            play(4, 60, pff_DRIVE=2, pff_OFFTEAM="CTYA", pff_DEFTEAM="RIBR",
                 pff_OFFSCORE=13, pff_DEFSCORE=13, pff_DRIVEENDEVENT="PUNT"),
        ])
        self.assertTrue(winners.empty)
        self.assertIn("Lead did not hold", audit.status.iloc[0])

    def test_overtime_win_is_not_regulation_winning_drive(self):
        winners, audit = self.extract([
            play(1, 120), play(2, 900, pff_QUARTER=5, pff_DRIVE=2),
        ])
        self.assertTrue(winners.empty)
        # First possession remains a Q4 candidate; overtime is explicitly audited.
        self.assertEqual(audit.status.iloc[0], "Overtime game")

    def test_return_td_is_not_offensive_td(self):
        winners, _ = self.extract([
            play(1, 120, pff_DRIVEENDEVENT="TOUCHDOWN", pff_TOUCHDOWN="CTYA D01"),
        ])
        self.assertTrue(winners.empty)

    def test_percentiles_follow_empirical_cdf(self):
        self.assertEqual(percentile(pd.Series([0, 60, 120, 180]), .75), 120)


if __name__ == "__main__":
    unittest.main()
