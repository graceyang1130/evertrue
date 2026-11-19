import matplotlib
matplotlib.use("Agg")
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np

IVY_OFFENSE_PATH = "../ivyo22to26.csv"
IVY_DEFENSE_PATH = "../ivyd_22to26.csv"


def run_all_plots():
    offense = pd.read_csv("harvard_offense.csv")
    defense = pd.read_csv("harvard_defense.csv")

    ivy_o_raw = pd.read_csv(IVY_OFFENSE_PATH, low_memory=False)
    ivy_d_raw = pd.read_csv(IVY_DEFENSE_PATH, low_memory=False)

    o_clean = clean_data(offense)
    d_clean = clean_data(defense)
    ivy_o   = clean_data(ivy_o_raw)
    ivy_d   = clean_data(ivy_d_raw)

    school = "Harvard"

    # offense
    playcall_by_distance(o_clean, 3, school + " offense")
    playcall_by_distance(o_clean, 4, school + " offense")

    playcall_success_by_distance(o_clean, 3, school + " offense", ivy_df=ivy_o)
    playcall_success_by_distance(o_clean, 4, school + " offense", ivy_df=ivy_o)

    play_percentage_by_distance(o_clean, 3, school + " offense", ivy_df=ivy_o)
    play_percentage_by_distance(o_clean, 4, school + " offense", ivy_df=ivy_o)

    playcall_success_by_distance_category(o_clean, 3, school + " offense", ivy_df=ivy_o)
    playcall_success_by_distance_category(o_clean, 4, school + " offense", ivy_df=ivy_o)

    # defense
    playcall_by_distance(d_clean, 3, school + " defense")
    playcall_by_distance(d_clean, 4, school + " defense")

    playcall_success_by_distance(d_clean, 3, school + " defense", ivy_df=ivy_d)
    playcall_success_by_distance(d_clean, 4, school + " defense", ivy_df=ivy_d)

    playcall_success_by_distance_category(d_clean, 3, school + " defense", ivy_df=ivy_d)
    playcall_success_by_distance_category(d_clean, 4, school + " defense", ivy_df=ivy_d)


def clean_data(unclean):
    clean = unclean[["pff_DOWN", "pff_DISTANCE", "pff_QBSCRAMBLE", "pff_RUNPASS", "pff_FIRST_DOWN_GAINED"]].copy()
    clean["pff_FIRST_DOWN_GAINED"] = clean["pff_FIRST_DOWN_GAINED"].fillna(0)
    clean["pff_QBSCRAMBLE"] = clean["pff_QBSCRAMBLE"].fillna('N')
    return clean


def _ivy_pct_by_distance(ivy_df, desired_down, distance_bins):
    """Compute ivy-average pass/run/scramble % at each distance bin.

    distance_bins is a list where entries are integers 1..N or the string '15+'.
    Returns three lists (pass_pct, run_pct, scramble_pct) parallel to distance_bins.
    """
    sub = ivy_df[ivy_df["pff_DOWN"] == desired_down]
    pass_pct, run_pct, scramble_pct = [], [], []

    for d in distance_bins:
        if d == "15+":
            sel = sub[sub["pff_DISTANCE"] >= 15]
        else:
            sel = sub[sub["pff_DISTANCE"] == d]

        total = len(sel)
        if total > 0:
            p = len(sel[(sel["pff_RUNPASS"] == "P") & (sel["pff_QBSCRAMBLE"] == 'N')]) / total * 100
            r = len(sel[(sel["pff_RUNPASS"] == "R") & (sel["pff_QBSCRAMBLE"] == 'N')]) / total * 100
            s = len(sel[sel["pff_QBSCRAMBLE"] != 'N']) / total * 100
        else:
            p = r = s = float('nan')

        pass_pct.append(p)
        run_pct.append(r)
        scramble_pct.append(s)

    return pass_pct, run_pct, scramble_pct


