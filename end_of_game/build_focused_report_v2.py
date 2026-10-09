import html
import json
import math
import os
import re
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/evertrue-mpl")
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
    Table, TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "pdf"
CHARTS = ROOT / "tmp" / "pdfs" / "endgame_v3_charts"
OUT.mkdir(parents=True, exist_ok=True)
CHARTS.mkdir(parents=True, exist_ok=True)

D = json.loads((ROOT / "tos" / "out" / "report_data.json").read_text())
C = json.loads((OUT / "clock_option_analysis.json").read_text())
R = D["recommend"]
P = D["wp_params"]
FILM = json.loads((OUT / "film_index.json").read_text())
PLAYLISTS = json.loads((OUT / "film_playlists.json").read_text())

PDF = OUT / "end_of_game_clock_report_v3.pdf"
MD = OUT / "end_of_game_clock_report_v3.md"

BROWN = "#4b2e23"
RUST = "#b24b36"
BLUE = "#2f73c9"
TEAL = "#2aa876"
GOLD = "#d7a928"
INK = "#231f20"
MUTED = "#66615e"
GRID = "#ddd7d1"
PALE = "#f4f0ec"
WHITE = "#ffffff"

TEAM = {
    "RIUN": "Rhode Island", "NJPR": "Princeton", "CTYA": "Yale",
    "DCGT": "Georgetown", "RIBT": "Bryant", "MAHA": "Harvard",
    "PAUN": "Penn", "NYCN": "Cornell", "NHDA": "Dartmouth",
    "NYCL": "Columbia", "CTNH": "New Haven", "CTCE": "Central Connecticut",
}


def team(code):
    return TEAM.get(code, code)


