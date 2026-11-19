# Ivy comparison preview

Recommendation: keep the existing black Ivy call-share tick and add a small
white diamond with a dark outline for Ivy conversion at Cornell's call share.
Only the Ivy overlay and legend are extended in these six previews.

The tick compares play selection: compare it with the top of Cornell's pass
segment (below any orange scramble segment), or the top of Cornell's run bar.

The diamond compares conversion: compare its height with the boundary between
Cornell's solid and faded fill for that play type. If the solid portion ends
above the diamond, Cornell's conversion rate is above the Ivy rate. On defense,
that means a higher conversion rate allowed. If a bar is entirely solid, its
top is the conversion boundary; if entirely faded, the boundary is zero.

For each down, distance, and pass/run play type:

    diamond height = Cornell call share (%) × Ivy conversion rate (0–1)

This places the benchmark on the same call-share axis as Cornell's solid fill.
The diamond's y-coordinate is not a raw conversion percentage. Comparing solid
fill and diamond gives a conversion comparison within that play type, holding
Cornell's call mix fixed. Omit the diamond when Cornell has no calls of that
type or when the Ivy conversion sample is absent. As in the current charts,
there is no scramble benchmark, and 15+ pools all distances at least 15 yards.

Example: Cornell offense, third and 3, 2024–2026. There are 13 passes among 28
charted plays, and 9 converted. Cornell's pass conversion rate is 69.2%; the
Ivy rate is 51.9% (111/214). Cornell's solid pass fill ends at 32.1% of all calls;
the Ivy diamond is at 24.1%. The existing call-share tick still compares play
selection independently.

Alternatives considered:

- A narrow Ivy bar with its own solid/faded split: shows the full Ivy profile,
  but adds visual density and requires comparing proportions across bars of
  different heights to judge conversion.
- A raw Ivy conversion tick on the current y-axis: would mix conversion rate
  with share of all calls and invite an incorrect comparison with solid fill.

These are descriptive comparisons against the same pooled Ivy exports used by
the current script. No significance claim or change to the reference population
is implied. Existing count labels remain important for sparse fourth downs.

Reproduce from the repository root:

    MPLCONFIGDIR=/private/tmp/evertrue-mpl python3 tmp/ivy_comparison_preview/preview.py

To integrate the design, use both outputs from `_ivy_benchmarks` in
`play_mix_and_conversion`, keep `_draw_ivy_ticks` for call share, and plot the
diamonds using the already-computed `pct[play_type] * ivy_conversions[play_type]`.
The bucketed conversion charts already compare raw conversion rates on their
own axis and do not need this scaling.
