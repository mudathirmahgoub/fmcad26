<!-- Generated 2026-07-27 by source analysis of the cvc5 liastar branch;
     companion to cvc5_stats.py / analyze_cvc5_stats.py. -->

# `theory::arith::liastar::*` statistics — verified reference

Codebase: `/Users/mahgoubyahia/fmcad26/cvc5`, branch `liastar`. All stats are declared in `src/theory/arith/liastar/liastar_stats.h:40-177` (**36 members**: 14 timers at :47-97, 22 counters at :101-176) and registered once in `src/theory/arith/liastar/liastar_stats.cpp:25-87` under the prefix `theory::arith::liastar::`. Update sites are exclusively in `src/theory/arith/liastar/liastar_extension.cpp` (**ext**, member `d_stats`, constructed ext:70) and `src/theory/arith/liastar/liastar_utils.cpp` (**utils**, via a `LiaStarStatistics*` pointer passed as `&d_stats` at ext:569). All liastar work runs inside `TheoryArith::postCheck` at full effort only (`theory_arith.cpp:251`, guard :278, call :292) — never concurrently with SAT search.

## Verification outcome (corrections to the input reports)

All three reports were verified line-by-line and are substantially correct. Two claims needed refinement:

1. **Subsolver backend selection is NOT decided by the option alone.** The branch at utils:574 is `if (fvs.size() > 0 && e->getOptions().arith.arithLiaStarNormalizAsSubSolver)`. A conjunction with **no free variables goes to `cvc5CheckSat` even when `--arith-liastar-subsolver-normaliz-as-subsolver` is on** (default off, `src/options/arith_options.toml:636-641`). So `cvc5SubSolverTime` can be nonzero in normaliz-subsolver runs.
2. **"Sub-solver runs per candidate disjunct" is imprecise.** In `distribute` (utils:150-283) the subsolver runs (a) once per *extension of a partial conjunction by an OR-disjunct* (utils:210) — extensions by non-OR conjuncts are appended **unchecked** (utils:225-231) — and (b) once more per *surviving complete disjunct* in the final pass (utils:236). A surviving final disjunct is therefore checked ≥ 1 time and typically several times; `subSolverCalls` counts **checks**, not distinct disjuncts.

Everything else — the containment tree, all 36 update-site line numbers, the header's overlap note (liastar_stats.h:36-38), the exclusivity of update sites to the two liastar files, and the `theory_arith.cpp` entry-point lines — was confirmed as reported.

## Verified timer containment tree

```
checkFullEffortTime                        ext:123 start / ext:280 stop  (checkFullEffort)
├── modelValueTime                         ext:172 / ext:198 or ext:201            [leaf]
├── (convertQFLIAToMatrices, ext:212 → body ext:540-582 — no timer of its own)
│   ├── toDnfTime                          utils:72 / utils:130  (toDNF, called ext:569)
│   │   ├── removeItesTime                 utils:74-76                             [leaf]
│   │   ├── removeNotTime                  utils:79-81                             [leaf]
│   │   └── distributeTime                 utils:111 / utils:115 (distribute + recursiveFlatten)
│   │       └── subSolverTime              utils:558 / utils:592 (areAssertionsUnsat —
│   │           │                          only callers: utils:210, utils:236, both in distribute)
│   │           ├── cvc5SubSolverTime      utils:602 / utils:626 (cvc5CheckSat, utils:582)
│   │           └── normalizSubSolverTime  utils:634 / utils:706 (normalizCheckSat, utils:578)
│   │               │                      — per-call mutually exclusive with cvc5SubSolverTime;
│   │               │                        branch condition fvs>0 && option, utils:574
│   │               ├── getMatricesTime [A]     utils:654-657
│   │               ├── normalizInputTime [A]   utils:671-678
│   │               └── normalizComputeTime [A] utils:682-690   (A-instances sequential/disjoint)
│   └── getMatricesTime [B]                ext:574-577 — AFTER toDNF returns; sibling of toDnfTime,
│                                          NOT contained in it
├── getConesTime                           ext:288 / ext:438  (getCones, called ext:214)
│   ├── normalizInputTime [B]              ext:330-337
│   └── normalizComputeTime [B]            ext:339-346         (sequential/disjoint per loop iter)
└── getLiaTime                             ext:445 / ext:524  (getLia, called ext:215)     [leaf]
```

Sibling sets are strictly sequential (never overlap): {modelValueTime, toDnfTime, getMatricesTime_B, getConesTime, getLiaTime}; {removeItesTime, removeNotTime, distributeTime}; {cvc5SubSolverTime, normalizSubSolverTime}.

