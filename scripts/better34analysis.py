import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

#Load the data

def run_all_plots():
    offense = pd.read_csv("harvard_offense.csv")
    defense = pd.read_csv("harvard_defense.csv")

    o_clean = clean_data(offense)
    d_clean = clean_data(defense)

    school = "Harvard"

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

    # Initialize lists for percentages
    percentages_pass = []
    percentages_run = []
    percentages_scramble = []
    counts_total = []

    # Loop through distances from 1 to 14
    for distance in range(1, 15):
        # Filter the plays with the current distance
        plays_at_distance = plays[plays["pff_DISTANCE"] == distance]
        total_plays = len(plays_at_distance)
        counts_total.append(total_plays)

        if total_plays > 0:
            pass_percentage = len(pass_plays[pass_plays["pff_DISTANCE"] == distance]) / total_plays
            run_percentage = len(run_plays[run_plays["pff_DISTANCE"] == distance]) / total_plays
            scramble_percentage = len(scramble_plays[scramble_plays["pff_DISTANCE"] == distance]) / total_plays
        else:
            pass_percentage = run_percentage = scramble_percentage = 0

        # Normalize percentages to add up to 1
        total_percentage = pass_percentage + run_percentage + scramble_percentage
        if total_percentage > 0:
            pass_percentage /= total_percentage
            run_percentage /= total_percentage
            scramble_percentage /= total_percentage

        # Convert to percentage format
        percentages_pass.append(pass_percentage * 100)
        percentages_run.append(run_percentage * 100)
        percentages_scramble.append(scramble_percentage * 100)

    # Handle distances of 15+ yards
    plays_at_distance_11plus = plays[plays["pff_DISTANCE"] >= 15]
    total_plays_11plus = len(plays_at_distance_11plus)

    if total_plays_11plus > 0:
        pass_percentage_11plus = len(pass_plays[pass_plays["pff_DISTANCE"] >= 15]) / total_plays_11plus
        run_percentage_11plus = len(run_plays[run_plays["pff_DISTANCE"] >= 15]) / total_plays_11plus
        scramble_percentage_11plus = len(scramble_plays[scramble_plays["pff_DISTANCE"] >= 15]) / total_plays_11plus

        # Normalize percentages to add up to 1
        total_percentage_11plus = pass_percentage_11plus + run_percentage_11plus + scramble_percentage_11plus
        if total_percentage_11plus > 0:
            pass_percentage_11plus /= total_percentage_11plus
            run_percentage_11plus /= total_percentage_11plus
            scramble_percentage_11plus /= total_percentage_11plus
    else:
        pass_percentage_11plus = run_percentage_11plus = scramble_percentage_11plus = 0

    # Convert to percentage format
    percentages_pass.append(pass_percentage_11plus * 100)
    counts_total.append(total_plays_11plus)
    percentages_run.append(run_percentage_11plus * 100)
    percentages_scramble.append(scramble_percentage_11plus * 100)

    # Define the x-axis positions and bar width
    distances = list(range(1, 15)) + ['15+']
    bar_width = 0.35  # Width of each bar
    index = np.arange(len(distances))

    # Plot the bars for pass, run, and scramble percentages
    plt.figure(figsize=(12, 7))

    # Pass bars with scramble stacked on top
    pass_bars = plt.bar(index, percentages_pass, bar_width, label='Pass Plays', color='blue')
    scramble_bars = plt.bar(index, percentages_scramble, bar_width, bottom=percentages_pass, label='Scramble Plays', color='orange')

    # Run bars
    run_bars = plt.bar(index + bar_width, percentages_run, bar_width, label='Run Plays', color='green')

    # Adding labels and formatting
    plt.xlabel('Distance (Yards)')
    plt.ylabel('Percentage of Plays (%)')
    plt.ylim(0, 100)  # Set y-axis limit to 100
    plt.title(f'{school} Down #{desired_down}: % of Plays by Distance')
    plt.xticks(index + bar_width / 2, distances)
    plt.legend()
    plt.grid(axis='y')

    for i, n in enumerate(counts_total):
        plt.text(i + bar_width/2, 102, f"n={n}", ha="center", va="bottom", fontsize=8)

    # Save and show plot
    plt.tight_layout()
    plt.savefig(f'{school}_{desired_down}_%plays.png')
    plt.show()