def clock(seconds):
    seconds = int(round(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def lead_text(lead):
    return f"Up {lead}" if lead > 0 else f"Down {-lead}" if lead < 0 else "Tied"


def film_link(game_id, label):
    url = next((row["film_url"] for row in FILM if row["game_id"] == game_id), None)
    if url is None:
        url = PLAYLISTS[str(game_id)]["url"]
    return f'<link href="{url}" color="{BROWN}">{label}</link>'


def drive_needs(yards):
    dt = D["drive_time"]
    at20 = dt["a"] + 20 * dt["b"]
    return dt["a"] + dt["b"] * yards if yards >= 20 else 30 + (at20 - 30) * yards / 20


def need_for(lead, ytg):
    if lead <= -9:
        return drive_needs(ytg) + drive_needs(20)
    if lead <= -4:
        return drive_needs(ytg)
    return drive_needs(max(0, ytg - 30))


def ball_back(their_ytg, lead):
    punt = D["punt"]
    if their_ytg <= punt["fg_range"]:
        return lead - 3, 75
    return lead, 100 - max(punt["floor"], their_ytg - punt["net"])


def phi(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def wp_offense(lead, ep, secs, strength):
    t = max(secs, 1) / 3600
    den = P["sigma"] * math.sqrt(t) + P["c"]
    return phi((lead + P["a"] * ep + P["b"] * strength * t) / den)


def our_wp(side, lead, ep, secs, strength):
    if side == "us":
        return wp_offense(lead, ep, secs, strength)
    return 1 - wp_offense(-lead, ep, secs, -strength)


KILL_CYCLE = next(x for x in D["play_time"]["rows"]["all"] if x["mode"] == "four_minute" and x["call"] == "R")["total"]
KNEEL_ROW = next(x for x in D["play_time"]["rows"]["all"] if x["mode"] == "kneel")


def decide(side, lead, k, strength, row, yard, ti):
    down = R["downs"][row]["down"]
    ytg = 100 - yard if side == "us" else yard
    yi = R["ytgs"].index(ytg)
    t = R["grid_clock"][ti]
    ep = R["ep"][row][yi][ti]
    save = D["seconds_saved"]["def" if side == "them" else "ball"]
    wp = our_wp(side, lead, ep, t, strength)
    result = {
        "t": t, "wp": 100 * wp, "save": save, "snaps_left": 5 - down,
        "value": 100 * max(0, our_wp(side, lead, ep, t + save, strength) - wp),
    }
    if side == "them" and lead < 0:
        kneels = result["snaps_left"]
        burn = kneels * KNEEL_ROW["live"] + max(0, kneels - k) * KNEEL_ROW["dead"]
        if burn >= t:
            result["cat"] = "kneel"
            return result
    if side == "them":
        back_lead, back_ytg = ball_back(ytg, lead)
        needed = need_for(back_lead, back_ytg)
    else:
        needed = need_for(lead, ytg)
    if result["wp"] >= 99.5 or result["wp"] <= 0.5:
        result["cat"] = "over"
    elif lead > 0:
        result["cat"] = "ahead"
    elif side == "them":
        ball_back_time = max(0, t - result["snaps_left"] * KILL_CYCLE)
        if ball_back_time >= needed:
            result["cat"] = "save"
        else:
            result["cat"] = "call" if k >= result["snaps_left"] else "wait"
    elif lead == 0:
        result["cat"] = "save"
    elif t >= needed:
        result["cat"] = "save"
    elif lead <= -9 and t >= 90:
        result["cat"] = "defense"
    else:
        result["cat"] = "call"
    return result


CAT_ORDER = ["call", "wait", "defense", "save", "ahead", "kneel", "over"]
CAT_COLOR = {
    "call": RUST, "wait": GOLD, "defense": "#7558a5", "save": "#d9e7df",
    "ahead": "#eeeeec", "kneel": "#8a8581", "over": "#4d4947",
}
CAT_LABEL = {
    "call": "Call now", "wait": "Wait a down", "defense": "Save for defense",
    "save": "Hold", "ahead": "Let clock run", "kneel": "They can kneel",
    "over": "Game decided",
}


def savefig(fig, name):
    path = CHARTS / name
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def style_axes(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.spines[["left", "bottom"]].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=7)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def recommendation_small_multiples(strength):
    times = [t for t in R["grid_clock"] if t <= 480]
    leads = R["grid_lead"]
    fig, axes = plt.subplots(2, 3, figsize=(9.4, 6.3), sharex=True, sharey=True)
    cmap = ListedColormap([CAT_COLOR[x] for x in CAT_ORDER])
    norm = BoundaryNorm(np.arange(-0.5, len(CAT_ORDER) + 0.5), cmap.N)
    for ri, side in enumerate(["them", "us"]):
        yard = 65 if side == "them" else 35
        for ci, k in enumerate([1, 2, 3]):
            z = []
            for lead in leads:
                z.append([
                    CAT_ORDER.index(decide(side, lead, k, strength, 7, yard, R["grid_clock"].index(t))["cat"])
                    for t in times
                ])
            ax = axes[ri, ci]
            ax.imshow(z, origin="lower", aspect="auto", cmap=cmap, norm=norm,
                      extent=[times[0] - 15, times[-1] + 15, leads[0] - .5, leads[-1] + .5])
            ax.set_title(f"{k} timeout{'s' if k > 1 else ''}", fontsize=9, weight="bold", color=INK)
            ax.set_xticks([60, 180, 300, 420]); ax.set_xticklabels(["1:00", "3:00", "5:00", "7:00"])
            ax.set_yticks([-14, -7, 0, 7]); ax.set_yticklabels(["Down 14", "Down 7", "Tied", "Up 7"])
            ax.tick_params(labelsize=7, length=0)
            for s in ax.spines.values(): s.set_color(WHITE)
        axes[ri, 0].set_ylabel("They have ball\n3rd & 5, own 35" if side == "them" else "We have ball\n3rd & 5, own 35", fontsize=8, weight="bold")
    for ax in axes[-1]: ax.set_xlabel("Time left", fontsize=7)
    fig.suptitle(f"Timeout decision map - team strength {strength:+d} points per game", x=.08, ha="left", fontsize=13, weight="bold", color=BROWN)
    handles = [Patch(facecolor=CAT_COLOR[c], label=CAT_LABEL[c]) for c in CAT_ORDER]
    fig.legend(handles=handles, ncol=4, frameon=False, loc="lower center", bbox_to_anchor=(.5, -.01), fontsize=7)
    fig.tight_layout(rect=[0, .06, 1, .94])
    return savefig(fig, f"recommend_strength_{strength:+d}.png")


def trigger_maps():
    fig, axes = plt.subplots(2, 1, figsize=(9.4, 6.7), constrained_layout=True)
    downs = [f"{d['down']} & {d['distance']}" for d in R["downs"]]
    for ax, side in zip(axes, ["them", "us"]):
        data = np.full((len(downs), len(R["yards"])), np.nan)
        for i in range(len(downs)):
            for j, yard in enumerate(R["yards"]):
                start = np.nan
                for ti in range(len(R["grid_clock"]) - 1, -1, -1):
                    if decide(side, -3, 3, 0, i, yard, ti)["cat"] == "call":
                        start = R["grid_clock"][ti] / 60
                        break
                data[i, j] = start
        im = ax.imshow(data, aspect="auto", cmap="Blues", vmin=.5, vmax=10, origin="upper")
        ax.set_yticks(range(len(downs))); ax.set_yticklabels(downs, fontsize=6.5)
        ax.set_xticks(range(0, len(R["yards"]), 2))
        ax.set_xticklabels([("50" if y == 50 else f"O{y}" if y < 50 else f"T{100-y}") for y in R["yards"]][::2], fontsize=6.5)
        ax.set_title(("They have the ball" if side == "them" else "We have the ball") + " - Brown down 3, 3 timeouts, even teams", loc="left", fontsize=9, weight="bold")
        ax.set_xlabel("Ball position from Brown view: O = own, T = their", fontsize=7)
        for s in ax.spines.values(): s.set_visible(False)
    cbar = fig.colorbar(im, ax=axes, shrink=.7, pad=.02)
    cbar.set_label("Start-call threshold, minutes left", fontsize=7)
    cbar.ax.tick_params(labelsize=7)
    fig.suptitle("Start-call threshold by down, distance, and field position", x=.01, ha="left", fontsize=13, weight="bold", color=BROWN)
    return savefig(fig, "recommend_trigger_maps.png")


def value_maps():
    times = [t for t in R["grid_clock"] if t <= 480]
    leads = R["grid_lead"]
    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.0), sharex=True, sharey=True, constrained_layout=True)
    vmax = 0
    matrices = []
    for side in ["them", "us"]:
        yard = 65 if side == "them" else 35
        z = np.array([[decide(side, lead, 3, 0, 7, yard, R["grid_clock"].index(t))["value"] for t in times] for lead in leads])
        matrices.append(z); vmax = max(vmax, float(z.max()))
    for ax, side, z in zip(axes, ["them", "us"], matrices):
        im = ax.imshow(z, origin="lower", aspect="auto", cmap="Blues", vmin=0, vmax=min(4, vmax), extent=[15, 495, -16.5, 8.5])
        ax.set_title("They have the ball" if side == "them" else "We have the ball", fontsize=9, weight="bold")
        ax.set_xticks([60,180,300,420]); ax.set_xticklabels(["1:00","3:00","5:00","7:00"])
        ax.set_yticks([-14,-7,0,7]); ax.set_yticklabels(["Down 14","Down 7","Tied","Up 7"])
        ax.tick_params(labelsize=7, length=0)
        ax.set_xlabel("Time left", fontsize=7)
        for s in ax.spines.values(): s.set_visible(False)
    axes[0].set_ylabel("Brown score margin", fontsize=7)
    cb = fig.colorbar(im, ax=axes, shrink=.78, pad=.02); cb.set_label("Win-probability points added", fontsize=7); cb.ax.tick_params(labelsize=7)
    fig.suptitle("Value of one timeout - 3rd & 5 at the possession team's 35", x=.01, ha="left", fontsize=13, weight="bold", color=BROWN)
    return savefig(fig, "recommend_value_maps.png")


def timeline_chart():
    four = next(x for x in D["play_time"]["rows"]["all"] if x["mode"] == "four_minute" and x["call"] == "R")
    live, dead, start = four["live"], D["seconds_saved"]["def"], 150
    fig, ax = plt.subplots(figsize=(9.4, 2.5))
    labels = ["No timeouts", "Three timeouts"]
    for y, use_to in enumerate([False, True]):
        left = start
        elapsed = 0
        for _ in range(3):
            ax.barh(y, live, left=elapsed, color=BLUE, height=.42)
            elapsed += live
            left -= live
            if not use_to:
                ax.barh(y, dead, left=elapsed, color="#f26d3d", height=.42)
                elapsed += dead
                left -= dead
        ax.text(start-left+3, y, f"{clock(left)} left", va="center", fontsize=8, weight="bold")
    ax.set_yticks([0,1]); ax.set_yticklabels(labels); ax.invert_yaxis()
    ax.set_xlim(0,150); ax.set_xticks([0,30,60,90,120,150]); ax.set_xticklabels(["2:30","2:00","1:30","1:00","0:30","0:00"])
    style_axes(ax); ax.grid(axis="x", color=GRID)
    ax.legend([Patch(color=BLUE), Patch(color="#f26d3d")], ["Play", "Wait stopped by timeout"], frameon=False, ncol=2, fontsize=7, loc="lower center", bbox_to_anchor=(.5,-.42))
    ax.set_title("Three defensive stops", loc="left", fontsize=12, weight="bold", color=BROWN)
    return savefig(fig, "timeline.png")


def penalty_chart():
    rows = D["penalty_costs"]
    fig, ax = plt.subplots(figsize=(9.4, 3.6))
    y = np.arange(len(rows)); vals = [r["cost"] for r in rows]
    ax.barh(y, vals, color=BLUE, height=.55)
    ax.axvline(D["option_value"]["one_score"], color=RUST, lw=2, label=f"Saved timeout: {D['option_value']['one_score']:.2f}")
    ax.set_yticks(y); ax.set_yticklabels([r["spot"] for r in rows]); ax.invert_yaxis()
    ax.set_xlabel("Win-probability points lost by a 5-yard penalty", fontsize=8)
    for i,v in enumerate(vals): ax.text(v+.05,i,f"{v:.1f}",va="center",fontsize=7)
    style_axes(ax); ax.legend(frameon=False, fontsize=7, loc="lower right")
    ax.set_title("Delay of game cost versus saving a timeout", loc="left", fontsize=12, weight="bold", color=BROWN)
    return savefig(fig, "penalty.png")


def playtime_chart():
    fig, axes = plt.subplots(1, 3, figsize=(9.4, 5.0), sharex=True, constrained_layout=True)
    for ax, group, title in zip(axes, ["all","ivy","brown"], ["All FBS/FCS","Ivy","Brown"]):
        rows = D["play_time"]["rows"][group]
        y = np.arange(len(rows)); live = [r["live"] for r in rows]; dead = [r["dead"] for r in rows]
        alpha = [1 if r["n"] >= 30 else .35 for r in rows]
        for i,(a,b) in enumerate(zip(live,dead)):
            ax.barh(i,a,color=BLUE,alpha=alpha[i],height=.58)
            ax.barh(i,b,left=a,color="#f26d3d",alpha=alpha[i],height=.58)
            ax.text(a+b+.4,i,f"{a+b:.0f}",va="center",fontsize=6)
        ax.set_yticks(y); ax.set_yticklabels([r["label"].replace("Running out the clock: ","Kill: ").replace("Two-minute drill: ","2-min: ") for r in rows], fontsize=6)
        ax.invert_yaxis(); ax.set_title(title, fontsize=9, weight="bold"); ax.set_xlim(0,47)
        style_axes(ax); ax.set_xlabel("Seconds per snap",fontsize=7)
    axes[0].legend([Patch(color=BLUE),Patch(color="#f26d3d")],["Play","Between plays"],frameon=False,fontsize=7,loc="lower center",bbox_to_anchor=(1.5,-.23),ncol=2)
    fig.suptitle("Play time - every team-group view", x=.01, ha="left", fontsize=13, weight="bold", color=BROWN)
    return savefig(fig, "playtime_all_groups.png")


def playclock_chart():
    hist = D["play_time"]["clock_left_hist"]
    x = np.arange(41)
    fig, ax = plt.subplots(figsize=(9.4, 3.1))
    ax.plot(x,100*np.array(hist["normal"]),color=MUTED,lw=1.6,label="Normal plays")
    ax.plot(x,100*np.array(hist["four_minute"]),color=BLUE,lw=2,label="Running out clock")
    ax.fill_between(x,0,100*np.array(hist["four_minute"]),color=BLUE,alpha=.10)
    ax.axvline(D["play_time"]["four_minute_clock_left"],color=BLUE,lw=1)
    ax.set_xlim(0,40); ax.set_xlabel("Seconds left on play clock",fontsize=8); ax.set_ylabel("Share of snaps",fontsize=8)
    ax.legend(frameon=False,fontsize=7); style_axes(ax)
    ax.set_title("Play clock left at the snap",loc="left",fontsize=12,weight="bold",color=BROWN)
    return savefig(fig,"playclock.png")


def reality_chart():
    rows = [("FCS",D["defense_reality"]["fcs"]),("Ivy",D["defense_reality"]["ivy"]),("Brown",D["defense_reality"]["brown"])]
    fig, axes = plt.subplots(1,2,figsize=(9.4,3.0),constrained_layout=True)
    axes[0].bar([r[0] for r in rows],[100*r[1]["called_when_should"] for r in rows],color=["#908b87",TEAL,BROWN])
    axes[0].set_ylim(0,100); axes[0].set_ylabel("Called timeout (%)",fontsize=8); axes[0].set_title("Call rate in flagged spots",fontsize=10,weight="bold")
    axes[1].bar([r[0] for r in rows],[r[1]["seconds_lost_when_missed"] for r in rows],color=["#908b87",TEAL,BROWN])
    axes[1].set_ylim(0,45); axes[1].set_ylabel("Seconds",fontsize=8); axes[1].set_title("Clock lost when no timeout came",fontsize=10,weight="bold")
    for ax in axes:
        style_axes(ax); ax.tick_params(axis="x",rotation=20)
    fig.suptitle("Timeout use in urgent defensive spots",x=.01,ha="left",fontsize=13,weight="bold",color=BROWN)
    return savefig(fig,"defense_reality.png")


PURPOSE = {
    "clock":"Stop clock at half end", "defense":"Other defense", "play_clock":"Play clock",
    "fourth_down":"Before 4th down", "pre_punt":"Before punt", "pre_kick":"Before kick", "offense":"Other offense",
}


def audit_chart():
    groups=["Brown","Rest of Ivy","All FBS/FCS"]
    cols=[BROWN,TEAL,BLUE]
    purposes=D["audit"]["purposes"]
    fig,ax=plt.subplots(figsize=(9.4,3.7))
    for i,p in enumerate(purposes):
        vals=[D["audit"]["rates"][g][p] for g in groups]
        ax.plot([min(vals),max(vals)],[i,i],color=GRID,lw=2,zorder=1)
        for g,c,v in zip(groups,cols,vals): ax.scatter(v,i,s=34,color=c,edgecolor=WHITE,zorder=2,label=g if i==0 else None)
    ax.set_yticks(range(len(purposes))); ax.set_yticklabels([PURPOSE[p] for p in purposes]); ax.invert_yaxis(); ax.set_xlim(0,2.15)
    ax.set_xlabel("Timeouts per game",fontsize=8); style_axes(ax); ax.legend(frameon=False,ncol=3,fontsize=7,loc="lower center",bbox_to_anchor=(.5,-.30))
    ax.set_title("Timeout use by purpose",loc="left",fontsize=12,weight="bold",color=BROWN)
    return savefig(fig,"timeout_audit.png")


def calibration_chart():
    rows=D["calibration"]
    fig,axes=plt.subplots(1,2,figsize=(9.4,3.5),constrained_layout=True)
    pred=[100*r["predicted"] for r in rows]; act=[100*r["actual"] for r in rows]
    axes[0].plot([0,100],[0,100],color=GRID,lw=1.5); axes[0].scatter(pred,act,color=BLUE,s=34)
    axes[0].set_xlabel("Predicted win rate",fontsize=8); axes[0].set_ylabel("Actual win rate",fontsize=8); axes[0].set_aspect("equal"); axes[0].set_xlim(0,100);axes[0].set_ylim(0,100);style_axes(axes[0]);axes[0].set_title("2025 calibration",fontsize=10,weight="bold")
    sc=D["scenario"]; labels=["Model:\nBrown-Yale","Model:\neven teams","Ivy history","PFF tool"]
    vals=[sc["brown_vs_yale"][-1],sc["even_teams"][-1],100*sc["ivy_history"]["won"]/sc["ivy_history"]["n"],sc["pff"][-1]]
    axes[1].bar(labels,vals,color=[BROWN,BLUE,TEAL,"#908b87"]);axes[1].set_ylim(0,40);axes[1].set_ylabel("Chance of winning (%)",fontsize=8);style_axes(axes[1]);axes[1].set_title("Down 3, 2:00, own 25",fontsize=10,weight="bold")
    for i,v in enumerate(vals): axes[1].text(i,v+.8,f"{v:.0f}%",ha="center",fontsize=7)
    fig.suptitle("Model checks",x=.01,ha="left",fontsize=13,weight="bold",color=BROWN)
    return savefig(fig,"calibration.png")


def timeout_spike_chart():
    groups = ["FCS", "Ivy", "Brown"]
    situations = [
        ("after_first_down", "After a first down", BLUE),
        ("after_play_short_of_first_down", "After a play short of 1st down", RUST),
    ]
    fig, ax = plt.subplots(figsize=(9.4, 3.25))
    x = np.arange(len(groups)); width = .34
    for j, (key, label, color) in enumerate(situations):
        values, ns = [], []
        for group in groups:
            cell = C["timeout_vs_spike"][group][key]
            values.append(cell["mean"] if cell["mean"] is not None else 0)
            ns.append(cell["n"])
        bars = ax.bar(x + (j - .5) * width, values, width, color=color, label=label)
        for bar, value, n in zip(bars, values, ns):
            if n < 10:
                bar.set_alpha(.3)
            if n:
                ax.text(bar.get_x() + bar.get_width()/2, value + .35, f"{value:.1f}\nn={n}",
                        ha="center", va="bottom", fontsize=7)
            else:
                ax.text(bar.get_x() + bar.get_width()/2, .35, "No sample", ha="center",
                        va="bottom", fontsize=7, color=MUTED, rotation=90)
    ax.set_xticks(x); ax.set_xticklabels(groups)
    ax.set_ylim(0, 15); ax.set_ylabel("Seconds saved by a timeout", fontsize=8)
    ax.legend(frameon=False, fontsize=7, ncol=2, loc="upper right")
    style_axes(ax)
    ax.set_title("Timeout versus hurry-and-spike", loc="left", fontsize=12,
                 weight="bold", color=BROWN)
    return savefig(fig, "timeout_vs_spike.png")


CHART = {
    "rec_m7": recommendation_small_multiples(-7),
    "rec_0": recommendation_small_multiples(0),
    "rec_p7": recommendation_small_multiples(7),
    "triggers": trigger_maps(),
    "values": value_maps(),
    "timeline": timeline_chart(),
    "penalty": penalty_chart(),
    "playtime": playtime_chart(),
    "playclock": playclock_chart(),
    "reality": reality_chart(),
    "audit": audit_chart(),
    "calibration": calibration_chart(),
    "spike": timeout_spike_chart(),
}


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="TitleV2", fontName="Helvetica-Bold", fontSize=24, leading=27, textColor=colors.HexColor(BROWN), spaceAfter=12))
styles.add(ParagraphStyle(name="Deck", fontName="Helvetica", fontSize=12, leading=16, textColor=colors.HexColor(INK), spaceAfter=15))
styles.add(ParagraphStyle(name="HeadV2", fontName="Helvetica-Bold", fontSize=14, leading=16, textColor=colors.HexColor(BROWN), spaceBefore=9, spaceAfter=6, keepWithNext=True))
styles.add(ParagraphStyle(name="SubV2", fontName="Helvetica-Bold", fontSize=10.5, leading=13, textColor=colors.HexColor(INK), spaceBefore=7, spaceAfter=4, keepWithNext=True))
styles.add(ParagraphStyle(name="BodyV2", fontName="Helvetica", fontSize=9.6, leading=13.4, textColor=colors.HexColor(INK), spaceAfter=7))
styles.add(ParagraphStyle(name="SmallV2", fontName="Helvetica", fontSize=7.6, leading=9.8, textColor=colors.HexColor(MUTED), spaceAfter=5))
styles.add(ParagraphStyle(name="NoteV2", fontName="Helvetica-Bold", fontSize=9.4, leading=13, textColor=colors.HexColor(BROWN), backColor=colors.HexColor(PALE), borderPadding=8, spaceAfter=9))
styles.add(ParagraphStyle(name="CellV2", fontName="Helvetica", fontSize=7.3, leading=9.2, textColor=colors.HexColor(INK)))
styles.add(ParagraphStyle(name="CellSmall", fontName="Helvetica", fontSize=6.2, leading=7.5, textColor=colors.HexColor(INK)))