**Multi-parent timers** (totals cannot be attributed to one parent): `getMatricesTime` = ext:574 (top level, main path) + utils:654 (inside normalizSubSolverTime); `normalizInputTime` and `normalizComputeTime` = ext:330/ext:339 (inside getConesTime) + utils:671/utils:682 (inside normalizSubSolverTime). With default options (normaliz-as-subsolver **off**), the subsolver instances are dead and each of these three has a single parent (checkFullEffortTime / getConesTime / getConesTime respectively).

## The 36 statistics, one line each

**Timers (14)** — declared liastar_stats.h:47-97:

| Stat | Meaning | Updated |
|---|---|---|
| checkFullEffortTime | Total wall time of `checkFullEffort`; root containing all other liastar timers | ext:123/280 |
| modelValueTime | Time substituting the candidate arith model into a star literal's predicate and rewriting | ext:172, 198, 201 |
| toDnfTime | Whole DNF pipeline (ITE removal + NNF + distribution incl. subsolver pruning) | utils:72/130 |
| removeItesTime | ITE elimination (`removeItes`) | utils:74-76 |
| removeNotTime | NNF conversion / negation push-down (`removeNot`) | utils:79-81 |
| distributeTime | Cartesian-product distribution to DNF + `recursiveFlatten`, incl. all subsolver pruning time | utils:111/115 |
| getMatricesTime | Converting DNF disjuncts to Normaliz symbolic-constraint strings (`getMatrices`) | ext:574-577 + utils:654-657 |
| normalizInputTime | Parsing constraint text via `libnormaliz::readNormalizInput` | ext:330-337 + utils:671-678 |
| normalizComputeTime | Normaliz cone construction + `compute(HilbertBasis)` + `compute(ModuleGenerators)` | ext:339-346 + utils:682-690 |
| getConesTime | All of `getCones`: cone computation + building mu/lambda star constraints | ext:288/438 |
| getLiaTime | All of `getLia`: building ∃-form LIA formulas (consumed only by `liastar-ext-smt` trace, ext:218-263, but computed unconditionally) | ext:445/524 |
| subSolverTime | All of `areAssertionsUnsat` (both backends), i.e. total disjunct-pruning check time | utils:558/592 |
| cvc5SubSolverTime | `cvc5CheckSat`: fresh-subsolver `checkWithSubsolver` on the (∃-wrapped, ≥0-constrained) conjunction | utils:602/626 |
| normalizSubSolverTime | `normalizCheckSat`: one cone per conjunction; UNSAT iff empty (`getAffineDim()==-1`, utils:696) | utils:634/706 |

**Counters (22)** — declared liastar_stats.h:101-176:

| Stat | Meaning | Updated |
|---|---|---|
| checkRuns | Invocations of `checkFullEffort` | ext:130 |
| starContainsLiterals | STAR_CONTAINS literals (both polarities) collected from the fact queue, accumulated **once per check run** — the same literal is recounted every run | ext:135 |
| modelValueChecks | Model-evaluation attempts on star literals (one per literal per run reaching the check; runs even for already-reduced literals, since the processed-guard at ext:204 comes after) | ext:173 |
| modelValueSolved | Literals discharged this round because the substituted+rewritten predicate == `true` — no reduction lemma needed | ext:191 |
| starTermsReduced | `literal = star` reduction lemmas emitted (`ARITH_LIA_STAR_EXISTS`); at most once per distinct literal (guard ext:204-209, push ext:276) | ext:277 |
| itesRemoved | ITE eliminations (boolean utils:334, integer utils:498); duplicated ITEs may be counted more than once (liastar_stats.h:117-121) | utils:334, 498 |
| dnfCalls | **Completed** `convertQFLIAToMatrices` conversions — incremented only after both `toDNF` and `getMatrices` return | ext:578 |
| dnfDisjuncts | Total disjuncts (matrix/Node pairs) over all conversions; a constant predicate counts as 1 | ext:579 |
| dnfDisjunctsMax | Max disjuncts in a single conversion | ext:580 |
| disjunctsPrunedUnsat | Pruning events during distribution: partial conjunctions (utils:214) + complete disjuncts (utils:240) discarded as UNSAT. One partial prune kills a whole subtree of candidates but counts as 1 | utils:214, 240 |
| subSolverCalls | Dispatched `areAssertionsUnsat` checks (after the `--arith-liastar-subsolver` gate, utils:551-553; default on, arith_options.toml:628-633). Counts checks, not disjuncts — see correction 2 | utils:557 |
| subSolverSat | Checks returning sat (kept) | utils:588 |
| subSolverUnsat | Checks returning unsat (pruned) — equals `disjunctsPrunedUnsat` by construction | utils:589 |
| subSolverUnknown | Checks returning unknown/none (kept) | utils:590 |
| normalizCalls | Normaliz cone computations: main reduction (ext:338) + normaliz-as-subsolver (utils:681) | ext:338 + utils:681 |
| conesEmpty | Main-reduction disjuncts with empty inhomogeneous cone (skipped; subsolver cones excluded) | ext:355 |
| conesNonempty | Main-reduction disjuncts with nonempty cone (contribute constraints) | ext:359 |
| hilbertBasisTotal | Sum of Hilbert-basis sizes over nonempty main-reduction cones | ext:360 |
| hilbertBasisMax | Max Hilbert-basis size in a single cone | ext:361 |
| moduleGeneratorsTotal | Sum of module-generator counts over nonempty main-reduction cones | ext:362 |
| moduleGeneratorsMax | Max module-generator count in a single cone | ext:363 |
| dimensionMax | Max star-vector dimension seen by `getCones` | ext:292 |

