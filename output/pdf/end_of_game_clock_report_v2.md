# End-of-game clock decisions

A focused staff report on timeouts, clock preservation, and clock killing

BROWN FOOTBALL  |  8 OCTOBER 2026  |  Revised version

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
| A defensive timeout can save a full wait. | National clock-kill runs used 33.5 seconds between plays. | If the timeout is part of the plan, call it right away. |
| Brown had 26 flagged defensive spots. | Brown called timeout in 13. The other 13 lost 37.2 seconds on average. | Review the sequence. The flag alone does not prove an error. |
| Teams leave time on the play clock. | The national median was 5 seconds. Only 35% of snaps came at 3 seconds or less. | A rehearsed late-snap process can add useful time. |
| Kneel thresholds depend on the clock state. | A running first clock and a stopped first clock can differ by a full play-clock interval. | Check the restart before using a chart. |

## Sample

The national file has 5,578 games, 773,020 modeled snaps, and 35,040 reconstructed timeouts. It covers 2023 through Week 4 of 2026. Brown has 32 games in that file.

The appendix contains every chart mode from the prior dashboard. The new timeout map replaces thousands of selector combinations with small multiples and two full situation maps.

# 1. Trailing: protect useful time

## Defensive timeouts

A defensive timeout removes the wait after a play. It does not remove the play itself. National clock-kill runs averaged 7.1 seconds for the play and 33.5 seconds before the next snap.

Brown had 26 late defensive spots that met the audit rule. Brown called timeout in 13. The other 13 intervals used 484 estimated seconds in total.

| Their next down | Waits before a punt | Call now when we have |
| --- | --- | --- |
| 1st | 4 | No full coverage with three timeouts |
| 2nd | 3 | 3 timeouts |
| 3rd | 2 | 2 or 3 timeouts |
| 4th | 1 | At least 1 timeout |

This rule assumes a running clock and an expected punt after stops. A first down, fourth-down try, penalty, natural stop, or two-minute timeout changes the plan.

## Brown examples

