#!/usr/bin/env python3

"""
Analyze cvc5 statistics csvs collected by cvc5_stats.py.

    python3 analyze_cvc5_stats.py output/cvc5_stats_timeout.csv
                                  [output/cvc5_stats_sat.csv ...]

For each input csv this prints, over its benchmarks:

  1. overview        answers, wall time, share of cvc5 time spent in the
                     liastar extension (theory::arith::liastar::*)
  2. time breakdown  the liastar timer tree with each timer's share --
                     the containment relations and accounting identities
                     are the verified ones of liastar_stats_reference.md
                     (default options: normaliz-as-subsolver off)
  3. counters        aggregated liastar counters and derived ratios
  4. per benchmark   one line per benchmark: where its time went and a
                     diagnosis of the dominant code path
  5. lemmas          the ARITH_LIA_STAR_* inference lemma counts

With several csvs a final section compares their medians side by side
(e.g. the timeout set against the sat set).

Diagnosis categories (see liastar_stats_reference.md):
  stuck-in-distribute   dnfCalls = 0 with distributeTime dominant: the
                        first DNF conversion never completed.  Suffixed
                        (subsolver-bound) when the pruning sub-solver
                        takes >=70% of distributeTime, else
                        (product-bound).
  model-value           solved without ever emitting a reduction lemma
                        (starTermsReduced = 0): the candidate arithmetic
                        model already satisfied every star literal.
  reduction-pipeline    reduction lemmas were emitted (DNF + cones +
                        Hilbert bases); suffixed with the dominant
                        pipeline stage, or (lia-search-dominant) when
                        most of cvc5's time was spent searching for a
                        LIA model of the reduced formula rather than in
                        the liastar extension itself.
"""

import csv
import re
import statistics
import sys

PREFIX = "theory::arith::liastar::"

# (name, depth) rows of the timer tree, in print order; shares are of
# checkFullEffortTime. distribute~product is the derived pure
# cartesian-product cost distributeTime - subSolverTime.
TIMER_TREE = [
    ("modelValueTime", 1),
    ("toDnfTime", 1),
    ("removeItesTime", 2),
    ("removeNotTime", 2),
    ("distributeTime", 2),
    ("subSolverTime", 3),
    ("cvc5SubSolverTime", 4),
    ("normalizSubSolverTime", 4),
    ("distribute~product", 3),
    ("getMatricesTime", 1),
    ("getConesTime", 1),
    ("normalizInputTime", 2),
    ("normalizComputeTime", 2),
    ("getLiaTime", 1),
]

COUNTERS = [
    "checkRuns", "starContainsLiterals", "starTermsReduced",
    "modelValueChecks", "modelValueSolved", "itesRemoved",
    "dnfCalls", "dnfDisjuncts", "dnfDisjunctsMax",
    "subSolverCalls", "subSolverSat", "subSolverUnsat", "subSolverUnknown",
    "disjunctsPrunedUnsat", "normalizCalls", "conesEmpty", "conesNonempty",
    "hilbertBasisTotal", "hilbertBasisMax",
    "moduleGeneratorsTotal", "moduleGeneratorsMax", "dimensionMax",
]

# key overall cvc5 stats reported alongside the liastar ones
GLOBAL_STATS = ["global::totalTime", "sat::conflicts", "sat::decisions"]


def num(row, key):
    """A stat as int (0 when absent/non-numeric)."""
    value = row.get(key, "") or ""
    try:
        return int(value)
    except ValueError:
        try:
            return int(float(value))
        except ValueError:
            return 0


def lia(row, name):
    if name == "distribute~product":
        return lia(row, "distributeTime") - lia(row, "subSolverTime")
    return num(row, PREFIX + name)


def histogram(row, key):
    """Parse a histogram-valued stat '{ A: 1, B: 2 }' into a dict."""
    return {k: int(v) for k, v in
            re.findall(r"([\w:]+)\s*:\s*(\d+)", row.get(key, "") or "")}


def fmt_ms(ms):
    return "{:.1f}s".format(ms / 1000) if ms >= 1000 else "{}ms".format(ms)


def share(part, whole):
    return "{:5.1f}%".format(100 * part / whole) if whole else "     -"


def diagnose(row):
    """Classify which code path this benchmark exercised (see docstring)."""
    total = num(row, "global::totalTime")
    root = lia(row, "checkFullEffortTime")
    distribute = lia(row, "distributeTime")
    if lia(row, "dnfCalls") == 0 and root and distribute >= root / 2:
        sub = lia(row, "subSolverTime")
        kind = "subsolver-bound" if sub >= 0.7 * distribute \
            else "product-bound"
        return "stuck-in-distribute ({})".format(kind)
    if lia(row, "starTermsReduced") == 0:
        if lia(row, "modelValueSolved") > 0:
            return "model-value"
        return "no-reduction"
    if total and root < total / 2:
        return "reduction-pipeline (lia-search-dominant)"
    stages = [("distribute", distribute),
              ("normaliz", lia(row, "normalizInputTime")
               + lia(row, "normalizComputeTime")),
              ("cones-other", lia(row, "getConesTime")
               - lia(row, "normalizInputTime")
               - lia(row, "normalizComputeTime")),
              ("matrices", lia(row, "getMatricesTime")),
              ("model-value", lia(row, "modelValueTime")),
              ("getLia", lia(row, "getLiaTime"))]
    stage = max(stages, key=lambda s: s[1])
    return "reduction-pipeline ({})".format(
        stage[0] if stage[1] > 0 else "cheap")


