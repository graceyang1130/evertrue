# Review notes: end-of-game clock report

Reviewed 6 October 2026. The deliverable is `end_of_game_clock_report.pdf`; editable prose is `end_of_game_clock_report.md`. The PDF has four report pages and one evidence page. Analysis scripts and source data were not changed.

## Reproduction

Run `python3 tos/clock_game.py` to reproduce the clock summaries, successful-drive timing, punt assumptions, and defensive audit. This was run successfully on the available national play-by-play. Its console heading says “medians,” but `_split` returns arithmetic means for total/live/dead; only clock-left is a median. The report uses the actual calculations.

Run `python3 end_of_game/build_focused_report.py` to regenerate the report and editable text. Requires reportlab and pymupdf. The builder renders page images into `tmp/pdfs/`. Visual review was performed on all five final pages.

Run `python3 end_of_game/build_film_index.py` first after an audit change. It joins each audit row to a unique PFF snap and the next raw event, using the verified playlist manifest. The current output has 13 intervals, eight playlists and 16 clickable film references in the PDF. Every starting and next-event ID is included in the saved selections. All eight dedicated playlist pages were opened and their clocks/down-distance checked.

The original queue description incorrectly called its clock the previous-snap clock. `defense_reality()` stores `r.clock - LIVE_BALL`, so it is snap minus an assumed seven seconds. The revised queue uses actual snap clocks. The audit calculations were preserved, and neither its play-end clock nor its dead-ball wait is described as film-measured.

Film review adds two concrete caveats: the 2024 Princeton third-down interval ends at a fourth-down defensive-holding no-play (5933649), followed by a new first down; the 2026 Harvard sequence reaches a fourth-down pass at 2:00 in Brown territory. The playlists include those context plays. The 2023 Princeton flags occurred in a game Brown won in overtime, demonstrating why these flags cannot be treated as causal evidence of losses. The site review's scope and the private-playlist access limitations are recorded in ultimate_site_review.md.

The saved JSON was checked against the rerun: national four-minute runs n=6,833, mean live/dead 7.1/33.5 seconds; Brown two-minute passes n=61, mean dead 16.0; Brown audit 26 flagged spots, 13 calls, 13 noncalls; national 3,337 spots at 55.1%; Ivy 121 at 63.6%. The flagged noncalls total 484 estimated seconds, average 37.23; 11 of 13 held three timeouts. Brown games.csv counts are 10/10/10/2 by season 2023/2024/2025/2026.

## Material corrections to the prior presentation

- National export completeness was not independently established. State dataset counts rather than “every FBS and FCS game.” Comparisons use team-game exposure: the national 11,156 figure in the prior audit is twice 5,578 games, not another distinct-game sample.
- Timeout counts reconstruct charged uses; purposes are proxies. The last-two-minutes label cannot establish why a timeout was called.
- The audit is a heuristic that assumes stops, a typical punt, and successful-drive timing. It omits an explicit pending two-minute timeout state. Therefore its exact count of recommended calls cannot be treated as a validated error count.
- The 44-second Brown figure has a selected-game denominator. It is not clock lost per game across the entire 32-game sample.
- Repeated flagged intervals within games are not independent observations. The 32%-68% Wilson interval is a simple illustrative interval, not a cluster-adjusted comparison.
- The 151-second hurry-up benchmark selects successful drives (at least three snaps, at least 80% two-minute tags, same quarter), and uses first-to-last snap. It does not estimate scoring probability or a required drive duration.
- The 0.33-point option value pools offense and defense at the first sampled state inside four minutes and clips negative clock values. It is not the complete value of holding a timeout, nor a same-state comparison against delay of game. Five-yard examples are tied, third-quarter snapshots.
- Full-season team strength uses outcomes unavailable before a live decision. Holding out 2025 fitting does not turn those retrospective inputs into prospective validation. Snap-level calibration also repeats game outcomes.
- The Brown-Yale/PFF comparison was omitted from the lean report. The prior source compares a 2026 PFF rating scenario with a 2025-strength custom scenario and a historical 5/16 Ivy tally whose extraction is not encoded in scenario(). It is a diagnostic disagreement, not independent proof that either model is right. The current JSON shows 29.7% matchup-adjusted and 33.3% even-team with three timeouts, superseding slightly different transcript iterations.
- Three of six close losses with timeouts remaining are film targets, not evidence that unused timeouts caused losses.
- “Always run,” “use them all,” and “save them whenever down two scores” are stronger than the analysis supports. Conversion, offensive completion, and possession value matter.

## Kneel chart review

Reviewed the complete one-page staff chart and all 11 pages of Brown Timeout Decisions.pdf. The two-point chart is outside the requested clock/timeout scope.

The chart's 4-second plays and 38-second clock use, clock_kill.py's 2+39 convention, and the interactive report's measured 4.2+31.5 average are not interchangeable. The running-clock 1st-down/one-timeout illustration gives three kneels and two waits, 88 seconds. Starting stopped at the first snap gives three kneels and one wait, 50 seconds. These examples explicitly exclude adding a fourth-down play without verifying expiration and possession. Neither expectation is a guarantee; actual play duration, clock remaining, restart signal, and field position control execution.

The highlighted staff windows near 2:00 are tied to the automatic stoppage. clock_kill.py has no explicit pending-two-minute-timeout or initial-running-clock state. Exact thresholds should be verified by sequence before creating a replacement sideline card.

## Historical endgame model status

Reviewed DESIGN.md, the refit plan, current opponent model, and the relevant development chronology in the two supplied transcripts. Earlier design claims were superseded by later amendments; the report does not treat them as current results.

The later record reports an approved swap from ep_start to yards_to_goal and sensitivity checks across deficit caps 10-24. That swap is not implemented in the current source. The historical Ivy CSV is missing, so the 720-drive validation and later sensitivity investigations cannot be reproduced from that exact dataset here.

Ran `python3 end_of_game/opp_offense.py end_of_game/brown_19t26.csv --gates`. It exits 1, with 153 decision-population drives and all six gates failing. This is the intended thin-sample safeguard; using Brown-only data is not a substitute for the missing Ivy training population and does not disprove the earlier Ivy fit.

The planned play-outcome, punt, and full endgame simulation modules are absent. No completed optimal run/pass/punt policy is asserted.

## Rules sources

Checked official NCAA material on 2023 first-down timing changes, 2024 adoption of the two-minute timeout, and the current playing-rules resource page. These changes mean that 2023-2026 is not literally one timing regime. Links are included in the final PDF. The present report does not purport to adjudicate every boundary case under the current rulebook.