story=[]
md=[]


def title(text, deck=None):
    story.append(Paragraph(text,styles["TitleV2"])); md.extend([f"# {text}",""])
    if deck:
        story.append(Paragraph(deck,styles["Deck"])); md.extend([re.sub("<[^>]+>","",deck),""])


def head(text):
    story.append(Paragraph(text,styles["HeadV2"])); md.extend([f"## {text}",""])


def sub(text):
    story.append(Paragraph(text,styles["SubV2"])); md.extend([f"### {text}",""])


def body(text):
    story.append(Paragraph(text,styles["BodyV2"])); md.extend([to_md(text),""])


def small(text):
    story.append(Paragraph(text,styles["SmallV2"])); md.extend([to_md(text),""])


def note(text):
    story.append(Paragraph(text,styles["NoteV2"])); md.extend([f"> {to_md(text)}",""])


def to_md(text):
    text=re.sub(r'<link href="([^"]+)"[^>]*>(.*?)</link>',r'[\2](\1)',text)
    return html.unescape(re.sub(r"<[^>]+>","",text))


def table(headers, rows, widths=None, small_cells=False, repeat=1):
    sty=styles["CellSmall" if small_cells else "CellV2"]
    data=[[Paragraph(f"<b>{html.escape(str(c))}</b>",sty) for c in headers]]
    for row in rows:
        data.append([Paragraph(str(c) if str(c).startswith("<link ") else html.escape(str(c)),sty) for c in row])
    t=Table(data,colWidths=widths,repeatRows=repeat,hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#e9e1da")),
        ("TEXTCOLOR",(0,0),(-1,0),colors.HexColor(BROWN)),
        ("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LINEBELOW",(0,0),(-1,0),1,colors.HexColor(BROWN)),
        ("LINEBELOW",(0,1),(-1,-1),.25,colors.HexColor(GRID)),
    ]))
    story.extend([t,Spacer(1,7)])
    md.extend(["| "+" | ".join(map(str,headers))+" |","| "+" | ".join(["---"]*len(headers))+" |"])
    md.extend(["| "+" | ".join(to_md(str(c)) for c in r)+" |" for r in rows]);md.append("")


