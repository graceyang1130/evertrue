# End-of-game clock decisions

A focused staff report on timeouts, clock preservation, and clock killing

BROWN FOOTBALL  |  8 OCTOBER 2026  |  Version 3

> Set the clock plan before each late possession. Name the timeout trigger, the expected final down, the clock restart, and the status of the two-minute timeout.

## Four calls for the sideline

| Situation | Call |
| --- | --- |
| Trailing on defense | When time is tight and our timeouts can cover the waits before a punt, call at the whistle. |
| Trailing with the ball | Use a timeout when the drive cannot finish on the clock. Keep one only if the last sequence may end in bounds. |
| Leading | Kneel only after the clock math is checked from the current down and restart state. |
| Play clock near zero | Call timeout in the ordinary spots studied here. The five-yard penalty cost more than the saved timeout. |

## What the evidence says

| Finding | Evidence | Meaning |
| --- | --- | --- |
| A defensive timeout can save a full wait. | FCS clock-kill runs used 33.0 seconds between plays. | If the timeout is part of the plan, call it right away. |
| Brown has 17 adjusted defensive flags. | Nine of the original 26 were set aside because the expected series reached the two-minute timeout. | Brown called timeout in 8 of the remaining 17. |
| Teams leave time on the play clock. | The national median was 5 seconds. Only 35% of snaps came at 3 seconds or less. | A rehearsed late-snap process can add useful time. |
| A chart time assumes a clock restart. | With one timeout, the same three kneels cover 1:28 if the clock runs first and 0:50 if it does not. | Check whether the clock is running before using the chart. |

## Sample

The full file has 5,578 games, 773,020 modeled snaps, and 35,040 reconstructed timeouts. It covers 2023 through Week 4 of 2026. FCS teams were identified with ESPN standings and game results. Brown has 32 games in the file.

The appendix contains every chart mode from the prior dashboard. The new timeout map replaces thousands of selector combinations with small multiples and two full situation maps.

# 1. Trailing: protect useful time

## Defensive timeouts

A defensive timeout removes the wait after a play. It does not remove the play itself. FCS clock-kill runs averaged 7.4 seconds for the play and 33.0 seconds before the next snap.

The original rule flagged 26 Brown spots. The revised screen sets aside nine because the expected series reaches the two-minute timeout before the punt. Brown called timeout in 8 of the remaining 17. The other nine intervals used 341 estimated seconds in total.

| Their next down | Waits before a punt | Call now when we have |
| --- | --- | --- |
| 1st | 4 | No full coverage with three timeouts |
| 2nd | 3 | 3 timeouts |
| 3rd | 2 | 2 or 3 timeouts |
| 4th | 1 | At least 1 timeout |

This rule assumes a running clock and an expected punt after stops. For 2024 onward, do not apply it when the average no-timeout path begins above 2:00 and reaches 2:00 before the punt.

## Brown examples