def _ivy_success_by_distance(ivy_df, desired_down, distance_bins):
    """Compute ivy-average success rate for pass/run/scramble at each distance bin."""
    sub = ivy_df[ivy_df["pff_DOWN"] == desired_down]
    pass_sr, run_sr, scramble_sr = [], [], []

    for d in distance_bins:
        if d == "11+":
            p_sel = sub[(sub["pff_RUNPASS"] == "P") & (sub["pff_QBSCRAMBLE"] == 'N') & (sub["pff_DISTANCE"] >= 11)]
            r_sel = sub[(sub["pff_RUNPASS"] == "R") & (sub["pff_QBSCRAMBLE"] == 'N') & (sub["pff_DISTANCE"] >= 11)]
            s_sel = sub[(sub["pff_QBSCRAMBLE"] != 'N') & (sub["pff_DISTANCE"] >= 11)]
        else:
            p_sel = sub[(sub["pff_RUNPASS"] == "P") & (sub["pff_QBSCRAMBLE"] == 'N') & (sub["pff_DISTANCE"] == d)]
            r_sel = sub[(sub["pff_RUNPASS"] == "R") & (sub["pff_QBSCRAMBLE"] == 'N') & (sub["pff_DISTANCE"] == d)]
            s_sel = sub[(sub["pff_QBSCRAMBLE"] != 'N') & (sub["pff_DISTANCE"] == d)]

        cp, cr, cs = len(p_sel), len(r_sel), len(s_sel)
        pass_sr.append((p_sel["pff_FIRST_DOWN_GAINED"] == 1).sum() / cp if cp > 0 else float('nan'))
        run_sr.append((r_sel["pff_FIRST_DOWN_GAINED"] == 1).sum() / cr if cr > 0 else float('nan'))
        scramble_sr.append((s_sel["pff_FIRST_DOWN_GAINED"] == 1).sum() / cs if cs > 0 else float('nan'))

    return pass_sr, run_sr, scramble_sr


def _ivy_success_by_category(ivy_df, desired_down):
    """Compute ivy-average success rate for pass/run/scramble for the four distance categories."""
    sub = ivy_df[ivy_df["pff_DOWN"] == desired_down].copy()
    sub['distance_category'] = pd.cut(
        sub['pff_DISTANCE'],
        bins=[0, 2, 6, 10, np.inf],
        labels=['1-2', '3-6', '7-10', '11+'],
        right=True, include_lowest=True,
    )

    pass_sr, run_sr, scramble_sr = [], [], []
    for cat in ['1-2', '3-6', '7-10', '11+']:
        sel = sub[sub['distance_category'] == cat]
        p_sel = sel[(sel["pff_RUNPASS"] == "P") & (sel["pff_QBSCRAMBLE"] == 'N')]
        r_sel = sel[(sel["pff_RUNPASS"] == "R") & (sel["pff_QBSCRAMBLE"] == 'N')]
        s_sel = sel[sel["pff_QBSCRAMBLE"] != 'N']

        cp, cr, cs = len(p_sel), len(r_sel), len(s_sel)
        pass_sr.append((p_sel["pff_FIRST_DOWN_GAINED"] == 1).sum() / cp if cp > 0 else float('nan'))
        run_sr.append((r_sel["pff_FIRST_DOWN_GAINED"] == 1).sum() / cr if cr > 0 else float('nan'))
        scramble_sr.append((s_sel["pff_FIRST_DOWN_GAINED"] == 1).sum() / cs if cs > 0 else float('nan'))

    return pass_sr, run_sr, scramble_sr


def _draw_ivy_ticks(ax, x_centers_by_type, values_by_type, bar_width):
    """Draw charcoal horizontal tick marks with white outline at ivy average positions.

    Each tick spans the full width of the corresponding bar and is centered
    on the ivy average value, making above/below comparisons immediate.
    """
    tick_half = bar_width * 0.44
    label_added = False
    for x_pos, vals in zip(x_centers_by_type, values_by_type):
        vals_arr = np.array(vals, dtype=float)
        for xi, val in zip(x_pos, vals_arr):
            if not np.isnan(val):
                label = 'Ivy League Avg' if not label_added else '_nolegend_'
                line, = ax.plot(
                    [xi - tick_half, xi + tick_half], [val, val],
                    color='#2d2d2d', linewidth=3.5, solid_capstyle='round',
                    label=label, zorder=5,
                )
                line.set_path_effects([pe.withStroke(linewidth=6, foreground='white')])
                label_added = True


