import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# =========================
# Config
# =========================
MIN_PLAYS_PER_BAR = 5
USE_LEGACY_EPA = False
EXCLUDE_GARBAGETIME = True
DOWNS_TO_PLOT = [1, 2, 3, 4]
ALSO_PLOT_EPA_BARS = False
OUT_DIR = "out"     # all PNGs go here


# =========================
# Helpers
# =========================
def _to_bool(x):
    """
    Robust truthy/falsey mapper for PFF flag columns that can be 1/0, Y/N, True/False, or blank.
    """
    s = str(x).strip().lower()
    if s in {"1", "y", "yes", "true", "t"}:
        return True
    if s in {"0", "n", "no", "false", "f", ""}:
        return False
    return False


def ensure_out_dir(path: str):
    if not os.path.isdir(path):
        os.makedirs(path, exist_ok=True)


def save_and_show(fig, filepath):
    fig.savefig(filepath, dpi=150, bbox_inches="tight")
    print(f"[saved] {filepath}")
    plt.show()  # will show if your environment supports it
    plt.close(fig)


# =========================
# Season filters
# =========================
def apply_season_filter(df: pd.DataFrame, recent_years=None, min_season=None) -> pd.DataFrame:
    """
    Optionally keep only the last N seasons present and/or seasons >= min_season.
    """
    if "pff_GAMESEASON" not in df.columns:
        return df

    tmp = df.copy()
    tmp["pff_GAMESEASON"] = pd.to_numeric(tmp["pff_GAMESEASON"], errors="coerce")

    if min_season is not None:
        tmp = tmp[tmp["pff_GAMESEASON"] >= int(min_season)]

    if recent_years is not None and not tmp["pff_GAMESEASON"].isna().all():
        max_season = int(tmp["pff_GAMESEASON"].max())
        cutoff = max_season - int(recent_years) + 1
        tmp = tmp[tmp["pff_GAMESEASON"] >= cutoff]

    return tmp


# =========================
# Cleaning & classification
# =========================
def clean_data(df: pd.DataFrame, is_defense: bool) -> pd.DataFrame:
    """
    - drop penalties, no-plays, special teams, non-1..4 downs, (optional) garbage time
    - classify play_type (Pass/Run/Scramble/Other) and play_style
    - keep EPA as offense perspective; defense frame is 'EPA allowed'
    """
    df = df.copy()

    epa_col = "pff_EXPECTED_POINTS_ADDED_LEGACY" if USE_LEGACY_EPA else "pff_EXPECTED_POINTS_ADDED"
    need_cols = [
        "pff_DOWN", "pff_RUNPASS", "pff_QBSCRAMBLE", "pff_SCREEN", "pff_PLAYACTION",
        "pff_RUNPASSOPTION", "pff_DEEPPASS", "pff_RUNCONCEPTPRIMARY", "pff_DRAW",
        "pff_NOPLAY", "pff_PENALTY", "pff_GARBAGETIME", "pff_SPECIALTEAMSTYPE",
        epa_col
    ]
    for c in need_cols:
        if c not in df.columns:
            df[c] = np.nan

    # numerics & flags
    df["pff_DOWN"] = pd.to_numeric(df["pff_DOWN"], errors="coerce").fillna(-1).astype(int)

    flag_cols = [
        "pff_QBSCRAMBLE", "pff_SCREEN", "pff_PLAYACTION", "pff_RUNPASSOPTION",
        "pff_DEEPPASS", "pff_DRAW", "pff_NOPLAY", "pff_PENALTY", "pff_GARBAGETIME"
    ]
    for c in flag_cols:
        df[c] = df[c].map(_to_bool)

    df["pff_RUNPASS"] = df["pff_RUNPASS"].astype(str).str.upper().str.strip()
    df["EPA"] = pd.to_numeric(df[epa_col], errors="coerce")

    # filter valid football plays (offense/defense perspective)
    valid = (
        (df["pff_NOPLAY"] == False) &
        (df["pff_PENALTY"] == False) &
        (df["EPA"].notna()) &
        (df["pff_DOWN"].between(1, 4)) &
        (df["pff_SPECIALTEAMSTYPE"].isna() | (df["pff_SPECIALTEAMSTYPE"].astype(str).str.strip() == "")) &
        (
            (df["pff_RUNPASS"].isin(["P", "R"])) |
            (df["pff_QBSCRAMBLE"] == True)
        )
    )
    if EXCLUDE_GARBAGETIME:
        valid &= (df["pff_GARBAGETIME"] == False)

    df = df.loc[valid].copy()

    # classify types/styles
    df["play_type"] = df.apply(classify_type, axis=1)
    df["play_style"] = df.apply(classify_style, axis=1)

    # If you want defensive EPA (positive-good-for-defense), flip sign here:
    # if is_defense:
    #     df["EPA"] = -df["EPA"]

    return df[["pff_DOWN", "play_type", "play_style", "EPA"]].reset_index(drop=True)


def classify_type(row) -> str:
    if row["pff_QBSCRAMBLE"]:
        return "Scramble"
    rp = row.get("pff_RUNPASS", "")
    if rp == "P":
        return "Pass"
    if rp == "R":
        return "Run"
    return "Other"


