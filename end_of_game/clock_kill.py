"""How much clock can we actually kill? -- end-of-game decision tool.

Answers the sideline question: with a lead, the ball, this much time, and the
opponent holding this many timeouts, can we end the game -- and if not, what do
we need and what do they get back?

HOW THE ARITHMETIC WORKS
------------------------
Each play costs the clock two chunks (see runoff_model.py):

    burn(n plays, T opponent timeouts) = n * live_ball + (n - T) * dead_ball

The opponent's best response is to spend a timeout on every dead-ball period
they can, so T timeouts erase T dead-ball chunks. The live-ball chunk is not
erasable -- that is the clock you are guaranteed to burn no matter what they do.

Downs are the constraint that makes this interesting. A set of downs buys three
plays; the fourth is a punt. So reaching 0:00 is not a question of time alone,
it is a question of how many first downs you must convert to get enough snaps.

WHOSE NUMBERS
-------------
Defaults to Brown's own measured rates, which matter because Brown is roughly
6 seconds per play faster than the Ivy average -- a tempo offense by identity.
Planning a four-minute drill off league numbers would promise about 40s a play
when Brown actually delivers 35s: over a six-play drive, half a possession of
imaginary clock. Pass --params to model a different team.

A KNEEL IS NOT A RUN, AND NOT ALWAYS BETTER. Victory formation takes the play
clock to the wire (~39s dead) but the snap itself is over instantly (~2s live).
A live run is the mirror: less dead ball (~33s, because Brown snaps with time to
spare and runs can end out of bounds) but far more live ball (~8s).

At 41s a cycle they are a wash -- until the opponent has timeouts. A timeout
erases dead-ball seconds and cannot touch live-ball seconds, so against
timeouts the RUN burns more clock than the kneel:

    3 snaps, opponent holding 3 timeouts:   kneel 0:06   run 0:24

That is counterintuitive and it is worth knowing, but it is a clock argument
only. A kneel cannot fumble and cannot lose yardage; a run can do both. Treat
the extra seconds as the price of risk, not as free money.

Usage:
    python clock_kill.py --clock 3:10 --opp-timeouts 2 --down 1
    python clock_kill.py --card                      # the sideline reference card
    python clock_kill.py --card --params params_ivy.json
"""

import argparse
import json
import math
import os

# Victory formation: the snap is surrendered instantly and the play clock is
# taken to the wire, so a kneel cycle is live-ball ~2s plus a near-full 40s.
KNEEL_LIVE = 2
KNEEL_DEAD = 39

DEFAULT_PARAMS = "params_brown.json"


def parse_clock(text):
    """'3:10' or '190' -> 190 seconds."""
    text = str(text).strip()
    if ":" in text:
        minutes, seconds = text.split(":")
        return int(minutes) * 60 + int(seconds)
    return int(text)


def fmt(seconds):
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


# --------------------------------------------------------------------------
# the model
# --------------------------------------------------------------------------

class Runoff:
    """Live-ball and dead-ball seconds for one team, in the kill regime."""

    def __init__(self, live, dead, source="?"):
        self.live = live
        self.dead = dead
        self.source = source

    @classmethod
    def from_params(cls, path, call="R", regime="kill"):
        with open(path) as handle:
            params = json.load(handle)
        cell = params["runoff"][regime][call]
        live = cell["live_ball"]["median"]
        dead = cell["dead_ball"]["median"]
        label = os.path.basename(path).replace("params_", "").replace(".json", "")
        return cls(live, dead, source=f"{label} {regime}-regime {'run' if call=='R' else 'pass'}")

    def burn(self, plays, opp_timeouts):
        """Clock burned by `plays` snaps against an opponent spending timeouts."""
        stopped = min(opp_timeouts, plays)
        return plays * self.live + (plays - stopped) * self.dead

    def plays_to_kill(self, time_left, opp_timeouts, cap=40):
        """Fewest snaps that burn `time_left`. None if the clock cannot be reached."""
        for plays in range(1, cap + 1):
            if self.burn(plays, opp_timeouts) >= time_left:
                return plays
        return None


def first_downs_needed(plays, down):
    """First downs required to get `plays` snaps, starting on `down`.

    A set of downs is worth three snaps -- the fourth is a punt -- so from 1st
    down you have three before you must convert.
    """
    in_hand = max(0, 4 - down)
    if plays <= in_hand:
        return 0
    return math.ceil((plays - in_hand) / 3)


def kneel_out(time_left, opp_timeouts, down=1):
    """Can victory formation alone end it from here?"""
    kneels = max(0, 4 - down)
    burned = (kneels * KNEEL_LIVE
              + max(0, kneels - opp_timeouts) * KNEEL_DEAD)
    return burned >= time_left, burned


# --------------------------------------------------------------------------
# single-situation report
# --------------------------------------------------------------------------