def playcall_by_distance(df, desired_down, school="Brown Offense"):
    required_columns = ["pff_RUNPASS", "pff_QBSCRAMBLE", "pff_DOWN", "pff_DISTANCE"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Dataframe is missing required column: {col}")

    plays = df[df["pff_DOWN"] == desired_down]
    pass_plays = plays[(plays["pff_RUNPASS"] == "P") & (plays["pff_QBSCRAMBLE"] == 'N')]
    run_plays = plays[(plays["pff_RUNPASS"] == "R") & (plays["pff_QBSCRAMBLE"] == 'N')]
    scramble_plays = plays[plays["pff_QBSCRAMBLE"] != 'N']

    rates_pass = []
    rates_run = []
    rates_scramble = []

    for distance in range(1, 15):
        rates_pass.append(len(pass_plays[pass_plays["pff_DISTANCE"] == distance]))
        rates_run.append(len(run_plays[run_plays["pff_DISTANCE"] == distance]))
        rates_scramble.append(len(scramble_plays[scramble_plays["pff_DISTANCE"] == distance]))

    rates_pass.append(len(pass_plays[pass_plays["pff_DISTANCE"] >= 15]))
    rates_run.append(len(run_plays[run_plays["pff_DISTANCE"] >= 15]))
    rates_scramble.append(len(scramble_plays[scramble_plays["pff_DISTANCE"] >= 15]))

    distances = list(range(1, 15)) + ['15+']
    bar_width = 0.35
    index = np.arange(len(distances))

    plt.figure(figsize=(12, 7))

    pass_bars     = plt.bar(index, rates_pass, bar_width, label='Pass Plays', color='blue')
    scramble_bars = plt.bar(index, rates_scramble, bar_width, bottom=rates_pass, label='Scramble Plays', color='orange')
    run_bars      = plt.bar(index + bar_width, rates_run, bar_width, label='Run Plays', color='green')

    for bar in pass_bars:
        h = bar.get_height()
        if h > 0:
            plt.text(bar.get_x() + bar.get_width()/2, h + 0.5, f"{int(h)}",
                     ha="center", va="bottom", fontsize=8)

    for bar in scramble_bars:
        top = bar.get_y() + bar.get_height()
        seg = bar.get_height()
        if seg > 0:
            plt.text(bar.get_x() + bar.get_width()/2, top + 0.5, f"{int(seg)}",
                     ha="center", va="bottom", fontsize=8)

    for bar in run_bars:
        h = bar.get_height()
        if h > 0:
            plt.text(bar.get_x() + bar.get_width()/2, h + 0.5, f"{int(h)}",
                     ha="center", va="bottom", fontsize=8)

    plt.xlabel('Distance (Yards)')
    plt.ylabel('# of Plays')
    plt.title(f'{school} Down #{desired_down}: # of Plays by Distance')
    plt.xticks(index + bar_width / 2, distances)
    plt.legend()
    plt.grid(axis='y')

    plt.tight_layout()
    plt.savefig(f'{school}_{desired_down}_#plays.png')
    plt.show()


def play_percentage_by_distance(df, desired_down, school="Brown Offense", ivy_df=None):
    required_columns = ["pff_RUNPASS", "pff_QBSCRAMBLE", "pff_DOWN", "pff_DISTANCE"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Dataframe is missing required column: {col}")

    plays = df[df["pff_DOWN"] == desired_down]
    pass_plays    = plays[(plays["pff_RUNPASS"] == "P") & (plays["pff_QBSCRAMBLE"] == 'N')]
    run_plays     = plays[(plays["pff_RUNPASS"] == "R") & (plays["pff_QBSCRAMBLE"] == 'N')]
    scramble_plays = plays[plays["pff_QBSCRAMBLE"] != 'N']

    distance_bins = list(range(1, 15)) + ["15+"]

    percentages_pass, percentages_run, percentages_scramble = [], [], []
    counts_pass, counts_run, counts_scramble = [], [], []

    for d in distance_bins:
        if d == "15+":
            p_sel = pass_plays[pass_plays["pff_DISTANCE"] >= 15]
            r_sel = run_plays[run_plays["pff_DISTANCE"] >= 15]
            s_sel = scramble_plays[scramble_plays["pff_DISTANCE"] >= 15]
            total_sel = plays[plays["pff_DISTANCE"] >= 15]
        else:
            p_sel = pass_plays[pass_plays["pff_DISTANCE"] == d]
            r_sel = run_plays[run_plays["pff_DISTANCE"] == d]
            s_sel = scramble_plays[scramble_plays["pff_DISTANCE"] == d]
            total_sel = plays[plays["pff_DISTANCE"] == d]

        cp, cr, cs = len(p_sel), len(r_sel), len(s_sel)
        counts_pass.append(cp)
        counts_run.append(cr)
        counts_scramble.append(cs)

        total = len(total_sel)
        if total > 0:
            pp = cp / total
            pr = cr / total
            ps = cs / total
            s = pp + pr + ps
            if s > 0:
                pp, pr, ps = pp / s, pr / s, ps / s
        else:
            pp = pr = ps = 0.0

        percentages_pass.append(pp * 100.0)
        percentages_run.append(pr * 100.0)
        percentages_scramble.append(ps * 100.0)

    bar_width = 0.35
    x = np.arange(len(distance_bins))

    fig, ax = plt.subplots(figsize=(12, 7))
    pass_bars     = ax.bar(x, percentages_pass, bar_width, label='Pass Plays', color='blue')
    scramble_bars = ax.bar(x, percentages_scramble, bar_width, bottom=percentages_pass,
                           label='Scramble Plays', color='orange')
    run_bars      = ax.bar(x + bar_width, percentages_run, bar_width, label='Run Plays', color='green')

    for i, rect in enumerate(pass_bars):
        if counts_pass[i] > 0:
            ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 2,
                    str(counts_pass[i]), ha="center", va="bottom", fontsize=8)

    for i, rect in enumerate(scramble_bars):
        if counts_scramble[i] > 0:
            top = rect.get_y() + rect.get_height()
            ax.text(rect.get_x() + rect.get_width()/2, top + 2,
                    str(counts_scramble[i]), ha="center", va="bottom", fontsize=8)

    for i, rect in enumerate(run_bars):
        if counts_run[i] > 0:
            ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 2,
                    str(counts_run[i]), ha="center", va="bottom", fontsize=8)

    # Ivy average marker strips
    if ivy_df is not None:
        ivy_pass, ivy_run, ivy_scramble = _ivy_pct_by_distance(ivy_df, desired_down, distance_bins)
        pass_centers     = x
        run_centers      = x + bar_width
        scramble_centers = x  # same column as pass (stacked)
        _draw_ivy_ticks(
            ax,
            [pass_centers, run_centers, scramble_centers],
            [ivy_pass, ivy_run, ivy_scramble],
            bar_width,
        )

    ax.set_xlabel('Distance (Yards)')
    ax.set_ylabel('Percentage of Plays (%)')
    ax.set_ylim(0, 105)
    ax.set_title(f'{school} Down #{desired_down}: % of Plays by Distance')
    ax.set_xticks(x + bar_width/2)
    ax.set_xticklabels(distance_bins)
    ax.legend()
    ax.grid(axis='y')

    fig.tight_layout()
    fig.savefig(f'{school}_{desired_down}_%plays.png', dpi=150, bbox_inches='tight')
    plt.show()


