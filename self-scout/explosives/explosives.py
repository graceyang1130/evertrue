"""Self-scout: where do we give up big plays?

A big play is a run of 10+ yards or a pass (scrambles included) of 20+. Only
plays that stood count. One page, four views:
  by down                      share of plays that went big
  passes by how far it was     big passes by where the ball was caught
  thrown                       (behind the line, short, medium, deep)
  who was covering             defender PFF charted in coverage on big passes
  missed tackles               defenders who missed a tackle on a big play

Also writes explosive_plays.csv, every big play with game, clock, situation
and who was involved, sorted for pulling film.

Jersey numbers are as PFF charted them; a number that changed hands between
2025 and 2026 shows both seasons.

Usage:
    python self-scout/explosives/explosives.py "self-scout/blitz_102926/play_feed (1).csv"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from scout_common import (BIG_PASS, BIG_RUN, DOWN_NAMES, SMALL_SAMPLE, TEAM_CODE, board, footer,
                          games_line, load_snaps, out_dir_for, player, row, save, start_page)

DEPTHS = [("Behind the line", -np.inf, -1), ("Short (0-9 yds)", 0, 9),
          ("Medium (10-19 yds)", 10, 19), ("Deep (20+ yds)", 20, np.inf)]
TOP_PLAYERS = 8


def play_type(plays):
    return np.select([~plays["is_pass"], plays["pff_PASSRESULT"].eq("RUN")],
                     ["Run", "Scramble"], default="Pass")


def plural(n, word):
    return f"{n} {word}" + ("" if n == 1 else "es" if word.endswith("s") else "s")


def spot(to_goal):
    """Yards from our goal -> 'our 35' / 'their 20' / 'midfield'."""
    if to_goal == 50:
        return "midfield"
    return f"our {int(to_goal)}" if to_goal < 50 else f"their {int(100 - to_goal)}"


def film_list(plays):
    big = plays[plays["explosive"]].sort_values(["date", "pff_QUARTER", "pff_SORTORDER"])
    kind = play_type(big)
    detail = np.where(kind == "Run",
                      big["pff_RUNCONCEPTPRIMARY"].str.capitalize().fillna("")
                      + " · " + big["pff_POAACTUAL"].fillna(""),
                      "thrown " + big["pff_PASSDEPTH"].map(
                          lambda d: f"{d:.0f} yds" if pd.notna(d) else "?")
                      + " " + big["pff_PASSDIRECTION"].fillna(""))
    return pd.DataFrame({
        "season": big["season"], "date": big["date"].dt.strftime("%Y-%m-%d"),
        "opponent": big["opponent"], "quarter": big["pff_QUARTER"], "clock": big["pff_CLOCK"],
        "down": big["pff_DOWN"].map(DOWN_NAMES), "distance": big["pff_DISTANCE"],
        "ball_on": big["to_goal"].map(spot), "play": kind, "yards": big["gain"],
        "detail": np.where(kind == "Scramble", "QB scramble", detail),
        "our_rush": big["rush"].fillna(""), "box": big["box"], "front": big["front"],
        "in_coverage": big["pff_PASSCOVERAGE1"].map(player),
        "missed_tackles": big["pff_MISSEDTACKLE"].fillna("").str.split("; ").map(
            lambda codes: ", ".join(player(c) for c in codes if c)),
        "pff_play_id": big["pff_PLAYID"],
    })


def player_counts(plays, column, picked):
    """Big plays per defender named in `column`, with seasons and a base count."""
    named = plays[["season", column, "explosive"]].dropna(subset=[column]).copy()
    named[column] = named[column].str.split("; ")
    named = named.explode(column)
    named["player"] = named[column].map(player)
    out = named.groupby("player").agg(plays=("explosive", "size"), big=("explosive", "sum"),
                                      seasons=("season", lambda s: sorted(set(s))))
    out = out[out["big"] > 0].sort_values(["big", "plays"], ascending=[False, True])
    return out.head(picked)


def draw(plays, path):
    big = plays[plays["explosive"]]
    n_runs = int((~big["is_pass"]).sum())
    n_passes = len(big) - n_runs
    games = plays["pff_GAMEID"].nunique()

    passes = plays[plays["is_pass"]]
    big_passes = passes[passes["explosive"]]
    thrown_deep = (big_passes["pff_PASSDEPTH"] >= 20).sum()
    thrown = big_passes["pff_PASSDEPTH"].notna().sum()
    answer = (f"{len(big)} big plays in {games} games ({len(big) / games:.1f} a game): "
              f"{n_runs} runs of {BIG_RUN}+ and {n_passes} passes of {BIG_PASS}+. "
              f"{thrown_deep} of the {thrown} big completions were thrown 20+ yards downfield; "
              f"the other {thrown - thrown_deep} came on shorter throws.")
    width, height = 15, 10
    fig, top = start_page(width, height, "Where do we give up big plays?", answer,
                          f"{games_line(plays)} · {len(plays)} plays")

    # by down
    downs = []
    for down, name in DOWN_NAMES.items():
        group = plays[plays["pff_DOWN"] == down]
        b = group["explosive"]
        runs = int((b & ~group["is_pass"]).sum())
        downs.append(row(f"{name} down", 100 * b.mean(), len(group),
                         text=f"{100 * b.mean():.0f}%   {int(b.sum())} of {len(group)} "
                              f"({plural(runs, 'run')}, {plural(int(b.sum()) - runs, 'pass')})"))
    upper = (height - 5.6 - top - 0.55) / height
    ax = fig.add_axes([1.6 / width, 5.6 / height, 4.6 / width, upper])
    board(ax, [(None, downs)], title="Share of plays that went big, by down",
          xmax=max(r["value"] for r in downs) * 2.6)

    # by how far the pass was thrown
    depth = passes["pff_PASSDEPTH"]
    rows = []
    for label, low, high in DEPTHS:
        group = passes[depth.between(low, high)]
        rows.append(row(label, 100 * group["explosive"].mean(), len(group),
                        text=f"{100 * group['explosive'].mean():.0f}%   "
                             f"{int(group['explosive'].sum())} of {len(group)} throws"))
    scrambles = passes[passes["pff_PASSRESULT"].eq("RUN")]
    rows.append(row("QB scrambles", 100 * scrambles["explosive"].mean(), len(scrambles),
                    text=f"{100 * scrambles['explosive'].mean():.0f}%   "
                         f"{int(scrambles['explosive'].sum())} of {len(scrambles)} scrambles"))
    ax = fig.add_axes([9.4 / width, 5.6 / height, 4.6 / width, upper])
    board(ax, [(None, rows)], title=f"Passes: share that went {BIG_PASS}+, by throw distance",
          xmax=max(r["value"] for r in rows) * 2.2)

    # who was covering, who missed tackles
    for left, column, base, title in [
        (1.6, "pff_PASSCOVERAGE1", passes, f"Defender in coverage on {BIG_PASS}+ passes"),
        (9.4, "pff_MISSEDTACKLE", plays, "Missed a tackle on a big play"),
    ]:
        counts = player_counts(base, column, TOP_PLAYERS)
        unit = "targeted" if column == "pff_PASSCOVERAGE1" else "missed tackles in all"
        rows = [row(f"{name} ({', '.join(str(s) for s in r['seasons'])})", r["big"], r["plays"],
                    small=False, text=f"{plural(int(r['big']), 'big play')} · "
                                      f"{int(r['plays'])} {unit}")
                for name, r in counts.iterrows()]
        ax = fig.add_axes([left / width, 1.15 / height, 4.6 / width, 3.4 / height])
        board(ax, [(None, rows)], title=title, fmt="{:.0f}",
              xmax=max(r["value"] for r in rows) * 2.2)

    footer(fig, [
        f"Big play = run of {BIG_RUN}+ yards or pass of {BIG_PASS}+ (scrambles count as passes). "
        f"Striped bar: fewer than {SMALL_SAMPLE} plays behind it. Player lists show the top "
        f"{TOP_PLAYERS}, with the seasons each number appears.",
        "Coverage defender is the one PFF charted on the targeted receiver. Throw distance is "
        "how far past the line the ball was caught or thrown. Every big play is listed in "
        "explosive_plays.csv for film.",
    ])
    save(fig, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, help="PFF play-by-play export of our defensive games")
    parser.add_argument("--team", default=TEAM_CODE, help="PFF code of the defense to scout")
    parser.add_argument("--out", help="folder for the outputs (default: this script's folder)")
    args = parser.parse_args()

    snaps = load_snaps(args.csv, args.team)
    plays = snaps[snaps["counts"]]
    out_dir = out_dir_for(__file__, args.out)

    films = film_list(plays)
    films.to_csv(out_dir / "explosive_plays.csv", index=False)
    print(films.groupby(["season", "play"]).size().to_string())
    print(f"[saved] {out_dir / 'explosive_plays.csv'}")
    draw(plays, out_dir / "explosives.png")


if __name__ == "__main__":
    main()
