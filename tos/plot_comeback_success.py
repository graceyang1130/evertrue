"""Late-game comeback success: every drive counted, not only the ones that worked.

The winning-drive percentiles (plot_winning_drives.py) look only at drives that
won. This asks the other question: when a drive starts at this time, this far
from the end zone, tied or behind, how often does it work?

Drives counted: FCS offenses, the drive's first snap in the 4th quarter with the
offense tied or behind by 1-8 (data/ncaa/pbp.csv.gz, 2023 through week 4 of 2026).
Time is the game clock at the drive's first snap.

Two outcomes per drive:
  won        the offense won the game (overtime wins count and are flagged)
  got_score  the drive got the score it needed: a TD or made FG when tied or down
             1-3, a TD when down 4-8

Charts, in output/plots/comeback_success/ (each with a CSV of its numbers):
  1a_win_by_time_all          chance of winning, 15-second windows, all scores on one chart
  1b_win_by_time_by_score     the same as bars, one panel per score
  2a_score_by_time_all        chance the drive gets the score it needs, all scores
  2b_score_by_time_by_score   the same as bars, one panel per score
  3_scored_then_lost          tied/down 1-3 drives that scored but still lost, 15-second windows
  4_pace_grid                 time left x yards to go: share that got the score
  5_seconds_per_yard          share that got the score, by seconds per yard to go
  6a_timeouts_all             time left x the offense's timeouts left: share that got the score
  6b_timeouts_by_score        the same grid, one per score

Charts 1 and 2 show raw counts, no smoothing. Their subtitles price one defensive
timeout as the median dead-ball seconds it saves while the other team runs out the
clock (Ivy, end_of_game/params_ivy.json), against a straight-line fit of the drives
starting in the last 4:00.

Run: MPLCONFIGDIR=/private/tmp/evertrue-mpl python3 tos/plot_comeback_success.py
     add --since 2024 to count only 2024 onward; that set goes in comeback_success/2024_onward/
     add --ivy for Ivy offenses only: just the bar panels of charts 1 and 2, in 15-second
     windows (1b, 2b) and whole minutes (1c, 2c), in comeback_success/ivy[_2024_onward]/
"""

from __future__ import annotations

import argparse
import json
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap, Normalize, to_rgb
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/plots/comeback_success"
IVY = {"RIBR", "NYCL", "NYCN", "NHDA", "MAHA", "PAUN", "NJPR", "CTYA"}

# Validated categorical slots 1-3 (dataviz reference palette, all-pairs safe).
STATES = {"Tied": "#2a78d6", "Down 1-3": "#eb6834", "Down 4-8": "#1baf7a"}
NAVY, INK, MUTED, GRID, SURFACE = "#193a59", "#1b2733", "#4a5d6b", "#e0e6eb", "#ffffff"
MIN_CELL = 10  # fewer drives than this and a grid cell, bar or dot is marked "too few"
WINDOW = 15    # seconds per bar / dot on charts 1 and 2
MAX_T = 360    # charts 1 and 2 cover drives starting in the last 6:00
TIME_BANDS = [(180, 240, "3:00-4:00"), (120, 180, "2:00-3:00"), (60, 120, "1:00-2:00"),
              (0, 60, "Last minute")]  # chart 6 columns, more time on the left
SHARE_CMAP = LinearSegmentedColormap.from_list(
    "blue", ["#eef4fc", "#86b6ef", "#2a78d6", "#104281"])


# ----------------------------------------------------------------------------- data

def late_drives(drives: pd.DataFrame, winners: pd.Series, ot_games: set) -> pd.DataFrame:
    """Pick the counted drives out of drive_table() and score both outcomes."""
    d = drives[drives.q_first.eq(4) & drives.fcs & drives.c_first.gt(0)].copy()
    d["margin"] = d.offscore - d.defscore
    d = d[d.margin.between(-8, 0)].copy()
    d["state"] = np.select([d.margin.eq(0), d.margin.ge(-3)], ["Tied", "Down 1-3"], "Down 4-8")
    d["need_td"] = d.margin.le(-4)
    d["got_score"] = np.where(d.need_td, d.end.eq("TOUCHDOWN"),
                              d.end.isin(["TOUCHDOWN", "FIELD GOAL"]))
    d["won"] = d.pff_GAMEID.map(winners).eq(d.offense)
    d["overtime"] = d.pff_GAMEID.isin(ot_games)
    d["scored_then_lost"] = d.got_score & ~d.won
    d["secs"] = d.c_first
    d["secs_at_last_snap"] = d.c_last
    d["ivy"] = d.offense.isin(IVY)
    return d.reset_index(drop=True)


def load() -> pd.DataFrame:
    from plot_winning_drives import drive_table, load_plays

    plays = load_plays()
    games = pd.read_csv(ROOT / "data/ncaa/games.csv").set_index("pff_GAMEID")
    ot_games = set(plays.loc[plays.pff_QUARTER.gt(4), "pff_GAMEID"])
    return late_drives(drive_table(plays), games.winner, ot_games)


def timeout_seconds() -> float:
    params = json.loads((ROOT / "end_of_game/params_ivy.json").read_text())
    return float(params["runoff"]["kill"]["R"]["dead_ball"]["median"])


def windows(d: pd.DataFrame, outcome: str, width: int, top: int = MAX_T) -> pd.DataFrame:
    """Raw counts: drives starting in each `width`-second window, and how many worked.

    A window holds drives with more than `starts_after` and at most `starts_by` left.
    """
    edges = np.arange(0, top + width, width)
    rows = []
    for state in STATES:
        sub = d[d.state.eq(state)]
        for lo, hi in zip(edges[:-1], edges[1:]):
            sel = sub[(sub.secs > lo) & (sub.secs <= hi)]
            rows.append(dict(state=state, window_seconds=width, starts_after=mmss(lo),
                             starts_by=mmss(hi), mid=(lo + hi) / 2, drives=len(sel),
                             worked=int(sel[outcome].sum()),
                             share=sel[outcome].mean() if len(sel) else np.nan))
    return pd.DataFrame(rows)


