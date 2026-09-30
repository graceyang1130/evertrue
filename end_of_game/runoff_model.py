"""Expected clock runoff per play, for end-of-game clock management.

Estimates how much game clock a single play burns, from snap to the next snap,
out of PFF play-by-play exports. This is the input to clock_kill.py, which
answers the sideline question ("can we end this game?").

THE CORE IDEA
-------------
A "play" costs the game clock two separable chunks:

    snap-to-snap elapsed  =  live-ball time  +  dead-ball time

  * live-ball  -- snap to whistle. Always burns clock. ~6-8s.
  * dead-ball  -- whistle to next snap. Burns clock ONLY if the clock keeps
                  running. Killed outright by a timeout, an incompletion, a
                  play ending out of bounds, a score, or a penalty. ~27-35s.

Keeping these apart is the whole point. A blended "a run burns 31 seconds"
average cannot answer "what if they have two timeouts left?", because a timeout
removes the dead-ball chunk and leaves the live-ball chunk untouched.

The export has no clock-at-end-of-play field, so live-ball time is not directly
observed. It is recovered two independent ways, which agree:

  (a) On an incomplete pass the clock stops at the incompletion and restarts at
      the next snap, so the entire interval IS that play's live-ball time.
  (b) On a clock-running play, dead-ball time equals play-clock time consumed,
      which is (40 - play clock remaining at the next snap). The residual
      elapsed - dead-ball is live-ball time.

Run --validate to re-check that those two agree on the current data, plus the
timeout test: intervals with a charged timeout should collapse to live-ball only.

REGIME MATTERS MORE THAN ANYTHING ELSE
--------------------------------------
Teams deliberately milking the clock burn far more per play than the same call
in a neutral situation -- about 43s vs 33s for a run. Estimates are therefore
conditioned on regime, never pooled across it. Using an all-situations average
to plan a four-minute drill understates runoff by roughly a third.

Usage:
    python runoff_model.py brown_19t26.csv --team RIBR
    python runoff_model.py brown_19t26.csv --team RIBR --validate
    python runoff_model.py ivy_19t26.csv --out params_ivy.json

    from runoff_model import load_intervals, estimate
    params = estimate(load_intervals("brown_19t26.csv", team="RIBR"))
"""

import argparse
import json

import numpy as np
import pandas as pd

# The play clock is 40s from the end of the previous play; it resets to 25s
# after administrative stoppages. Dead-ball reconstruction uses the 40s case,
# which is every interval where the clock kept running.
PLAY_CLOCK = 40

# Runoff is conditioned on these. Call type and regime are the two big levers;
# result matters mainly because it determines whether the clock stopped.
CALLS = ["R", "P"]


# --------------------------------------------------------------------------
# interval construction
# --------------------------------------------------------------------------

def _clock_to_seconds(value):
    """'14:33' -> 873. Returns NaN on anything unparseable."""
    try:
        minutes, seconds = str(value).split(":")
        return int(minutes) * 60 + int(seconds)
    except (ValueError, AttributeError):
        return np.nan