def report(runoff, time_left, opp_timeouts, down, lead=None):
    print("=" * 66)
    head = f"BROWN BALL -- {fmt(time_left)} left, {down}{_ord(down)} down, opp {opp_timeouts} TO"
    if lead is not None:
        head += f", up {lead}"
    print(head)
    print("=" * 66)
    print(f"model: {runoff.source}  ({runoff.live}s live + {runoff.dead}s dead per snap)")

    can_kneel, kneel_burn = kneel_out(time_left, opp_timeouts, down)
    print(f"\nVICTORY FORMATION: {'YES -- kneel it out' if can_kneel else 'NO'}"
          f"   ({max(0, 4-down)} kneels burn {fmt(kneel_burn)})")

    plays = runoff.plays_to_kill(time_left, opp_timeouts)
    if plays is None:
        print("\nCannot reach 0:00 by running plays from here.")
    else:
        downs = first_downs_needed(plays, down)
        print(f"\nTO REACH 0:00 BY RUNNING PLAYS:")
        print(f"  snaps needed      {plays}")
        print(f"  first downs needed {downs}")
        if downs == 0:
            print("  -> you can end it without converting. Stay in bounds.")
        else:
            print(f"  -> you must convert {downs} first down"
                  f"{'s' if downs > 1 else ''} or you are punting.")

    # what happens if the drive stalls
    in_hand = max(0, 4 - down)
    burned = runoff.burn(in_hand, opp_timeouts)
    left = time_left - burned
    their_to = max(0, opp_timeouts - in_hand)
    print(f"\nIF YOU GO THREE-AND-OUT ({in_hand} snaps):")
    print(f"  burns {fmt(burned)}  ->  punt with {fmt(left)} left, "
          f"they keep {their_to} TO")

    print("\nCLOCK COST OF THEIR TIMEOUTS (over the next {} snaps):".format(in_hand))
    print(f"  {'their TO':>9s} {'run':>8s} {'kneel':>8s}")
    for t in range(0, 4):
        run_burn = runoff.burn(in_hand, t)
        kneel_burn = (in_hand * KNEEL_LIVE + max(0, in_hand - t) * KNEEL_DEAD)
        print(f"  {t:>9d} {fmt(run_burn):>8s} {fmt(kneel_burn):>8s}")
    print("  (a timeout erases dead-ball seconds only -- live-ball seconds are")
    print("   yours no matter what, which is why runs outlast kneels vs timeouts)")


def _ord(n):
    return {1: "st", 2: "nd", 3: "rd", 4: "th"}.get(n, "th")


# --------------------------------------------------------------------------
# sideline reference card
# --------------------------------------------------------------------------

def card(runoff):
    print("=" * 74)
    print("CLOCK-KILL CARD -- Brown ball, leading, 1st & 10")
    print("=" * 74)
    print(f"model: {runoff.source}  ({runoff.live}s live + {runoff.dead}s dead per snap)")
    print("\ncell = first downs you must convert to reach 0:00")
    print("K = victory formation ends it   . = ends it on this set, no conversion\n")

    print(f"  {'clock':>7s} |" + "".join(f"{f'opp {t} TO':>11s}" for t in range(4)))
    print("  " + "-" * 8 + "+" + "-" * 44)
    for secs in range(30, 391, 30):
        row = f"  {fmt(secs):>7s} |"
        for t in range(4):
            can_kneel, _ = kneel_out(secs, t, down=1)
            if can_kneel:
                cell = "K"
            else:
                plays = runoff.plays_to_kill(secs, t)
                if plays is None:
                    cell = "--"
                else:
                    downs = first_downs_needed(plays, 1)
                    cell = "." if downs == 0 else str(downs)
            row += f"{cell:>11s}"
        print(row)

    print("\nreading it: at 3:00 with the opponent holding 2 timeouts, you need")
    print("the number in that cell in first downs, or you are handing the ball back.")
    print("\nCAVEATS")
    print("  - inside 2:00 a first down stops the clock to set the chains, so the")
    print("    last set of downs before 2:00 burns less than this card credits.")
    print("  - a play ending out of bounds kills the dead-ball chunk exactly like a")
    print("    timeout. These are expectations over real outcomes, not guarantees.")
    print("  - spread is wide (see runoff_model.py p25/p75). Treat a one-snap")
    print("    margin as no margin.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--params", default=DEFAULT_PARAMS,
                        help="runoff parameters JSON from runoff_model.py")
    parser.add_argument("--call", default="R", choices=["R", "P"])
    parser.add_argument("--clock", default=None, help="time remaining, e.g. 3:10")
    parser.add_argument("--opp-timeouts", type=int, default=3)
    parser.add_argument("--down", type=int, default=1)
    parser.add_argument("--lead", type=int, default=None)
    parser.add_argument("--card", action="store_true",
                        help="print the sideline reference card")
    args = parser.parse_args()

    runoff = Runoff.from_params(args.params, call=args.call)

    if args.card or args.clock is None:
        card(runoff)
    else:
        report(runoff, parse_clock(args.clock), args.opp_timeouts,
               args.down, args.lead)


if __name__ == "__main__":
    main()