def chart(path,width=7.0,height=None):
    im=Image(str(path),width=width*inch)
    if height: im.drawHeight=height*inch
    else: im.drawHeight=im.imageHeight*(im.drawWidth/im.imageWidth)
    story.extend([im,Spacer(1,5)])


def page(): story.append(PageBreak())


# Main report
title("End-of-game clock decisions", "A focused staff report on timeouts, clock preservation, and clock killing")
small("BROWN FOOTBALL  |  8 OCTOBER 2026  |  Version 3")
note("Set the clock plan before each late possession. Name the timeout trigger, the expected final down, the clock restart, and the status of the two-minute timeout.")
head("Four calls for the sideline")
table(["Situation","Call"],[
    ["Trailing on defense","When time is tight and our timeouts can cover the waits before a punt, call at the whistle."],
    ["Trailing with the ball","Use a timeout when the drive cannot finish on the clock. Keep one only if the last sequence may end in bounds."],
    ["Leading","Kneel only after the clock math is checked from the current down and restart state."],
    ["Play clock near zero","Call timeout in the ordinary spots studied here. The five-yard penalty cost more than the saved timeout."],
],[130,374])
head("What the evidence says")
table(["Finding","Evidence","Meaning"],[
    ["A defensive timeout can save a full wait.","FCS clock-kill runs used 33.0 seconds between plays.","If the timeout is part of the plan, call it right away."],
    ["Brown has 17 adjusted defensive flags.","Nine of the original 26 were set aside because the expected series reached the two-minute timeout.","Brown called timeout in 8 of the remaining 17."],
    ["Teams leave time on the play clock.","The national median was 5 seconds. Only 35% of snaps came at 3 seconds or less.","A rehearsed late-snap process can add useful time."],
    ["A chart time assumes a clock restart.","With one timeout, the same three kneels cover 1:28 if the clock runs first and 0:50 if it does not.","Check whether the clock is running before using the chart."],
],[148,175,181])
head("Sample")
body("The full file has 5,578 games, 773,020 modeled snaps, and 35,040 reconstructed timeouts. It covers 2023 through Week 4 of 2026. FCS teams were identified with ESPN standings and game results. Brown has 32 games in the file.")
small("The appendix contains every chart mode from the prior dashboard. The new timeout map replaces thousands of selector combinations with small multiples and two full situation maps.")

