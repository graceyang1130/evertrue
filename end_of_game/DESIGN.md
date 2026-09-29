# End-of-game decision model — design

**Status:** proposed, awaiting review
**Date:** 2026-09-29
**Builds on:** `runoff_model.py`, `clock_kill.py` (both complete and validated)

## The question this answers

`clock_kill.py` answers *"can I kill the clock?"* — deterministic arithmetic over
snap-to-snap runoff. It tells you that you need two first downs. It has no opinion
on whether you'll get them.

This model answers *"which call gives me the best chance to win?"*

That reframe exists because clock-killing can defeat itself. Playing to burn clock
means runs, staying in bounds, staying conservative — all of which lower your
conversion rate. Fail to convert and you punt early, handing the opponent **more**
time than an aggressive drive would have. Somewhere there is a line where throwing
the ball while protecting a lead is correct. Deterministic clock arithmetic cannot
find that line. A win-probability model can.

## Approach

Monte Carlo simulation, pre-tabulated onto printed cards.

The deliverable is a paper packet for a sideline, not a live application, so
precomputing a grid of realistic states is the right shape. Monte Carlo (rather
than backward induction) because the underlying distributions are messy and thin;
simulation keeps that honesty visible instead of smoothing it away behind a
closed-form policy.

The key simplification that makes this tractable: **the opponent's possession is
not simulated play by play.** It is resolved in one step by `opp_offense.py`, which
returns the probability they score from where and when they get the ball. Without
this the state space explodes and nothing is estimable from 308 games.

## State

    (seconds_left, down, distance, yardline, score_diff, our_timeouts, their_timeouts)

Card grid:

| dimension | values |
|---|---|
| `seconds_left` | 0–600, 15s steps |
| `down` | 1–4 |
| `distance` | 1, 2, 3, 5, 7, 10, 15 |
| `yardline` | own 5 → opp 5, 5-yard steps |
| `score_diff` | +1–3, +4–7, +8–10, +11+ (the buckets that change behavior) |
| `our_timeouts`, `their_timeouts` | 0–3 |

Decisions evaluated at each state: **run / pass / kneel / punt / field goal**
(field goal only when in range).

## Modules, in build order

### 1. `opp_offense.py` — build and validate first

Highest-risk piece, thinnest data, and every punt-versus-go decision depends on
it. If it does not survive contact with the data we need to know that before
building three modules on top of it.

**Estimates:** P(opponent scores) given they take over with `t` seconds left, at
field position `y`, holding `T` timeouts, needing either a field goal or a
touchdown.

Touchdown and field goal are modelled separately, because a team down 4 will not
settle for a field goal and therefore plays differently from a team down 2. The
deficit they face is an input, not an afterthought.

**Data:** Q4 drives — 1,982 total, 1,136 starting ≤10:00, 649 ≤5:00. Outcome read
from `pff_DRIVEENDEVENT`: `TOUCHDOWN` / `FIELD GOAL` count as scores; `PUNT`,
`DOWNS`, `INTERCEPTION`, `FUMBLE`, `MISSED FG`, `END OF GAME` do not.

**Method:** logistic regression, not raw cell means — 649 drives cannot fill a
four-way grid. Form:

    logit P(score) ~ EP_at_drive_start + log(seconds_left) + timeouts + needs_TD

`pff_EXPECTED_POINTS` (100% filled) carries field-position value as a single
covariate, which is what keeps the dimensionality survivable.

**Validation — all five must pass before anything is built on this:**

1. **Calibration.** Bin predictions into deciles; predicted rate must track
   observed rate along the diagonal.
2. **Season holdout.** Fit 2019–2024, test 2025–26. Calibration and AUC must hold
   out of sample.
3. **Monotonicity.** P(score) must rise with more time, better field position, and
   more timeouts. **A sign flip on any of these is a failure, not a curiosity** —
   it means the model is fitting noise.
4. **Anchor check.** A team taking over at its own 25, 1:00 left, one timeout,
   needing a touchdown should land in the low single digits to ~10%. A model that
   says 40% is broken regardless of its fit statistics.
