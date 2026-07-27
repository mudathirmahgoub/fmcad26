#!/usr/bin/env python3

"""
Collect cvc5 statistics over benchmarks selected from comparison.csv.

    python3 cvc5_stats.py timeout|sat|unsat|unknown|all
                          [--timeout N] [--benchmarks NAME[,NAME...]]
                          [--out FILE]

Selects the benchmarks whose cvc5 result column of comparison.csv matches
the given result (all = every benchmark), then runs the liastar cvc5
build on each one SEQUENTIALLY -- one at a time, for meaningful timers --
through its python API (update_comparison.solve_cvc5_api: bindings
loaded once, one forked child per benchmark, statistics collected with
Statistics.get(True, True) after the run completes; see the "Running
cvc5 through its python API" comment in update_comparison.py)

and writes one row per benchmark to --out (default:
output/cvc5_stats_<selection>.csv): benchmark, answer, wall_seconds, then
one column per statistic, in sorted key order (the union over all rows;
histogram-valued statistics like { ARITH_UNATE: 1 } are stored verbatim).
Times reported by cvc5 (18ms) are stored as integer milliseconds.

The per-benchmark timeout defaults to 100 seconds, matching
update_comparison.py. A run killed at the wall timeout cannot report API
statistics (the child is gone), so those benchmarks are rerun once
through the cvc5 binary with

    cvc5 --tlimit=<timeout in ms> --stats --stats-all --stats-internal

whose CLI signal handler is the only mechanism that can snapshot
statistics mid-solve; the answer and duration still come from the API
run.

--benchmarks additionally restricts the selection by name, with the same
matching rule as update_comparison.py (exact benchmarks/-relative name or
whole-component path suffix).
"""

import argparse
import csv
import os
import subprocess
import sys

import update_comparison

FMCAD_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARKS_DIR = os.path.join(FMCAD_DIR, "benchmarks")
COMPARISON_CSV = os.path.join(FMCAD_DIR, "comparison.csv")
DEFAULT_OUT_DIR = os.path.join(FMCAD_DIR, "output")
WINDOWS = os.name == "nt"
CVC5_BINARY = os.path.join(FMCAD_DIR, "cvc5", "build", "install", "bin",
                           "cvc5.exe" if WINDOWS else "cvc5")

# comparison.csv columns of the cvc5 configuration (see update_comparison)
CVC5_FILE_COLUMN, CVC5_RESULT_COLUMN = 3, 4


def match_benchmark(benchmark, names):
    """update_comparison.py's --benchmarks matching rule."""
    b = benchmark.replace(os.sep, "/")
    return any(b == n or b.endswith("/" + n)
               for n in (name.replace(os.sep, "/") for name in names))


def select_benchmarks(selection, names):
    """(benchmark, recorded result) rows of comparison.csv whose cvc5
    result matches `selection`, optionally restricted to `names`."""
    with open(COMPARISON_CSV, newline="") as f:
        rows = list(csv.reader(f))[1:]
    picked = []
    for row in rows:
        benchmark = row[CVC5_FILE_COLUMN].strip()
        result = row[CVC5_RESULT_COLUMN].strip()
        if selection != "all" and result != selection:
            continue
        if names and not match_benchmark(benchmark, names):
            continue
        picked.append((benchmark, result))
    return picked


def parse_stats(output):
    """Parse cvc5's `key = value` statistics lines. Times (18ms) become
    integer milliseconds; everything else is kept verbatim."""
    stats = {}
    for line in output.splitlines():
        if " = " not in line:
            continue
        key, value = line.split(" = ", 1)
        key, value = key.strip(), value.strip()
        if not key or " " in key:
            continue
        if value.endswith("ms") and value[:-2].isdigit():
            value = value[:-2]
        # --stats-all prints some public statistics a second time with
        # defaulted values (e.g. a global::totalTime = 0ms after the real
        # one); keep the informative occurrence
        if key in stats and stats[key] not in ("", "0", "{}"):
            continue
        stats[key] = value
    return stats


def binary_stats(benchmark, timeout):
    """Harvest interrupted-at-timeout statistics by running the cvc5
    BINARY with --tlimit and the stats flags: its CLI signal handler
    prints the statistics mid-solve, which the API cannot do for a
    killed child."""
    cmd = [CVC5_BINARY, os.path.join(BENCHMARKS_DIR, benchmark),
           "--tlimit={}".format(timeout * 1000),
           "--stats", "--stats-all", "--stats-internal"]
    # generous backstop in case --tlimit fails to fire, so cvc5 can
    # still finish printing statistics after the interrupt
    try:
        proc = subprocess.run(cmd, capture_output=True,
                              timeout=timeout + 30, cwd=FMCAD_DIR)
        output = (proc.stdout + proc.stderr).decode("utf-8")
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or b"") + (exc.stderr or b"")).decode("utf-8")
    return parse_stats(output)


def run_one(benchmark, timeout):
    """Run cvc5 with statistics on one benchmark through the python API
    (see module docstring). Returns (answer, wall seconds, stats dict);
    answer is sat/unsat/unknown/timeout/error. Runs killed at the wall
    timeout get their statistics from a binary rerun."""
    answer, duration, stats = update_comparison.solve_cvc5_api(
        os.path.join(BENCHMARKS_DIR, benchmark), timeout)
    if not stats or set(stats) == {"error"}:
        stats = binary_stats(benchmark, timeout)
    return answer, duration, stats


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("selection",
                   choices=["timeout", "sat", "unsat", "unknown", "all"],
                   help="which benchmarks to run, by their cvc5 result "
                        "in comparison.csv")
    p.add_argument("--timeout", type=int, default=100,
                   help="per-benchmark timeout in seconds, passed to cvc5 "
                        "as --tlimit (default: 100)")
    p.add_argument("--benchmarks", metavar="NAME[,NAME...]", default=None,
                   help="further restrict to these benchmarks")
    p.add_argument("--out", default=None,
                   help="output csv (default: "
                        "output/cvc5_stats_<selection>.csv)")
    args = p.parse_args()

    if not os.path.exists(CVC5_BINARY):
        sys.exit("error: {} not found -- run python3 setup.py first"
                 .format(CVC5_BINARY))
    names = args.benchmarks.split(",") if args.benchmarks else None
    picked = select_benchmarks(args.selection, names)
    if not picked:
        sys.exit("error: no benchmarks match")
    out = args.out or os.path.join(
        DEFAULT_OUT_DIR, "cvc5_stats_{}.csv".format(args.selection))

    print("{} benchmarks, sequential, timeout {}s, -> {}".format(
        len(picked), args.timeout, out), flush=True)
    rows = []
    for i, (benchmark, recorded) in enumerate(picked, 1):
        answer, duration, stats = run_one(benchmark, args.timeout)
        note = "" if answer == recorded else \
            " (comparison.csv had {})".format(recorded)
        print("  [{}/{}] {} : {} : {:.2f}s{}".format(
            i, len(picked), benchmark, answer, duration, note), flush=True)
        row = {"benchmark": benchmark, "answer": answer,
               "wall_seconds": "{:.3f}".format(duration)}
        row.update(stats)
        rows.append(row)

    keys = sorted(set().union(*(row.keys() for row in rows))
                  - {"benchmark", "answer", "wall_seconds"})
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["benchmark", "answer", "wall_seconds"] + keys)
        writer.writeheader()
        writer.writerows(rows)
    print("wrote {}".format(out), flush=True)


if __name__ == "__main__":
    main()