page();title("1. Trailing: protect useful time")
head("Defensive timeouts")
body("A defensive timeout removes the wait after a play. It does not remove the play itself. FCS clock-kill runs averaged 7.4 seconds for the play and 33.0 seconds before the next snap.")
body("The original rule flagged 26 Brown spots. The revised screen sets aside nine because the expected series reaches the two-minute timeout before the punt. Brown called timeout in 8 of the remaining 17. The other nine intervals used 341 estimated seconds in total.")
table(["Their next down","Waits before a punt","Call now when we have"],[
    ["1st","4","No full coverage with three timeouts"],["2nd","3","3 timeouts"],["3rd","2","2 or 3 timeouts"],["4th","1","At least 1 timeout"],
],[120,170,214])
body("This rule assumes a running clock and an expected punt after stops. For 2024 onward, do not apply it when the average no-timeout path begins above 2:00 and reaches 2:00 before the punt.")
head("Brown examples")
body(film_link(25327,"2023 Princeton, Q4 3:31 to 2:01")+" has two flagged waits with Brown down seven and all three timeouts. The audit estimates 38 seconds in each wait.")
body(film_link(27785,"2024 Princeton, Q4 3:16 to 2:33")+" shows why film matters. Defensive holding created a first down, so the assumed-punt path did not occur.")
body(film_link(32154,"2026 Harvard, Q4 2:52 to 2:14")+" is now held out of the flag count. The expected series reaches the automatic timeout before the possession ends.")
head("How to read the audit")
body("A flag means the adjusted rule recommends an immediate timeout. A two-minute holdout means the automatic stop changes the sequence, so this simple audit does not judge the call.")
small("Brown's 47.1% call rate comes from only 17 adjusted flags. It cannot show that Brown differs from the FCS or Ivy rate with confidence.")

