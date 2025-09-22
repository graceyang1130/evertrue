import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


MIN_PLAYS_PER_BAR = 5
USE_LEGACY_EPA = False
EXCLUDE_GARBAGETIME = True
DOWNS_TO_PLOT = [1, 2, 3, 4]
ALSO_PLOT_EPA_BARS = False



def run_all_plots(
    offense_csv,
    defense_csv,
    school_name,
    recent_years=None,   # e.g., 3 -> keep only last 3 seasons present in the file(s)
    min_season=None      # e.g., 2022 -> keep seasons >= 2022
):
    offense = pd.read_csv(offense_csv, low_memory=False)
    defense = pd.read_csv(defense_csv, low_memory=False)

    offense = apply_season_filter(offense, recent_years, min_season)
    defense = apply_season_filter(defense, recent_years, min_season)

    o = clean_data(offense, is_defense=False)
    d = clean_data(defense, is_defense=True)  # defense = "EPA allowed" perspective

    # OFFENSE & DEFENSE: counts by play type for each down
    for down in DOWNS_TO_PLOT:
        make_counts_by_type_chart(o, down, f"{school_name} offense")
        make_counts_by_type_chart(d, down, f"{school_name} defense (EPA allowed)")

        if ALSO_PLOT_EPA_BARS:
            make_epa_by_type_chart(o, down, f"{school_name} offense")
            make_epa_by_type_chart(d, down, f"{school_name} defense (EPA allowed)")


# --------------------------
# Filters
# --------------------------
def apply_season_filter(df: pd.DataFrame, recent_years, min_season):
    if "pff_GAMESEASON" not in df.columns:
        return df

    tmp = df.copy()
    tmp["pff_GAMESEASON"] = pd.to_numeric(tmp["pff_GAMESEASON"], errors="coerce")

    if min_season is not None:
        tmp = tmp[tmp["pff_GAMESEASON"] >= int(min_season)]

    if recent_years is not None:
        # keep last N seasons **present in this file**
        max_season = int(tmp["pff_GAMESEASON"].max())
        cutoff = max_season - int(recent_years) + 1
        tmp = tmp[tmp["pff_GAMESEASON"] >= cutoff]

    return tmp


# --------------------------
# Prep / classification
# --------------------------
def clean_data(df, is_defense: bool) -> pd.DataFrame:
    df = df.copy()

    epa_col = "pff_EXPECTED_POINTS_ADDED_LEGACY" if USE_LEGACY_EPA else "pff_EXPECTED_POINTS_ADDED"
    needed = [
        "pff_DOWN", "pff_RUNPASS", "pff_QBSCRAMBLE",
        "pff_SCREEN", "pff_PLAYACTION", "pff_RUNPASSOPTION", "pff_DEEPPASS",
        "pff_RUNCONCEPTPRIMARY", "pff_DRAW",
        "pff_NOPLAY", "pff_PENALTY", "pff_GARBAGETIME",
        epa_col
    ]
    for c in needed:
        if c not in df.columns:
            df[c] = np.nan

    flag_cols = ["pff_QBSCRAMBLE", "pff_SCREEN", "pff_PLAYACTION", "pff_RUNPASSOPTION",
                 "pff_DEEPPASS", "pff_DRAW", "pff_NOPLAY", "pff_PENALTY", "pff_GARBAGETIME"]
    for c in flag_cols:
        df[c] = df[c].astype(str).str.upper().fillna("N").replace({"TRUE":"Y","FALSE":"N"})

    # valid plays
    mask_valid = (df["pff_NOPLAY"] != "Y") & (df["pff_PENALTY"] != "Y") & (~df[epa_col].isna())
    if EXCLUDE_GARBAGETIME:
        mask_valid &= (df["pff_GARBAGETIME"] != "Y")
    df = df.loc[mask_valid].copy()

    # Types / styles
    df["play_type"]  = df.apply(classify_type, axis=1)
    df["play_style"] = df.apply(classify_style, axis=1)

    df["pff_DOWN"] = pd.to_numeric(df["pff_DOWN"], errors="coerce").fillna(-1).astype(int)

    # EPA (kept as offense perspective; defense frames are "EPA allowed")
    df["EPA"] = pd.to_numeric(df[epa_col], errors="coerce")

    # if you wanted "Defensive EPA" (positive good), flip sign:
    # if is_defense:
    #     df["EPA"] = -df["EPA"]

    return df[["pff_DOWN", "play_type", "play_style", "EPA"]].reset_index(drop=True)