[2023 Princeton, Q4 3:31 to 2:01](https://ultimate.pff.com/playlist/161424) has two flagged waits with Brown down seven and all three timeouts. The audit estimates 38 seconds in each wait.

[2024 Princeton, Q4 3:16 to 2:33](https://ultimate.pff.com/playlist/161428) shows why film matters. Defensive holding created a first down, so the assumed-punt path did not occur.

[2026 Harvard, Q4 2:52 to 2:14](https://ultimate.pff.com/playlist/161422) is now held out of the flag count. The expected series reaches the automatic timeout before the possession ends.

## How to read the audit

A flag means the adjusted rule recommends an immediate timeout. A two-minute holdout means the automatic stop changes the sequence, so this simple audit does not judge the call.

Brown's 47.1% call rate comes from only 17 adjusted flags. It cannot show that Brown differs from the FCS or Ivy rate with confidence.

# 2. Trailing on offense: timeout or spike

## A timeout saves time and a down

After a first down, the chain stoppage makes a hurry-and-spike fairly cheap. The FCS average was 5.2 seconds. After a play short of a first down, the average cost rose to 12.2 seconds.

| Group | After first down | After play short of first down |
| --- | --- | --- |
| FCS | 5.2 sec (n=229) | 12.2 sec (n=40) |
| Ivy | 3.8 sec (n=19) | 11.6 sec (n=2) |
| Brown | 4.3 sec (n=2) | No sample |

## Call

| Clock state | Default |
| --- | --- |
| First down just gained | Use the chain stoppage. Spike if about five seconds and the down are cheaper than the timeout. |
| Play ended in bounds short of first down | A timeout usually saves about 12 seconds and preserves the next down. |

## Brown film

[2025 Yale, Q2 0:23 to 0:16](https://ultimate.pff.com/ncaa/games/30167/boxscore): Brown gained a first down and spiked. The estimated timeout savings were 3.3 seconds.

[2026 New Haven, Q2 0:24 to 0:14](https://ultimate.pff.com/ncaa/games/32104/boxscore): Brown gained a first down and spiked. The estimated timeout savings were 5.3 seconds.

Method: observed final-two-minute spike sequences with no timeout or natural stop between snaps. The estimate removes the prior play's live time and adds the spike. Brown's sample is too small for a team rule; use the FCS values for planning.

# 3. Leading: verify the kneel-out

## The first question is whether the game clock is running

The staff chart uses 4 seconds for each kneel and 38 seconds of play-clock use. Its first-down, one-timeout line is 1:28. That total assumes a usable running-clock wait before the first snap.

| Start state | Three-kneel total vs. one timeout | Reason |
| --- | --- | --- |
| Clock running before first snap | 88 seconds | Three 4-second plays plus two 38-second waits |
| Clock stopped until first snap | 50 seconds | Three 4-second plays plus one 38-second wait |

## Three checks before victory formation

| Check | Question |
| --- | --- |
| Restart | Will the game clock run before the next snap? |
| Automatic stop | Has the two-minute timeout happened? Will this play cross 2:00? |
| Safe plays | How many downs remain? Is there room for each kneel and no fourth-down return? |

## Execution matters

The national clock-kill median was 5 seconds left on the play clock. Snapping at 1 instead of 5 uses four more seconds. Three such waits use 12 more seconds.

A four-minute run lasts about seven to eight seconds from snap to whistle. A kneel lasts about four to five seconds. The Brown samples are only seven runs and three kneels.

| Group | Clock-kill run | Kneel |
| --- | --- | --- |
| FCS | 7.4 sec (n=2,287) | 4.4 sec (n=551) |
| Ivy | 7.6 sec (n=188) | 4.7 sec (n=33) |
| Brown | 7.0 sec (n=7) | 4.7 sec (n=3) |

These are snap-to-whistle averages. Add the usable wait before the next snap only when the game clock will run.

# 4. Counterarguments and limits

### Save the timeout for offense

That can be right if the last drive may end with the clock running. Still, the adjusted Brown missed intervals averaged 37.9 seconds. Spend the timeout on defense when the offense can still finish without it.

### Always run when protecting a lead

A run can keep the clock moving. A failed series also returns the ball. If kneels cannot end the game, the choice must include conversion chance, turnover risk, punt position, and the opponent's next drive.

### A saved timeout is worth only 0.33 points

The estimate is 0.33 percentage points of win probability in sampled one-score states. It is an average. It does not price a substitution error, a bad call, or the last play of a drive.

### Unused timeouts caused close losses

Three of six sampled close losses ended with an unused timeout. That makes those games worth review. It does not show that a useful timeout chance existed.

### The 2:30 mark is a firm trigger

The 151-second value is the 75th percentile of 430 successful hurry-up drives. Failed drives were excluded. Treat it as a planning mark, not a universal deadline.

## Model limits

The win model is a clock-value estimate. Team strength uses full-season scoring margin. Calibration uses many plays from the same games. Those choices can make the results look more certain than a live decision is.

> Use the model to set the clock plan. Use the game state and film to make the call.

# 5. Brown film queue

The links open selected plays in Ultimate. Sign-in and playlist access may be required. The estimated wait is based on play-by-play timing, not a hand-timed film review.

| Film | Snap | Next | Score | Next down | TO | Est. wait |
| --- | --- | --- | --- | --- | --- | --- |
| [2023 Rhode Island](https://ultimate.pff.com/playlist/161425) | 02:39 | 01:54 | Down 4 | 2 | 3 | 38 sec |
| [2023 Princeton](https://ultimate.pff.com/playlist/161424) | 03:31 | 02:46 | Down 7 | 2 | 3 | 38 sec |
| [2023 Princeton](https://ultimate.pff.com/playlist/161424) | 02:46 | 02:01 | Down 7 | 3 | 3 | 38 sec |
| [2024 Penn](https://ultimate.pff.com/playlist/161426) | 01:16 | 00:29 | Down 10 | 4 | 1 | 40 sec |
| [2024 Harvard](https://ultimate.pff.com/playlist/161427) | 04:59 | 04:12 | Down 5 | 2 | 3 | 40 sec |
| [2024 Princeton](https://ultimate.pff.com/playlist/161428) | 04:44 | 03:58 | Down 5 | 2 | 3 | 39 sec |
| [2024 Princeton](https://ultimate.pff.com/playlist/161428) | 03:58 | 03:16 | Down 5 | 3 | 3 | 35 sec |
| [2024 Princeton](https://ultimate.pff.com/playlist/161428) | 03:16 | 02:33 | Down 5 | 4 | 3 | 36 sec |
| [2025 Yale](https://ultimate.pff.com/playlist/161430) | 04:41 | 03:57 | Down 12 | 2 | 3 | 37 sec |

## Source record

Primary data: tos/out/report_data.json, tos/out/timeout_report.html, output/pdf/clock_option_analysis.json, and data/ncaa/pbp.csv.gz.

Reference files: Brown Timeout Decisions.pdf; 2POINT_EOG - KNEEL DOWN SITUATION CHART.xlsx - USE THIS ONE w-2min waning NEW.pdf; evertrue1.txt; evertrue2.txt.

Rules: [2023 timing change](https://www.ncaa.org/news/media-center-football-timing-rules-approved-for-divisions-i-ii/); [2024 two-minute timeout](https://www.ncaa.org/news/media-center-technology-rules-approved-in-football/); [current NCAA rule resources](https://www.ncaa.org/championships/playing-rules/football-playing-rules/).

FCS classification: ESPN FCS standings and scoreboards were matched to PFF teams by date and final score. A code required at least three matches and 80% agreement across seasons.

Two-minute timeout: For 2024 onward, a raw defensive flag was set aside if it began above 2:00 and the average no-timeout path reached 2:00 before the expected punt. This is a conservative holdout, not a finding that a charged timeout had no value.

Film: Ultimate site structure, filters, report catalog, IQ tools, video pages, and playlist workflow were reviewed. The selected links were matched to PFF play IDs.

Missing historical file: end_of_game/ivy_19t26.csv is not in this checkout. The stored Ivy model parameters remain, but that historical fit cannot be rerun here. This is separate from the current PFF defensive audit, which uses the national play-by-play file.

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
