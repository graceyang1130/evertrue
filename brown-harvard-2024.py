import pandas as pd
import matplotlib.pyplot as plt

#1. A graph of percentage run, pass, and qb scramble for each 3rd/4th distance.
b_off = pd.read_csv("brown.csv")
b_34down = b_off[["pff_DOWN", "pff_DISTANCE", "pff_QBSCRAMBLE", "pff_RUNPASS", "pff_FIRST_DOWN_GAINED"]]

#fill empty columns with 0
b_34down["pff_FIRST_DOWN_GAINED"].fillna(0, inplace=True)
b_34down["pff_QBSCRAMBLE"].fillna('N', inplace=True)

#for run, pass, filter by distance, plot average success rate
#3rd

pass_plays = b_34down[b_34down["pff_RUNPASS"] == "P"]
run_plays = b_34down[(b_34down["pff_RUNPASS"] == "R") & (b_34down["pff_QBSCRAMBLE"] == 'N')]
scramble_plays = b_34down[(b_34down["pff_RUNPASS"] == "R") & (b_34down["pff_QBSCRAMBLE"] != 'N')]
success_rates_pass = []
success_rates_run = []
success_rates_scramble = []

for distance in range(1, 11):
    #for each distance, get plays
    plays_at_distance_pass = pass_plays[pass_plays["pff_DISTANCE"] == distance]
    plays_at_distance_run = run_plays[run_plays["pff_DISTANCE"] == distance]
    plays_at_distance_scramble = scramble_plays[scramble_plays["pff_DISTANCE"] == distance]

    #number of successful plays
    successful_plays_pass = plays_at_distance_pass[plays_at_distance_pass["pff_FIRST_DOWN_GAINED"] == 1]
    successful_plays_run = plays_at_distance_run[plays_at_distance_run["pff_FIRST_DOWN_GAINED"] == 1]
    successful_plays_scramble = plays_at_distance_scramble[plays_at_distance_scramble["pff_FIRST_DOWN_GAINED"] == 1]

    #total play count
    total_plays_pass = len(plays_at_distance_pass)
    total_plays_run = len(plays_at_distance_run)
    total_plays_scramble = len(plays_at_distance_scramble)
    
    #no errors!
    if total_plays_pass == 0: success_rate_pass = 0
    else: success_rate_pass = len(successful_plays_pass) / total_plays_pass

    if total_plays_run == 0: success_rate_run = 0
    else: success_rate_run = len(successful_plays_run) / total_plays_run

    if total_plays_scramble == 0: success_rate_scramble = 0
    else: success_rate_scramble = len(successful_plays_scramble) / total_plays_scramble
    
    success_rates_pass.append(success_rate_pass)
    success_rates_run.append(success_rate_run)
    success_rates_scramble.append(success_rate_scramble)

plays_at_distance_11plus = pass_plays[pass_plays["pff_DISTANCE"] >= 11]
successful_plays_11plus = plays_at_distance_11plus[plays_at_distance_11plus["pff_FIRST_DOWN_GAINED"] == 1]
total_plays_11plus = len(plays_at_distance_11plus)

# Calculate success rate for 11+ yards and append
if total_plays_11plus == 0:
    success_rate_11plus = 0
else:
    success_rate_11plus = len(successful_plays_11plus) / total_plays_11plus
success_rates_pass.append(success_rate_11plus)

# 8. Plot the success rates for distances 1-10 and 11+
plt.figure(figsize=(8, 5))
plt.bar(range(1, 12), success_rates_pass, label="Success Rate")
plt.title("Success Rate for Pass Plays Tagged 'P' by Distance (1-10 and 11+ Yards)")
plt.xlabel("Distance (Yards)")
plt.ylabel("Success Rate")
plt.grid(True)

# 9. Show the plot
plt.show()

#2. A graph of opponents success rate for each distance of 3rd/4th downs against Harvard.
h_def = pd.read_csv("harvard_def.csv")
h_34down = b_34down["pff_DOWN", "pff_DISTANCE", "pff_FIRST_DOWN_GAINED", "pff_QBSCRAMBLE", "pff_RUNPASS"] # Could also be interesting to split PASS/RUN success




#3. A graph for short (1-3 yards), medium (4-6), and long (7+) opponent success rate against Harvard for 3rd and 4th downs.


#3a: PASS: A graph for short (1-3 yards), medium (4-6), and long (7+) opponent success rate against Harvard for 3rd and 4th downs

#3b: RUN: A graph for short (1-3 yards), medium (4-6), and long (7+) opponent success rate against Harvard for 3rd and 4th downs pass excl. pff_QBSCRAMLBLE
