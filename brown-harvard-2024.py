import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# 1. Load the data
b_off = pd.read_csv("brown.csv")

# 2. Select specific columns
b_34down = b_off[["pff_DOWN", "pff_DISTANCE", "pff_QBSCRAMBLE", "pff_RUNPASS", "pff_FIRST_DOWN_GAINED"]]

# 3. Fill empty columns with 0 for first down gained
b_34down["pff_FIRST_DOWN_GAINED"].fillna(0, inplace=True)
b_34down["pff_QBSCRAMBLE"].fillna('N', inplace=True)

def doitall(b_34down, desired_down):
    # 4. Filter pass, run, and scramble plays
    pass_plays = b_34down[(b_34down["pff_RUNPASS"] == "P") & (b_34down["pff_DOWN"] == desired_down)]
    run_plays = b_34down[(b_34down["pff_RUNPASS"] == "R") & (b_34down["pff_QBSCRAMBLE"] == 'N') & (b_34down["pff_DOWN"] == desired_down)]
    scramble_plays = b_34down[(b_34down["pff_RUNPASS"] == "R") & (b_34down["pff_QBSCRAMBLE"] != 'N') & (b_34down["pff_DOWN"] == desired_down)]

    # Initialize success rate lists
    success_rates_pass = []
    success_rates_run = []
    success_rates_scramble = []

    # 5. Loop through distances from 1 to 10
    for distance in range(1, 11):
        # Filter the plays with the current distance
        plays_at_distance_pass = pass_plays[pass_plays["pff_DISTANCE"] == distance]
        plays_at_distance_run = run_plays[run_plays["pff_DISTANCE"] == distance]
        plays_at_distance_scramble = scramble_plays[scramble_plays["pff_DISTANCE"] == distance]

        # Calculate the number of successful plays
        successful_plays_pass = plays_at_distance_pass[plays_at_distance_pass["pff_FIRST_DOWN_GAINED"] == 1]
        successful_plays_run = plays_at_distance_run[plays_at_distance_run["pff_FIRST_DOWN_GAINED"] == 1]
        successful_plays_scramble = plays_at_distance_scramble[plays_at_distance_scramble["pff_FIRST_DOWN_GAINED"] == 1]

        # Calculate the total number of plays for the given distance
        total_plays_pass = len(plays_at_distance_pass)
        total_plays_run = len(plays_at_distance_run)
        total_plays_scramble = len(plays_at_distance_scramble)
        
        # Calculate success rates
        success_rate_pass = len(successful_plays_pass) / total_plays_pass if total_plays_pass > 0 else 0
        success_rate_run = len(successful_plays_run) / total_plays_run if total_plays_run > 0 else 0
        success_rate_scramble = len(successful_plays_scramble) / total_plays_scramble if total_plays_scramble > 0 else 0

        # Append success rates
        success_rates_pass.append(success_rate_pass)
        success_rates_run.append(success_rate_run)
        success_rates_scramble.append(success_rate_scramble)

    # 6. Handle distances of 11+ yards
    plays_at_distance_11plus_pass = pass_plays[pass_plays["pff_DISTANCE"] >= 11]
    plays_at_distance_11plus_run = run_plays[run_plays["pff_DISTANCE"] >= 11]
    plays_at_distance_11plus_scramble = scramble_plays[scramble_plays["pff_DISTANCE"] >= 11]

    # Calculate the number of successful plays for 11+ yards
    successful_plays_11plus_pass = plays_at_distance_11plus_pass[plays_at_distance_11plus_pass["pff_FIRST_DOWN_GAINED"] == 1]
    successful_plays_11plus_run = plays_at_distance_11plus_run[plays_at_distance_11plus_run["pff_FIRST_DOWN_GAINED"] == 1]
    successful_plays_11plus_scramble = plays_at_distance_11plus_scramble[plays_at_distance_11plus_scramble["pff_FIRST_DOWN_GAINED"] == 1]

    # Calculate the total number of plays for 11+ yards
    total_plays_11plus_pass = len(plays_at_distance_11plus_pass)
    total_plays_11plus_run = len(plays_at_distance_11plus_run)
    total_plays_11plus_scramble = len(plays_at_distance_11plus_scramble)

    # Calculate success rates for 11+ yards and append
    success_rate_11plus_pass = len(successful_plays_11plus_pass) / total_plays_11plus_pass if total_plays_11plus_pass > 0 else 0
    success_rate_11plus_run = len(successful_plays_11plus_run) / total_plays_11plus_run if total_plays_11plus_run > 0 else 0
    success_rate_11plus_scramble = len(successful_plays_11plus_scramble) / total_plays_11plus_scramble if total_plays_11plus_scramble > 0 else 0

    # Append success rates for 11+ yards
    success_rates_pass.append(success_rate_11plus_pass)
    success_rates_run.append(success_rate_11plus_run)
    success_rates_scramble.append(success_rate_11plus_scramble)

    # Define the x-axis positions and bar width
    distances = list(range(1, 11)) + ['11+']  # Add '11+' as a label for distances 11 and more
    bar_width = 0.25  # Width of each bar
    index = np.arange(len(distances))  # X-axis positions for the bars

    # Plot the bars for pass, run, and scramble success rates
    plt.figure(figsize=(10, 6))

    # Pass success rates bars
    plt.bar(index, success_rates_pass, bar_width, label='Pass Success Rate', color='blue')

    # Run success rates bars
    plt.bar(index + bar_width, success_rates_run, bar_width, label='Run Success Rate', color='green')

    # Scramble success rates bars
    plt.bar(index + 2 * bar_width, success_rates_scramble, bar_width, label='Scramble Success Rate', color='orange')

    # Adding labels and formatting
    plt.xlabel('Distance (Yards)')
    plt.ylabel('Success Rate')
    plt.title('Success Rates for Pass, Run, and QB Scramble by Distance (1-10 and 11+ Yards)')
    plt.xticks(index + bar_width, distances)  # Set the x-ticks in the middle of the grouped bars
    plt.legend()
    plt.grid(True)

    # 9. Show the plot
    plt.tight_layout()
    plt.show()






#3. A graph for short (1-3 yards), medium (4-6), and long (7+) opponent success rate against Harvard for 3rd and 4th downs.


#3a: PASS: A graph for short (1-3 yards), medium (4-6), and long (7+) opponent success rate against Harvard for 3rd and 4th downs

#3b: RUN: A graph for short (1-3 yards), medium (4-6), and long (7+) opponent success rate against Harvard for 3rd and 4th downs pass excl. pff_QBSCRAMLBLE
