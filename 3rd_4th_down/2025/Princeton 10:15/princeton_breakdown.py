import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

#Load the data

def run_all_plots():
    offense = pd.read_csv("princeton_offense.csv") #2021-early 2025
    defense = pd.read_csv("princeton_defense.csv") #2021-early 2025

    o_clean = clean_data(offense)
    d_clean = clean_data(defense)

    school = "Princeton"

    #offense
    playcall_by_distance(o_clean, 3, school + " offense")
    playcall_by_distance(o_clean, 4, school + " offense")
    
    playcall_success_by_distance(o_clean, 3, school + " offense")
    playcall_success_by_distance(o_clean, 4, school + " offense")
    
    play_percentage_by_distance(o_clean, 3, school + " offense")
    play_percentage_by_distance(o_clean, 4, school + " offense")
    
    playcall_success_by_distance_category(o_clean, 3, school + " offense")
    playcall_success_by_distance_category(o_clean, 4, school + " offense")

    #defense
    playcall_by_distance(d_clean, 3, school + " defense")
    playcall_by_distance(d_clean, 4, school + " defense")

    playcall_success_by_distance(d_clean, 3, school + " defense")
    playcall_success_by_distance(d_clean, 4, school + " defense")

    playcall_success_by_distance_category(d_clean, 3, school + " defense")
    playcall_success_by_distance_category(d_clean, 4, school + " defense")


def clean_data(unclean):
    clean = unclean[["pff_DOWN", "pff_DISTANCE", "pff_QBSCRAMBLE", "pff_RUNPASS", "pff_FIRST_DOWN_GAINED"]].copy()
    clean["pff_FIRST_DOWN_GAINED"] = clean["pff_FIRST_DOWN_GAINED"].fillna(0)
    clean["pff_QBSCRAMBLE"] = clean["pff_QBSCRAMBLE"].fillna('N')
    return clean