5. **Sample floor.** Report `n` behind every cell the card uses. Refuse to print a
   cell backed by too little data rather than printing a confident guess.

**Fail-fast criterion.** If holdout calibration is badly off or monotonicity
flips, we do not proceed as designed. We fall back to a coarse
time × field-position lookup table, label it as coarse, and the final cards carry
that limitation on their face.

### 2. `play_outcomes.py`

Yards gained, P(first down), P(turnover), P(sack) by call / down / distance /
regime. Empirical distributions sampled directly in the simulation rather than
fitted to a parametric family — the tails are the whole point in a clock model and
a normal approximation would erase them.

### 3. `punt_model.py`

Net punt distance from the 2,804 punt rows, plus field goal make probability by
distance. Reuses the existing `misc/ivy_punting` work where it applies.

### 4. `endgame_sim.py`

From a state, for each candidate call: simulate to game end N times, return win
rate. Clock advances via `runoff_model.py`. Opponent possessions resolve through
`opp_offense.py`. Output is the recommended call, its win probability, and the
runner-up — so a coach can see when a decision is close and when it is not.

## Shrinkage — the central statistical problem

Brown has **95 kill-regime run snaps.** That is not enough to estimate anything
finely, and a naive model will produce confident nonsense in precisely the rare
situations the tool exists to handle.

Every Brown-specific rate is therefore shrunk toward the Ivy baseline in
proportion to how thin its cell is:

    estimate = w · brown + (1 − w) · ivy        w = n / (n + k)

`k` chosen by cross-validation. **`w` is reported alongside every estimate**, so it
is always visible how much of a number is Brown and how much is league. This is
built in from the start, not bolted on.

Brown's own rates matter enough to be worth this trouble: Brown burns ~6 fewer
seconds per snap than the Ivy average (28s vs 34s, matched on game state), driven
by a 16.1% tempo rate against the league's 7.4%. A model fitted on league rates
would promise Brown clock it does not actually burn.

## Validating the whole system

- **Backtest.** Replay Brown's actual Q4 leading situations; compare the
  recommended call to what was called and what happened. This is not proof —
  counterfactuals are unobservable — but it catches gross errors.
- **Aggregate calibration.** Model win probability at the start of the 4th quarter,
  bucketed, against actual win rates in those buckets.

## Out of scope for v1

Trailing/comeback side (the mirror model), onside kicks, weather and wind,
opponent-specific defensive adjustment. Each is a real effect; none blocks a
useful v1.

## Known limitations that will survive into v1

- **No out-of-bounds flag** in the PFF export, and Ultimate does not carry one. A
  play ending out of bounds kills the dead-ball chunk exactly like a timeout, and
  we can only absorb that into averages, never see it directly.
- **No clock-at-end-of-play field**, so live-ball time stays reconstructed rather
  than observed. Validated (two independent estimates agree within 2s) but noisy
  per play: the residual has σ ≈ 7s.
- **Inside 2:00 a first down stops the clock** to set the chains. Handled in the
  runoff model, but it means the last set of downs before 2:00 behaves differently
  from everything before it.
- Everything here is an **expectation over real outcomes**, never a guarantee. A
  one-snap margin is not a margin.

---

# Amendment 1 — `timeouts` removed as a regression feature (2026-09-29)

Validation gate 3 (monotonicity) failed during implementation: `timeouts` had a
net effect of **−0.238** on P(score). Gates 1, 2, 4 and 5 passed comfortably
(calibration 0.031, out-of-sample AUC 0.750, all anchors under ceiling, minimum
bin n=89).

The flip is real, not noise. Marginally more timeouts does mean more scoring
(0.170 at 0 TO rising to 0.333 at 3 TO), but `corr(timeouts, seconds_left) =
0.477` — and holding time constant the relationship reverses inside every time
bucket (at <2:00: 0.103 at 0 TO down to 0.060 at 3 TO; at 2–5 min: 0.375 down to
0.241). `corr(timeouts, deficit) = −0.002`, which APPEARS to rule out score margin as
the explanation. See Amendment 1a below: that claim is wrong.

