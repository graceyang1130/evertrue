# Winning-drive distribution: methodology review

Rebuilt from the local PFF feed. Run `MPLCONFIGDIR=/private/tmp/evertrue-mpl python3 tos/plot_winning_drives.py`.
The optional `--window-minutes` changes the start-clock cutoff (default 4); output filenames are reused.

## What the earlier analysis did

- `end_of_game/clock_kill.py` splits clock consumption into live-ball seconds and dead-ball waits; opponent timeouts remove waits. It is an expected-runoff calculation, with initial clock state and automatic stoppages requiring additional handling.
- `tos/clock_game.py` used the 75th percentile of successful hurry-up scoring drives as a planning target for defensive timeouts. Failed drives were absent; this was never a scoring-probability estimate.
- `end_of_game/opp_offense.py` models TD, FG, or neither from time, starting EP, and scoring need. Its design amendments remove timeouts as an observational predictor and restrict the population to tied/trailing offenses. The proposed full run/pass/punt simulation remains unfinished.
- `tos/plot_drive_time_distribution.py` compared that benchmark with regulation-winning drives starting in the final 4:00. `tos/plot_matched_comeback_drives.py` used a different population: trailing by 1-8, starting in the final 5:00, at least 80% hurry-up; its success category combines wins and OT-forcing ties. Those are different questions and cannot share a percentile without qualification.

## Material defect found

The two earlier plot scripts and `tos/clock_game.py::drive_time` group by `(game, drive number)`.
The feed reuses drive numbers for the opposing offense: **64,315 of 68,428 groups mix teams**.
This can combine clocks, scores, outcomes, and hurry-up tags from different possessions.
The old algorithm reproduces **430 benchmark rows**, with an interpolated 75th percentile of **2:31**;
that agreement reproduces the implementation defect rather than validating the statistic.
The old chart itself shows only 168 rows labeled FCS within those 430 rows;
the report's description of all 430 as FCS is also inconsistent.

The earlier plots and report have been preserved for comparison. Their drive-based numbers and timeout triggers derived from the benchmark require recomputation before reuse. This rebuild does not change the report, timeout model, or runoff estimates.

## Corrected selection and timing

1. Sort by game and play order. Group actual, non-no-play scrimmage snaps by **game + offense + drive number**. There are 132,706 such possessions before the late-game filter.
2. Require the possession to begin and end in Q4, with its first snap in `(0, 4:00]`, offense tied or trailing, and offense the final winner. No hurry-up tag or minimum snap count is required.
3. Verify an actual offensive TD using its scoring-team tag, or verify the immediately following FG attempt was made. Kicks usually have no drive number; attach them only before the next possession or kickoff. A blocked attempt or defensive return TD is not an offensive score.
4. After the TD and try (or FG), require a positive lead at every subsequent observed score state, plus a regulation win in the game table. OT games and OT-forcing ties are excluded. Retain one decisive possession per game; duplicate winners raise an error.
5. Measure first scrimmage snap to **the actual TD snap or made-FG snap**. This includes FG setup time. It excludes the final play's live-ball duration because no play-end clock is available. One-snap TDs can measure 0:00. The first snap also follows any possession-change delay, so this is shorter than ball-received-to-score time.
6. FCS means the offense is in the existing season-specific FCS code list, regardless of opponent. The broader series is called all offenses in the feed because this export is not independently restricted to verified FBS/FCS members.
7. Percentiles use the inverse empirical CDF (observed ranks), matching the step curve. The groups overlap; they are not independent comparison samples.

## Results and audit

Included **354 winning possessions**, of which **132** are FCS offenses.
TD finishes: 212; made-FG finishes: 142.
Among FG finishes, the median interval from last scrimmage snap to kick snap is **0:08**.

| Population | n | Median start | Median used | 75th used | 90th used |
| --- | ---: | ---: | ---: | ---: | ---: |
| All offenses | 354 | 1:55 | 1:24 | 2:03 | 2:50 |
| FCS offenses | 132 | 1:56 | 1:25 | 2:12 | 3:03 |
| All: TD finish | 212 | 2:02 | 1:16 | 1:51 | 2:30 |
| All: FG finish | 142 | 1:46 | 1:38 | 2:13 | 3:09 |

Candidate audit (already restricted to eventual winners, tied/trailing, scoring-end labels and the selected start window):

- Included: 354
- Overtime game: 81
- Lead did not hold or score did not create lead: 15
- No verified offensive TD or made FG: 1

## Interpretation for timeout planning

The left panel answers how much clock observed winning possessions consumed to reach their scoring snap.
The right answers how much clock those same possessions had at the start. The difference can include time left after the score.
Neither answers how likely a team is to score with a given clock budget. Successful drives are selected retrospectively,
and the start cutoff truncates possible durations. Moving that cutoff changes the question and the percentile.

For the next decision analysis, include failed possessions and condition on starting clock, field position,
deficit (TD needed versus FG sufficient), timeouts, and season. Separate winning leads from OT-forcing ties,
and check stability across seasons and start windows before recommending a timeout trigger.
The detailed CSV retains starting field position, timeouts, hurry-up share, scores, and both timing definitions for that work.
