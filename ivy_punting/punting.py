import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

#Load the data
#1. average punt net distance for every yardline
#2. percentage of punts where something bad happens by yardline * negative in the gain loss column or if the punt is blocked*

def run_all_plots():
	punts = pd.read_csv("punts.csv")
    punt_data = punts[["pff_DOWN", "pff_DISTANCE", "pff_QBSCRAMBLE", "pff_RUNPASS", "pff_FIRST_DOWN_GAINED"]]

	playcall_by_distance(brown_off, 3)
	playcall_by_distance(brown_off, 4)


def playcall_by_distance(df, desired_down, school = "Brown Offense"):
    #Filter pass, run, and scramble plays
    pass_plays = df[(df["pff_RUNPASS"] == "P") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    run_plays = df[(df["pff_RUNPASS"] == "R") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    scramble_plays = df[(df["pff_QBSCRAMBLE"] != 'N') & (df["pff_DOWN"] == desired_down)]

    #Initialize success rate lists
    rates_pass = []
    rates_run = []
    rates_scramble = []

    #Loop through distances from 1 to 10
    for distance in range(1, 15):
        #Filter the plays with the current distance
        plays_at_distance_pass = pass_plays[pass_plays["pff_DISTANCE"] == distance]
        plays_at_distance_run = run_plays[run_plays["pff_DISTANCE"] == distance]
        plays_at_distance_scramble = scramble_plays[scramble_plays["pff_DISTANCE"] == distance]

        pass_num = len(plays_at_distance_pass)
        run_num = len(plays_at_distance_run)
        scramble_num = len(plays_at_distance_scramble)

        #Append success rates
        rates_pass.append(pass_num)
        rates_run.append(run_num)
        rates_scramble.append(scramble_num)

    #Handle distances of 11+ yards
    plays_at_distance_11plus_pass = pass_plays[pass_plays["pff_DISTANCE"] >= 15]
    plays_at_distance_11plus_run = run_plays[run_plays["pff_DISTANCE"] >= 15]
    plays_at_distance_11plus_scramble = scramble_plays[scramble_plays["pff_DISTANCE"] >= 15]

    pass_11plus_num = len(plays_at_distance_11plus_pass)
    run_11plus_num = len(plays_at_distance_11plus_run)
    scramble_11plus_num = len(plays_at_distance_11plus_scramble)

    #Append success rates for 11+ yards
    rates_pass.append(pass_11plus_num)
    rates_run.append(run_11plus_num)
    rates_scramble.append(scramble_11plus_num)

    #Define the x-axis positions and bar width
    distances = list(range(1, 15)) + ['15+']
    bar_width = 0.25  # Width of each bar
    index = np.arange(len(distances))

    #Plot the bars for pass, run, and scramble success rates
    plt.figure(figsize=(10, 6))

    #Pass bars
    plt.bar(index, rates_pass, bar_width, label='Pass Plays', color='blue')

    #Run bars
    plt.bar(index + bar_width, rates_run, bar_width, label='Run Plays', color='green')

    #Scramble bars
    plt.bar(index + 2 * bar_width, rates_scramble, bar_width, label='Scramble Plays', color='orange')

    #Adding labels and formatting
    plt.xlabel('Distance (Yards)')
    plt.ylabel('# of Plays')
    plt.title(school + ': # of Plays for Pass, Run, and QB Scramble by Distance (1-14 and 15+ Yards), Down #' + str(desired_down))
    plt.xticks(index + bar_width, distances)
    plt.legend()
    plt.grid(True)

    plt.savefig(school + " " + str(desired_down) + ' Down Plays.png')

    #Show plot
    plt.tight_layout()
    plt.show()

def playcall_success_by_distance(df, desired_down, school = "Brown Offense"):
    #Filter pass, run, and scramble plays
    pass_plays = df[(df["pff_RUNPASS"] == "P") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    run_plays = df[(df["pff_RUNPASS"] == "R") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    scramble_plays = df[(df["pff_QBSCRAMBLE"] != 'N') & (df["pff_DOWN"] == desired_down)]

    #Initialize success rate lists
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
    plt.title(school + ': Success Rates for Pass, Run, and QB Scramble by Distance (1-10 and 11+ Yards), Down #' + str(desired_down))
    plt.xticks(index + bar_width, distances)
    plt.legend()
    plt.grid(True)

    plt.savefig(school + " " + str(desired_down) + ' Down Success.png')

    #Show plot
    plt.tight_layout()
    plt.show()



def playcall_success_by_distance_category(df, desired_down, school):
    # Filter for only 3rd and 4th downs
    df = df[df["pff_DOWN"] == desired_down]

    # Categorize distances into short, medium, and long
    df['distance_category'] = pd.cut(df['pff_DISTANCE'],
                                           bins=[0, 3, 6, np.inf],
                                           labels=['Short (1-3)', 'Medium (4-6)', 'Long (7+)'])

    # Filter pass, run, and scramble plays
    pass_plays = df[(df["pff_RUNPASS"] == "P") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    run_plays = df[(df["pff_RUNPASS"] == "R") & (df["pff_QBSCRAMBLE"] == 'N') & (df["pff_DOWN"] == desired_down)]
    scramble_plays = df[(df["pff_QBSCRAMBLE"] != 'N') & (df["pff_DOWN"] == desired_down)]

    # Initialize success rate lists for short, medium, and long distances
    success_rates_pass = []
    success_rates_run = []
    success_rates_scramble = []

    # Loop through the distance categories
    for category in ['Short (1-3)', 'Medium (4-6)', 'Long (7+)']:
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

    # Define the x-axis labels and bar width
    categories = ['Short (1-3)', 'Medium (4-6)', 'Long (7+)']
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
    plt.title(school + ': Success Rates by Distance Category, Down #' + str(desired_down))
    plt.xticks(index + bar_width, categories)
    plt.legend()
    plt.grid(True)

    plt.savefig(school + " " + str(desired_down) + ' Down Success by Categories.png')

    # Show plot
    plt.tight_layout()
    plt.show()





#3. A graph for short (1-3 yards), medium (4-6), and long (7+) opponent success rate against Harvard for 3rd and 4th downs.


#3a: PASS: A graph for short (1-3 yards), medium (4-6), and long (7+) opponent success rate against Harvard for 3rd and 4th downs

#3b: RUN: A graph for short (1-3 yards), medium (4-6), and long (7+) opponent success rate against Harvard for 3rd and 4th downs pass