def playcall_success_by_distance(df, desired_down, school = "Brown Offense"):
    #Filter pass, run, and scramble plays
    pass_plays = df[(df["pff_RUNPASS"] == "P") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    run_plays = df[(df["pff_RUNPASS"] == "R") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    scramble_plays = df[(df["pff_QBSCRAMBLE"] != 'N') & (df["pff_DOWN"] == desired_down)]

    #Initialize success rate lists
    total_counts = []
    success_rates_pass = []
    success_rates_run = []
    success_rates_scramble = []

    #Loop through distances from 1 to 10
    for distance in range(1, 11):
        #Filter the plays with the current distance
        plays_at_distance_pass = pass_plays[pass_plays["pff_DISTANCE"] == distance]
        plays_at_distance_run = run_plays[run_plays["pff_DISTANCE"] == distance]
        plays_at_distance_scramble = scramble_plays[scramble_plays["pff_DISTANCE"] == distance]

        #Calculate the number of successful plays
        successful_plays_pass = plays_at_distance_pass[plays_at_distance_pass["pff_FIRST_DOWN_GAINED"] == 1]
        successful_plays_run = plays_at_distance_run[plays_at_distance_run["pff_FIRST_DOWN_GAINED"] == 1]
        successful_plays_scramble = plays_at_distance_scramble[plays_at_distance_scramble["pff_FIRST_DOWN_GAINED"] == 1]

        #Calculate the total number of plays for the given distance
        total_plays_pass = len(plays_at_distance_pass)
        total_plays_run = len(plays_at_distance_run)
        total_plays_scramble = len(plays_at_distance_scramble)
        total_counts.append(total_plays_pass + total_plays_run + total_plays_scramble)

        #Calculate success rates
        success_rate_pass = len(successful_plays_pass) / total_plays_pass if total_plays_pass > 0 else 0
        success_rate_run = len(successful_plays_run) / total_plays_run if total_plays_run > 0 else 0
        success_rate_scramble = len(successful_plays_scramble) / total_plays_scramble if total_plays_scramble > 0 else 0

        #Append success rates
        success_rates_pass.append(success_rate_pass)
        success_rates_run.append(success_rate_run)
        success_rates_scramble.append(success_rate_scramble)

    #Handle distances of 11+ yards
    plays_at_distance_11plus_pass = pass_plays[pass_plays["pff_DISTANCE"] >= 11]
    plays_at_distance_11plus_run = run_plays[run_plays["pff_DISTANCE"] >= 11]
    plays_at_distance_11plus_scramble = scramble_plays[scramble_plays["pff_DISTANCE"] >= 11]

    #Calculate the number of successful plays for 11+ yards
    successful_plays_11plus_pass = plays_at_distance_11plus_pass[plays_at_distance_11plus_pass["pff_FIRST_DOWN_GAINED"] == 1]
    successful_plays_11plus_run = plays_at_distance_11plus_run[plays_at_distance_11plus_run["pff_FIRST_DOWN_GAINED"] == 1]
    successful_plays_11plus_scramble = plays_at_distance_11plus_scramble[plays_at_distance_11plus_scramble["pff_FIRST_DOWN_GAINED"] == 1]

    #Calculate the total number of plays for 11+ yards
    total_plays_11plus_pass = len(plays_at_distance_11plus_pass)
    total_plays_11plus_run = len(plays_at_distance_11plus_run)
    total_plays_11plus_scramble = len(plays_at_distance_11plus_scramble)

    #Calculate success rates for 11+ yards and append
    success_rate_11plus_pass = len(successful_plays_11plus_pass) / total_plays_11plus_pass if total_plays_11plus_pass > 0 else 0
    success_rate_11plus_run = len(successful_plays_11plus_run) / total_plays_11plus_run if total_plays_11plus_run > 0 else 0
    success_rate_11plus_scramble = len(successful_plays_11plus_scramble) / total_plays_11plus_scramble if total_plays_11plus_scramble > 0 else 0

    #Append success rates for 11+ yards
    success_rates_pass.append(success_rate_11plus_pass)
    success_rates_run.append(success_rate_11plus_run)
    success_rates_scramble.append(success_rate_11plus_scramble)
    total_counts.append(total_plays_11plus_pass + total_plays_11plus_run + total_plays_11plus_scramble)

    #Define the x-axis positions and bar width
    distances = list(range(1, 11)) + ['11+']
    bar_width = 0.25  # Width of each bar
    index = np.arange(len(distances))

    #Plot the bars for pass, run, and scramble success rates
    plt.figure(figsize=(10, 6))

    #Pass success rates bars
    plt.bar(index, success_rates_pass, bar_width, label='Pass Success Rate', color='blue')

    #Run success rates bars
    plt.bar(index + bar_width, success_rates_run, bar_width, label='Run Success Rate', color='green')

    #Scramble success rates bars
    plt.bar(index + 2 * bar_width, success_rates_scramble, bar_width, label='Scramble Success Rate', color='orange')

    #Adding labels and formatting
    plt.xlabel('Distance (Yards)')
    plt.ylabel('Success Rate')
    plt.title(f'{school} Down #{desired_down}: Conversion % by Distance')
    plt.xticks(index + bar_width, distances)
    plt.legend()
    plt.grid(True)
    for i, n in enumerate(total_counts):
        plt.text(i + bar_width, 1.02, f"n={n}", ha="center", va="bottom", fontsize=8, transform=plt.gca().get_xaxis_transform())

    plt.savefig(f'{school}_{desired_down}_%success.png')

    #Show plot
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
    categories = categories = ['1-2', '3-6', '7-10', '11+']
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

    # Adding labels and formatting
    plt.xlabel('Distance Category')
    plt.ylabel('Success Rate')
    plt.title(f'{school} Down #{desired_down}: Conversion % by Distance Category')
    plt.xticks(index + bar_width, categories)
    plt.legend()
    plt.grid(True)
    for i, cat in enumerate(categories):
        plt.text(i + bar_width, 1.02, f"n={int(counts_by_cat.loc[cat])}", ha="center", va="bottom",
             fontsize=8, transform=plt.gca().get_xaxis_transform())
    
    plt.savefig(f'{school}_{desired_down}_%success_category.png')

    # Show plot
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    run_all_plots()