def classify_type(row) -> str:
    if str(row.get("pff_QBSCRAMBLE", "N")).upper() != "N":
        return "Scramble"
    rp = str(row.get("pff_RUNPASS", "")).upper()
    if rp == "P":
        return "Pass"
    if rp == "R":
        return "Run"
    return "Other"


def classify_style(row) -> str:
    t = classify_type(row)
    if t == "Pass":
        return classify_pass_style(row)
    if t == "Run":
        return classify_run_style(row)
    if t == "Scramble":
        return "Scramble"
    return "Other"


def classify_pass_style(row) -> str:
    if str(row.get("pff_SCREEN", "N")).upper() == "Y":
        return "Screen"
    if str(row.get("pff_PLAYACTION", "N")).upper() == "Y":
        return "Play Action"
    if str(row.get("pff_RUNPASSOPTION", "N")).upper() == "Y":
        return "RPO"
    if str(row.get("pff_DEEPPASS", "N")).upper() == "Y":
        return "Deep"
    return "Standard"


def classify_run_style(row) -> str:
    if str(row.get("pff_DRAW", "N")).upper() == "Y":
        return "Draw"
    concept = str(row.get("pff_RUNCONCEPTPRIMARY", "")).upper()
    if "INSIDE ZONE" in concept or "INSIDEZONE" in concept:
        return "Inside Zone"
    if "OUTSIDE ZONE" in concept or "OUTSIDEZONE" in concept or "WIDE ZONE" in concept:
        return "Outside Zone"
    if "POWER" in concept or "COUNTER" in concept or "GAP" in concept or "DUO" in concept:
        return "Gap/Power/Counter"
    return "Other Run"


# --------------------------
# Charts (by down)
# --------------------------
def make_counts_by_type_chart(df, down: int, label_prefix: str):
    d = df[df["pff_DOWN"] == down]
    if d.empty:
        return
    g = d.groupby("play_type")["play_type"].count().rename("count").reset_index()
    g = g[g["count"] >= MIN_PLAYS_PER_BAR]
    if g.empty:
        return

    plt.figure(figsize=(10, 6))
    bars = plt.bar(g["play_type"], g["count"])
    for bar, cnt in zip(bars, g["count"]):
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, h, f"n={int(cnt)}",
                 ha="center", va="bottom", fontsize=9)
    plt.ylabel("# of Plays")
    plt.title(f"{label_prefix}: Play Count by Type — Down {down}")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{label_prefix} - Down {down} - Count by Type.png", dpi=150)
    plt.close()


def make_epa_by_type_chart(df, down: int, label_prefix: str):
    # optional, controlled by ALSO_PLOT_EPA_BARS
    d = df[df["pff_DOWN"] == down]
    if d.empty:
        return
    g = d.groupby("play_type")["EPA"].agg(["count", "mean"]).reset_index()
    g = g[g["count"] >= MIN_PLAYS_PER_BAR]
    if g.empty:
        return

    plt.figure(figsize=(10, 6))
    bars = plt.bar(g["play_type"], g["mean"])
    for bar, cnt in zip(bars, g["count"]):
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, h, f"n={int(cnt)}",
                 ha="center", va="bottom", fontsize=9)
    plt.ylabel("Mean EPA")
    plt.title(f"{label_prefix}: Mean EPA by Play Type — Down {down}")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(f"{label_prefix} - Down {down} - EPA by Type.png", dpi=150)
    plt.close()


def main():
    run_all_plots(
        "../../data/2025/harvard/harvard_offense.csv",
        "../../data/2025/harvard/harvard_defense.csv",
        "Harvard",
        min_season=2022
    )