def analyze(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    print("=" * 78)
    print("{}  ({} benchmarks)".format(path, len(rows)))
    print("=" * 78)

    # 1. overview
    answers = {}
    for row in rows:
        answers[row["answer"]] = answers.get(row["answer"], 0) + 1
    total = sum(num(r, "global::totalTime") for r in rows)
    root = sum(lia(r, "checkFullEffortTime") for r in rows)
    print("answers: {}".format(
        ", ".join("{} {}".format(v, k) for k, v in sorted(answers.items()))))
    print("cvc5 time {} of which liastar extension {} ({})".format(
        fmt_ms(total), fmt_ms(root), share(root, total)))

    # 2. time breakdown
    print("\nliastar time breakdown (summed; % of checkFullEffortTime):")
    print("  {:<44} {:>10} {}".format(
        "checkFullEffortTime", fmt_ms(root), share(root, root)))
    for name, depth in TIMER_TREE:
        ms = sum(lia(r, name) for r in rows)
        print("  {:<44} {:>10} {}".format(
            "  " * depth + name, fmt_ms(ms), share(ms, root)))
    residual = root - sum(
        sum(lia(r, name) for r in rows)
        for name, depth in TIMER_TREE if depth == 1)
    print("  {:<44} {:>10} {}   (guard lemmas, rewriting, loop)".format(
        "  residual", fmt_ms(residual), share(residual, root)))

    # 3. counters
    print("\nliastar counters (sum / mean / median / max over benchmarks):")
    for name in COUNTERS:
        values = [lia(r, name) for r in rows]
        print("  {:<24} {:>12} {:>12.1f} {:>10.1f} {:>12}".format(
            name, sum(values), statistics.mean(values),
            statistics.median(values), max(values)))
    calls = sum(lia(r, "subSolverCalls") for r in rows)
    pruned = sum(lia(r, "subSolverUnsat") for r in rows)
    if calls:
        print("  sub-solver prune ratio (unsat/calls): {:.1%}".format(
            pruned / calls))

    # 4. per benchmark
    print("\nper benchmark:")
    print("  {:<34} {:>7} {:>8} {:>5} {:>6} {:>9} {:>8}  {}".format(
        "benchmark", "answer", "total", "lia%", "runs", "subCalls",
        "disj", "diagnosis"))
    for row in rows:
        total_b = num(row, "global::totalTime")
        root_b = lia(row, "checkFullEffortTime")
        print("  {:<34} {:>7} {:>8} {:>5} {:>6} {:>9} {:>8}  {}".format(
            row["benchmark"].replace("card/", "").replace("arith/", ""),
            row["answer"], fmt_ms(total_b),
            share(root_b, total_b).strip().rstrip("%"),
            lia(row, "checkRuns"), lia(row, "subSolverCalls"),
            lia(row, "dnfDisjuncts"), diagnose(row)))

    diagnoses = {}
    for row in rows:
        d = diagnose(row)
        diagnoses[d] = diagnoses.get(d, 0) + 1
    print("\ndiagnosis totals: {}".format(
        ", ".join("{} x {}".format(v, k)
                  for k, v in sorted(diagnoses.items(),
                                     key=lambda kv: -kv[1]))))

    # 5. lemmas
    lemmas = {}
    for row in rows:
        for key, count in histogram(
                row, "theory::arith::inferencesLemma").items():
            if "LIA_STAR" in key:
                lemmas[key] = lemmas.get(key, 0) + count
    if lemmas:
        print("\nARITH_LIA_STAR_* lemmas (summed): {}".format(
            ", ".join("{} {}".format(v, k.replace("ARITH_LIA_STAR_", ""))
                      for k, v in sorted(lemmas.items()))))
    print()
    return rows


def compare(paths, row_sets):
    keys = ([("wall_seconds", "wall seconds")]
            + [(k, k.split("::")[-1]) for k in GLOBAL_STATS]
            + [(PREFIX + n, n) for n, _ in TIMER_TREE if n != "distribute~product"]
            + [(PREFIX + n, n) for n in COUNTERS])
    print("=" * 78)
    print("medians side by side")
    print("=" * 78)
    print("{:<26}".format("") + "".join(
        "{:>16}".format(p.split("/")[-1]
                        .replace("cvc5_stats_", "").replace(".csv", ""))
        for p in paths))
    for key, label in keys:
        cells = []
        for rows in row_sets:
            values = sorted(
                float(r.get(key) or 0) if key == "wall_seconds"
                else num(r, key) for r in rows)
            cells.append("{:>16.2f}".format(statistics.median(values)))
        print("{:<26}".format(label) + "".join(cells))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__.strip().split("\n")[3].strip()
                 + " [more csvs ...]")
    row_sets = [analyze(path) for path in sys.argv[1:]]
    if len(row_sets) > 1:
        compare(sys.argv[1:], row_sets)


if __name__ == "__main__":
    main()
