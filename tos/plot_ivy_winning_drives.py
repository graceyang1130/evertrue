"""Plot every 5th percentile for Ivy offenses, uncapped and final-four-minute starts.

Run after plot_winning_drives.py: python3 tos/plot_ivy_winning_drives.py
"""

import pandas as pd

from plot_winning_drives import PLOTS, fmt, percentile, plot_percentile_steps

# Same PFF codes as IVY in tos/clock_game.py and tos/report_data.py.
IVY_TEAMS = {
    "RIBR": "Brown", "MAHA": "Harvard", "CTYA": "Yale", "NJPR": "Princeton",
    "PAUN": "Penn", "NHDA": "Dartmouth", "NYCN": "Cornell", "NYCL": "Columbia",
}


def main():
    winners = pd.read_csv(PLOTS / "winning_drive_distribution_uncapped_drives.csv")
    ivy = winners[winners.offense.isin(IVY_TEAMS)].copy()
    if ivy.empty:
        raise ValueError("No Ivy winning drives in saved analysis")
    cohorts = [("Uncapped", ivy, None, "winning_drive_distribution_ivy_uncapped"),
               ("Start in final 4:00", ivy[ivy.start_regulation_seconds.le(240)], 240,
                "winning_drive_distribution_ivy_last_4m")]
    comparison = pd.DataFrame({"percentile": range(5, 101, 5)})
    summary = []
    for name, frame, window, stem in cohorts:
        ranks = plot_percentile_steps(frame, stem, window, population="Ivy League offenses")
        frame.to_csv(PLOTS / f"{stem}_drives.csv", index=False)
        key = "uncapped" if window is None else "last_4m"
        comparison[f"{key}_seconds"] = ranks.population_seconds
        comparison[f"{key}_m_ss"] = ranks.population_m_ss
        summary.append({"cohort": name, "n": len(frame),
                        **{f"p{q}_seconds": percentile(frame.to_score_snap_seconds, q / 100)
                           for q in [50, 75, 90, 95, 100]}})
    comparison.to_csv(PLOTS / "winning_drive_distribution_ivy_5pct_comparison.csv", index=False)
    text = """# Ivy League winning-drive percentiles

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
"""
    for r in summary:
        text += f"| {r['cohort']} | {r['n']} | " + " | ".join(fmt(r[f'p{q}_seconds']) for q in [50, 75, 90, 95, 100]) + " |\n"
    text += "\n## Every 5th percentile\n\n| Percentile | Uncapped | Start in final 4:00 |\n| --- | ---: | ---: |\n"
    for r in comparison.itertuples():
        text += f"| {r.percentile}% | {r.uncapped_m_ss} | {r.last_4m_m_ss} |\n"
    text += "\n## Included drives by offense\n\n| Team | Uncapped | Start in final 4:00 |\n| --- | ---: | ---: |\n"
    for code, name in sorted(IVY_TEAMS.items(), key=lambda item: item[1]):
        own = ivy[ivy.offense.eq(code)]
        text += f"| {name} | {len(own)} | {int(own.start_regulation_seconds.le(240).sum())} |\n"
    text += f"""
## Interpretation

There are only {len(ivy)} uncapped drives and {len(cohorts[1][1])} final-four-minute drives.
Repeated cutoffs are expected: a 5% step may correspond to fewer than one whole observation.
The fine percentile spacing does not imply fine statistical precision. These are observed winning-drive durations,
not scoring probabilities or validated timeout thresholds; the 100th percentile is the sample maximum.

## Reproduction

Run `MPLCONFIGDIR=/private/tmp/evertrue-mpl python3 tos/plot_ivy_winning_drives.py`.
The plot PNGs, percentile CSVs and included-drive CSVs are in `output/plots` under the
`winning_drive_distribution_ivy_uncapped` and `winning_drive_distribution_ivy_last_4m` prefixes.
The PDFs are in `output/pdf`. The combined table is `winning_drive_distribution_ivy_5pct_comparison.csv`.
"""
    (PLOTS / "winning_drive_distribution_ivy_report.md").write_text(text)
    print(pd.DataFrame(summary).to_string(index=False))
    print(comparison[["percentile", "uncapped_m_ss", "last_4m_m_ss"]].to_string(index=False))


if __name__ == "__main__":
    main()