def playcall_by_distance(df, desired_down, school="Brown Offense"):
    # Verify that required columns exist
    required_columns = ["pff_RUNPASS", "pff_QBSCRAMBLE", "pff_DOWN", "pff_DISTANCE"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Dataframe is missing required column: {col}")

    # Filter pass, run, and scramble plays for the desired down
    plays = df[df["pff_DOWN"] == desired_down]
    pass_plays = plays[(plays["pff_RUNPASS"] == "P") & (plays["pff_QBSCRAMBLE"] == 'N')]
    run_plays = plays[(plays["pff_RUNPASS"] == "R") & (plays["pff_QBSCRAMBLE"] == 'N')]
    scramble_plays = plays[plays["pff_QBSCRAMBLE"] != 'N']

    # Initialize success rate lists
    rates_pass = []
    rates_run = []
    rates_scramble = []

    # Loop through distances from 1 to 14
    for distance in range(1, 15):
        # Filter the plays with the current distance
        pass_num = len(pass_plays[pass_plays["pff_DISTANCE"] == distance])
        run_num = len(run_plays[run_plays["pff_DISTANCE"] == distance])
        scramble_num = len(scramble_plays[scramble_plays["pff_DISTANCE"] == distance])

        # Append success rates
        rates_pass.append(pass_num)
        rates_run.append(run_num)
        rates_scramble.append(scramble_num)

    # Handle distances of 15+ yards
    pass_11plus_num = len(pass_plays[pass_plays["pff_DISTANCE"] >= 15])
    run_11plus_num = len(run_plays[run_plays["pff_DISTANCE"] >= 15])
    scramble_11plus_num = len(scramble_plays[scramble_plays["pff_DISTANCE"] >= 15])

    # Append success rates for 15+ yards
    rates_pass.append(pass_11plus_num)
    rates_run.append(run_11plus_num)
    rates_scramble.append(scramble_11plus_num)

    # Define the x-axis positions and bar width
    distances = list(range(1, 15)) + ['15+']
    bar_width = 0.35  # Width of each bar
    index = np.arange(len(distances))

    # Plot the bars for pass + scramble (stacked) and run success rates
    plt.figure(figsize=(12, 7))

    # Pass bars with scramble stacked on top
    pass_bars = plt.bar(index, rates_pass, bar_width, label='Pass Plays', color='blue')
    scramble_bars = plt.bar(index, rates_scramble, bar_width, bottom=rates_pass, label='Scramble Plays', color='orange')

    # Run bars
    run_bars = plt.bar(index + bar_width, rates_run, bar_width, label='Run Plays', color='green')
    
    for bar in pass_bars:
        h = bar.get_height()
        if h > 0:
            plt.text(bar.get_x() + bar.get_width()/2, h + 0.5, f"{int(h)}",
                     ha="center", va="bottom", fontsize=8)

    # Scramble segment (stacked on Pass)
    for bar in scramble_bars:
        top = bar.get_y() + bar.get_height()  # stacked top
        seg = bar.get_height()
        if seg > 0:
            plt.text(bar.get_x() + bar.get_width()/2, top + 0.5, f"{int(seg)}",
                     ha="center", va="bottom", fontsize=8)

    # Run bars (right group)
    for bar in run_bars:
        h = bar.get_height()
        if h > 0:
            plt.text(bar.get_x() + bar.get_width()/2, h + 0.5, f"{int(h)}",
                     ha="center", va="bottom", fontsize=8)
    # Adding labels and formatting
    plt.xlabel('Distance (Yards)')
    plt.ylabel('# of Plays')
    plt.title(f'{school} Down #{desired_down}: # of Plays by Distance')
    plt.xticks(index + bar_width / 2, distances)
    plt.legend()
    plt.grid(axis='y')

    # Save and show plot
    plt.tight_layout()
    plt.savefig(f'{school}_{desired_down}_#plays.png')
    plt.show()

def play_percentage_by_distance(df, desired_down, school="Brown Offense"):
    # Verify that required columns exist
    required_columns = ["pff_RUNPASS", "pff_QBSCRAMBLE", "pff_DOWN", "pff_DISTANCE"]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Dataframe is missing required column: {col}")

    # Filter pass, run, and scramble plays for the desired down
    plays = df[df["pff_DOWN"] == desired_down]
    pass_plays = plays[(plays["pff_RUNPASS"] == "P") & (plays["pff_QBSCRAMBLE"] == 'N')]
    run_plays = plays[(plays["pff_RUNPASS"] == "R") & (plays["pff_QBSCRAMBLE"] == 'N')]
    scramble_plays = plays[plays["pff_QBSCRAMBLE"] != 'N']

    # Distances 1..14 plus 15+
    distance_bins = list(range(1, 15)) + ["15+"]

    # Percentages and counts per type/bin
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
            # Normalize (safety; should already sum to 1.0 unless other types exist)
            s = pp + pr + ps
            if s > 0:
                pp, pr, ps = pp / s, pr / s, ps / s
        else:
            pp = pr = ps = 0.0

        percentages_pass.append(pp * 100.0)
        percentages_run.append(pr * 100.0)
        percentages_scramble.append(ps * 100.0)

    # Plot
    bar_width = 0.35
    x = np.arange(len(distance_bins))

    plt.figure(figsize=(12, 7))
    pass_bars = plt.bar(x, percentages_pass, bar_width, label='Pass Plays', color='blue')
    scramble_bars = plt.bar(x, percentages_scramble, bar_width, bottom=percentages_pass,
                            label='Scramble Plays', color='orange')
    run_bars = plt.bar(x + bar_width, percentages_run, bar_width, label='Run Plays', color='green')

    # ---- Annotate counts on each individual bar ----
    # Pass counts above blue bars
    for i, rect in enumerate(pass_bars):
        if counts_pass[i] > 0:
            plt.text(rect.get_x() + rect.get_width()/2,
                     rect.get_height() + 2,
                     str(counts_pass[i]),
                     ha="center", va="bottom", fontsize=8)

    # Scramble counts at top of the stacked (blue + orange)
    for i, rect in enumerate(scramble_bars):
        if counts_scramble[i] > 0:
            top = rect.get_y() + rect.get_height()
            plt.text(rect.get_x() + rect.get_width()/2,
                     top + 2,
                     str(counts_scramble[i]),
                     ha="center", va="bottom", fontsize=8)

    # Run counts above green bars
    for i, rect in enumerate(run_bars):
        if counts_run[i] > 0:
            plt.text(rect.get_x() + rect.get_width()/2,
                     rect.get_height() + 2,
                     str(counts_run[i]),
                     ha="center", va="bottom", fontsize=8)

    # Labels/formatting
    plt.xlabel('Distance (Yards)')
    plt.ylabel('Percentage of Plays (%)')
    plt.ylim(0, 105)  # headroom for labels over 100% stack
    plt.title(f'{school} Down #{desired_down}: % of Plays by Distance')
    plt.xticks(x + bar_width/2, distance_bins)
    plt.legend()
    plt.grid(axis='y')

    plt.tight_layout()
    plt.savefig(f'{school}_{desired_down}_%plays.png', dpi=150, bbox_inches='tight')
    plt.show()

def playcall_success_by_distance(df, desired_down, school="Brown Offense"):
    # Filter plays for this down
    pass_plays = df[(df["pff_RUNPASS"] == "P") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    run_plays = df[(df["pff_RUNPASS"] == "R") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    scramble_plays = df[(df["pff_QBSCRAMBLE"] != 'N') & (df["pff_DOWN"] == desired_down)]

    # Accumulators
    success_rates_pass, success_rates_run, success_rates_scramble = [], [], []
    counts_pass, counts_run, counts_scramble = [], [], []

    # Distances 1..10
    for distance in range(1, 11):
        p = pass_plays[pass_plays["pff_DISTANCE"] == distance]
        r = run_plays[run_plays["pff_DISTANCE"] == distance]
        s = scramble_plays[scramble_plays["pff_DISTANCE"] == distance]

        # Counts
        cp, cr, cs = len(p), len(r), len(s)
        counts_pass.append(cp); counts_run.append(cr); counts_scramble.append(cs)

        # Successes
        sp = (p["pff_FIRST_DOWN_GAINED"] == 1).sum()
        sr = (r["pff_FIRST_DOWN_GAINED"] == 1).sum()
        ss = (s["pff_FIRST_DOWN_GAINED"] == 1).sum()

        # Rates
        success_rates_pass.append(sp / cp if cp > 0 else 0.0)
        success_rates_run.append(sr / cr if cr > 0 else 0.0)
        success_rates_scramble.append(ss / cs if cs > 0 else 0.0)

    # 11+ bin
    p11 = pass_plays[pass_plays["pff_DISTANCE"] >= 11]
    r11 = run_plays[run_plays["pff_DISTANCE"] >= 11]
    s11 = scramble_plays[scramble_plays["pff_DISTANCE"] >= 11]

    cp11, cr11, cs11 = len(p11), len(r11), len(s11)
    counts_pass.append(cp11); counts_run.append(cr11); counts_scramble.append(cs11)

    sp11 = (p11["pff_FIRST_DOWN_GAINED"] == 1).sum()
    sr11 = (r11["pff_FIRST_DOWN_GAINED"] == 1).sum()
    ss11 = (s11["pff_FIRST_DOWN_GAINED"] == 1).sum()

    success_rates_pass.append(sp11 / cp11 if cp11 > 0 else 0.0)
    success_rates_run.append(sr11 / cr11 if cr11 > 0 else 0.0)
    success_rates_scramble.append(ss11 / cs11 if cs11 > 0 else 0.0)

    # Plot
    distances = list(range(1, 11)) + ['11+']
    bar_width = 0.25
    index = np.arange(len(distances))

    plt.figure(figsize=(10, 6))
    pass_bars = plt.bar(index, success_rates_pass, bar_width, label='Pass Success Rate', color='blue')
    run_bars = plt.bar(index + bar_width, success_rates_run, bar_width, label='Run Success Rate', color='green')
    scramble_bars = plt.bar(index + 2 * bar_width, success_rates_scramble, bar_width, label='Scramble Success Rate', color='orange')

    # Annotate individual counts above each bar
    # (skip label if count is 0; adjust vertical offset if you want more spacing)
    for i, rect in enumerate(pass_bars):
        if counts_pass[i] > 0:
            plt.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.02, f"{counts_pass[i]}",
                     ha="center", va="bottom", fontsize=8)
    for i, rect in enumerate(run_bars):
        if counts_run[i] > 0:
            plt.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.02, f"{counts_run[i]}",
                     ha="center", va="bottom", fontsize=8)
    for i, rect in enumerate(scramble_bars):
        if counts_scramble[i] > 0:
            plt.text(rect.get_x() + rect.get_width()/2, rect.get_height() + 0.02, f"{counts_scramble[i]}",
                     ha="center", va="bottom", fontsize=8)

    # Labels / formatting
    plt.xlabel('Distance (Yards)')
    plt.ylabel('Success Rate')
    plt.ylim(0, 1.06)
    plt.title(f'{school} Down #{desired_down}: Conversion % by Distance')
    plt.xticks(index + bar_width, distances)
    plt.legend()
    plt.grid(True)

    plt.savefig(f'{school}_{desired_down}_%success.png')
    plt.tight_layout()
    plt.show()




def playcall_success_by_distance_category(df, desired_down, school):
    # Filter for only 3rd and 4th downs
    df = df[df["pff_DOWN"] == desired_down]

    # Categorize distances into short, medium, and long
    df['distance_category'] = pd.cut(
    df['pff_DISTANCE'],
    bins=[0, 2, 6, 10, np.inf],
    labels=['1-2', '3-6', '7-10', '11+'],
    right=True, include_lowest=True
    )


    # Filter pass, run, and scramble plays
    pass_plays = df[(df["pff_RUNPASS"] == "P") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    run_plays = df[(df["pff_RUNPASS"] == "R") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    scramble_plays = df[(df["pff_QBSCRAMBLE"] != 'N') & (df["pff_DOWN"] == desired_down)]

    # Initialize success rate lists for short, medium, and long distances
    success_rates_pass = []
    success_rates_run = []
    success_rates_scramble = []

    # Loop through the distance categories
    for category in ['1-2', '3-6', '7-10', '11+']:
        # Filter plays by distance category
        plays_at_category_pass = pass_plays[pass_plays['distance_category'] == category]
        plays_at_category_run = run_plays[run_plays['distance_category'] == category]
        plays_at_category_scramble = scramble_plays[scramble_plays['distance_category'] == category]

        # Calculate successful plays
        successful_plays_pass = plays_at_category_pass[plays_at_category_pass["pff_FIRST_DOWN_GAINED"] == 1]
        successful_plays_run = plays_at_category_run[plays_at_category_run["pff_FIRST_DOWN_GAINED"] == 1]
        successful_plays_scramble = plays_at_category_scramble[plays_at_category_scramble["pff_FIRST_DOWN_GAINED"] == 1]

        # Calculate total plays for the category
        total_plays_pass = len(plays_at_category_pass)
        total_plays_run = len(plays_at_category_run)
        total_plays_scramble = len(plays_at_category_scramble)

        # Calculate success rates
        success_rate_pass = len(successful_plays_pass) / total_plays_pass if total_plays_pass > 0 else 0
        success_rate_run = len(successful_plays_run) / total_plays_run if total_plays_run > 0 else 0
        success_rate_scramble = len(successful_plays_scramble) / total_plays_scramble if total_plays_scramble > 0 else 0

        # Append success rates for each category
        success_rates_pass.append(success_rate_pass)
        success_rates_run.append(success_rate_run)
        success_rates_scramble.append(success_rate_scramble)

    counts_by_cat = df.groupby('distance_category').size().reindex(['1-2', '3-6', '7-10', '11+'], fill_value=0)
    # Define the x-axis labels and bar width
    categories = ['1-2', '3-6', '7-10', '11+']
    bar_width = 0.25  # Width of each bar
    index = np.arange(len(categories))  # X-axis positions for the bars

    # Plot the bars for pass, run, and scramble success rates
    plt.figure(figsize=(10, 6))

    # Pass success rates bars
    plt.bar(index, success_rates_pass, bar_width, label='Pass Success Rate', color='blue')

    # Run success rates bars
    plt.bar(index + bar_width, success_rates_run, bar_width, label='Run Success Rate', color='green')

    # Scramble success rates bars
    plt.bar(index + 2 * bar_width, success_rates_scramble, bar_width, label='Scramble Success Rate', color='orange')

    for i, cat in enumerate(categories):
        n_pass = len(pass_plays[pass_plays['distance_category'] == cat])
        n_run = len(run_plays[run_plays['distance_category'] == cat])
        n_scramble = len(scramble_plays[scramble_plays['distance_category'] == cat])

        if success_rates_pass[i] > 0:
            plt.text(index[i], success_rates_pass[i] + 0.02, f"{n_pass}",
                     ha="center", va="bottom", fontsize=8)
        if success_rates_run[i] > 0:
            plt.text(index[i] + bar_width, success_rates_run[i] + 0.02, f"{n_run}",
                     ha="center", va="bottom", fontsize=8)
        if success_rates_scramble[i] > 0:
            plt.text(index[i] + 2 * bar_width, success_rates_scramble[i] + 0.02, f"{n_scramble}",
                     ha="center", va="bottom", fontsize=8)

    # Adding labels and formatting
    plt.xlabel('Distance Category')
    plt.ylabel('Success Rate')
    plt.title(f'{school} Down #{desired_down}: Conversion % by Distance Category')
    plt.xticks(index + bar_width, categories)
    plt.legend()
    plt.grid(True)
    
    plt.savefig(f'{school}_{desired_down}_%success_category.png')

    # Show plot
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    run_all_plots()