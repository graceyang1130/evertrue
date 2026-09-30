"""Build the timeout report as an HTML file you can open and edit.

report_template.html holds all of the page's wording as plain HTML. Numbers in
it are written as {{name}}; this script fills them in from out/report_data.json
and embeds the same data for the charts.

By default the result is a complete HTML document (doctype, head, body) that
opens in any browser. --fragment writes the page without that wrapper, which is
the form the claude.ai artifact publisher expects.

Re-running this overwrites the output file. To keep wording changes through a
data refresh, make them in report_template.html.

Usage:
    python build_report.py
    python build_report.py --out ~/Desktop/timeouts.html
    python build_report.py --fragment --out /tmp/timeout_report.html
"""

import argparse
import json
import os
import re

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def pct(value):
    """A change in chance of winning, in percentage points: 0.35 -> '0.35%'."""
    return f"{value:.2f}%" if value < 1 else f"{value:.1f}%"


def clock(seconds):
    """150 -> '2:30'."""
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def r0(value):
    """Round half up (Python's round() sends 33.5 to 34 but 34.5 to 34)."""
    return int(np.floor(value + 0.5))


def fill_values(data):
    """Every {{name}} the template uses, formatted for reading."""
    rates, unused = data["audit"]["rates"], data["audit"]["unused"]
    close = data["close_losses"]
    scenario = data["scenario"]
    costs = [p["cost"] for p in data["penalty_costs"]]
    late = max(float(np.max(data["value_grid"][f"{side}|1"])) for side in ["ball", "def"])
    worst = max(abs(c["predicted"] - c["actual"]) for c in data["calibration"])
    seasons = data["meta"]["seasons"]
    ivy = scenario["ivy_history"]

    # play time (all FBS/FCS); totals are the sum of the rounded parts so the
    # sentences add up
    rows = {r["label"]: r for r in data["play_time"]["rows"]["all"]}
    kill, normal, kneel = (rows["Running out the clock: run"], rows["Normal run"],
                           rows["Kneel-down"])
    four_left = r0(data["play_time"]["four_minute_clock_left"])

    # the worked example: down 3, 2:00 left, their ball
    grid = data["value_grid"]["def|1"]
    example = grid[data["grid_lead"].index(-3)][data["grid_clock"].index(120)]

    reality = data["defense_reality"]
    brown = reality["brown"]

    return {
        "first_season": seasons[0],
        "last_season": seasons[-1],
        "last_week": data["meta"]["last_week"],
        "games": f"{data['meta']['games']:,}",
        "timeouts": f"{data['meta']['timeouts']:,}",
        "secs_def": r0(data["seconds_saved"]["def"]),
        "secs_ball": r0(data["seconds_saved"]["ball"]),
        "kill_live": r0(kill["live"]),
        "kill_dead": r0(kill["dead"]),
        "kill_total": r0(kill["live"]) + r0(kill["dead"]),
        "normal_dead": r0(normal["dead"]),
        "normal_total": r0(normal["live"]) + r0(normal["dead"]),
        "kneel_total": r0(kneel["live"]) + r0(kneel["dead"]),
        "four_left": four_left,
        "four_share3": f"{data['play_time']['four_minute_share_3s']:.0%}",
        "extra_per_snap": four_left - 1,
        "extra_per_set": 3 * (four_left - 1),
        "ex_value": pct(example),
        "ex_per_second": f"{example / data['seconds_saved']['def']:.2f}%",
        "need": clock(r0(data["drive_time"]["p75"] / 10) * 10),
        "need_n": f"{data['drive_time']['n']:,}",
        "need_fg": clock(r0((data["drive_time"]["a"] + 45 * data["drive_time"]["b"]) / 5) * 5),
        "need_td": clock(r0((data["drive_time"]["a"] + 75 * data["drive_time"]["b"]) / 5) * 5),
        "punt_net": r0(data["punt"]["net"]),
        "punt_floor": r0(data["punt"]["floor"]),
        "fg_range": data["punt"]["fg_range"],
        "dr_all_pct": f"{reality['all']['called_when_should']:.0%}",
        "dr_ivy_pct": f"{reality['ivy']['called_when_should']:.0%}",
        "dr_all_n": f"{reality['all']['should_call']:,}",
        "dr_lost": r0(reality["all"]["seconds_lost_when_missed"]),
        "brown_called": r0(brown["called_when_should"] * brown["should_call"]),
        "brown_should": brown["should_call"],
        "brown_lost_game": r0(brown["seconds_lost_per_game"]),
        "timeout_value": pct(data["option_value"]["one_score"]),
        "pen_low": pct(min(costs)),
        "pen_high": pct(max(costs)),
        "late_max": f"{late:.0f}%",
        "close_unused": sum(1 for g in close["brown_games"] if g["unused"] > 0),
        "close_n": len(close["brown_games"]),
        "close_brown_share": f"{close['brown_share_with_unused']:.0%}",
        "close_all_share": f"{close['ncaa_share_with_unused']:.0%}",
        "brown_total": f"{rates['Brown']['total']:.1f}",
        "ivy_total": f"{rates['Rest of Ivy']['total']:.1f}",
        "brown_play_clock": f"{rates['Brown']['play_clock']:.2f}",
        "ivy_play_clock": f"{rates['Rest of Ivy']['play_clock']:.2f}",
        "all_play_clock": f"{rates['All FBS/FCS']['play_clock']:.2f}",
        "brown_half": f"{unused['Brown']['half']:.1f}",
        "ivy_half": f"{unused['Rest of Ivy']['half']:.1f}",
        "all_half": f"{unused['All FBS/FCS']['half']:.1f}",
        "brown_end": f"{unused['Brown']['game']:.1f}",
        "ivy_end": f"{unused['Rest of Ivy']['game']:.1f}",
        "all_end": f"{unused['All FBS/FCS']['game']:.1f}",
        "cal_worst": f"{worst * 100:.1f}",
        "yale_3": f"{scenario['brown_vs_yale'][3]:.0f}%",
        "yale_0": f"{scenario['brown_vs_yale'][0]:.0f}%",
        "even_3": f"{scenario['even_teams'][3]:.0f}%",
        "even_0": f"{scenario['even_teams'][0]:.0f}%",
        "ivy_won": ivy["won"],
        "ivy_n": ivy["n"],
        "ivy_pct": f"{ivy['won'] / ivy['n']:.0%}",
        "pff_3": f"{scenario['pff'][3]}%",
    }


