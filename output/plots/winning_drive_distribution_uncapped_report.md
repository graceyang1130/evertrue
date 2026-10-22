# Q4 winning drives: distribution without a drive-start cutoff

## Selection and timing

No drive-start cutoff. The end-of-game definition is a **winning TD or made field goal in Q4**.
The offense must be **tied or trailing at the first scrimmage snap**, create a positive lead after the scoring play and try,
and keep that lead through the end of regulation. There is one decisive drive per game.
Drives that begin before Q4 are included; earlier-quarter scores that stood as the winning lead are outside this Q4 analysis.
No hurry-up requirement, minimum snap count, starting field-position limit, or deficit limit is applied.
Overtime games, OT-forcing ties, and defensive/special-teams return scores are excluded.

Possessions use game + offense + drive number. No-play rows cannot set the first or last scrimmage snap.
TDs are verified against the offensive scoring-team tag. Made FGs are attached before the next possession/kickoff.
The lead is checked after the try, at subsequent score states, and against the game's final winner.

Elapsed time is **first scrimmage snap to the TD snap or made-FG snap**, including FG setup.
For drives crossing a quarter boundary, remaining regulation time is `(4 - quarter) * 900 + quarter clock`;
subtracting the scoring-snap clock gives the full game-clock interval. Quarter breaks consume no game clock.
The final play's live-ball duration and delays before the first scrimmage snap are unavailable and excluded.
Percentiles use observed ranks (inverse empirical CDF), not interpolation.

Source: local PFF feed, 2023-2026 through week 4. FCS uses the saved season-specific offense code list, regardless of opponent;
FCS is a subset of all offenses. The broader feed is not independently restricted to verified FBS/FCS members.

## Results

**1,053 winning drives**, including **424 by FCS offenses**.
Added beyond the prior final-4:00 cohort: **699 drives**.
Drives beginning before Q4: **130**.
Drives longer than 4:00 to reach the scoring snap: **269**.

| Population | Start / finish | Drives | Median used | 75th | 90th | 95th | Longest |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All offenses | All finishes | 1053 | 2:31 | 4:03 | 5:34 | 6:25 | 10:00 |
| All offenses | TD | 790 | 2:30 | 4:02 | 5:24 | 6:17 | 10:00 |
| All offenses | FG | 263 | 2:35 | 4:10 | 5:55 | 6:43 | 8:39 |
| All offenses | Tied at start | 388 | 2:42 | 4:26 | 6:17 | 6:56 | 8:39 |
| All offenses | Trailing at start | 665 | 2:27 | 3:53 | 5:13 | 5:54 | 10:00 |
| FCS offenses | All finishes | 424 | 2:47 | 4:06 | 5:34 | 6:25 | 10:00 |
| FCS offenses | TD | 329 | 2:50 | 4:09 | 5:36 | 6:31 | 10:00 |
| FCS offenses | FG | 95 | 2:31 | 3:44 | 5:15 | 6:02 | 8:39 |
| FCS offenses | Tied at start | 160 | 2:50 | 4:13 | 5:46 | 6:51 | 8:39 |
| FCS offenses | Trailing at start | 264 | 2:46 | 3:56 | 5:21 | 6:07 | 10:00 |

## Clock used at every 5th percentile

Each cutoff is the shortest observed duration at which at least that percentage of winning drives is included. The 100th percentile is the sample maximum, not a guarantee for future drives.

| Percentile | All offenses | FCS offenses |
| --- | ---: | ---: |
| 5% | 0:19 | 0:18 |
| 10% | 0:39 | 0:46 |
| 15% | 0:54 | 1:00 |
| 20% | 1:06 | 1:19 |
| 25% | 1:22 | 1:32 |
| 30% | 1:38 | 1:48 |
| 35% | 1:51 | 2:00 |
| 40% | 2:03 | 2:11 |
| 45% | 2:17 | 2:29 |
| 50% | 2:31 | 2:47 |
| 55% | 2:50 | 3:02 |
| 60% | 3:07 | 3:17 |
| 65% | 3:25 | 3:33 |
| 70% | 3:46 | 3:49 |
| 75% | 4:03 | 4:06 |
| 80% | 4:25 | 4:26 |
| 85% | 4:55 | 5:04 |
| 90% | 5:34 | 5:34 |
| 95% | 6:25 | 6:25 |
| 100% | 10:00 | 10:00 |

## Effect of removing the four-minute start cutoff

| Population | Cohort | Drives | Median used | 75th | 90th |
| --- | --- | ---: | ---: | ---: | ---: |
| All offenses | No start cutoff | 1053 | 2:31 | 4:03 | 5:34 |
| All offenses | Prior final 4:00 | 354 | 1:24 | 2:03 | 2:50 |
| FCS offenses | No start cutoff | 424 | 2:47 | 4:06 | 5:34 |
| FCS offenses | Prior final 4:00 | 132 | 1:25 | 2:12 | 3:03 |

The earlier restriction preferentially selected drives that had little clock available. Removing it admits longer possessions and a broader range of offensive tempo. The expanded percentiles describe this broader winning-drive population; they are not required time to score or the probability of success given a clock budget.

## Cohort audit

Candidates already require a Q4 scoring-end label, a tied/trailing start, and the eventual winning offense.

- Included: 1053
- Lead did not hold or score did not create lead: 517
- Overtime game: 237
- No verified offensive TD or made FG: 7

Season coverage among included drives:

- 2023: 300 total, 117 FCS
- 2024: 332 total, 130 FCS
- 2025: 328 total, 135 FCS
- 2026: 93 total, 42 FCS

## Reproduction and files

Run `MPLCONFIGDIR=/private/tmp/evertrue-mpl python3 tos/plot_winning_drives.py`.
`--window-minutes 4` optionally reproduces a capped comparison under a separate output prefix.
The earlier four-minute plots and report are preserved.

- `winning_drive_distribution_uncapped.png` / PDF: cumulative duration and starting-clock distributions.
- `winning_drive_distribution_uncapped_finishes.png` / PDF: duration histograms and separate TD/FG curves, for all offenses and FCS.
- `winning_drive_distribution_uncapped_5pct.png` / PDF: duration cutoffs plotted and tabulated at every 5th percentile.
- `winning_drive_distribution_uncapped_5pct.csv`: the 5%-increment table, in seconds and m:ss.
- `winning_drive_distribution_uncapped_drives.csv`: each included drive, scores, quarters, clock values, field position, timeouts, and timing definitions.
- `winning_drive_distribution_uncapped_candidate_audit.csv`: every candidate and inclusion/exclusion status.
- `winning_drive_distribution_uncapped_summary.csv`, `winning_drive_distribution_uncapped_percentiles.csv`, `winning_drive_distribution_uncapped_comparison.csv`: numerical results.

The earlier methodology review documents the possession-key defect in the legacy analyses; this run uses the corrected key.