**Mechanism.** A team that has spent its fourth-quarter timeouts is a team
already playing urgently — it has been stopping the clock to get the ball back.
Timeouts-remaining measures *revealed urgency*, not clock capability.

**Why that makes the coefficient unusable.** The simulator needs the causal
quantity: if we leave the opponent two timeouts instead of none, how much more
likely are they to score? The observational coefficient answers a different
question — how often did teams that happened to hold two timeouts score — and
those teams were systematically less urgent. Wired into `endgame_sim.py` it would
conclude that leaving the opponent more timeouts *reduces* their scoring chance,
and recommend never forcing them to burn one. That is inverted sideline advice.

**Change.** `timeouts` is dropped from `FEATURE_NAMES`, which becomes
`["log_seconds", "ep_start", "needs_td"]`. The opponent's timeouts instead enter
through the clock, where we already hold a *causal* estimate: `runoff_model.py`
measured a charged timeout as worth ~12–15s of game clock, and the live/dead
decomposition explains why (a timeout erases the ~33s dead-ball chunk and cannot
touch the ~8s live-ball chunk). `endgame_sim.py` therefore converts the
opponent's remaining timeouts into additional effective possession seconds and
calls `predict` with that larger `seconds_left`. The effect enters through the
variable it actually acts on, estimated causally rather than observationally.

`load_drives` still returns a `timeouts` column — `endgame_sim.py` needs it — it
is simply no longer a regression feature.

**This supersedes the coarse-table fallback for this specific failure.** The
fallback was written for a model fitting noise. This model is not: four gates
passed with margin and one feature was mis-specified. Dropping the bad feature is
the proportionate remedy; discarding a well-calibrated model with 0.750 AUC would
not be.

**Correction to the gate's own rationale.** `DESIGN.md` stated that a sign flip
"means the model is fitting noise." That was too narrow. A sign flip can equally
mean a feature is confounded — as here. The gate was right to fire and right to
be non-negotiable; its prescribed interpretation was wrong. Gate 3 is retained
for `log_seconds` and `ep_start`, and becomes vacuous for a feature that no
longer exists.


---

# Amendment 1a — correction to Amendment 1's evidence (2026-09-29)

Amendment 1's claim that `corr(timeouts, deficit) = −0.002` rules out score margin
is **wrong. The conclusion it supports is nevertheless right.** Both halves are
recorded here, because a reasoning error of this shape propagates.

`deficit` is `(-score_diff).clip(lower=0)`, so all **894 leading offenses** in the
1,978-drive sample collapse to `deficit = 0` regardless of how far ahead they are.
A correlation against that variable cannot see score margin at all, and the
underlying relationship is non-monotone besides, so a near-zero linear correlation
establishes nothing.

Score margin **is** part of the confound. Mean signed `score_diff` by timeouts
remaining: **−7.44 at 0 TO, −1.57 at 1 TO, +1.17 at 2 TO, −0.91 at 3 TO.** A team
with no timeouts left is trailing by a touchdown. That *is* the revealed urgency,
and deficit is its measurable form rather than an independent factor ruled out.

Re-run against the signed margin the confound is still weak —
`corr(timeouts, score_diff) = 0.040` and `corr(timeouts, |score_diff|) = 0.061` —
so dropping `timeouts` remains correct for the reasons Amendment 1 gives. Only the
stated evidence was invalid, not the decision.

**A second caveat Amendment 1 overstated.** Routing the timeout effect through the
clock is coherent but not equivalent. A timeout's value is sharply non-linear in
time remaining: at 1:30 it lets an offense attack the middle of the field instead
of only the sideline, which no quantity of extra seconds reproduces; at 5:00 it is
worth little because the clock is not the binding constraint. Converting timeouts
to effective seconds forces the effect to be linear in `log_seconds`. Usable, but
`endgame_sim.py` must not treat it as settled.