page();title("2. Trailing on offense: timeout or spike")
head("A timeout saves time and a down")
body("After a first down, the chain stoppage makes a hurry-and-spike fairly cheap. The FCS average was 5.2 seconds. After a play short of a first down, the average cost rose to 12.2 seconds.")
table(["Group","After first down","After play short of first down"],[
    ["FCS","5.2 sec (n=229)","12.2 sec (n=40)"],
    ["Ivy","3.8 sec (n=19)","11.6 sec (n=2)"],
    ["Brown","4.3 sec (n=2)","No sample"],
],[120,192,192])
head("Call")
table(["Clock state","Default"],[
    ["First down just gained","Use the chain stoppage. Spike if about five seconds and the down are cheaper than the timeout."],
    ["Play ended in bounds short of first down","A timeout usually saves about 12 seconds and preserves the next down."],
],[175,329])
head("Brown film")
body('<link href="https://ultimate.pff.com/ncaa/games/30167/boxscore" color="#4b2e23">2025 Yale, Q2 0:23 to 0:16</link>: Brown gained a first down and spiked. The estimated timeout savings were 3.3 seconds.')
body('<link href="https://ultimate.pff.com/ncaa/games/32104/boxscore" color="#4b2e23">2026 New Haven, Q2 0:24 to 0:14</link>: Brown gained a first down and spiked. The estimated timeout savings were 5.3 seconds.')
small("Method: observed final-two-minute spike sequences with no timeout or natural stop between snaps. The estimate removes the prior play's live time and adds the spike. Brown's sample is too small for a team rule; use the FCS values for planning.")

page();title("3. Leading: verify the kneel-out")
head("The first question is whether the game clock is running")
body("The staff chart uses 4 seconds for each kneel and 38 seconds of play-clock use. Its first-down, one-timeout line is 1:28. That total assumes a usable running-clock wait before the first snap.")
table(["Start state","Three-kneel total vs. one timeout","Reason"],[
    ["Clock running before first snap","88 seconds","Three 4-second plays plus two 38-second waits"],
    ["Clock stopped until first snap","50 seconds","Three 4-second plays plus one 38-second wait"],
],[165,165,174])
head("Three checks before victory formation")
table(["Check","Question"],[
    ["Restart","Will the game clock run before the next snap?"],
    ["Automatic stop","Has the two-minute timeout happened? Will this play cross 2:00?"],
    ["Safe plays","How many downs remain? Is there room for each kneel and no fourth-down return?"],
],[135,369])
head("Execution matters")
body("The national clock-kill median was 5 seconds left on the play clock. Snapping at 1 instead of 5 uses four more seconds. Three such waits use 12 more seconds.")
body("A four-minute run lasts about seven to eight seconds from snap to whistle. A kneel lasts about four to five seconds. The Brown samples are only seven runs and three kneels.")
table(["Group","Clock-kill run","Kneel"],[
    ["FCS","7.4 sec (n=2,287)","4.4 sec (n=551)"],
    ["Ivy","7.6 sec (n=188)","4.7 sec (n=33)"],
    ["Brown","7.0 sec (n=7)","4.7 sec (n=3)"],
],[120,192,192])
small("These are snap-to-whistle averages. Add the usable wait before the next snap only when the game clock will run.")

page();title("4. Counterarguments and limits")
sub("Save the timeout for offense")
body("That can be right if the last drive may end with the clock running. Still, the adjusted Brown missed intervals averaged 37.9 seconds. Spend the timeout on defense when the offense can still finish without it.")
sub("Always run when protecting a lead")
body("A run can keep the clock moving. A failed series also returns the ball. If kneels cannot end the game, the choice must include conversion chance, turnover risk, punt position, and the opponent's next drive.")
sub("A saved timeout is worth only 0.33 points")
body("The estimate is 0.33 percentage points of win probability in sampled one-score states. It is an average. It does not price a substitution error, a bad call, or the last play of a drive.")
sub("Unused timeouts caused close losses")
body("Three of six sampled close losses ended with an unused timeout. That makes those games worth review. It does not show that a useful timeout chance existed.")
sub("The 2:30 mark is a firm trigger")
body("The 151-second value is the 75th percentile of 430 successful hurry-up drives. Failed drives were excluded. Treat it as a planning mark, not a universal deadline.")
head("Model limits")
body("The win model is a clock-value estimate. Team strength uses full-season scoring margin. Calibration uses many plays from the same games. Those choices can make the results look more certain than a live decision is.")
note("Use the model to set the clock plan. Use the game state and film to make the call.")

