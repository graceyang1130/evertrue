"""Build the 4th-down card as an HTML file you can open and edit.

fourth_template.html holds all of the page's wording as plain HTML. Numbers in
it are written as {{name}}; this script fills them in from out/fourth_data.json
and embeds the same data for the card and charts. It shares the page tools in
tos/build_report.py, so the two pages behave the same way.

Re-running this overwrites the output file. To keep wording changes through a
data refresh, make them in fourth_template.html.

Usage:
    python build_card.py
    python build_card.py --fragment --out /tmp/fourth_down_card.html
"""

import argparse
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tos"))

from build_report import ascii_only, fill, r0, standalone  # noqa: E402


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


def fill_values(data):
    conv, fg, punt = data["conversion"], data["field_goal"], data["punt"]
    seasons = data["meta"]["seasons"]

    # Brown's shifts, said in football terms
    avg40 = sigmoid(fg["b0"] + fg["b_dist"] * 40)
    brown40 = sigmoid(fg["b0"] + fg["b_dist"] * 40 + fg["brown_shift"])
    conv_word = ("about average" if abs(conv["brown_shift"]) < 0.1
                 else "above average" if conv["brown_shift"] > 0 else "below average")
    punt_yards = punt["brown_shift"]
    punt_word = (f"about {abs(r0(punt_yards))} yards {'worse' if punt_yards > 0 else 'better'} than average"
                 if abs(punt_yards) >= 1 else "about average")

    return {
        "first_season": seasons[0],
        "last_season": seasons[-1],
        "games": f"{data['meta']['games']:,}",
        "conv_n": f"{conv['n']:,}",
        "fg_n": f"{fg['n']:,}",
        "brown_fg_n": fg["brown_n"],
        "brown_conv_note": f"{conv_word} ({conv['brown_n']} snaps)",
        "brown_fg_note": (f"{'below' if brown40 < avg40 else 'above'} average, about "
                          f"{brown40:.0%} from 40 yards against {avg40:.0%} ({fg['brown_n']} kicks)"),
        "brown_punt_note": f"{punt_word} ({punt['brown_n']} punts)",
        "punt_from30": r0(punt["a"] + punt["b"] * 70),
        "punt_from5": r0(punt["a"] + punt["b"] * 95),
        "punt_floor": r0(punt["floor"]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=os.path.join(HERE, "out", "fourth_data.json"))
    parser.add_argument("--out", default=os.path.join(HERE, "out", "fourth_down_card.html"))
    parser.add_argument("--fragment", action="store_true",
                        help="skip the <html>/<head> wrapper (for publishing as an artifact)")
    args = parser.parse_args()

    with open(os.path.join(HERE, "fourth_template.html")) as handle:
        template = handle.read()
    with open(args.data) as handle:
        data = json.load(handle)

    page = fill(template, fill_values(data))
    page = page.replace("__CARD_DATA__", json.dumps(data, separators=(",", ":")))
    page = ascii_only(page)
    if not args.fragment:
        page = standalone(page)

    out = os.path.expanduser(args.out)
    with open(out, "w") as handle:
        handle.write(page)
    print(f"wrote {out} ({len(page) / 1e3:.0f} KB)")


if __name__ == "__main__":
    main()