[2023 Princeton, Q4 3:31 to 2:01](https://ultimate.pff.com/playlist/161424) has two flagged waits with Brown down seven and all three timeouts. The audit estimates 38 seconds in each wait.

[2024 Princeton, Q4 3:16 to 2:33](https://ultimate.pff.com/playlist/161428) shows why film matters. Defensive holding created a first down, so the assumed-punt path did not occur.

[2026 Harvard, Q4 2:52 to 2:14](https://ultimate.pff.com/playlist/161422) reaches fourth down at the two-minute timeout. The automatic stop and field position must be part of the call.

## How to read the audit

A flag means the existing rule recommends an immediate timeout. It does not prove that the staff made the wrong choice. The rule also does not model the two-minute timeout directly.

Brown's 50% call rate comes from only 26 flags. It cannot show that Brown differs from the national or Ivy rate with confidence.

# 2. Leading: verify the kneel-out

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

The Brown sample is too small for a team estimate. It has seven tagged clock-kill runs, two passes, and three kneels.

## What the three clocks in this project assume

| Source | Live play | Wait |
| --- | --- | --- |
| Staff kneel chart | 4 sec | 38 sec |
| Current clock-kill code | 2 sec | 39 sec |
| National observed kneels | 4.2 sec | 31.5 sec |

These values answer different questions. Use the live clock and the actual play clock for the game decision.

# 3. Counterarguments and limits

### Save the timeout for offense

That can be right if the last drive may end with the clock running. Still, the measured wait was about 34 seconds on defense and 16 seconds in Brown's hurry-up passing sample. Spend it on defense when the offense can still finish without it.

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

# 4. Brown film queue

The links open selected plays in Ultimate. Sign-in and playlist access may be required. The estimated wait is based on play-by-play timing, not a hand-timed film review.

| Film | Snap | Next | Score | Next down | TO | Est. wait |
| --- | --- | --- | --- | --- | --- | --- |
| [2023 Rhode Island](https://ultimate.pff.com/playlist/161425) | 02:39 | 01:54 | Down 4 | 2 | 3 | 38 sec |
| [2023 Princeton](https://ultimate.pff.com/playlist/161424) | 03:31 | 02:46 | Down 7 | 2 | 3 | 38 sec |
| [2023 Princeton](https://ultimate.pff.com/playlist/161424) | 02:46 | 02:01 | Down 7 | 3 | 3 | 38 sec |
| [2024 Penn](https://ultimate.pff.com/playlist/161426) | 03:13 | 02:27 | Down 10 | 2 | 3 | 39 sec |
| [2024 Penn](https://ultimate.pff.com/playlist/161426) | 01:16 | 00:29 | Down 10 | 4 | 1 | 40 sec |
| [2024 Harvard](https://ultimate.pff.com/playlist/161427) | 04:59 | 04:12 | Down 5 | 2 | 3 | 40 sec |
| [2024 Harvard](https://ultimate.pff.com/playlist/161427) | 03:26 | 02:43 | Down 5 | 2 | 3 | 36 sec |
| [2024 Princeton](https://ultimate.pff.com/playlist/161428) | 04:44 | 03:58 | Down 5 | 2 | 3 | 39 sec |
| [2024 Princeton](https://ultimate.pff.com/playlist/161428) | 03:58 | 03:16 | Down 5 | 3 | 3 | 35 sec |
| [2024 Princeton](https://ultimate.pff.com/playlist/161428) | 03:16 | 02:33 | Down 5 | 4 | 3 | 36 sec |
| [2025 Penn](https://ultimate.pff.com/playlist/161429) | 03:36 | 02:52 | Down 7 | 2 | 3 | 37 sec |
| [2025 Yale](https://ultimate.pff.com/playlist/161430) | 04:41 | 03:57 | Down 12 | 2 | 3 | 37 sec |
| [2026 Harvard](https://ultimate.pff.com/playlist/161422) | 02:52 | 02:14 | Down 4 | 3 | 2 | 31 sec |

## Source record

Primary data: tos/out/report_data.json and tos/out/timeout_report.html. The play-time and defensive audit summaries were reproduced from data/ncaa/pbp.csv.gz.

Reference files: Brown Timeout Decisions.pdf; 2POINT_EOG - KNEEL DOWN SITUATION CHART.xlsx - USE THIS ONE w-2min waning NEW.pdf; evertrue1.txt; evertrue2.txt.

Rules: [2023 timing change](https://www.ncaa.org/news/media-center-football-timing-rules-approved-for-divisions-i-ii/); [2024 two-minute timeout](https://www.ncaa.org/news/media-center-technology-rules-approved-in-football/); [current NCAA rule resources](https://www.ncaa.org/championships/playing-rules/football-playing-rules/).

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
| Play-time group: all, Ivy, Brown | Three side-by-side panels |
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

Brown called timeout in 13 of 26 flagged spots. A missed Brown flag used 37.2 seconds on average.

# A9. Brown's missed defensive spots

| Game | Time | Score | Next snap | TO | Clock lost |
| --- | --- | --- | --- | --- | --- |
| 2023 Rhode Island | 2:32 | Down 4 | 2 down | 3 | 38 sec |
| 2023 Princeton | 3:24 | Down 7 | 2 down | 3 | 38 sec |
| 2023 Princeton | 2:39 | Down 7 | 3 down | 3 | 38 sec |
| 2024 Penn | 3:06 | Down 10 | 2 down | 3 | 39 sec |
| 2024 Penn | 1:09 | Down 10 | 4 down | 1 | 40 sec |
| 2024 Harvard | 4:52 | Down 5 | 2 down | 3 | 40 sec |
| 2024 Harvard | 3:19 | Down 5 | 2 down | 3 | 36 sec |
| 2024 Princeton | 4:37 | Down 5 | 2 down | 3 | 39 sec |
| 2024 Princeton | 3:51 | Down 5 | 3 down | 3 | 35 sec |
| 2024 Princeton | 3:09 | Down 5 | 4 down | 3 | 36 sec |
| 2025 Penn | 3:29 | Down 7 | 2 down | 3 | 37 sec |
| 2025 Yale | 4:34 | Down 12 | 2 down | 3 | 37 sec |
| 2026 Harvard | 2:45 | Down 4 | 3 down | 2 | 31 sec |

Eleven of the 13 spots began with all three timeouts. Every row should be checked against film and the two-minute timeout.

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

Known limits: timeouts and purposes are reconstructed; drive timing excludes failed drives; full-season strength leaks later results; repeated plays from the same game are not independent; the two-minute timeout is not modeled directly in the audit rule.