## How to read the numbers (bottleneck analysis)

**Accounting identities** (up to loop/trace overhead):
- `checkFullEffortTime ≈ modelValueTime + toDnfTime + getMatricesTime(main) + getConesTime + getLiaTime` + per-literal overhead (guard lemmas ext:147-169, star rewrite ext:267).
- `toDnfTime ≈ removeItesTime + removeNotTime + distributeTime` (liastar_stats.h:36-38).
- `distributeTime − subSolverTime` = pure cartesian-product + flatten cost; `subSolverTime ≈ cvc5SubSolverTime + normalizSubSolverTime`.
- `subSolverCalls = subSolverSat + subSolverUnsat + subSolverUnknown` (utils:586-591); `subSolverUnsat = disjunctsPrunedUnsat`.
- With default options: `normalizCalls = conesEmpty + conesNonempty`, and all of `normalizInputTime`/`normalizComputeTime` sits inside `getConesTime`.
- Reduction-lemma size ∝ `Σ per cone (#generators × #HilbertBasis)` fresh skolems (ext:377-415) — `hilbertBasisTotal`/`moduleGeneratorsTotal` predict lemma blowup fed back to the linear solver.

**Diagnostic patterns:**
- **`dnfCalls = 0` with large `distributeTime`**: the first DNF conversion never finished — the solver is stuck (or was killed by timeout) inside `distribute`'s cartesian product / pruning loop, before the counter at ext:578 is reached. Running timers still print their elapsed time (`StatisticTimerValue::get`, `src/util/statistics_value.cpp:100-108`), so large `toDnfTime`/`distributeTime`/`checkFullEffortTime` with `dnfCalls = dnfDisjuncts = conesNonempty = starTermsReduced = 0` is the signature of DNF-distribution blowup. Split further: `subSolverTime` ≈ `distributeTime` means the pruning subsolver is the sink; `subSolverTime` small means the product itself is.
- **Large `distributeTime`, high `subSolverCalls`, low unsat ratio** (`subSolverUnsat/subSolverCalls`): pruning is paying for itself poorly — most checks return sat/unknown and prune nothing; consider `--no-arith-liastar-subsolver`.
- **Large `normalizComputeTime`**: Hilbert-basis computation is the bottleneck; correlate with `hilbertBasisMax`, `moduleGeneratorsMax`, `dimensionMax`, `dnfDisjunctsMax`.
- **`modelValueSolved` high with `starTermsReduced = 0`**: the benchmark was discharged entirely by the model-value short-circuit (ext:170-202) — DNF/Normaliz machinery was never exercised; `toDnfTime`/`getConesTime` should be ~0.
- **`starContainsLiterals ≫ starTermsReduced`**: expected — literals are recounted every run (ext:135) while reduction happens once per literal; the gap is refinement-loop iterations, not lost work.
- **Nontrivial `getLiaTime`**: pure overhead unless tracing — `getLia`'s output feeds only the `liastar-ext-smt` self-check trace (ext:218-263) yet is computed unconditionally (ext:215).
- **`conesEmpty` high**: many disjuncts survived subsolver pruning but were geometrically empty — the second pruning layer (ext:348-358) is catching what the first missed (or the subsolver is off/unknown-heavy).