def fill(template, values):
    def swap(match):
        name = match.group(1)
        if name not in values:
            raise KeyError(f"template uses {{{{{name}}}}} but build_report.py has no value for it")
        return str(values[name])
    return re.sub(r"\{\{(\w+)\}\}", swap, template)


def ascii_only(page):
    """Escape non-ASCII so the page reads right whatever charset it is served with.

    Inside <script> a character becomes a JS \\uXXXX escape; elsewhere an HTML
    numeric entity.
    """
    head, _, rest = page.rpartition("<script>")
    script, _, tail = rest.partition("</script>")
    as_entity = lambda s: "".join(c if ord(c) < 128 else f"&#x{ord(c):x};" for c in s)
    as_js = "".join(c if ord(c) < 128 else f"\\u{ord(c):04x}" for c in script)
    return as_entity(head) + "<script>" + as_js + "</script>" + as_entity(tail)


def standalone(page):
    """Wrap the page in a full document: title, fonts and styles go in <head>."""
    head, sep, body = page.partition("</style>")
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
        f"{head}{sep}\n</head>\n<body>\n{body.lstrip()}\n</body>\n</html>\n"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=os.path.join(HERE, "out", "report_data.json"))
    parser.add_argument("--out", default=os.path.join(HERE, "out", "timeout_report.html"))
    parser.add_argument("--fragment", action="store_true",
                        help="skip the <html>/<head> wrapper (for publishing as an artifact)")
    args = parser.parse_args()

    with open(os.path.join(HERE, "report_template.html")) as handle:
        template = handle.read()
    with open(args.data) as handle:
        data = json.load(handle)

    page = fill(template, fill_values(data))
    page = page.replace("__REPORT_DATA__", json.dumps(data, separators=(",", ":")))
    page = ascii_only(page)
    if not args.fragment:
        page = standalone(page)

    out = os.path.expanduser(args.out)
    with open(out, "w") as handle:
        handle.write(page)
    print(f"wrote {out} ({len(page) / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