def scored_then_lost_windows(d: pd.DataFrame, width: int, top: int = 300) -> pd.DataFrame:
    """Tied/down 1-3 drives that got their score, by the window of time left at the last snap
    (a score with 0:00 left counts in the first window), and how many still lost."""
    scored = d[d.state.ne("Down 4-8") & d.got_score & d.secs_at_last_snap.le(top)]
    slot = np.maximum(np.ceil(scored.secs_at_last_snap / width), 1).astype(int)
    rows = []
    for k, (lo, hi) in enumerate(zip(range(0, top, width), range(width, top + width, width)), 1):
        sel = scored[slot.eq(k)]
        rows.append(dict(window_seconds=width, starts_after=mmss(lo), starts_by=mmss(hi),
                         mid=(lo + hi) / 2, scored=len(sel),
                         still_lost=int(sel.scored_then_lost.sum()),
                         share_lost=sel.scored_then_lost.mean() if len(sel) else np.nan))
    return pd.DataFrame(rows)


def ladder(d: pd.DataFrame, outcome: str) -> pd.DataFrame:
    """Share that worked per whole minute of time left (rows: state; columns: 0, 1, 2, ...)."""
    tab = windows(d, outcome, 60)
    return tab.assign(minute=(tab.mid // 60).astype(int)).pivot(
        index="state", columns="minute", values="share")


def per_minute(d: pd.DataFrame, state: str, outcome: str, top: int = 240) -> float:
    """Straight-line change in the share that worked per extra minute, last `top` seconds."""
    sub = d[d.state.eq(state) & d.secs.le(top)]
    return float(np.polyfit(sub.secs, sub[outcome].astype(float), 1)[0] * 60)


def timeout_grid(d: pd.DataFrame, outcome: str) -> pd.DataFrame:
    """Drives and successes by the offense's timeouts left x time-left band (last 4:00)."""
    rows = []
    for timeouts in (3, 2, 1, 0):
        for lo, hi, label in TIME_BANDS:
            sel = d[d.timeouts.eq(timeouts) & d.secs.gt(lo) & d.secs.le(hi)]
            rows.append(dict(timeouts=timeouts, time_left=label, drives=len(sel),
                             worked=int(sel[outcome].sum()),
                             share=sel[outcome].mean() if len(sel) else np.nan))
    return pd.DataFrame(rows)


def timeout_vs_time(d: pd.DataFrame, outcome: str, top: int = 240) -> dict:
    """Logistic fit on drives starting in the last `top` seconds: outcome ~ minutes left +
    timeouts left + yards to go + score. Effects are on the log-odds scale, with 95% ranges;
    timeout_in_seconds prices one timeout in clock with the same effect.
    """
    d = d[d.secs.le(top) & d.yards_to_goal.between(1, 99)]
    X = np.column_stack([np.ones(len(d)), d.secs / 60, d.timeouts, d.yards_to_goal / 10,
                         d.state.eq("Down 1-3"), d.state.eq("Down 4-8")]).astype(float)
    y = d[outcome].astype(float).to_numpy()
    b = np.zeros(X.shape[1])
    for _ in range(100):  # Newton steps
        p = 1 / (1 + np.exp(-X @ b))
        info = X.T @ (X * (p * (1 - p))[:, None])
        step = np.linalg.solve(info, X.T @ (y - p))
        b += step
        if np.abs(step).max() < 1e-9:
            break
    se = np.sqrt(np.diag(np.linalg.inv(info)))
    out = dict(drives=len(d))
    for name, i in (("per_minute", 1), ("per_timeout", 2)):
        out[name] = b[i]
        out[f"{name}_low"], out[f"{name}_high"] = b[i] - 1.96 * se[i], b[i] + 1.96 * se[i]
    out["timeout_in_seconds"] = b[2] / b[1] * 60
    return out


def behind_pace(secs: np.ndarray, yards: np.ndarray, tbins, ybins) -> np.ndarray:
    """For each yards x time cell: did most of its drives have under 1 second per yard?

    Rows follow ybins, columns follow tbins. A cell with no drives uses its middle.
    """
    ti = np.digitize(secs, tbins[1:-1], right=True)
    yi = np.digitize(yards, ybins[1:-1], right=True)
    out = np.zeros((len(ybins) - 1, len(tbins) - 1), dtype=bool)
    for r in range(out.shape[0]):
        for c in range(out.shape[1]):
            sel = (yi == r) & (ti == c)
            if sel.any():
                out[r, c] = (secs[sel] < yards[sel]).mean() > 0.5
            else:
                out[r, c] = (tbins[c] + tbins[c + 1]) / 2 < (ybins[r] + ybins[r + 1]) / 2
    return out


# ----------------------------------------------------------------------------- drawing

def mmss(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def drive_count(n) -> str:
    return f"{int(n)} drive" + ("" if int(n) == 1 else "s")


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def page(height: float = 6.9):
    fig = plt.figure(figsize=(11, height), facecolor=SURFACE)
    return fig


def header(fig, title: str, takeaway: str, context: str, foot: str):
    """Question as the title, the short answer under it, then what was counted."""
    lines = textwrap.wrap(takeaway, width=114)
    inch = 1 / fig.get_figheight()
    line_h = 11.5 * 1.45 / 72 * inch
    top = 1 - 0.24 * inch
    fig.text(0.07, top, title, fontsize=17, weight="bold", color=NAVY, va="top")
    fig.text(0.07, top - 0.42 * inch, "\n".join(lines), fontsize=11.5, color=INK, va="top",
             linespacing=1.45)
    fig.text(0.07, top - 0.42 * inch - len(lines) * line_h - 0.08 * inch,
             "\n".join(textwrap.wrap(context, width=150)), fontsize=9.5, color=MUTED, va="top",
             linespacing=1.4)
    fig.text(0.07, 0.17 * inch, foot, fontsize=8.5, color=MUTED, va="bottom", linespacing=1.4)


def style(ax, ygrid: bool = True):
    ax.set_facecolor(SURFACE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color("#9eabb5")
    ax.tick_params(colors=MUTED, labelsize=10, length=0)
    if ygrid:
        ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def time_axis(ax, labels: bool = True, pad: float = 4, top: int = MAX_T, step: int = 30):
    ax.set_xlim(top + 6, -6)  # the clock runs down left to right
    ticks = range(0, top + 1, step)
    ax.set_xticks(ticks)
    ax.set_xticklabels([mmss(t) for t in ticks] if labels else [])
    ax.tick_params(axis="x", pad=pad)
    ax.spines["bottom"].set_bounds(top, 0)


def count_key(ax, ramp, most: int, color: str, label: str = "Drives in the window"):
    """Small light-to-dark strip above the plot's top right: how many drives a shade means."""
    key = ax.inset_axes([0.80, 1.07, 0.18, 0.065])
    key.imshow(np.linspace(0, 1, 256)[None, :], cmap=ramp, aspect="auto", extent=[0, most, 0, 1])
    key.set_yticks([])
    key.set_xticks(sorted({t for t in (10, 25, 50) if t < most - 5} | {0, most}))
    key.xaxis.tick_top()
    key.tick_params(axis="x", length=2, pad=1.5, labelsize=8, colors=MUTED)
    for sp in key.spines.values():
        sp.set_color(color)
        sp.set_linewidth(0.6)
    key.text(-0.03, 0.5, label, transform=key.transAxes, ha="right", va="center",
             fontsize=8.5, color=MUTED)


def percent_axis(ax, step: int = 20):
    ax.set_ylim(0, 104)
    ax.set_yticks(range(0, 101, step))
    ax.set_yticklabels([f"{v}%" for v in range(0, 101, step)])


def chart_time_scatter(tab, d, ylabel, title, takeaway, foot, path):
    """Every 15-second window as a dot, all three scores together; dot size = drives."""
    fig = page(7.4)
    ax = fig.add_axes([0.08, 0.13, 0.88, 0.50])
    style(ax)
    nudge = dict(zip(STATES, (2.5, 0.0, -2.5)))  # keep the three dots in a window apart
    for state, color in STATES.items():
        sub = tab[tab.state.eq(state) & tab.drives.gt(0)]
        thin = sub.drives < MIN_CELL
        for mask, filled in ((~thin, True), (thin, False)):
            part = sub[mask]
            ax.scatter(part.mid + nudge[state], part.share * 100, s=part.drives * 7,
                       color=color if filled else SURFACE, edgecolors=SURFACE if filled else color,
                       linewidths=1.2 if filled else 1.6, zorder=3 if filled else 4)
    time_axis(ax)
    percent_axis(ax)
    ax.set_xlabel("Time left in the 4th quarter at the drive's first snap", color=MUTED,
                  fontsize=10.5)
    ax.set_ylabel(ylabel, color=MUTED, fontsize=10.5)

    counts = d[d.secs.le(MAX_T)].state.value_counts()
    who = [Line2D([], [], ls="", marker="o", ms=10, color=c, mec=SURFACE,
                  label=f"{s} ({counts.get(s, 0)} drives)") for s, c in STATES.items()]
    leg = ax.legend(handles=who, loc="lower left", bbox_to_anchor=(0, 1.02), frameon=False,
                    fontsize=10, ncol=3, handletextpad=0.3, columnspacing=1.4)
    for text in leg.get_texts():
        text.set_color(INK)
    ax.add_artist(leg)
    sizes = [Line2D([], [], ls="", marker="o", ms=np.sqrt(n * 7), color=MUTED, mec=SURFACE,
                    label=f"{n}") for n in (10, 25, 50)]
    sizes.append(Line2D([], [], ls="", marker="o", ms=np.sqrt(6 * 7), color=SURFACE, mec=MUTED,
                        mew=1.6, label="under 10"))
    size_leg = ax.legend(handles=sizes, loc="lower right", bbox_to_anchor=(1, 1.02),
                         frameon=False, fontsize=9.5, ncol=4, handletextpad=0.2,
                         columnspacing=0.9, title="Drives in the window:", title_fontsize=9.5,
                         alignment="left")
    plt.setp(size_leg.get_texts(), color=MUTED)
    size_leg.get_title().set_color(MUTED)
    header(fig, title, takeaway,
           f"Each dot is the drives that started in one {WINDOW}-second window (for example "
           f"1:45-2:00 left). Bigger dot = more drives; hollow = fewer than {MIN_CELL}.", foot)
    fig.savefig(path, dpi=190, facecolor=SURFACE)
    plt.close(fig)


def draw_cell(ax, x, y, cnt, share, small: bool = False):
    """One grid cell: share as a blue shade with the number on it; hatched if too few."""
    if cnt < MIN_CELL:
        ax.add_patch(plt.Rectangle((x, y), 1, 1, fc=SURFACE, ec=GRID, lw=1, hatch="///"))
        ax.text(x + 0.5, y + 0.5, f"{drive_count(cnt)}\ntoo few", ha="center", va="center",
                fontsize=7.5 if small else 8.5, color=MUTED)
        return
    ax.add_patch(plt.Rectangle((x, y), 1, 1, fc=SHARE_CMAP(float(min(share / 0.5, 1.0))),
                               ec=SURFACE, lw=2.5))
    dark = share > 0.27
    ax.text(x + 0.5, y + 0.6, pct(share), ha="center", va="center", fontsize=11.5 if small else 14,
            weight="bold", color="white" if dark else INK)
    ax.text(x + 0.5, y + 0.27, drive_count(cnt), ha="center", va="center",
            fontsize=7.5 if small else 8.5, color="white" if dark else MUTED)


def count_ramp(color: str) -> LinearSegmentedColormap:
    """One hue, light to dark: a pale tint for few drives, a deep shade for many."""
    base = np.array(to_rgb(color))
    light, dark = base + (1 - base) * 0.78, base * 0.5
    return LinearSegmentedColormap.from_list(color, [light, base, dark])


def shade_top(most_drives: int) -> int:
    """Darkest shade on the count scale: round up to tens, or the exact count under 10."""
    return int(np.ceil(most_drives / 10) * 10) if most_drives >= 10 else max(int(most_drives), 1)


def chart_time_panels(tab, d, ylabel, title, takeaway, foot, path, width: int = WINDOW):
    """The same windows as bars, one panel per score; darker bar = more drives."""
    fig = page(11.9)
    inch = 1 / 11.9
    height, gap, bottom = 2.0 * inch, 1.05 * inch, 1.25 * inch
    counts = d[d.secs.le(MAX_T)].state.value_counts()
    tab = tab[tab.window_seconds.eq(width)] if "window_seconds" in tab else tab
    most = shade_top(tab.drives.max())
    shade = Normalize(0, most)  # same scale in every panel: same darkness = same drives
    for k, (state, color) in enumerate(STATES.items()):
        ax = fig.add_axes([0.08, bottom + (2 - k) * (height + gap), 0.88, height])
        style(ax)
        ramp = count_ramp(color)
        sub = tab[tab.state.eq(state) & tab.drives.gt(0)]
        for row in sub.itertuples():
            ax.bar(row.mid, row.share * 100, width=width - 2.5, color=ramp(shade(row.drives)),
                   edgecolor=color, lw=0.8)
            if row.share == 0:
                ax.text(row.mid, 1.5, "0%", ha="center", va="bottom", fontsize=7.5, color=MUTED)
            ax.text(row.mid, -0.07, f"{row.drives}", transform=ax.get_xaxis_transform(),
                    ha="center", va="top", fontsize=7.5, color=MUTED)
        ax.text(-0.006, -0.07, "drives", transform=ax.transAxes, ha="right", va="top",
                fontsize=7.5, color=MUTED)
        time_axis(ax, pad=25, step=60 if width >= 60 else 30)
        percent_axis(ax, step=25)
        swatch = ax.text(0, 1.06, "■", transform=ax.transAxes, color=color, fontsize=14,
                         va="bottom")
        name = ax.annotate(f" {state}", xy=(1, 0), xycoords=swatch, fontsize=12.5,
                           weight="bold", color=INK, va="bottom")
        ax.annotate(f"   {counts.get(state, 0)} drives in the last 6:00", xy=(1, 0),
                    xycoords=name, fontsize=10, color=MUTED, va="bottom")
        count_key(ax, ramp, most, color,
                  "Drives in the minute" if width == 60 else "Drives in the window")
    fig.text(0.08, bottom - 0.74 * inch, "Time left in the 4th quarter at the drive's first "
             "snap", color=MUTED, fontsize=10.5, ha="left")
    fig.text(0.018, bottom + 1.5 * height + gap, ylabel, rotation=90, color=MUTED,
             fontsize=10.5, ha="center", va="center")
    span = "minute of time left" if width == 60 else f"{width}-second window"
    header(fig, title, takeaway,
           f"Each bar is the drives that started in one {span}. Darker bar = more "
           f"drives behind it; the number under each bar is how many.", foot)
    fig.savefig(path, dpi=190, facecolor=SURFACE)
    plt.close(fig)


# ----------------------------------------------------------------------------- charts

def chart_win(d, to_secs, foot, tab):
    m = ladder(d, "won")
    v = lambda state, minute: pct(m.loc[state, minute])
    slope = per_minute(d, "Down 4-8", "won") * 100
    takeaway = (f"Down 4-8, every minute counts: {v('Down 4-8', 0)} won when the drive started in "
                f"the last minute, {v('Down 4-8', 1)} with 1:00-2:00, {v('Down 4-8', 2)} with "
                f"2:00-3:00, {v('Down 4-8', 3)} with 3:00-4:00. That is about {slope:.0f} more "
                f"wins per 100 drives for each extra minute, about {slope * to_secs / 60:.0f} for "
                f"the {to_secs:.0f} seconds one defensive timeout saves. Tied and down 1-3 show no "
                f"steady climb inside 3:00 (down 1-3: {v('Down 1-3', 0)}, {v('Down 1-3', 1)}, "
                f"{v('Down 1-3', 2)}; tied: {v('Tied', 0)}, {v('Tied', 1)}, {v('Tied', 2)}): tied "
                f"teams that don't score still get overtime, and an early score leaves the other "
                f"side time to answer (chart 3).")
    title = "When the drive starts late, how often does that team win?"
    ylabel = "Share of these teams that won the game"
    chart_time_scatter(tab, d, ylabel, title, takeaway, foot, OUT / "1a_win_by_time_all.png")
    chart_time_panels(tab, d, ylabel, title, takeaway, foot, OUT / "1b_win_by_time_by_score.png")


def chart_score(d, to_secs, foot, tab):
    m = ladder(d, "got_score")
    v = lambda state, minute: pct(m.loc[state, minute])
    tied = per_minute(d, "Tied", "got_score") * 100
    td = per_minute(d, "Down 4-8", "got_score") * 100
    per_to = sorted(round(x * to_secs / 60) for x in (tied, td))
    takeaway = (f"More time clearly helps the drive itself. Starting in the last minute, "
                f"{v('Tied', 0)} of tied drives, {v('Down 1-3', 0)} of down 1-3 and "
                f"{v('Down 4-8', 0)} of down 4-8 got the score they needed; starting with 3:00-4:00 "
                f"left, {v('Tied', 3)}, {v('Down 1-3', 3)} and {v('Down 4-8', 3)}. Each extra "
                f"minute meant about {tied:.0f} more scores per 100 drives for tied teams and "
                f"{td:.0f} for teams needing a touchdown, so the {to_secs:.0f} seconds of one "
                f"defensive timeout goes with about {per_to[0]}-{per_to[1]} more per 100.")
    title = "How often does the drive get the score it needs?"
    ylabel = "Share of drives that got the score they needed"
    chart_time_scatter(tab, d, ylabel, title, takeaway, foot, OUT / "2a_score_by_time_all.png")
    chart_time_panels(tab, d, ylabel, title, takeaway, foot,
                      OUT / "2b_score_by_time_by_score.png")


def chart_scored_then_lost(d, foot):
    table = pd.concat([scored_then_lost_windows(d, w) for w in (WINDOW, 60)])
    table.drop(columns="mid").assign(share_lost=lambda f: (f.share_lost * 100).round(1)) \
        .to_csv(OUT / "3_scored_then_lost.csv", index=False)
    bars = table[table.window_seconds.eq(WINDOW) & table.scored.gt(0)]

    fig = page(7.4)
    ax = fig.add_axes([0.08, 0.16, 0.88, 0.47])
    style(ax)
    ramp = LinearSegmentedColormap.from_list(
        "navy", [np.array(to_rgb(NAVY)) + (1 - np.array(to_rgb(NAVY))) * 0.8, NAVY])
    most = int(np.ceil(bars.scored.max() / 10) * 10)
    shade = Normalize(0, most)
    for row in bars.itertuples():
        ax.bar(row.mid, row.share_lost * 100, width=WINDOW - 2.5, color=ramp(shade(row.scored)),
               edgecolor=NAVY, lw=0.8)
        if row.share_lost == 0:
            ax.text(row.mid, 1.5, "0%", ha="center", va="bottom", fontsize=7.5, color=MUTED)
        ax.text(row.mid, -0.05, f"{row.scored}", transform=ax.get_xaxis_transform(),
                ha="center", va="top", fontsize=7.5, color=MUTED)
    ax.text(-0.006, -0.05, "scored", transform=ax.transAxes, ha="right", va="top",
            fontsize=7.5, color=MUTED)
    time_axis(ax, pad=22, top=300)
    percent_axis(ax, step=25)
    count_key(ax, ramp, most, NAVY, "Scoring drives in the window")
    ax.set_xlabel("Time left when the drive scored (clock at its last snap)", color=MUTED,
                  fontsize=10.5)
    ax.set_ylabel("Scored, but still lost the game", color=MUTED, fontsize=10.5)

    s = table[table.window_seconds.eq(60)].set_index("starts_by").share_lost
    takeaway = (f"Tied or down 1-3 teams that scored with 2:00-3:00 left still lost "
                f"{pct(s['3:00'])} of the time; with 1:00-2:00 left, {pct(s['2:00'])}; scoring in "
                f"the last minute, only {pct(s['1:00'])}. That is why the chance of winning "
                f"(chart 1) moves so little for these teams: time saved for our drive is also "
                f"time left for theirs.")
    header(fig, "Score too early and they can still answer", takeaway,
           f"Tied or down 1-3 drives that got the score they needed, by the {WINDOW}-second window "
           f"they scored in. Darker bar = more scoring drives; the number under each bar is how "
           f"many. Includes overtime losses.", foot)
    fig.savefig(OUT / "3_scored_then_lost.png", dpi=190, facecolor=SURFACE)
    plt.close(fig)


def chart_pace_grid(d, foot):
    late = d[d.secs.le(300) & d.yards_to_goal.between(1, 99)].copy()
    tbins = [0, 30, 60, 90, 120, 180, 240, 300]
    ybins = [0, 49, 64, 74, 84, 99]
    ylabels = ["Inside 50", "50-64", "65-74", "75-84", "85-99"]
    late["tb"] = pd.cut(late.secs, tbins, right=True)
    late["yb"] = pd.cut(late.yards_to_goal, ybins, right=True, labels=ylabels)
    tab = late.groupby(["yb", "tb"], observed=False).got_score.agg(["size", "sum"])
    tab["share"] = tab["sum"] / tab["size"]
    n = tab["size"].unstack().to_numpy()
    r = tab["share"].unstack().to_numpy()
    behind = behind_pace(late.secs.to_numpy(float), late.yards_to_goal.to_numpy(float),
                         tbins, ybins)
    out = tab.reset_index()
    out["tb"] = [f"{mmss(i.left)}-{mmss(i.right)}" for i in out.tb]
    out["most_under_1_sec_per_yard"] = behind.ravel()
    out.rename(columns={"yb": "yards_to_go", "tb": "time_left", "size": "drives",
                        "sum": "got_score"}).assign(share=lambda f: (f.share * 100).round(1)) \
        .to_csv(OUT / "4_pace_grid.csv", index=False)

    fig = page(7.2)
    ax = fig.add_axes([0.135, 0.14, 0.835, 0.59])
    nt, ny = len(tbins) - 1, len(ybins) - 1
    for yi in range(ny):
        for ti in range(nt):
            # more time on the left; the clock runs down left to right
            draw_cell(ax, nt - 1 - ti, yi, n[yi, ti], r[yi, ti])

    # Staircase along the cell edges: right of it, most drives had under 1 second per yard.
    line = dict(color=INK, lw=2.4, ls=(0, (4, 2.5)), zorder=5, solid_capstyle="butt")
    for yi in range(ny):
        for ti in range(nt):
            if not behind[yi, ti]:
                continue
            x = nt - 1 - ti
            if ti + 1 < nt and not behind[yi, ti + 1]:  # the cell with more time sits left
                ax.plot([x, x], [yi, yi + 1], **line)
            if yi > 0 and not behind[yi - 1, ti]:  # the cell nearer the end zone sits below
                ax.plot([x, x + 1], [yi, yi], **line)
    top_x = nt - behind[-1].sum()
    ax.plot([top_x, top_x], [ny, ny + 0.16], **line)
    ax.text(top_x - 0.06, ny + 0.08, "Most drives right of this line had less than 1 second "
            "per yard (\"50 yards, 50 seconds\")", fontsize=9.5, color=INK, ha="right",
            va="center")
    ax.set_xlim(0, nt)
    ax.set_ylim(0, ny + 0.4)
    ax.set_xticks(np.arange(nt + 1))
    ax.set_xticklabels([mmss(t) for t in tbins[::-1]])
    ax.set_yticks(np.arange(ny) + 0.5)
    ax.set_yticklabels(ylabels, fontsize=10.5, color=INK)
    ax.tick_params(colors=MUTED, labelsize=10, length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.set_xlabel("Time left at the drive's first snap", color=MUTED, fontsize=10.5)
    ax.set_ylabel("Yards to the end zone at the first snap", color=MUTED, fontsize=10.5,
                  labelpad=10)

    by_time = late.groupby(pd.cut(late.secs, [0, 30, 60, 300]), observed=False).got_score.mean()
    typical = late[late.yards_to_goal.between(65, 84) & late.secs.gt(60)]
    takeaway = (f"With under 30 seconds, only {pct(by_time.iloc[0])} of drives got the score they "
                f"needed; with 0:30-1:00, {pct(by_time.iloc[1])}; with more than a minute, "
                f"{pct(by_time.iloc[2])}. The big drop is inside the last minute. From our own "
                f"16-35 (most drives after a kickoff or punt) with over a minute left, "
                f"{pct(typical.got_score.mean())} got there.")
    header(fig, "How far and how fast: when does the drive run out of time?", takeaway,
           "Share of drives that got the score they needed (FG if tied or down 1-3, TD if down "
           "4-8). Hatched = fewer than 10 drives.", foot)
    fig.savefig(OUT / "4_pace_grid.png", dpi=190, facecolor=SURFACE)
    plt.close(fig)


def chart_seconds_per_yard(d, foot):
    late = d[d.secs.le(300) & d.yards_to_goal.between(1, 99)].copy()
    late["spy"] = late.secs / late.yards_to_goal
    edges = [0, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, np.inf]
    labels = ["Under 0.5", "0.5-0.75", "0.75-1", "1-1.5", "1.5-2", "2-3", "3 or more"]
    late["bin"] = pd.cut(late.spy, edges, right=False, labels=labels)
    tab = late.groupby(["state", "bin"], observed=False).got_score.agg(["size", "sum"])
    tab["share"] = tab["sum"] / tab["size"]
    tab.reset_index().rename(columns={"bin": "seconds_per_yard", "size": "drives",
                                      "sum": "got_score"}) \
        .assign(share=lambda f: (f.share * 100).round(1)) \
        .to_csv(OUT / "5_seconds_per_yard.csv", index=False)

    fig = page(7.2)
    ax = fig.add_axes([0.08, 0.16, 0.88, 0.54])
    style(ax)
    width = 0.26
    x = np.arange(len(labels))
    for k, (state, color) in enumerate(STATES.items()):
        for xi, label in zip(x, labels):
            cnt, share = tab.loc[(state, label), "size"], tab.loc[(state, label), "share"]
            xpos = xi + (k - 1) * (width + 0.02)
            if cnt == 0:
                continue
            thin = cnt < MIN_CELL
            ax.bar(xpos, share * 100, width=width, color=SURFACE if thin else color,
                   edgecolor=color, hatch="///" if thin else None, lw=1.2 if thin else 0,
                   label=state if xi == 0 else None)
            ax.text(xpos, share * 100 + 1, f"{share * 100:.0f}", ha="center", va="bottom",
                    fontsize=9, color=INK)
    ax.axvline(2.5, color=INK, lw=1.6, ls=(0, (5, 3)))
    ax.text(2.45, 78, "behind pace", ha="right", va="top", fontsize=10, color=INK, weight="bold")
    ax.text(2.55, 78, "on pace (1 second per yard or more)", ha="left", va="top", fontsize=10,
            color=INK, weight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10.5, color=INK)
    ax.set_ylim(0, 80)
    ax.set_yticks(range(0, 81, 20))
    ax.set_yticklabels([f"{v}%" for v in range(0, 81, 20)])
    ax.set_xlabel("Seconds left per yard to go at the first snap (75 yards at 1:15 = 1 second "
                  "per yard)", color=MUTED, fontsize=10.5)
    ax.set_ylabel("Share of drives that got the score they needed", color=MUTED, fontsize=10.5)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.01), frameon=False, fontsize=10, ncol=3)

    behind = late[late.spy < 1].got_score.mean()
    ahead = late[late.spy >= 1].got_score.mean()
    td = late[late.need_td]
    pooled = late.groupby("bin", observed=False).got_score.mean()
    takeaway = (f"Behind the 1-second-per-yard pace, {pct(behind)} of drives got the score they "
                f"needed; on pace or ahead, {pct(ahead)}. Needing a touchdown: "
                f"{pct(td[td.spy < 1].got_score.mean())} behind pace, "
                f"{pct(td[td.spy >= 1].got_score.mean())} on pace. All teams together: "
                f"{pct(pooled['Under 0.5'])} under half a second per yard, "
                f"{pct(pooled['1-1.5'])} at 1-1.5, {pct(pooled['3 or more'])} at 3 or more.")
    header(fig, "Is \"50 yards, 50 seconds\" the right pace?", takeaway,
           "Numbers on bars are percentages. Yards are to the end zone for every team, though a "
           "field goal needs fewer. Hatched = fewer than 10 drives.", foot)
    fig.savefig(OUT / "5_seconds_per_yard.png", dpi=190, facecolor=SURFACE)
    plt.close(fig)


def timeout_axes(ax, labels: bool = True):
    ax.set_xlim(0, len(TIME_BANDS))
    ax.set_ylim(0, 4)
    ax.set_xticks(np.arange(len(TIME_BANDS)) + 0.5)
    ax.set_xticklabels([b[2] for b in TIME_BANDS], color=INK)
    ax.set_yticks(np.arange(4) + 0.5)
    ax.set_yticklabels(["No timeouts", "1 timeout", "2 timeouts", "3 timeouts"] if labels else [],
                       color=INK)
    ax.tick_params(colors=MUTED, labelsize=10, length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)


def fill_timeout_grid(ax, tab, small: bool = False):
    columns = [b[2] for b in TIME_BANDS]
    for row in tab.itertuples():
        draw_cell(ax, columns.index(row.time_left), row.timeouts, row.drives, row.share, small)


def chart_timeouts(d, foot):
    late = d[d.secs.le(240)]
    tabs = {"All scores": timeout_grid(late, "got_score")}
    tabs.update({state: timeout_grid(late[late.state.eq(state)], "got_score") for state in STATES})
    pd.concat([t.assign(score=k) for k, t in tabs.items()]) \
        .assign(share=lambda f: (f.share * 100).round(1)) \
        [["score", "timeouts", "time_left", "drives", "worked", "share"]] \
        .to_csv(OUT / "6_timeouts.csv", index=False)

    check = timeout_vs_time(late, "got_score")
    pd.DataFrame([check]).round(3).to_csv(OUT / "6_timeouts_check.csv", index=False)
    g = tabs["All scores"].set_index(["timeouts", "time_left"]).share

    def column(band):
        return ", ".join(f"{pct(g[t, band])} with {name}"
                         for t, name in ((3, "3"), (2, "2"), (1, "1"), (0, "none")))

    time_says = ("more time clearly did" if check["per_minute_low"] > 0
                 else "time showed no clear lift either")
    if check["per_timeout_low"] > 0:
        verdict = (f"each extra timeout went with about as much as "
                   f"{check['timeout_in_seconds']:.0f} more seconds of clock.")
    elif check["per_timeout_high"] < 0:
        verdict = f"more timeouts went with slightly fewer scores, while {time_says}."
    else:
        verdict = f"the number of timeouts showed no clear lift; {time_says}."
    takeaway = (f"Look down a column to compare teams with the same time left. With 1:00-2:00 "
                f"left: {column('1:00-2:00')}. In the last minute: {column('Last minute')}. "
                f"Lining up drives with the same time left, field position and score, {verdict}")
    title = "Does having timeouts left help the drive as much as having time?"
    what = ("Share of drives that got the score they needed (FG if tied or down 1-3, TD if down "
            "4-8), by the offense's timeouts left at the first snap. Hatched = fewer than 10 drives.")

    fig = page(7.2)
    ax = fig.add_axes([0.16, 0.14, 0.80, 0.56])
    fill_timeout_grid(ax, tabs["All scores"])
    timeout_axes(ax)
    ax.set_xlabel("Time left at the drive's first snap", color=MUTED, fontsize=10.5)
    header(fig, title, takeaway, what, foot)
    fig.savefig(OUT / "6a_timeouts_all.png", dpi=190, facecolor=SURFACE)
    plt.close(fig)

    fig = page(6.6)
    counts = late.state.value_counts()
    for k, (state, color) in enumerate(STATES.items()):
        ax = fig.add_axes([0.125 + k * 0.29, 0.15, 0.265, 0.5])
        fill_timeout_grid(ax, tabs[state], small=True)
        timeout_axes(ax, labels=k == 0)
        ax.tick_params(axis="x", labelsize=8.5)
        swatch = ax.text(0, 1.03, "\u25A0", transform=ax.transAxes, color=color, fontsize=13,
                         va="bottom")
        name = ax.annotate(f" {state}", xy=(1, 0), xycoords=swatch, fontsize=12, weight="bold",
                           color=INK, va="bottom")
        ax.annotate(f"  {counts.get(state, 0)} drives", xy=(1, 0), xycoords=name, fontsize=9.5,
                    color=MUTED, va="bottom")
    fig.text(0.545, 0.085, "Time left at the drive's first snap", color=MUTED, fontsize=10.5,
             ha="center")
    header(fig, title, takeaway, what.replace("Share of drives", "Split by score: share of "
                                              "drives"), foot)
    fig.savefig(OUT / "6b_timeouts_by_score.png", dpi=190, facecolor=SURFACE)
    plt.close(fig)


def x_of_y(worked: pd.Series) -> str:
    return f"{int(worked.sum())} of {len(worked)}" if len(worked) else "no drives"


def two_bands(d: pd.DataFrame, outcome: str) -> str:
    """Per score: successes inside the last 2:00 vs with 2:00-4:00 left, as 'x of n'."""
    parts = []
    for state in STATES:
        sub = d[d.state.eq(state)]
        late, early = sub[sub.secs.le(120)], sub[sub.secs.gt(120) & sub.secs.le(240)]
        parts.append(f"{state.lower()} {x_of_y(late[outcome])} vs {x_of_y(early[outcome])}")
    return "; ".join(parts)


def ivy_charts(d: pd.DataFrame, fcs_drives: int, foot: str) -> None:
    """Charts 1 and 2 as bar panels for Ivy offenses only, 15-second and 1-minute windows.

    The sample is small, so the subtitle gives raw counts in two wide bands instead of
    the FCS charts' minute-by-minute rates and fitted slopes.
    """
    n = int(d.secs.le(MAX_T).sum())
    times = round(fcs_drives / n)
    for outcome, verb, title, ylabel, stem in (
            ("won", "won the game", "When an Ivy team's drive starts late, how often does it win?",
             "Share of these teams that won the game", "win"),
            ("got_score", "got the score they needed",
             "How often does an Ivy team's late drive get the score it needs?",
             "Share of drives that got the score they needed", "score")):
        takeaway = (f"Only {n} Ivy drives fit, so a bar is a handful of drives and one drive can "
                    f"swing it from 0% to 100%. Pooled into two bands (drive starting inside the "
                    f"last 2:00 vs with 2:00-4:00 left), teams {verb}: {two_bands(d, outcome)}. "
                    f"Too few to stand alone; the all-FCS version of this chart has about {times} "
                    f"times as many drives.")
        tab = pd.concat([windows(d, outcome, w) for w in (WINDOW, 60)])
        k = "1" if outcome == "won" else "2"
        chart_time_panels(tab, d, ylabel, title, takeaway, foot,
                          OUT / f"{k}b_{stem}_by_time_by_score.png", width=WINDOW)
        chart_time_panels(tab, d, ylabel, title, takeaway, foot,
                          OUT / f"{k}c_{stem}_by_minute_by_score.png", width=60)


def time_csv(d: pd.DataFrame, outcome: str) -> pd.DataFrame:
    """15-second windows (the charts) and whole minutes (the subtitles), shares in percent."""
    tab = pd.concat([windows(d, outcome, w) for w in (WINDOW, 60)])
    return tab.drop(columns="mid").assign(share=lambda f: (f.share * 100).round(1))


def main() -> None:
    global OUT
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", type=int, help="count only this season onward")
    parser.add_argument("--ivy", action="store_true",
                        help="Ivy offenses only; draws just the bar panels of charts 1 and 2")
    args = parser.parse_args()
    folder = f"{args.since}_onward" if args.since else ""
    if args.ivy:
        folder = "ivy" + (f"_{folder}" if folder else "")
    OUT = OUT / folder if folder else OUT
    OUT.mkdir(parents=True, exist_ok=True)
    for old in ("1_win_by_time.png", "2_score_by_time.png"):  # replaced by the 1a/1b, 2a/2b pairs
        (OUT / old).unlink(missing_ok=True)
    d = load()
    if args.since:
        d = d[d.season.ge(args.since)].reset_index(drop=True)
    fcs_drives = int(d.secs.le(MAX_T).sum())
    if args.ivy:
        d = d[d.ivy].reset_index(drop=True)
    to_secs = timeout_seconds()
    cohort = d[d.secs.le(MAX_T)]
    who = ("Ivy League offenses (any opponent)" if args.ivy else "FCS offenses")
    ivy_note = "" if args.ivy else f"; {int(cohort.ivy.sum())} by Ivy teams"
    foot = (f"{who}, drives starting in the 4th quarter tied or behind by 1-8, "
            f"{int(d.season.min())} through week 4 of 2026 ({len(cohort):,} drives in the last "
            f"6:00{ivy_note}).\nOvertime wins count as wins "
            f"({int(cohort.overtime.sum())} of these drives were in overtime games). "
            f"Every number on this chart is in the CSV saved beside it.")
    d.to_csv(OUT / "drives.csv", index=False, columns=[
        "pff_GAMEID", "season", "offense", "defense", "state", "margin", "secs",
        "secs_at_last_snap", "yards_to_goal", "timeouts", "end", "got_score", "won",
        "scored_then_lost", "overtime", "ivy"])
    time_csv(d, "won").to_csv(OUT / "1_win_by_time.csv", index=False)
    time_csv(d, "got_score").to_csv(OUT / "2_score_by_time.csv", index=False)
    if args.ivy:
        ivy_charts(d, fcs_drives, foot)
        print(f"[saved] {OUT} ({len(cohort):,} Ivy drives in the last 6:00)")
        return
    chart_win(d, to_secs, foot, windows(d, "won", WINDOW))
    chart_score(d, to_secs, foot, windows(d, "got_score", WINDOW))
    chart_scored_then_lost(d, foot)
    chart_pace_grid(d, foot)
    chart_seconds_per_yard(d, foot)
    chart_timeouts(d, foot)
    print(f"[saved] {OUT} ({len(d):,} drives; timeout = {to_secs:.0f} seconds)")


if __name__ == "__main__":
    main()