def load_intervals(path, team=None, seasons=None):
    """Load a PFF export and build one row per snap-to-snap interval.

    An interval spans from this play's snap to the next play's snap. Intervals
    are built within (game, quarter) so a quarter break never becomes an
    interval. Special teams and clock-impossible intervals are dropped.

    team    -- restrict to this team's OFFENSIVE snaps (e.g. "RIBR" for Brown).
               None keeps every team, which is what you want for a baseline.
    seasons -- iterable of seasons to keep; None keeps all.
    """
    df = pd.read_csv(path, low_memory=False)

    if seasons is not None:
        df = df[df.pff_GAMESEASON.isin(seasons)]

    df["clock"] = df.pff_CLOCK.map(_clock_to_seconds)
    df["play_clock"] = pd.to_numeric(df.pff_PLAYCLOCK, errors="coerce")
    df["off_to"] = pd.to_numeric(df.pff_OFF_TIMEOUTS_REMAINING, errors="coerce")
    df["def_to"] = pd.to_numeric(df.pff_DEF_TIMEOUTS_REMAINING, errors="coerce")
    df["score_diff"] = pd.to_numeric(df.pff_SCOREDIFFERENTIAL, errors="coerce")

    df = df.sort_values(["pff_GAMEID", "pff_SORTORDER"]).reset_index(drop=True)

    # Look ahead to the next play, but never across a quarter boundary.
    by_period = df.groupby(["pff_GAMEID", "pff_QUARTER"])
    for source, target in [
        ("clock", "next_clock"),
        ("play_clock", "next_play_clock"),
        ("pff_OFFTEAM", "next_offense"),
        ("off_to", "next_off_to"),
        ("def_to", "next_def_to"),
    ]:
        df[target] = by_period[source].shift(-1)

    df["elapsed"] = df.clock - df.next_clock

    # Scrimmage plays only, with a physically possible interval. A 0s interval
    # is real (clock already stopped); >60s means a stoppage we can't see.
    keep = (
        df.pff_SPECIALTEAMSTYPE.isna()
        & df.pff_DOWN.between(1, 4)
        & df.elapsed.between(0, 60)
    )
    intervals = df[keep].copy()

    intervals = _classify(intervals)

    if team is not None:
        intervals = intervals[intervals.pff_OFFTEAM == team]

    return intervals


def _flag(series):
    """PFF writes these as 1/NaN rather than 1/0."""
    return pd.to_numeric(series, errors="coerce").fillna(0) == 1


def _classify(intervals):
    """Tag each interval with what stopped the clock, the regime, and the call."""
    same_possession = intervals.pff_OFFTEAM == intervals.next_offense

    # A timeout is charged during this dead-ball period if either side's count
    # drops before the next snap. A change of possession re-bases the counts,
    # so it only counts when possession is unchanged.
    intervals["timeout_used"] = same_possession & (
        (intervals.next_off_to < intervals.off_to)
        | (intervals.next_def_to < intervals.def_to)
    ).fillna(False)

    incomplete = intervals.pff_PASSRESULT.isin(
        ["INCOMPLETE", "THROWN AWAY", "BATTED PASS", "HIT AS THREW", "SPIKE"]
    )
    intervals["incomplete"] = incomplete

    # Before 2023 the clock stopped on every first down to set the chains.
    # From 2023 it runs except inside the last two minutes of a half.
    # pff_2MINUTE is PFF's 0/2/4 offense tag, not a clock flag, so read the clock.
    first_down = _flag(intervals.pff_FIRST_DOWN_GAINED)
    late = intervals.pff_QUARTER.isin([2, 4]) & (intervals.clock <= 120)
    chains_stop = first_down & (
        (intervals.pff_GAMESEASON <= 2022) | late
    )

    intervals["clock_stopped"] = (
        incomplete
        | _flag(intervals.pff_TOUCHDOWN)
        | _flag(intervals.pff_NOPLAY)
        | _flag(intervals.pff_TURNOVER)
        | ~same_possession
        | intervals.timeout_used
        | chains_stop
    )

    intervals["regime"] = _regime(intervals)
    intervals["call"] = intervals.pff_RUNPASS.where(
        intervals.pff_RUNPASS.isin(CALLS)
    )
    return intervals


def _regime(intervals):
    """Classify the clock intent of each snap.

    kill   -- leading late with the ball: actively burning clock.
    hurry  -- trailing late, or any two-minute drill: actively saving clock.
    normal -- everything else, where clock is not the primary consideration.
    """
    quarter = intervals.pff_QUARTER
    clock = intervals.clock
    lead = intervals.score_diff

    end_of_half = ((quarter == 2) | (quarter == 4)) & (clock <= 300)

    kill = (quarter == 4) & (lead > 0) & (clock <= 600)
    hurry = end_of_half & (lead <= 0)

    return np.select([kill, hurry], ["kill", "hurry"], default="normal")


# --------------------------------------------------------------------------
# estimation
# --------------------------------------------------------------------------

