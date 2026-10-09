# End-of-game clock management

6 OCTOBER 2026

Recommendation:   
Make the clock plan explicit before each late possession based on: 

1. How many timeouts the opponent has   
2. Whether the two-minute timeout has occurred  
3. What the next down is  
4. Whether the clock is stopped

When Brown is trailing and time is scarce, we should consider calling timeout to conserve time. When Brown is leading, we will establish situations where we can run the time out vs possessions that still requires a first down.

## What we studied

Analysis based on 6,833 FCS runs in the final 4 minutes.

| Finding | Evidence | Staff implication |
| :---- | :---- | :---- |
| Defensive timeouts preserve a substantial clock interval. | 33.5 seconds pass between plays on average when the clock is running. | Calling timeout when trailing on defense is essential to save the clock |
| Clock-killing depends on execution. | The ball was snapped with a median 5 seconds left on the play clock; only 35% were at 3 or less. Brown’s median was 6 seconds left on the play clock (from 11 plays). | Use a rehearsed late-snap procedure. |

## Where the evidence comes from

The national timeout dataset contains 5,578 games, 773,020 modeled scrimmage snaps, and 35,040 reconstructed timeouts, including seasons 2023 to 2026 through week 4\. 

Brown has 32 games: 10 in each of 2023-2025 and 2 in 2026\.

*Flagged* means that our approach recommends a timeout. Sources and review details appear on page 5\.

# 1\. When trailing, call timeouts on Defense.

On national four-minute runs with a running clock, we measured an average of:  
7.1 seconds of live play \+ 33.5 seconds between plays \= 40.6 seconds from snap to snap

In comparison, Brown’s hurry-up offense (not calling a TO between plays while the clock is running in the final 2 mins) takes up 16.0 seconds between plays on average. The FCS average is 12 seconds. Note that offensive timeout still has value when Brown needs to preserve a down, change personnel, or avoid a rushed play. Those benefits should be weighed against the time advantage of calling a timeout on defense.

TLDR: Defensive TO saves 33.5 seconds on average, offensive TO saves 16.0 seconds (+ maybe a down if we spike it)

## What down to start calling TO (on defense)

When the clock is running and we are trailing, we should use our timeouts to stop the clock as soon possible, but need to make sure we are able to take timeouts to stop the clock every play after until we get the ball back.

| Their next down | Intervals between downs (assuming the other team punts) | Immediate trigger |
| :---- | :---- | :---- |
| 1st | 4 | Cannot cover all with 3 timeouts |
| 2nd | 3 | 3 timeouts |
| 3rd | 2 | 2 or 3 timeouts |
| 4th | 1 | At least 1 timeout |

With fewer timeouts than waits, postponing one can preserve the same total clock if the offense fails to convert and intervals between plays are interchangeable.   
Note that a first down, fourth-down attempt, or another clock stoppage changes the sequence. Reassess considering those factors after every play.

### When to Start Calling Timeouts on Defense

Start the timeout sequence when the expected punt would leave less time than Brown needs for its next drive. For planning, use **2:31** as the target. That is the 75th-percentile length of 430 successful hurry-up scoring drives in the FCS data.

An FCS clock-killing play removes about **40.4 seconds** ( play lasts 7.4 seconds, 33.0 seconds interval). A defensive timeout preserves most of that 33-second wait.

#### Default start times for a one-score game

| Opponent’s next down | Clock-draining intervals before an expected punt | Start calling near |
| :---- | ----: | ----: |
| First down | 4 | **5:13 — assess, but usually wait one down** |
| Second down | 3 | **4:32** |
| Third down | 2 | **3:52** |
| Fourth down | 1 | **3:11** |

These times refer to the **game clock at the end of the play**. They assume the clock is running and the opponent will punt after fourth down.

#### Accounting for the two-minute timeout

The automatic two-minute timeout can replace one charged timeout. It affects the expected series when the clock is below roughly:

| Opponent’s next down | 2-min timeout likely influences at & after |
| :---- | ----: |
| First down | 4:42 |
| Second down | 4:01 |
| Third down | 3:21 |
| Fourth down | 2:40 |

Before calling timeout, identify which interval the automatic timeout will stop. Do not spend a charged timeout on that same interval.   
At each whistle:

1. Identify the opponent’s next down.  
2. Count the clock-draining intervals before the expected punt.  
3. Include the automatic two-minute timeout if it will stop one interval.  
4. Estimate when Brown will receive the ball.  
5. If the expected possession begins with less than 2:31 remaining, start the timeout sequence as soon as the available stops can cover every remaining interval.

Move these start times earlier when Brown needs two possessions. They can move later when Brown needs only a field goal, expects favorable field position, or expects the opponent to snap early. A first down, likely fourth-down attempt, or opponent scoring opportunity slightly different calculation as well.

## Example

[2023 Princeton: Q4 3:31, 2:46 and 2:01](https://ultimate.pff.com/playlist/161424) shows two intervals when we might have benefited from calling timeout, with Brown down seven and three timeouts. 38 seconds passed on average between plays. Brown won 28-27 in overtime but the sequence is an example of how we could have taken better advantage of the available clock.

[See the table below](?tab=t.0) with 26 situations we would recommend taking a timeout where Brown trailed by 1-2 scores. Brown called timeout in 13 of them. In the remaining 13, about 37.2 seconds passed per interval; 11 had all three timeouts available. Across the FCS, teams called timeout in 55.1% of our 3,337 flagged situations; the rate for Ivies was 63.6% of 121\. 

Note this analysis does not explicitly account for the two-minute timeout (but we anticipate that being a small subsect of these situations). & This sample cannot independently establish that Brown is really worse than the league, but should be something to consider upon review.

# 2\. When leading, killing time

When a lead can be protected by exhausting the clock without surrendering possession, victory formation removes the need to gain yards. When it cannot, the offense still needs a conversion or a plan for returning the ball..

## The staff chart and the model answer different clock states

The staff chart assumes each play lasts 4 seconds and the offense uses 38 seconds of the play clock. It says, on first-down \+ opponent with 1 TO, to start kneeling at 1:28. That matches three kneels and two full waits: 3 × 4 \+ 2 × 38 \= 88 seconds.

## Required checks

| Check | Why it changes the answer |
| :---- | :---- |
| Two-minute timeout pending or taken? | The automatic stoppage can erase a planned wait. A play crossing 2:00 must be timed through the stoppage. |
| How many safe plays remain? | Track the down, opponent timeouts, space for kneel losses, and whether a fourth-down play ends the game. |

The chart’s highlighted no-timeout windows (2:01-2:07 and 2:41-2:53 after first down) are due to 2 minute timeouts. The current clock-kill function assumes 2 seconds live plus 39 seconds dead per kneel and does not explicitly model the two-minute timeout or initial clock state. 

## Execution can change the margin

National clock-running four-minute snaps had a median 5 seconds left on the play clock. Snapping at 1 rather than 5 would consume 4 additional seconds on that wait; three comparable running-clock waits would consume 12\. This is available only when the clock runs and no timeout intervenes. Brown’s tagged sample is too small for a reliable team estimate: 7 running intervals for runs, 2 for passes, and 3 for kneels. \[1,2\]

## Average time taken to slightly stretch the clock

| Group | Clock-kill run: live play |
| :---- | ----: |
| FCS | 7.4 sec (n=2,287) |
| Ivy | 7.6 sec (n=188) |
| Brown | 7.0 sec (n=7) |

When the clock continues running, the modeled full cycle is:

| Group | Clock-kill run |
| :---- | ----: |
| FCS | 40.4 sec |
| Ivy | 41.1 sec |
| Brown | 37.6 sec |

# 3\. What the evidence can support

## “We should save the timeouts for our offense.”

There is a valid reason to save one: an offensive timeout can prevent the final possession from ending with the clock running. But the measured dead-ball interval is about 34 seconds against a clock-killing opponent versus 16 in Brown’s hurry-up passing sample. Prefer the defensive use when the offense can still finish its drive without it. If spending every timeout leaves no workable offensive finish, retain one. A two-score deficit does not remove the need to complete the first score.

## “We should always run when protecting a lead.”

Runs can keep the clock moving, but a failed series returns the ball. When kneeling cannot end the game, conversion probability, turnover risk, field position, and the opponent’s scoring chance all matter. The proposed play-outcome, punt, and endgame simulation modules are absent from the current checkout. Their optimal-call recommendations are not established results. \[5,6\]

## “The model proves a timeout is worth only 0.33 points.”

The saved-timeout estimate averages 0.33 percentage points of win probability in the sampled one-score states at the start of the final four minutes. The prior five-yard estimates range from 1.82 to 4.70 points in selected tied, third-quarter situations. This supports using a timeout to avoid delay of game in many ordinary situations. It does not compare both choices in the same late-game state or price protection against a bad call, substitution problem, or clock expiration. \[1,3\]

The win model translates extra seconds into a change in estimated win probability. That is a coherent clock-value approximation, not a demonstrated causal effect of timeout use. Its held-out calibration uses many snaps from the same games, and team strength is calculated from full-season scoring margins, including results unavailable at the time of a live decision. Strong average calibration does not validate every late-game choice. \[3\]

## “Unused timeouts cost Brown close games.”

Three of six sampled Brown losses by eight or fewer ended with timeouts unused. That identifies games to inspect; it does not establish a lost opportunity. A timeout can remain because no running-clock possession offered a useful chance to spend it. In [2024 Princeton, Q4 3:16 to 2:33](https://ultimate.pff.com/playlist/161428), the flagged wait leads into a fourth-down defensive-holding no-play, then first down at 2:22. Nothing we can do there. \[1-3,8\]

## “The earlier report’s 2:30 cutoff is the right rule.”

The 151-second estimate is the 75th percentile of 430 successful hurry-up scoring drives. Unsuccessful attempts were excluded; time is measured from first to last snap, not through the final scoring play. It describes those successes and supplies a planning heuristic. It is not the required time to score, a 75% success probability, or a validated universal timeout threshold. \[2\]

Staff takeaway: adopt the clock-state checklist and prompt-call procedure; use the audit to select film; treat exact trigger times and run/pass advice as provisional until the full possession model is completed and validated.

# Evidence and source record

## Brown film-review queue

All 13 audit intervals. Click a game for selected film; clocks below are Q4 snap clocks. “Est. wait” is snap-to-next-event time minus an assumed 7-second play, not the precise interval time range. Sign-in and playlist access are required. 

| Film / game | Snap / next | Margin | Next down | TO left | Est. wait | Link |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| [2023 Rhode Island](https://ultimate.pff.com/playlist/161425) | 02:39 / 01:54 | Down 4 | 2 | 3 | 38 sec | https://ultimate.pff.com/playlist/161425 |
| [2023 Princeton](https://ultimate.pff.com/playlist/161424) | 03:31 / 02:46 | Down 7 | 2 | 3 | 38 sec | https://ultimate.pff.com/playlist/161424 |
| [2023 Princeton](https://ultimate.pff.com/playlist/161424) | 02:46 / 02:01 | Down 7 | 3 | 3 | 38 sec | https://ultimate.pff.com/playlist/161424 |
| [2024 Penn](https://ultimate.pff.com/playlist/161426) | 03:13 / 02:27 | Down 10 | 2 | 3 | 39 sec | https://ultimate.pff.com/playlist/161426) |
| [2024 Penn](https://ultimate.pff.com/playlist/161426) | 01:16 / 00:29 | Down 10 | 4 | 1 | 40 sec | https://ultimate.pff.com/playlist/161426) |
| [2024 Harvard](https://ultimate.pff.com/playlist/161427) | 04:59 / 04:12 | Down 5 | 2 | 3 | 40 sec | https://ultimate.pff.com/playlist/161427 | 
| [2024 Harvard](https://ultimate.pff.com/playlist/161427) | 03:26 / 02:43 | Down 5 | 2 | 3 | 36 sec | https://ultimate.pff.com/playlist/161427 |
| [2024 Princeton](https://ultimate.pff.com/playlist/161428) | 04:44 / 03:58 | Down 5 | 2 | 3 | 39 sec | https://ultimate.pff.com/playlist/161428 |
| [2024 Princeton](https://ultimate.pff.com/playlist/161428) | 03:58 / 03:16 | Down 5 | 3 | 3 | 35 sec | https://ultimate.pff.com/playlist/161428 |
| [2024 Princeton](https://ultimate.pff.com/playlist/161428) | 03:16 / 02:33 | Down 5 | 4 | 3 | 36 sec | https://ultimate.pff.com/playlist/161428 |
| [2025 Penn](https://ultimate.pff.com/playlist/161429) | 03:36 / 02:52 | Down 7 | 2 | 3 | 37 sec | https://ultimate.pff.com/playlist/161429 |
| [2025 Yale](https://ultimate.pff.com/playlist/161430) | 04:41 / 03:57 | Down 12 | 2 | 3 | 37 sec | https://ultimate.pff.com/playlist/161430 |
| [2026 Harvard](https://ultimate.pff.com/playlist/161422) | 02:52 / 02:14 | Down 4 | 3 | 2 | 31 sec | https://ultimate.pff.com/playlist/161422 |



## Sources and method

\[1\] Existing report and saved results. Brown Timeout Decisions.pdf, supplied reference (11 pages); tos/out/report\_data.json and timeout\_report.html. The 11-page reference was reviewed and its claims checked against the available code.

\[2\] Reproduced clock evidence. data/ncaa/pbp.csv.gz; tos/clock\_game.py, using end\_of\_game/runoff\_model.py. The rerun reproduced the play-time summaries, 430-drive statistic and 13 flagged intervals. Live time uses snap clocks and play-clock use, clipped to 0-20 seconds; unflagged stops and resets can affect it.

\[3\] Timeout reconstruction and valuation. tos/timeouts.py, wp\_model.py, report\_data.py; data/ncaa/games.csv, timeouts.csv and timeouts\_unused.csv. Timeout purposes are inferred. The audit excludes known natural stops and filters short unflagged stops; urgency assumes a stop, typical punt position and successful-drive timing.

\[4\] Staff reference. 2POINT\_EOG \- KNEEL DOWN SITUATION CHART.xlsx \- USE THIS ONE w-2min waning NEW.pdf (one page). The two-point conversion portion is outside this report’s scope. \[5\] end\_of\_game/clock\_kill.py, params\_brown.json, params\_ivy.json, opp\_offense.py, DESIGN.md and PLAN-02-refit.md.

\[6\] Development history. /Users/graceyang/Documents/evertrue1.txt and evertrue2.txt. The later record reports an approved switch from expected points to raw yards-to-goal; current opp\_offense.py still uses expected points. Its historical 720-drive Ivy validation cannot be rerun because ivy\_19t26.csv is absent. The available Brown-only CSV fails all six gates, as intended for a thin sample; this does not invalidate the historical Ivy fit.

\[7\] Rules context. NCAA’s 2023 first-down timing change and 2024 two-minute timeout mean this sample spans different timing regimes. Official sources: [2023 timing changes](https://www.ncaa.org/news/media-center-football-timing-rules-approved-for-divisions-i-ii/); [2024 timing changes](https://www.ncaa.org/news/media-center-technology-rules-approved-in-football/). Current rule resources: [NCAA Football Playing Rules](https://www.ncaa.org/championships/playing-rules/football-playing-rules/). Exact boundary cases require the current rule and the actual restart signal.

\[8\] Ultimate film review. Reviewed the main sections, report catalogs, clock filters, IQ timing tools and video/playlist workflow on 6 October. Eight selected film sequences cover all 13 audit intervals, matched by PFF play ID and checked on their playlist pages. See film\_index.md, film\_index.json and ultimate\_site\_review.md. Links identify the plays; the audit estimates are not presented as film-measured timeout savings.

# Appendix: charts and tables

Short explanations are placed under each item. All values come from the saved report data and the reproduced clock audit.

## Coverage of the old dashboard

| Old control or view | Static coverage here |
| --- | --- |
| Who has the ball | Both rows on each decision-map page |
| Timeouts: 1, 2, 3 | Three columns on each decision-map page |
| Team strength: -7, 0, +7 | One full page for each setting |
| Score and time | Both axes on all 18 decision maps |
| Card view: down, distance, field position | Two full trigger maps |
| Show numbers | Two timeout-value maps |
| Play-time group: all, FCS, Ivy, Brown | Original panels plus the FCS timing plate |
| Audit chart / table | Both forms included |

A literal export of every selector combination would create more than 200,000 repeated cells. The plates below preserve every dimension and show its full range.

## Decision-map key

Each square answers what to do after a play that leaves the clock running. The maps use 3rd-and-5 at the possession team's 35 so the possession, timeout, score, time, and strength effects can be compared cleanly.

# A1. Timeout decision map: They are better by 7

Use the row for possession and the column for timeouts left. Score is vertical and game time is horizontal.

# A2. Timeout decision map: Even teams

Use the row for possession and the column for timeouts left. Score is vertical and game time is horizontal.

# A3. Timeout decision map: Brown is better by 7

Use the row for possession and the column for timeouts left. Score is vertical and game time is horizontal.

# A4. Down, distance, and field position

Darker cells mean the start-call point comes earlier. Blank cells mean the rule never says 'call now' in the last 15 minutes for that fixed setting.

# A5. What one timeout adds

The color is the modeled gain from the seconds saved by one timeout. This is the static version of the dashboard's 'Show numbers' setting.

# A6. Three stops and delay of game

Three immediate defensive timeouts preserve about 1:40 in this average sequence. The exact game result depends on the live play time and the next down.

In the eight tested spots, a five-yard penalty cost 1.8 to 4.7 win-probability points. The saved-timeout average was 0.33 points.

# A7. Time used per snap

Faded Brown bars have fewer than 30 snaps. The national and Ivy samples are more useful for setting a clock assumption.

# A8. Play clock and defensive urgency

Clock-kill teams snapped with a median of 5 seconds left. Only 35% snapped with 3 seconds or less.

After the two-minute holdout, Brown called timeout in 8 of 17 flags. The FCS rate was 50.4% of 979; the Ivy rate was 65.5% of 84.

# A9. Brown's adjusted defensive audit

| Game | Time | Score | Next snap | TO | Clock lost |
| --- | --- | --- | --- | --- | --- |
| 2023 Rhode Island | 2:32 | Down 4 | 2 down | 3 | 38 sec |
| 2023 Princeton | 3:24 | Down 7 | 2 down | 3 | 38 sec |
| 2023 Princeton | 2:39 | Down 7 | 3 down | 3 | 38 sec |
| 2024 Penn | 1:09 | Down 10 | 4 down | 1 | 40 sec |
| 2024 Harvard | 4:52 | Down 5 | 2 down | 3 | 40 sec |
| 2024 Princeton | 4:37 | Down 5 | 2 down | 3 | 39 sec |
| 2024 Princeton | 3:51 | Down 5 | 3 down | 3 | 35 sec |
| 2024 Princeton | 3:09 | Down 5 | 4 down | 3 | 36 sec |
| 2025 Yale | 4:34 | Down 12 | 2 down | 3 | 37 sec |

Nine adjusted flags had no timeout. They averaged 37.9 seconds; eight began with all three timeouts.

## Set aside because the series reaches 2:00

| Game | Snap | Next | Next down | TO | Result |
| --- | --- | --- | --- | --- | --- |
| 2024 Penn | 2:27 | 2:20 | 3 down | 3 | Called |
| 2024 Penn | 3:13 | 2:27 | 2 down | 3 | No call |
| 2024 Harvard | 3:26 | 2:43 | 2 down | 3 | No call |
| 2024 Rhode Island | 2:27 | 2:22 | 3 down | 2 | Called |
| 2024 Rhode Island | 2:34 | 2:27 | 2 down | 3 | Called |
| 2025 Penn | 3:36 | 2:52 | 2 down | 3 | No call |
| 2025 Yale | 2:58 | 2:55 | 3 down | 2 | Called |
| 2025 Yale | 3:04 | 2:58 | 2 down | 3 | Called |
| 2026 Harvard | 2:52 | 2:14 | 3 down | 2 | No call |

These nine rows are outside the call-rate calculation. Five used a charged timeout and four did not.

# A10. How Brown uses timeouts

Brown used 3.38 timeouts per game in the sample. The use labels are inferred from game state.

| Use | Brown | Other Ivy | All FBS/FCS |
| --- | --- | --- | --- |
| Stop clock at half end | 1.97 | 1.67 | 1.57 |
| Other defense | 0.69 | 0.70 | 0.63 |
| Play clock | 0.22 | 0.29 | 0.42 |
| Before 4th down | 0.19 | 0.10 | 0.14 |
| Before punt | 0.12 | 0.12 | 0.13 |
| Before kick | 0.00 | 0.08 | 0.07 |
| Other offense | 0.19 | 0.11 | 0.19 |
| Total | 3.38 | 3.07 | 3.14 |

| Unused | Brown | Other Ivy | All FBS/FCS |
| --- | --- | --- | --- |
| Left at halftime | 1.09 | 1.47 | 1.31 |
| Left at end of game | 1.53 | 1.49 | 1.57 |

Brown carried fewer timeouts into halftime than the comparison groups. End-of-game unused timeouts were close to the national level.

# A11. Brown play-clock timeouts and close losses

| Game | Time | Down | Score | TO left | 5-yard cost | Cheaper |
| --- | --- | --- | --- | --- | --- | --- |
| 2023 Rhode Island | Q2 13:31 | 3 & 8 | Up 4 | 1 | 4.58 | Timeout |
| 2023 Princeton | Q1 12:22 | 3 & 4 | Tied | 2 | 4.58 | Timeout |
| 2024 Yale | Q2 8:24 | 1 & 1 | Down 21 | 2 | 0.43 | Timeout |
| 2025 Georgetown | Q2 7:55 | 2 & 5 | Up 14 | 2 | 0.64 | Timeout |
| 2025 Rhode Island | Q1 4:27 | 3 & 3 | Tied | 1 | 4.70 | Timeout |
| 2025 Bryant | Q1 0:12 | 2 & 3 | Down 6 | 1 | 2.06 | Timeout |
| 2026 Harvard | Q4 14:02 | 2 & 15 | Down 11 | 2 | 0.56 | Timeout |

The five-yard cost exceeded the 0.33-point saved-timeout average in all seven logged cases. The comparison is a screen, not a same-state late-game simulation.

| Close loss | Lost by | Timeouts left |
| --- | --- | --- |
| 2023 Harvard | 3 | 1 |
| 2023 Rhode Island | 4 | 1 |
| 2024 Bryant | 7 | 2 |
| 2025 Penn | 7 | 0 |
| 2025 Cornell | 6 | 0 |
| 2026 Harvard | 4 | 0 |

Three of six close losses ended with a timeout left. This identifies film to review; it does not show causation.

# A12. Model checks

The 2025 calibration is close in broad bins. The example state shows that the PFF value is far below the fitted model and the small Ivy history sample.

## Method in plain terms

| Step | What was done |
| --- | --- |
| Timeouts | A drop in PFF's timeout count was treated as a timeout. |
| Play time | Snap clocks and play clocks split each interval into live play and the wait. |
| Urgency | The rule compares time left after expected stops with successful hurry-up drive time. |
| Win chance | Score, expected points, time, and team strength feed a fitted probability model. |
| Recommendation | The rule checks urgency, remaining downs, timeouts, and whether two scores are needed. |

Known limits: timeouts and purposes are reconstructed; drive timing excludes failed drives; full-season strength leaks later results; repeated plays from the same game are not independent; the two-minute timeout is not modeled directly in the defensive audit rule.

# A13. Offensive timeout, spike, and clock-kill timing

The first-down chain stoppage cuts the FCS hurry-and-spike cost to 5.2 seconds. Without a first down, the cost is 12.2 seconds and the spike still uses a down.

| Group | Play | n | Live | Wait | Total |
| --- | --- | --- | --- | --- | --- |
| FCS | Clock-kill run | 2287 | 7.4 | 33.0 | 40.4 |
| FCS | Kneel | 551 | 4.4 | 30.9 | 35.3 |
| Ivy | Clock-kill run | 188 | 7.6 | 33.5 | 41.1 |
| Ivy | Kneel | 33 | 4.7 | 29.6 | 34.3 |
| Brown | Clock-kill run | 7 | 7.0 | 30.6 | 37.6 |
| Brown | Kneel | 3 | 4.7 | 21.0 | 25.7 |

Live is snap to whistle. Wait is whistle to the next snap and counts only when the game clock keeps running.

The spike estimate uses 269 FCS, 21 Ivy, and two Brown sequences. The prior play's live time is estimated from comparable final-two-minute snaps because the export records the clock at the snap, not at the whistle.