def classify_style(row) -> str:
    t = row["play_type"]
    if t == "Pass":
        if row["pff_SCREEN"]:
            return "Screen"
        if row["pff_PLAYACTION"]:
            return "Play Action"
        if row["pff_RUNPASSOPTION"]:
            return "RPO"
        if row["pff_DEEPPASS"]:
            return "Deep"
        return "Standard"
    if t == "Run":
        if row["pff_DRAW"]:
            return "Draw"
        concept = str(row.get("pff_RUNCONCEPTPRIMARY", "")).upper()
        if "INSIDE ZONE" in concept or "INSIDEZONE" in concept:
            return "Inside Zone"
        if "OUTSIDE ZONE" in concept or "OUTSIDEZONE" in concept or "WIDE ZONE" in concept:
            return "Outside Zone"
        if any(k in concept for k in ["POWER", "COUNTER", "GAP", "DUO"]):
            return "Gap/Power/Counter"
        return "Other Run"
    if t == "Scramble":
        return "Scramble"
    return "Other"


# =========================
# Charts
# =========================
def make_counts_by_type_chart(df: pd.DataFrame, down: int, label_prefix: str, out_dir: str):
    d = df[df["pff_DOWN"] == down]
    if d.empty:
        print(f"[skip] {label_prefix} — Down {down}: no plays")
        return
    g = d.groupby("play_type")["play_type"].count().rename("count").reset_index()
    g = g[g["count"] >= MIN_PLAYS_PER_BAR]
    if g.empty:
        print(f"[skip] {label_prefix} — Down {down}: fewer than {MIN_PLAYS_PER_BAR} plays per bar")
        return

    fig = plt.figure(figsize=(9, 6))
    bars = plt.bar(g["play_type"], g["count"])
    for bar, cnt in zip(bars, g["count"]):
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, h, f"n={int(cnt)}",
                 ha="center", va="bottom", fontsize=9)
    plt.ylabel("# of Plays")
    plt.title(f"{label_prefix}: Play Count by Type — Down {down}")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()

    filepath = os.path.join(out_dir, f"{label_prefix} - Down {down} - Count by Type.png")
    save_and_show(fig, filepath)


def make_epa_by_type_chart(df: pd.DataFrame, down: int, label_prefix: str, out_dir: str):
    d = df[df["pff_DOWN"] == down]
    if d.empty:
        print(f"[skip] {label_prefix} — Down {down}: no plays")
        return
    g = d.groupby("play_type")["EPA"].agg(["count", "mean"]).reset_index()
    g = g[g["count"] >= MIN_PLAYS_PER_BAR]
    if g.empty:
        print(f"[skip] {label_prefix} — Down {down}: fewer than {MIN_PLAYS_PER_BAR} plays per bar")
        return

    fig = plt.figure(figsize=(9, 6))
    bars = plt.bar(g["play_type"], g["mean"])
    for bar, cnt in zip(bars, g["count"]):
        h = bar.get_height()
        plt.text(bar.get_x() + bar.get_width() / 2, h, f"n={int(cnt)}",
                 ha="center", va="bottom", fontsize=9)
    plt.ylabel("Mean EPA")
    plt.title(f"{label_prefix}: Mean EPA by Type — Down {down}")
    plt.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()

    filepath = os.path.join(out_dir, f"{label_prefix} - Down {down} - EPA by Type.png")
    save_and_show(fig, filepath)


# =========================
# Debug prints
# =========================
def print_debug_counts(tag: str, raw: pd.DataFrame, cleaned: pd.DataFrame):
    print(f"\n=== {tag} ===")
    print(f"raw rows: {len(raw):,}")
    if "pff_GAMESEASON" in raw.columns:
        seasons = sorted(pd.to_numeric(raw["pff_GAMESEASON"], errors="coerce").dropna().unique().astype(int))
        print(f"seasons present: {seasons}")
    print(f"cleaned rows (plays used): {len(cleaned):,}")
    for down in [1, 2, 3, 4]:
        cnt = (cleaned["pff_DOWN"] == down).sum()
        print(f"  down {down}: {cnt:,} plays")
    print(cleaned["play_type"].value_counts().to_string())


# =========================
# Orchestration
# =========================
def run_all_plots(
    offense_csv: str,
    defense_csv: str,
    school_name: str,
    recent_years: int | None = None,  # e.g., 3 keeps the last 3 seasons present in file
    min_season: int | None = None,    # e.g., 2022 keeps seasons >= 2022
    out_dir: str = OUT_DIR
):
    ensure_out_dir(out_dir)

    offense_raw = pd.read_csv(offense_csv, low_memory=False)
    defense_raw = pd.read_csv(defense_csv, low_memory=False)

    offense = apply_season_filter(offense_raw, recent_years, min_season)
    defense = apply_season_filter(defense_raw, recent_years, min_season)

    o = clean_data(offense, is_defense=False)
    d = clean_data(defense, is_defense=True)  # defense = "EPA allowed"

    print_debug_counts(f"{school_name} — OFFENSE", offense, o)
    print_debug_counts(f"{school_name} — DEFENSE", defense, d)

    for down in DOWNS_TO_PLOT:
        make_counts_by_type_chart(o, down, f"{school_name} offense", out_dir)
        make_counts_by_type_chart(d, down, f"{school_name} defense (EPA allowed)", out_dir)
        if ALSO_PLOT_EPA_BARS:
            make_epa_by_type_chart(o, down, f"{school_name} offense", out_dir)
            make_epa_by_type_chart(d, down, f"{school_name} defense (EPA allowed)", out_dir)


# =========================
# Example entry point
# =========================
if __name__ == "__main__":
    # Update these paths to your actual CSVs
    run_all_plots(
        offense_csv="../../data/2025/harvard/harvard_offense.csv",
        defense_csv="../../data/2025/harvard/harvard_defense.csv",
        school_name="Harvard",
        # choose one or both:
        recent_years=None,  # e.g., 3
        min_season=2022,    # e.g., 2022
        out_dir="out"
    )