def _live_ball_estimate(intervals):
    """Recover live-ball seconds the two independent ways described up top."""
    # (a) direct: an incompletion's whole interval is its live-ball time
    direct = intervals[
        intervals.incomplete
        & (intervals.pff_OFFTEAM == intervals.next_offense)
        & ~_flag(intervals.pff_NOPLAY)
        & ~intervals.timeout_used
    ].elapsed

    # (b) residual: elapsed minus reconstructed dead-ball, on running-clock plays
    running = intervals[~intervals.clock_stopped & intervals.next_play_clock.notna()]
    residual = running.elapsed - (PLAY_CLOCK - running.next_play_clock)
    # trim physically impossible residuals; play clock is noisy in the tails
    residual = residual[(residual >= 0) & (residual <= 20)]

    return {
        "direct_incompletion": _summary(direct),
        "residual_running_clock": _summary(residual),
    }


def _summary(series):
    series = series.dropna()
    if series.empty:
        return {"n": 0}
    return {
        "n": int(series.size),
        "mean": round(float(series.mean()), 1),
        "median": round(float(series.median()), 1),
        "p25": round(float(series.quantile(0.25)), 1),
        "p75": round(float(series.quantile(0.75)), 1),
        "p90": round(float(series.quantile(0.90)), 1),
    }


def _cell(intervals):
    """Summarise one (regime, call) cell: total runoff and its live/dead split."""
    out = _summary(intervals.elapsed)
    if not out.get("n"):
        return out

    running = intervals[~intervals.clock_stopped]
    stopped = intervals[intervals.clock_stopped]

    out["pct_clock_stopped"] = round(100 * len(stopped) / len(intervals), 1)
    out["runoff_clock_running"] = _summary(running.elapsed)
    out["runoff_clock_stopped"] = _summary(stopped.elapsed)

    with_pc = running[running.next_play_clock.notna()]
    if len(with_pc):
        dead = PLAY_CLOCK - with_pc.next_play_clock
        out["dead_ball"] = _summary(dead)
        out["live_ball"] = _summary(
            (with_pc.elapsed - dead).clip(lower=0, upper=20)
        )
    return out


def estimate(intervals):
    """Produce the runoff parameters clock_kill.py needs."""
    params = {
        "n_intervals": int(len(intervals)),
        "seasons": sorted(int(s) for s in intervals.pff_GAMESEASON.unique()),
        "live_ball": _live_ball_estimate(intervals),
        "runoff": {},
        "timeout_effect": {},
    }

    for regime in ["kill", "normal", "hurry"]:
        block = intervals[intervals.regime == regime]
        params["runoff"][regime] = {
            call: _cell(block[block.call == call]) for call in CALLS
        }

    # What a charged timeout is worth: running-clock runoff minus timeout runoff.
    for call in CALLS:
        block = intervals[
            (intervals.call == call)
            & (intervals.pff_OFFTEAM == intervals.next_offense)
            & ~intervals.incomplete
            & ~_flag(intervals.pff_NOPLAY)
        ]
        charged = block[block.timeout_used].elapsed
        running = block[~block.clock_stopped].elapsed
        saved = None
        if len(charged) and len(running):
            saved = round(float(running.mean() - charged.mean()), 1)
        params["timeout_effect"][call] = {
            "clock_running": _summary(running),
            "timeout_charged": _summary(charged),
            "seconds_saved": saved,
        }
    return params


# --------------------------------------------------------------------------
# validation -- the four checks that proved the decomposition holds
# --------------------------------------------------------------------------