def playcall_success_by_distance(df, desired_down, school="Brown Offense", ivy_df=None):
    pass_plays    = df[(df["pff_RUNPASS"] == "P") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    run_plays     = df[(df["pff_RUNPASS"] == "R") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    scramble_plays = df[(df["pff_QBSCRAMBLE"] != 'N') & (df["pff_DOWN"] == desired_down)]

    success_rates_pass, success_rates_run, success_rates_scramble = [], [], []
    counts_pass, counts_run, counts_scramble = [], [], []

    for distance in range(1, 11):
        p = pass_plays[pass_plays["pff_DISTANCE"] == distance]
        r = run_plays[run_plays["pff_DISTANCE"] == distance]
        s = scramble_plays[scramble_plays["pff_DISTANCE"] == distance]

        cp, cr, cs = len(p), len(r), len(s)
        counts_pass.append(cp); counts_run.append(cr); counts_scramble.append(cs)

        success_rates_pass.append((p["pff_FIRST_DOWN_GAINED"] == 1).sum() / cp if cp > 0 else 0.0)
        success_rates_run.append((r["pff_FIRST_DOWN_GAINED"] == 1).sum() / cr if cr > 0 else 0.0)
        success_rates_scramble.append((s["pff_FIRST_DOWN_GAINED"] == 1).sum() / cs if cs > 0 else 0.0)

    p11 = pass_plays[pass_plays["pff_DISTANCE"] >= 11]
    r11 = run_plays[run_plays["pff_DISTANCE"] >= 11]
    s11 = scramble_plays[scramble_plays["pff_DISTANCE"] >= 11]

    cp11, cr11, cs11 = len(p11), len(r11), len(s11)
    counts_pass.append(cp11); counts_run.append(cr11); counts_scramble.append(cs11)

    success_rates_pass.append((p11["pff_FIRST_DOWN_GAINED"] == 1).sum() / cp11 if cp11 > 0 else 0.0)
    success_rates_run.append((r11["pff_FIRST_DOWN_GAINED"] == 1).sum() / cr11 if cr11 > 0 else 0.0)
    success_rates_scramble.append((s11["pff_FIRST_DOWN_GAINED"] == 1).sum() / cs11 if cs11 > 0 else 0.0)

    distances = list(range(1, 11)) + ['11+']
    bar_width = 0.25
    index = np.arange(len(distances))

    fig, ax = plt.subplots(figsize=(10, 6))
    pass_bars     = ax.bar(index, success_rates_pass, bar_width, label='Pass Success Rate', color='blue')
    run_bars      = ax.bar(index + bar_width, success_rates_run, bar_width, label='Run Success Rate', color='green')
    scramble_bars = ax.bar(index + 2 * bar_width, success_rates_scramble, bar_width, label='Scramble Success Rate', color='orange')

    for i, rect in enumerate(pass_bars):
        if counts_pass[i] > 0:
            ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.02, f"{counts_pass[i]}",
                    ha="center", va="bottom", fontsize=8)
    for i, rect in enumerate(run_bars):
        if counts_run[i] > 0:
            ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.02, f"{counts_run[i]}",
                    ha="center", va="bottom", fontsize=8)
    for i, rect in enumerate(scramble_bars):
        if counts_scramble[i] > 0:
            ax.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.02, f"{counts_scramble[i]}",
                    ha="center", va="bottom", fontsize=8)

    # Ivy average marker strips
    if ivy_df is not None:
        ivy_pass, ivy_run, ivy_scramble = _ivy_success_by_distance(ivy_df, desired_down, distances)
        pass_centers     = index
        run_centers      = index + bar_width
        scramble_centers = index + 2 * bar_width
        _draw_ivy_ticks(
            ax,
            [pass_centers, run_centers, scramble_centers],
            [ivy_pass, ivy_run, ivy_scramble],
            bar_width,
        )

    ax.set_xlabel('Distance (Yards)')
    ax.set_ylabel('Success Rate')
    ax.set_ylim(0, 1.06)
    ax.set_title(f'{school} Down #{desired_down}: Conversion % by Distance')
    ax.set_xticks(index + bar_width)
    ax.set_xticklabels(distances)
    ax.legend()
    ax.grid(True)

    fig.savefig(f'{school}_{desired_down}_%success.png')
    fig.tight_layout()
    plt.show()


