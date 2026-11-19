# Ivy League winning-drive percentiles

The two plots use only offensive possessions by Brown, Columbia, Cornell, Dartmouth,
Harvard, Penn, Princeton, or Yale, against any opponent. This matches the prior FCS-offense definition;
both teams do not have to be Ivy members. The source is the audited uncapped winning-drive CSV.

The offense must start tied or trailing, produce the final winning lead with a Q4 TD or made FG,
and hold that lead through regulation. No overtime games or return TDs. The uncapped series includes
Q3 starts; the capped series requires the first snap at or below 4:00 remaining in regulation.
Time runs from first scrimmage snap to scoring snap, including FG setup and excluding the final play's duration.
Percentiles use observed ranks, computed separately within each cohort.

Source: local PFF feed, 2023-2026 through week 4. No data or cohort definitions changed from the previous analysis except filtering the offense to Ivy teams.

## Summary

| Cohort | Drives | Median | 75th | 90th | 95th | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Uncapped | 30 | 2:07 | 3:32 | 4:46 | 5:44 | 10:00 |
| Start in final 4:00 | 14 | 0:54 | 3:07 | 3:24 | 3:44 | 3:44 |

## Every 5th percentile

| Percentile | Uncapped | Start in final 4:00 |
| --- | ---: | ---: |
| 5% | 0:00 | 0:00 |
| 10% | 0:17 | 0:00 |
| 15% | 0:34 | 0:17 |
| 20% | 0:39 | 0:17 |
| 25% | 0:59 | 0:33 |
| 30% | 0:59 | 0:34 |
| 35% | 1:13 | 0:34 |
| 40% | 1:25 | 0:39 |
| 45% | 1:58 | 0:54 |
| 50% | 2:07 | 0:54 |
| 55% | 2:29 | 1:25 |
| 60% | 2:52 | 1:58 |
| 65% | 3:14 | 2:52 |
| 70% | 3:24 | 2:52 |
| 75% | 3:32 | 3:07 |
| 80% | 3:39 | 3:14 |
| 85% | 3:49 | 3:14 |
| 90% | 4:46 | 3:24 |
| 95% | 5:44 | 3:44 |
| 100% | 10:00 | 3:44 |

## Included drives by offense

| Team | Uncapped | Start in final 4:00 |
| --- | ---: | ---: |
| Brown | 5 | 3 |
| Columbia | 1 | 0 |
| Cornell | 2 | 1 |
| Dartmouth | 6 | 3 |
| Harvard | 4 | 4 |
| Penn | 2 | 1 |
| Princeton | 3 | 0 |
| Yale | 7 | 2 |

## Interpretation

There are only 30 uncapped drives and 14 final-four-minute drives.
Repeated cutoffs are expected: a 5% step may correspond to fewer than one whole observation.
The fine percentile spacing does not imply fine statistical precision. These are observed winning-drive durations,
not scoring probabilities or validated timeout thresholds; the 100th percentile is the sample maximum.

## Reproduction

Run `MPLCONFIGDIR=/private/tmp/evertrue-mpl python3 tos/plot_ivy_winning_drives.py`.
The plot PNGs, percentile CSVs and included-drive CSVs are in `output/plots` under the
`winning_drive_distribution_ivy_uncapped` and `winning_drive_distribution_ivy_last_4m` prefixes.
The PDFs are in `output/pdf`. The combined table is `winning_drive_distribution_ivy_5pct_comparison.csv`.