def validate(intervals):
    """Re-run the decomposition checks. Returns True if all pass."""
    live = _live_ball_estimate(intervals)
    direct = live["direct_incompletion"]
    residual = live["residual_running_clock"]

    print("\nVALIDATION")
    print("-" * 68)
    checks = []

    print(f"1. live-ball from incompletions   n={direct['n']:6d}  "
          f"median {direct.get('median')}s")
    ok = direct["n"] > 100 and 2 <= direct.get("median", 0) <= 12
    checks.append(("live-ball direct read is physical (2-12s)", ok))

    print(f"2. live-ball from clock residual  n={residual['n']:6d}  "
          f"median {residual.get('median')}s")
    ok = residual["n"] > 100 and 2 <= residual.get("median", 0) <= 12
    checks.append(("live-ball residual is physical (2-12s)", ok))

    gap = abs(direct.get("median", 0) - residual.get("median", 0))
    print(f"3. the two estimates agree        gap {gap:.1f}s")
    checks.append(("independent live-ball estimates agree within 4s", gap <= 4))

    print("4. timeout collapses the interval:")
    collapse_ok = True
    for call in CALLS:
        block = intervals[
            (intervals.call == call)
            & (intervals.pff_OFFTEAM == intervals.next_offense)
            & ~intervals.incomplete
        ]
        charged = block[block.timeout_used].elapsed
        running = block[~block.clock_stopped].elapsed
        if len(charged) < 20 or not len(running):
            print(f"     {call}: too few timeout intervals to test")
            continue
        print(f"     {call}: running median {running.median():.0f}s  ->  "
              f"timeout median {charged.median():.0f}s")
        collapse_ok &= charged.median() < running.median() - 10
    checks.append(("timeout intervals collapse toward live-ball", collapse_ok))

    print()
    for label, passed in checks:
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}")
    return all(passed for _, passed in checks)


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def print_report(params, label):
    print("=" * 68)
    print(f"EXPECTED CLOCK RUNOFF PER PLAY -- {label}")
    print("=" * 68)
    print(f"{params['n_intervals']} snap-to-snap intervals, "
          f"seasons {params['seasons'][0]}-{params['seasons'][-1]}")

    live = params["live_ball"]
    print(f"\nlive-ball time  {live['direct_incompletion'].get('median')}s "
          f"(from incompletions, n={live['direct_incompletion']['n']})  /  "
          f"{live['residual_running_clock'].get('median')}s "
          f"(from clock residual, n={live['residual_running_clock']['n']})")

    for regime in ["kill", "normal", "hurry"]:
        print(f"\n{regime.upper()} regime")
        print(f"  {'call':6s} {'n':>6s} {'median':>7s} {'mean':>6s} "
              f"{'p25':>5s} {'p75':>5s} {'stop%':>6s} {'live':>6s} {'dead':>6s}")
        for call in CALLS:
            c = params["runoff"][regime][call]
            if not c.get("n"):
                continue
            name = "run" if call == "R" else "pass"
            live_s = c.get("live_ball", {}).get("median", "-")
            dead_s = c.get("dead_ball", {}).get("median", "-")
            print(f"  {name:6s} {c['n']:6d} {c['median']:7.0f} {c['mean']:6.1f} "
                  f"{c['p25']:5.0f} {c['p75']:5.0f} {c['pct_clock_stopped']:5.0f}% "
                  f"{live_s:>6} {dead_s:>6}")

    print("\nTIMEOUT EFFECT (opponent stops the clock in the dead-ball period)")
    for call in CALLS:
        t = params["timeout_effect"][call]
        name = "run" if call == "R" else "pass"
        if t["seconds_saved"] is None:
            continue
        print(f"  {name:6s} running {t['clock_running']['mean']:5.1f}s "
              f"(n={t['clock_running']['n']})  ->  timeout "
              f"{t['timeout_charged']['mean']:5.1f}s "
              f"(n={t['timeout_charged']['n']})   saves "
              f"{t['seconds_saved']:.1f}s")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", help="PFF play-by-play export")
    parser.add_argument("--team", default=None,
                        help="restrict to this team's offensive snaps, e.g. RIBR")
    parser.add_argument("--out", default=None, help="write parameters to JSON")
    parser.add_argument("--validate", action="store_true",
                        help="re-run the decomposition checks")
    args = parser.parse_args()

    intervals = load_intervals(args.csv, team=args.team)
    params = estimate(intervals)
    print_report(params, args.team or args.csv)

    if args.validate:
        validate(intervals)

    if args.out:
        with open(args.out, "w") as handle:
            json.dump(params, handle, indent=2)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