page();title("5. Brown film queue")
small("The links open selected plays in Ultimate. Sign-in and playlist access may be required. The estimated wait is based on play-by-play timing, not a hand-timed film review.")
rows=[]
for r in FILM:
    rows.append([film_link(r["game_id"],f"{r['season']} {r['opponent_name']}"),r["snap_clock"],r["next_snap_clock"],f"Down {-r['lead']}",str(r["next_down"]),str(r["timeouts"]),f"{r['lost']} sec"])
table(["Film","Snap","Next","Score","Next down","TO","Est. wait"],rows,[130,58,58,61,64,35,62],small_cells=True)
head("Source record")
small("<b>Primary data:</b> tos/out/report_data.json, tos/out/timeout_report.html, output/pdf/clock_option_analysis.json, and data/ncaa/pbp.csv.gz.")
small("<b>Reference files:</b> Brown Timeout Decisions.pdf; 2POINT_EOG - KNEEL DOWN SITUATION CHART.xlsx - USE THIS ONE w-2min waning NEW.pdf; evertrue1.txt; evertrue2.txt.")
small("<b>Rules:</b> <link href=\"https://www.ncaa.org/news/media-center-football-timing-rules-approved-for-divisions-i-ii/\" color=\"#4b2e23\">2023 timing change</link>; <link href=\"https://www.ncaa.org/news/media-center-technology-rules-approved-in-football/\" color=\"#4b2e23\">2024 two-minute timeout</link>; <link href=\"https://www.ncaa.org/championships/playing-rules/football-playing-rules/\" color=\"#4b2e23\">current NCAA rule resources</link>.")
small("<b>FCS classification:</b> ESPN FCS standings and scoreboards were matched to PFF teams by date and final score. A code required at least three matches and 80% agreement across seasons.")
small("<b>Two-minute timeout:</b> For 2024 onward, a raw defensive flag was set aside if it began above 2:00 and the average no-timeout path reached 2:00 before the expected punt. This is a conservative holdout, not a finding that a charged timeout had no value.")
small("<b>Film:</b> Ultimate site structure, filters, report catalog, IQ tools, video pages, and playlist workflow were reviewed. The selected links were matched to PFF play IDs.")
small("<b>Missing historical file:</b> end_of_game/ivy_19t26.csv is not in this checkout. The stored Ivy model parameters remain, but that historical fit cannot be rerun here. This is separate from the current PFF defensive audit, which uses the national play-by-play file.")

# Appendix
page();title("Appendix: charts and tables","Short explanations are placed under each item. All values come from the saved report data and the reproduced clock audit.")
head("Coverage of the old dashboard")
table(["Old control or view","Static coverage here"],[
    ["Who has the ball","Both rows on each decision-map page"],["Timeouts: 1, 2, 3","Three columns on each decision-map page"],
    ["Team strength: -7, 0, +7","One full page for each setting"],["Score and time","Both axes on all 18 decision maps"],
    ["Card view: down, distance, field position","Two full trigger maps"],["Show numbers","Two timeout-value maps"],
    ["Play-time group: all, FCS, Ivy, Brown","Original panels plus the FCS timing plate"],["Audit chart / table","Both forms included"],
],[205,299])
body("A literal export of every selector combination would create more than 200,000 repeated cells. The plates below preserve every dimension and show its full range.")
head("Decision-map key")
body("Each square answers what to do after a play that leaves the clock running. The maps use 3rd-and-5 at the possession team's 35 so the possession, timeout, score, time, and strength effects can be compared cleanly.")

for number,strength,key,label in [(1,-7,"rec_m7","They are better by 7"),(2,0,"rec_0","Even teams"),(3,7,"rec_p7","Brown is better by 7")]:
    page();title(f"A{number}. Timeout decision map: {label}")
    chart(CHART[key],7.0)
    body("Use the row for possession and the column for timeouts left. Score is vertical and game time is horizontal.")

page();title("A4. Down, distance, and field position")
chart(CHART["triggers"],7.0)
body("Darker cells mean the start-call point comes earlier. Blank cells mean the rule never says 'call now' in the last 15 minutes for that fixed setting.")

page();title("A5. What one timeout adds")
chart(CHART["values"],7.0)
body("The color is the modeled gain from the seconds saved by one timeout. This is the static version of the dashboard's 'Show numbers' setting.")

page();title("A6. Three stops and delay of game")
chart(CHART["timeline"],7.0)
body("Three immediate defensive timeouts preserve about 1:40 in this average sequence. The exact game result depends on the live play time and the next down.")
chart(CHART["penalty"],7.0)
body("In the eight tested spots, a five-yard penalty cost 1.8 to 4.7 win-probability points. The saved-timeout average was 0.33 points.")

page();title("A7. Time used per snap")
chart(CHART["playtime"],7.0)
body("Faded Brown bars have fewer than 30 snaps. The national and Ivy samples are more useful for setting a clock assumption.")

page();title("A8. Play clock and defensive urgency")
chart(CHART["playclock"],7.0)
body("Clock-kill teams snapped with a median of 5 seconds left. Only 35% snapped with 3 seconds or less.")
chart(CHART["reality"],7.0)
body("After the two-minute holdout, Brown called timeout in 8 of 17 flags. The FCS rate was 50.4% of 979; the Ivy rate was 65.5% of 84.")

page();title("A9. Brown's adjusted defensive audit")
miss=[]
for r in D["defense_reality"]["brown_missed"]:
    miss.append([f"{r['season']} {team(r['opponent'])}",clock(r["clock"]),lead_text(r["lead"]),f"{r['next_down']} down",r["timeouts"],f"{r['lost']} sec"])
