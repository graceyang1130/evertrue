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
