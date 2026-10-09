"""Measure clock-kill plays and the time saved by an offensive timeout.

The timeout comparison uses observed final-two-minute sequences in which an
offense hurried to the line and spiked the ball. The PFF export records the
clock at each snap, not at the whistle. We therefore estimate the time lost
after the prior play as:

    prior snap-to-spike gap - estimated prior live play + spike live play

First downs are reported separately because the NCAA clock stops while the
chains are set inside the final two minutes of each half.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from runoff_model import load_intervals


ROOT = Path(__file__).resolve().parents[1]
PBP = ROOT / "data" / "ncaa" / "pbp.csv.gz"
FCS_FILE = ROOT / "data" / "ncaa" / "fcs_team_codes.json"
OUT = ROOT / "output" / "pdf"
TEAM = "RIBR"
IVY = {"RIBR", "MAHA", "CTYA", "NJPR", "PAUN", "NHDA", "NYCN", "NYCL"}
PLAY_CLOCK = 40


def fcs_codes() -> dict[int, set[str]]:
    source = json.loads(FCS_FILE.read_text())
    base = set(source["base_codes"])
    result = {}
    for season, changes in source["season_adjustments"].items():
        result[int(season)] = (base | set(changes["add"])) - set(changes["remove"])
    return result


FCS = fcs_codes()


def is_fcs(frame: pd.DataFrame) -> pd.Series:
    return pd.Series(
        [team in FCS.get(int(season), set()) for team, season in zip(frame.pff_OFFTEAM, frame.pff_GAMESEASON)],
        index=frame.index,
    )


def clock_seconds(value) -> float:
    try:
        minutes, seconds = str(value).split(":")
        return int(minutes) * 60 + int(seconds)
    except (TypeError, ValueError):
        return np.nan


def stats(series: pd.Series) -> dict:
    values = pd.Series(series).dropna()
    if values.empty:
        return {"n": 0, "mean": None, "median": None, "p25": None, "p75": None}
    return {
        "n": int(len(values)),
        "mean": round(float(values.mean()), 1),
        "median": round(float(values.median()), 1),
        "p25": round(float(values.quantile(0.25)), 1),
        "p75": round(float(values.quantile(0.75)), 1),
    }


def add_groups(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["fcs"] = is_fcs(frame)
    frame["ivy"] = frame.pff_OFFTEAM.isin(IVY)
    frame["brown"] = frame.pff_OFFTEAM.eq(TEAM)
    return frame


def clock_kill_timing(intervals: pd.DataFrame) -> dict:
    intervals = add_groups(intervals)
    intervals["mode"] = pd.to_numeric(intervals.pff_2MINUTE, errors="coerce")
    intervals["kneel"] = intervals.pff_NON_TACKLE_TYPE.eq("TOOK A KNEE")
    intervals["wait"] = PLAY_CLOCK - intervals.next_play_clock
    intervals["live"] = (intervals.elapsed - intervals["wait"]).clip(0, 20)

    groups = {
        "FCS": intervals[intervals.fcs],
        "Ivy": intervals[intervals.ivy],
        "Brown": intervals[intervals.brown],
    }
    output = {}
    for group, frame in groups.items():
        output[group] = {}
        cells = {
            "four_minute_run": (frame["mode"] == 4) & (frame.call == "R") & ~frame.kneel,
            "kneel": frame.kneel,
        }
        for label, mask in cells.items():
            rows = frame[mask & ~frame.clock_stopped & frame.next_play_clock.notna()]
            live = stats(rows.live)
            wait = stats(rows["wait"])
            output[group][label] = {
                "n": live["n"],
                "live": live,
                "wait": wait,
                "modeled_total_mean": round(live["mean"] + wait["mean"], 1) if live["n"] else None,
            }
    return output


def spike_sequences(intervals: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    usecols = [
        "pff_PLAYID", "pff_GAMEID", "pff_GAMEDATE", "pff_GAMESEASON", "pff_QUARTER",
        "pff_DOWN", "pff_CLOCK", "pff_SORTORDER", "pff_OFFTEAM", "pff_DEFTEAM",
        "pff_RUNPASS", "pff_PASSRESULT", "pff_FIRST_DOWN_GAINED", "pff_PLAYCLOCK",
        "pff_OFF_TIMEOUTS_REMAINING", "pff_DEF_TIMEOUTS_REMAINING",
        "pff_SPECIALTEAMSTYPE", "pff_NOPLAY", "pff_TOUCHDOWN", "pff_TURNOVER",
        "pff_NON_TACKLE_TYPE", "pff_DRIVE", "pff_SCOREDIFFERENTIAL", "pff_2MINUTE",
    ]
    plays = pd.read_csv(PBP, usecols=usecols, low_memory=False)
    plays["clock"] = plays.pff_CLOCK.map(clock_seconds)
    plays = plays.sort_values(["pff_GAMEID", "pff_SORTORDER"])
    plays = plays[plays.pff_SPECIALTEAMSTYPE.isna() & plays.pff_DOWN.between(1, 4)].copy()
    by_period = plays.groupby(["pff_GAMEID", "pff_QUARTER"])
    previous = [
        "pff_PLAYID", "pff_OFFTEAM", "pff_DRIVE", "clock", "pff_RUNPASS", "pff_PASSRESULT",
        "pff_FIRST_DOWN_GAINED", "pff_NOPLAY", "pff_TOUCHDOWN", "pff_TURNOVER",
        "pff_NON_TACKLE_TYPE", "pff_OFF_TIMEOUTS_REMAINING", "pff_DEF_TIMEOUTS_REMAINING",
    ]
    for column in previous:
        plays[f"prev_{column}"] = by_period[column].shift(1)
    plays["next_clock"] = by_period.clock.shift(-1)

    rows = plays[plays.pff_PASSRESULT.eq("SPIKE")].copy()
    rows = rows[
        rows.pff_QUARTER.isin([2, 4])
        & rows.clock.le(120)
        & rows.prev_clock.le(120)
        & rows.pff_OFFTEAM.eq(rows.prev_pff_OFFTEAM)
        & rows.pff_DRIVE.eq(rows.prev_pff_DRIVE)
    ]

    numeric = lambda series: pd.to_numeric(series, errors="coerce")
    timeout_between = (
        numeric(rows.pff_OFF_TIMEOUTS_REMAINING).lt(numeric(rows.prev_pff_OFF_TIMEOUTS_REMAINING))
        | numeric(rows.pff_DEF_TIMEOUTS_REMAINING).lt(numeric(rows.prev_pff_DEF_TIMEOUTS_REMAINING))
    ).fillna(False)
    prior_stop = rows.prev_pff_PASSRESULT.isin(
        ["INCOMPLETE", "THROWN AWAY", "BATTED PASS", "HIT AS THREW", "SPIKE"]
    )
    prior_stop |= rows.prev_pff_NON_TACKLE_TYPE.eq("RAN OUT OF BOUNDS")
    prior_stop |= numeric(rows.prev_pff_NOPLAY).fillna(0).eq(1)
    prior_stop |= numeric(rows.prev_pff_TOUCHDOWN).fillna(0).eq(1)
    prior_stop |= numeric(rows.prev_pff_TURNOVER).fillna(0).eq(1)
    rows = rows[~timeout_between & ~prior_stop].copy()

    rows["snap_gap"] = rows.prev_clock - rows.clock
    rows["spike_live"] = rows.clock - rows.next_clock
    rows = rows[rows.snap_gap.between(1, 30) & rows.spike_live.between(0, 5)].copy()
    rows["first_down"] = numeric(rows.prev_pff_FIRST_DOWN_GAINED).fillna(0).eq(1)
    rows = add_groups(rows)

    model = add_groups(intervals)
    model["kneel"] = model.pff_NON_TACKLE_TYPE.eq("TOOK A KNEE")
    model["wait"] = PLAY_CLOCK - model.next_play_clock
    model["live"] = (model.elapsed - model["wait"]).clip(0, 20)
    model = model[
        model.pff_QUARTER.isin([2, 4]) & model.clock.le(120) & ~model.clock_stopped
        & model.next_play_clock.notna() & model.call.isin(["R", "P"]) & ~model.kneel
    ]

    groups = {
        "FCS": (rows[rows.fcs], model[model.fcs]),
        "Ivy": (rows[rows.ivy], model[model.ivy]),
        "Brown": (rows[rows.brown], model[model.brown]),
    }
    output, detail = {}, []
    for group, (sample, live_sample) in groups.items():
        estimates = live_sample.groupby("call").live.mean().to_dict()
        sample = sample.copy()
        sample["prior_live_estimate"] = sample.prev_pff_RUNPASS.map(estimates)
        sample["seconds_saved_by_timeout"] = (
            sample.snap_gap - sample.prior_live_estimate + sample.spike_live
        )
        sample = sample[sample.seconds_saved_by_timeout.between(0, 30)].copy()
        output[group] = {
            "all": stats(sample.seconds_saved_by_timeout),
            "after_first_down": stats(sample.loc[sample.first_down, "seconds_saved_by_timeout"]),
            "after_play_short_of_first_down": stats(sample.loc[~sample.first_down, "seconds_saved_by_timeout"]),
            "live_estimate_by_call": {
                call: {**stats(live_sample.loc[live_sample.call.eq(call), "live"])}
                for call in ["R", "P"]
            },
        }
        sample["group"] = group
        detail.append(sample)
    return output, pd.concat(detail, ignore_index=True)


def write_outputs() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    intervals = load_intervals(PBP)
    kill = clock_kill_timing(intervals)
    spike, detail = spike_sequences(intervals)
    result = {
        "sample": {"seasons": [2023, 2024, 2025, 2026], "games": 5578},
        "clock_kill": kill,
        "timeout_vs_spike": spike,
        "notes": [
            "Clock-kill timing includes only snaps for which the game clock kept running and the next play-clock reading was available.",
            "Timeout-versus-spike estimates remove the estimated live time of the preceding play because that play occurs under either choice.",
            "Brown has only two qualifying hurry-and-spike sequences; use the FCS estimate for planning.",
        ],
    }
    (OUT / "clock_option_analysis.json").write_text(json.dumps(result, indent=2))

    kill_rows = []
    for group, plays in kill.items():
        for play_type, values in plays.items():
            kill_rows.append({
                "group": group, "play_type": play_type, "n": values["n"],
                "live_mean": values["live"]["mean"], "wait_mean": values["wait"]["mean"],
                "modeled_total_mean": values["modeled_total_mean"],
            })
    pd.DataFrame(kill_rows).to_csv(OUT / "clock_kill_timing.csv", index=False)

    spike_rows = []
    for group, situations in spike.items():
        for situation in ["all", "after_first_down", "after_play_short_of_first_down"]:
            spike_rows.append({"group": group, "situation": situation, **situations[situation]})
    pd.DataFrame(spike_rows).to_csv(OUT / "timeout_vs_spike.csv", index=False)
    detail[[
        "group", "pff_GAMEID", "pff_PLAYID", "pff_GAMEDATE", "pff_GAMESEASON",
        "pff_OFFTEAM", "pff_QUARTER", "prev_clock", "clock", "first_down",
        "snap_gap", "spike_live", "prior_live_estimate", "seconds_saved_by_timeout",
    ]].to_csv(OUT / "timeout_vs_spike_detail.csv", index=False)
    return result


if __name__ == "__main__":
    result = write_outputs()
    print(json.dumps(result, indent=2))