def playcall_success_by_distance_category(df, desired_down, school, ivy_df=None):
    df = df[df["pff_DOWN"] == desired_down].copy()

    df['distance_category'] = pd.cut(
        df['pff_DISTANCE'],
        bins=[0, 2, 6, 10, np.inf],
        labels=['1-2', '3-6', '7-10', '11+'],
        right=True, include_lowest=True,
    )

    pass_plays    = df[(df["pff_RUNPASS"] == "P") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    run_plays     = df[(df["pff_RUNPASS"] == "R") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    scramble_plays = df[(df["pff_QBSCRAMBLE"] != 'N') & (df["pff_DOWN"] == desired_down)]

    success_rates_pass, success_rates_run, success_rates_scramble = [], [], []

    for category in ['1-2', '3-6', '7-10', '11+']:
        p = pass_plays[pass_plays['distance_category'] == category]
        r = run_plays[run_plays['distance_category'] == category]
        s = scramble_plays[scramble_plays['distance_category'] == category]

        cp, cr, cs = len(p), len(r), len(s)
        success_rates_pass.append(len(p[p["pff_FIRST_DOWN_GAINED"] == 1]) / cp if cp > 0 else 0)
        success_rates_run.append(len(r[r["pff_FIRST_DOWN_GAINED"] == 1]) / cr if cr > 0 else 0)
        success_rates_scramble.append(len(s[s["pff_FIRST_DOWN_GAINED"] == 1]) / cs if cs > 0 else 0)

    categories = ['1-2', '3-6', '7-10', '11+']
    bar_width = 0.25
    index = np.arange(len(categories))

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(index, success_rates_pass, bar_width, label='Pass Success Rate', color='blue')
    ax.bar(index + bar_width, success_rates_run, bar_width, label='Run Success Rate', color='green')
    ax.bar(index + 2 * bar_width, success_rates_scramble, bar_width, label='Scramble Success Rate', color='orange')

    for i, cat in enumerate(categories):
        n_pass    = len(pass_plays[pass_plays['distance_category'] == cat])
        n_run     = len(run_plays[run_plays['distance_category'] == cat])
        n_scramble = len(scramble_plays[scramble_plays['distance_category'] == cat])

        if success_rates_pass[i] > 0:
            ax.text(index[i], success_rates_pass[i] + 0.02, f"{n_pass}",
                    ha="center", va="bottom", fontsize=8)
        if success_rates_run[i] > 0:
            ax.text(index[i] + bar_width, success_rates_run[i] + 0.02, f"{n_run}",
                    ha="center", va="bottom", fontsize=8)
        if success_rates_scramble[i] > 0:
            ax.text(index[i] + 2 * bar_width, success_rates_scramble[i] + 0.02, f"{n_scramble}",
                    ha="center", va="bottom", fontsize=8)

    # Ivy average marker strips
    if ivy_df is not None:
        ivy_pass, ivy_run, ivy_scramble = _ivy_success_by_category(ivy_df, desired_down)
        pass_centers     = index
        run_centers      = index + bar_width
        scramble_centers = index + 2 * bar_width
        _draw_ivy_ticks(
            ax,
            [pass_centers, run_centers, scramble_centers],
            [ivy_pass, ivy_run, ivy_scramble],
            bar_width,
        )

    ax.set_xlabel('Distance Category')
    ax.set_ylabel('Success Rate')
    ax.set_title(f'{school} Down #{desired_down}: Conversion % by Distance Category')
    ax.set_xticks(index + bar_width)
    ax.set_xticklabels(categories)
    ax.legend()
    ax.grid(True)

    fig.savefig(f'{school}_{desired_down}_%success_category.png')
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    run_all_plots()