table(["Game","Time","Score","Next snap","TO","Clock lost"],miss,[160,60,70,72,38,72],small_cells=True)
body("Nine adjusted flags had no timeout. They averaged 37.9 seconds; eight began with all three timeouts.")
head("Set aside because the series reaches 2:00")
held=[]
for r in D["defense_reality"]["brown_two_minute_excluded"]:
    held.append([f"{r['season']} {team(r['opponent'])}",clock(r["snap_clock"]),clock(r["next_snap_clock"]),f"{r['next_down']} down",r["timeouts"],"Called" if r["called"] else "No call"])
table(["Game","Snap","Next","Next down","TO","Result"],held,[160,58,58,72,38,118],small_cells=True)
body("These nine rows are outside the call-rate calculation. Five used a charged timeout and four did not.")

page();title("A10. How Brown uses timeouts")
chart(CHART["audit"],7.0)
body("Brown used 3.38 timeouts per game in the sample. The use labels are inferred from game state.")
purposes=D["audit"]["purposes"]
rates=[]
for p in purposes:
    rates.append([PURPOSE[p]]+[f"{D['audit']['rates'][g][p]:.2f}" for g in ["Brown","Rest of Ivy","All FBS/FCS"]])
rates.append(["Total"]+[f"{D['audit']['rates'][g]['total']:.2f}" for g in ["Brown","Rest of Ivy","All FBS/FCS"]])
table(["Use","Brown","Other Ivy","All FBS/FCS"],rates,[225,80,90,100],small_cells=True)
unused=[]
for label,key in [("Left at halftime","half"),("Left at end of game","game")]:
    unused.append([label]+[f"{D['audit']['unused'][g][key]:.2f}" for g in ["Brown","Rest of Ivy","All FBS/FCS"]])
table(["Unused","Brown","Other Ivy","All FBS/FCS"],unused,[225,80,90,100],small_cells=True)
body("Brown carried fewer timeouts into halftime than the comparison groups. End-of-game unused timeouts were close to the national level.")

page();title("A11. Brown play-clock timeouts and close losses")
log=[]
for r in D["brown_log"]:
    log.append([f"{r['season']} {team(r['opponent'])}",f"Q{r['quarter']} {clock(r['clock'])}",f"{r['down']} & {r['distance']}",lead_text(r['lead']),r['left_after'],f"{r['penalty_cost']:.2f}","Timeout"])
table(["Game","Time","Down","Score","TO left","5-yard cost","Cheaper"],log,[125,70,68,62,45,68,64],small_cells=True)
body("The five-yard cost exceeded the 0.33-point saved-timeout average in all seven logged cases. The comparison is a screen, not a same-state late-game simulation.")
loss=[]
for r in D["close_losses"]["brown_games"]:
    loss.append([f"{r['season']} {team(r['opponent'])}",-r["margin"],r["unused"]])
table(["Close loss","Lost by","Timeouts left"],loss,[260,110,134],small_cells=True)
body("Three of six close losses ended with a timeout left. This identifies film to review; it does not show causation.")

page();title("A12. Model checks")
chart(CHART["calibration"],7.0)
body("The 2025 calibration is close in broad bins. The example state shows that the PFF value is far below the fitted model and the small Ivy history sample.")
head("Method in plain terms")
table(["Step","What was done"],[
    ["Timeouts","A drop in PFF's timeout count was treated as a timeout."],
    ["Play time","Snap clocks and play clocks split each interval into live play and the wait."],
    ["Urgency","The rule compares time left after expected stops with successful hurry-up drive time."],
    ["Win chance","Score, expected points, time, and team strength feed a fitted probability model."],
    ["Recommendation","The rule checks urgency, remaining downs, timeouts, and whether two scores are needed."],
],[120,384])
small("Known limits: timeouts and purposes are reconstructed; drive timing excludes failed drives; full-season strength leaks later results; repeated plays from the same game are not independent; the two-minute timeout is not modeled directly in the defensive audit rule.")

page();title("A13. Offensive timeout, spike, and clock-kill timing")
chart(CHART["spike"],7.0)
body("The first-down chain stoppage cuts the FCS hurry-and-spike cost to 5.2 seconds. Without a first down, the cost is 12.2 seconds and the spike still uses a down.")
kill_rows=[]
for group in ["FCS","Ivy","Brown"]:
    for key,label in [("four_minute_run","Clock-kill run"),("kneel","Kneel")]:
        cell=C["clock_kill"][group][key]
        kill_rows.append([group,label,cell["n"],f'{cell["live"]["mean"]:.1f}',f'{cell["wait"]["mean"]:.1f}',f'{cell["modeled_total_mean"]:.1f}'])
table(["Group","Play","n","Live","Wait","Total"],kill_rows,[72,125,55,72,80,80],small_cells=True)
body("Live is snap to whistle. Wait is whistle to the next snap and counts only when the game clock keeps running.")
small("The spike estimate uses 269 FCS, 21 Ivy, and two Brown sequences. The prior play's live time is estimated from comparable final-two-minute snaps because the export records the clock at the snap, not at the whistle.")


MD.write_text("\n".join(md))


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor(GRID)); canvas.line(54,43,558,43)
    canvas.setFont("Helvetica",7.4); canvas.setFillColor(colors.HexColor(MUTED))
    canvas.drawString(54,28,"BROWN FOOTBALL  |  END-OF-GAME CLOCK DECISIONS")
    canvas.drawRightString(558,28,str(doc.page))
    canvas.restoreState()


doc=SimpleDocTemplate(str(PDF),pagesize=(612,792),leftMargin=54,rightMargin=54,topMargin=43,bottomMargin=55,
                      title="Brown Football: End-of-game Clock Decisions",author="Brown Football Analytics")
doc.build(story,onFirstPage=footer,onLaterPages=footer)
print(PDF)
