# Where cvc5's liastar time goes — findings from the statistics runs

Generated 2026-07-27 from sequential (`-j 1`-style, one benchmark at a time)
cvc5 runs with `--stats --stats-all --stats-internal` at the standard 100s
timeout. Reproduce with:

    python3 cvc5_stats.py timeout        # -> output/cvc5_stats_timeout.csv (26 rows)
    python3 cvc5_stats.py sat            # -> output/cvc5_stats_sat.csv    (284 rows)
    python3 analyze_cvc5_stats.py output/cvc5_stats_sat.csv output/cvc5_stats_timeout.csv

Statistic semantics (timer nesting, counter meanings) are documented and
code-cited in `liastar_stats_reference.md`. Every number below was
recomputed independently from the csvs during an adversarial verification
pass. All 26 timeouts reproduced as timeouts and all 284 sats as sat.

2026-07-27 addendum: the collection was redone through the cvc5 python
API (bindings loaded once, fork per benchmark -- see cvc5_stats.py and
update_comparison.py), eliminating the ~40ms binary+dylib load per
invocation. Results and every diagnosis below reproduced exactly: same
284/199/26 comparison results (zero flips), same 151/128/4/1 sat-path
split, same 23/3 timeout split; median sat wall time dropped 41ms ->
15ms while median internal solve time stayed 14ms, confirming the load
overhead affected recorded wall durations only, not outcomes.

## The timeout benchmarks: two failure modes

**Mode 1 — died inside the first DNF conversion (23 of 26).** These spend
their entire 100s budget inside `distributeTime` (>= 99.99% of
`checkFullEffortTime`, which is ~100% of cvc5's total time), with
`dnfCalls = 0`: the ite -> DNF distribution never completed even once.
The sink is not the cartesian product itself — the pure product cost
(`distributeTime - subSolverTime`) is 1.08s summed over all 26 benchmarks.
It is the UNSAT-pruning sub-solver called on partial conjunctions during
distribution: ~238k-266k calls per benchmark (one outlier at 99k), 5.7M
calls in total, at a pooled 0.41 ms/call — 99.95% of all distribution
time. The pooled prune ratio is 55% (worst benchmark 34%), so on hard
instances nearly half the checks buy nothing. All 23 have a count_ite.py
disjunct lower bound >= 1024.

**Mode 2 — died after the DNF, in ordinary LIA reasoning (3 of 26:
card/cvc5_mapa/fol_0000048/49/97).** These complete the DNF (1,417
disjuncts, ~18s), compute all 1,417 cones + Hilbert bases
(hilbertBasisTotal 8,179), emit the `ARITH_LIA_STAR_EXISTS` reduction
lemma, and then spend ~77% of the budget outside the liastar extension
searching for a LIA model of the giant skolemized lemma. The specific
downstream sink is instance-dependent: simplex pivoting
(`theory::arith::dual::pivotTime` 65-73s) for fol_48/97, diophantine
conflict processing (`theory::arith::dio::conflictTimer` 56s +
`dio::cutTimer` 8s) for fol_49 — so "downstream LIA search", not
"simplex", is the accurate summary.

## The sat benchmarks: which code path solves them

| path | n | share of sat-set cvc5 time | what happens |
|---|---:|---:|---|
| model-value short-circuit | 151 (53%) | 0.45% | The candidate arithmetic model already satisfies the star literal; it is discharged by evaluation (`modelValueSolved`), no reduction lemma ever emitted. Every one takes exactly 2 full-effort runs; median 7ms. |
| full reduction pipeline | 132 (46%) | 99.5% | DNF completes (48-1,417 surviving disjuncts), cones + Hilbert bases computed, EXISTS lemma emitted, LIA search finds the model. |
| no star literal asserted | 1 | 0.005% | sql/linear/calcite-query222-call-0: both star-contains literals sit under disjunctions whose zero-vector branch the SAT engine took — plain CDCL(T) LIA solved it in 12ms. |

Within the reduction pipeline the honest cost split is ~44% pruning
sub-solver / ~43% post-reduction LIA search / ~9% cones+Hilbert — and the
43% LIA figure is dominated by just two benchmarks
(card/cvc5_mapa/fol_0000071/72, 62s each); excluding the 4
LIA-search-dominant rows it is 58% sub-solver / 24% LIA. Even on solved
instances the pruning sub-solver is the single largest cost (76.5% of all
liastar-extension time; per-row median prune ratio only 20%).
Normaliz/Hilbert-basis computation is never the bottleneck: 13.1% of
extension time, 7.4% of sat-set total.

## The tipping point, quantified

The seven card/cvc5_mapa benchmarks with count_ite estimate 256
(fol_0000048/49/71/72/96/97/118) are statistically identical in every
liastar counter — same 1,417 disjuncts, same 20,061 sub-solver calls, same
8,179 Hilbert basis vectors, same ~23s of extension time. Four are sat
(33-62s), three time out: at the 100s budget, sat-vs-timeout inside this
class is decided entirely by downstream LIA search behavior, which no
static disjunct count predicts.

The count_ite.py estimate is nevertheless a strong within-family
predictor (Spearman ~0.9 vs wall time; 1.0 vs actual surviving disjuncts
within each family): in card/cvc5_bapa everything <= 4096 is sat and
everything >= 16384 times out; in card/cvc5_mapa everything >= 1024 times
out and 256 is the coin-flip boundary. The thresholds are not portable
across encodings: pruning shrinks bapa DNFs to 0.09-0.18x the estimate,
while or-splits (which the estimate deliberately ignores) inflate mapa
DNFs to up to 5.5x.

## Takeaways

1. The dominant bottleneck is the **per-call price of eager sub-solver
   pruning during DNF distribution** (0.4-0.9 ms/call x hundreds of
   thousands of calls), not the exponential product itself.
2. Fixing distribution alone shifts the wall: the finished-DNF timeouts
   show the next bottleneck is **LIA search on the reduced lemma** (with
   instance-dependent simplex/diophantine sinks).
3. The **model-value short-circuit is what makes cvc5 fast** when it is
   fast: it solves 53% of the sat set for 0.45% of the time, engaging
   none of the expensive machinery.
