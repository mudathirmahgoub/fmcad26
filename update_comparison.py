#!/usr/bin/env python3

"""
Run all fmcad experiments and maintain comparison.csv.

Normally invoked through python3 run.py (which also performs setup and renders
the plots); direct invocation works too:

    sls-reachability/.venv/bin/python3 update_comparison.py [options]

Every path is resolved relative to this script's directory, which after
python3 setup.py looks like:

    fmcad/
      benchmarks/           canonical smt2 benchmark set (this repository)
      sls-reachability/     SLS solver clone (branch cvc5) + .venv
      SQLSolver/            SQLSolver pipeline clone (branch cvc5)
      cvc5/                 cvc5 clone (branch liastar), built
      output/               per-configuration result csvs (created)
      comparison.csv        the maintained result table (created)

Benchmarks
----------
benchmarks/ holds the canonical cvc5-format smt2 files, one comparison.csv
row per file, in three sections:

    sets (bapa):  benchmarks/arith/cvc5_bapa + benchmarks/card/cvc5_bapa (240)
    bags (mapa):  benchmarks/arith/cvc5_mapa + benchmarks/card/cvc5_mapa (240)
    sql:          benchmarks/sql/linear                                   (29)

Each section runs in six configurations, one per column triple of
comparison.csv:

    unfold0 / unfold5 / no_interp  (the SLS solver)
        For the sets/bags sections SLS does NOT read the cvc5-format
        files: translating them back through smt_to_sls.py was measured
        to hurt its performance badly (e.g. bapa unfold0: 53 timeouts via
        the translator vs 35 natively, July 2026). It runs
        lia_star_solver.py on the NATIVE benchmarks instead --
        sls-reachability/benchmarks/bapa/{arith,card}/fol_*, the very
        files the cvc5_bapa/cvc5_mapa ones were generated from -- with
        --mapa selecting the bags interpretation. The sql section has no
        native form, so there SLS goes through the smt_to_sls.py
        translator on the benchmarks/ files.
    cvc5
        the liastar cvc5 binary: cvc5/build/install/bin/cvc5 <file>
    sqlsolver / modified_sqlsolver
        the SQLSolver pipeline, via its SmtBenchmarksMain runner
        (gradle task :superopt:smtBenchmarks), which reads ../benchmarks
        relative to the SQLSolver clone -- i.e. the same benchmarks/
        directory -- and honors this script's TIMEOUT and -j arguments

Each configuration's file column in comparison.csv records the file that
configuration actually ran (the native path for sets/bags SLS, the
benchmarks/ path everywhere else); rows correspond across columns by
position: fol_N under arith/card maps to fol_N in every encoding.

SQLSolver flavors
-----------------
The two SQLSolver configurations run the same tests; they differ only in
the pipeline source. The modification lives in commit

    e2acacee3506fef2372313db2fddf6f6659e57ea  ("overapproximation unknown")

of the SQLSolver clone. modified_sqlsolver runs HEAD as-is; sqlsolver
reverse-applies that commit's diff to the working tree before running and
restores it afterwards. Both require superopt/src/main to be free of
uncommitted changes (the script aborts otherwise), and gradle recompiles
the pipeline on every flip. Do not edit the SQLSolver clone while a run
is in progress.

Pipeline
--------
1. run: every configuration writes <section>_<config>.csv with
   filename,result,duration rows (Excel-friendly) into output/.
2. parse: those result csvs are read back, stripping padding spaces.
3. update: results go into the configuration's columns of comparison.csv,
   matched per section by benchmark name; the file is saved after every
   configuration, so an interrupted run keeps completed results. If
   comparison.csv does not exist it is constructed from scratch (header +
   one row per benchmark); delete it to force a clean rebuild.

Results are lowercase throughout (sat / unsat / unknown / timeout / error).

Concurrency
-----------
Benchmarks of the sets/bags sections run in parallel (all CPUs but two by
default); the fast sql section runs sequentially for accurate timings; -j
overrides both. The worker pool uses threads, not processes, deliberately:
each job only spawns and waits on a solver subprocess, which releases the
GIL, so threads already provide full parallelism. The SQLSolver runner
parallelizes internally the same way and receives this script's TIMEOUT
and job count (sequential for the sql section), so all six
configurations share the same timeout and parallelism settings.

Usage
-----
    python3 run.py                                    # setup + everything + plots
    python3 update_comparison.py --only sets    # one section
    python3 update_comparison.py --configs cvc5,sqlsolver   # some configs
    python3 update_comparison.py -j 8           # limit parallelism
    python3 update_comparison.py --parse-only   # just re-read result csvs
"""

import argparse
import csv
import os
import subprocess
import sys
import time
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor, as_completed


# ---------------------------------------------------------------------------
# Configuration -- everything relative to this script's directory
# ---------------------------------------------------------------------------

FMCAD_DIR = os.path.dirname(os.path.abspath(__file__))
BENCHMARKS_DIR = os.path.join(FMCAD_DIR, "benchmarks")
WINDOWS = os.name == "nt"

SLS_DIR = os.path.join(FMCAD_DIR, "sls-reachability")
SLS_SOLVER = os.path.join(SLS_DIR, "lia_star_solver.py")
SLS_TRANSLATOR = os.path.join(SLS_DIR, "smt_to_sls.py")
SLS_NATIVE_DIR = os.path.join(SLS_DIR, "benchmarks")
SLS_PYTHON = os.path.join(
    SLS_DIR, ".venv",
    *(("Scripts", "python.exe") if WINDOWS else ("bin", "python3")))

CVC5_BINARY = os.path.join(FMCAD_DIR, "cvc5", "build", "install", "bin",
                           "cvc5.exe" if WINDOWS else "cvc5")
SQLSOLVER_DIR = os.path.join(FMCAD_DIR, "SQLSolver")
GRADLEW = os.path.join(SQLSOLVER_DIR,
                       "gradlew.bat" if WINDOWS else "gradlew")

DEFAULT_OUT_DIR = os.path.join(FMCAD_DIR, "output")
DEFAULT_CSV = os.path.join(FMCAD_DIR, "comparison.csv")

# Leave two CPUs free for the operating system and the IDE
DEFAULT_JOBS = max(1, (os.cpu_count() or 3) - 2)

# A configuration owns three adjacent columns of comparison.csv, starting
# at `column`: file, result and duration. solver_args only apply to the
# SLS configurations.
Config = namedtuple("Config", ["name", "solver_args", "column"])
CONFIGS = [
    Config("unfold0",            ["--unfold=0"],  column=0),
    Config("cvc5",               [],              column=3),
    Config("unfold5",            ["--unfold=5"],  column=6),
    Config("no_interp",          ["--no-interp"], column=9),
    Config("sqlsolver",          [],              column=12),
    Config("modified_sqlsolver", [],              column=15),
]
SQLSOLVER_FLAVORS = ("sqlsolver", "modified_sqlsolver")

HEADER = [
    "unfold0 file", "unfold0 result", "unfold0 duration",
    "cvc5 filename", "cvc5 result", "cvc5 duration",
    "unfold5 file", "unfold5 result", "unfold5 duration",
    "no_interp file", "no_interp result", "no_interp duration",
    "sqlsolver filename", "sqlsolver result", "sqlsolver duration",
    "modified_sqlsolver file", "modified_sqlsolver result",
    "modified_sqlsolver duration",
]

# The SQLSolver pipeline and its modification commit (see the docstring)
MODIFICATION_COMMIT = "e2acacee3506fef2372313db2fddf6f6659e57ea"
# Per section: the csv file the SmtBenchmarksMain runner writes into the
# SQLSolver root (its suite names equal the section prefixes)
SQLSOLVER_OUTPUTS = {
    "bapa": "sql_bapa.csv",
    "mapa": "sql_mapa.csv",
    "sql":  "sql_solver.csv",
}


def list_benchmarks(dirs):
    """Benchmark names, relative to benchmarks/, in stable per-directory
    sorted order."""
    names = []
    for d in dirs:
        names += sorted(
            d + "/" + f
            for f in os.listdir(os.path.join(BENCHMARKS_DIR, d))
            if f.endswith(".smt2"))
    return names


# A section is one fixed block of comparison.csv: `row` is its first data
# row (0-based, header excluded) and `benchmarks` its files in row order.
Section = namedtuple("Section", ["prefix", "row", "benchmarks"])
SECTIONS = []
_row = 0
for _prefix, _dirs in [
        ("bapa", ("arith/cvc5_bapa", "card/cvc5_bapa")),
        ("mapa", ("arith/cvc5_mapa", "card/cvc5_mapa")),
        ("sql",  ("sql/linear",))]:
    _benchmarks = list_benchmarks(_dirs)
    SECTIONS.append(Section(_prefix, _row, _benchmarks))
    _row += len(_benchmarks)
TOTAL_BENCHMARKS = _row

# --only names the sections by their paper terminology
ONLY_TO_PREFIX = {"sets": "bapa", "bags": "mapa", "sql": "sql"}

# The native benchmarks the SLS configurations run for sets/bags (via
# lia_star_solver.py; names relative to sls-reachability/benchmarks). Sets
# and bags share the files -- --mapa selects the bags interpretation --
# and fol_N here corresponds positionally to fol_N of the benchmarks/ set.
SLS_NATIVE_BENCHMARKS = ["bapa/{}/fol_{:07d}.smt2".format(d, i)
                         for d in ("arith", "card")
                         for i in range(1, 121)]


def preflight():
    """Verify the tools setup.py provides are in place."""
    checks = [
        (SLS_PYTHON, "the sls-reachability virtual environment"),
        (SLS_SOLVER, "the sls-reachability clone"),
        (CVC5_BINARY, "the cvc5 build"),
        (GRADLEW, "the SQLSolver clone"),
        (os.path.join(SLS_NATIVE_DIR, "bapa"), "the native SLS benchmarks"),
    ]
    missing = [(path, what) for path, what in checks
               if not os.path.exists(path)]
    if missing:
        lines = ["error: setup is incomplete -- run python3 setup.py first:"]
        lines += ["  missing {} ({})".format(path, what)
                  for path, what in missing]
        sys.exit("\n".join(lines))


# ---------------------------------------------------------------------------
# Running the solvers
# ---------------------------------------------------------------------------

def solve_lia_star(benchmark, timeout, solver_args):
    """Run the SLS solver natively (lia_star_solver.py) on a single
    sets/bags benchmark (names relative to sls-reachability/benchmarks;
    solver_args carries --mapa for the bags interpretation). With -i its
    stdout is: problem size / stats dict / sat|unsat. Returns
    (benchmark, result, duration)."""
    cmd = [SLS_PYTHON, SLS_SOLVER,
           os.path.join(SLS_NATIVE_DIR, benchmark), "-i"] + solver_args
    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              cwd=FMCAD_DIR)
        duration = time.time() - start
        try:
            result = proc.stdout.decode("utf-8").strip().split("\n")[2]
            if result not in ("sat", "unsat"):
                result = "error"
        except IndexError:
            result = "error"
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        result = "timeout"
    return benchmark, result, duration


def solve_sls(benchmark, timeout, solver_args):
    """Run the smt-to-sls translator + SLS solver on a single benchmark
    (used for the sql section, which only exists in cvc5 format).
    Returns (benchmark, result, duration) with result 'sat', 'unsat',
    'unknown', 'timeout' or 'error'."""
    cmd = [SLS_PYTHON, SLS_TRANSLATOR,
           os.path.join(BENCHMARKS_DIR, benchmark)] + solver_args
    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              cwd=FMCAD_DIR)
        duration = time.time() - start
        if proc.returncode != 0:
            result = "error"
        else:
            result = "unknown"
            for line in proc.stdout.decode("utf-8").splitlines():
                if line.strip() in ("sat", "unsat"):
                    result = line.strip()
                    break
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        result = "timeout"
    return benchmark, result, duration


def solve_cvc5(benchmark, timeout, solver_args):
    """Run the liastar cvc5 binary on a single benchmark. The timeout is
    also passed to cvc5 as --tlimit (milliseconds); hitting it makes cvc5
    exit with 'cvc5 interrupted by timeout.'."""
    cmd = [CVC5_BINARY, os.path.join(BENCHMARKS_DIR, benchmark),
           "--tlimit={}".format(timeout * 1000)]
    start = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout,
                              cwd=FMCAD_DIR)
        duration = time.time() - start
        output = (proc.stdout + proc.stderr).decode("utf-8")
        if "interrupted by timeout" in output:
            result = "timeout"
        elif proc.returncode != 0:
            result = "error"
        else:
            result = "unknown"
            for line in output.splitlines():
                if line.strip() in ("sat", "unsat", "unknown"):
                    result = line.strip()
                    break
    except subprocess.TimeoutExpired:
        duration = time.time() - start
        result = "timeout"
    return benchmark, result, duration


def run_configuration(name, benchmarks, solver, timeout, solver_args, jobs,
                      out_dir):
    """Run all benchmarks of one configuration through `solver`
    (solve_lia_star, solve_sls or solve_cvc5), then write <name>.csv into
    out_dir.

    With jobs == 1 the benchmarks run strictly sequentially, which gives
    the most accurate timings; otherwise a thread pool supervises `jobs`
    solver subprocesses at a time (threads suffice: each one just blocks
    in subprocess.run, releasing the GIL)."""
    print("\n=== {}: {} benchmarks, {}, timeout {}s ===".format(
        name, len(benchmarks),
        "sequential" if jobs == 1 else "{} parallel jobs".format(jobs),
        timeout), flush=True)

    results = {}

    def record(outcome, done):
        benchmark, result, duration = outcome
        results[benchmark] = (result, duration)
        print("  [{}/{}] {} : {} : {:.2f}s".format(
            done, len(benchmarks), benchmark, result, duration), flush=True)

    if jobs == 1:
        for done, benchmark in enumerate(benchmarks, 1):
            record(solver(benchmark, timeout, solver_args), done)
    else:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            futures = [pool.submit(solver, b, timeout, solver_args)
                       for b in benchmarks]
            for done, future in enumerate(as_completed(futures), 1):
                record(future.result(), done)

    write_run_file(name, benchmarks, results, out_dir)


def write_run_file(name, benchmarks, results, out_dir):
    """Write <name>.csv with filename,result,duration rows into out_dir,
    in benchmark order (results may arrive in completion order)."""
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, name + ".csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["filename", "result", "duration"])
        for benchmark in benchmarks:
            result, duration = results[benchmark]
            writer.writerow([benchmark, result, duration])
    print("  wrote {}".format(csv_path), flush=True)


# ---------------------------------------------------------------------------
# Running the SQLSolver pipeline
# ---------------------------------------------------------------------------

def check_sqlsolver_clean():
    """Both flavors need superopt/src/main clean so the flavor toggle
    below fully controls which pipeline is measured."""
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", "superopt/src/main"],
        cwd=SQLSOLVER_DIR, capture_output=True).stdout.decode().strip()
    if status:
        sys.exit("error: {} has uncommitted changes under "
                 "superopt/src/main:\n{}\ncommit or stash them first"
                 .format(SQLSOLVER_DIR, status))


def set_pipeline_modified(modified):
    """The modified pipeline is HEAD; the original one is HEAD with the
    modification commit's diff reverse-applied (working tree only)."""
    if modified:
        subprocess.run(
            ["git", "checkout", "HEAD", "--", "superopt/src/main"],
            cwd=SQLSOLVER_DIR, check=True)
    else:
        diff = subprocess.run(
            ["git", "diff", MODIFICATION_COMMIT + "^!", "--",
             "superopt/src/main"],
            cwd=SQLSOLVER_DIR, check=True, capture_output=True).stdout
        subprocess.run(["git", "apply", "-R"], cwd=SQLSOLVER_DIR,
                       check=True, input=diff)


def run_sqlsolver_pipeline(config_name, prefix, name, out_dir, timeout,
                           jobs):
    """Run the SQLSolver pipeline ('sqlsolver' = modification commit
    reverted, 'modified_sqlsolver' = HEAD) on one section's benchmarks and
    write <name>.csv into out_dir.

    Unlike the other runners this is one gradle invocation: the
    SmtBenchmarksMain runner (task :superopt:smtBenchmarks) recompiles the
    pipeline, runs the section's suite with the given per-benchmark
    timeout on `jobs` parallel workers, and writes
    filename,result,duration rows to a csv in the SQLSolver root."""
    check_sqlsolver_clean()
    test_csv = SQLSOLVER_OUTPUTS[prefix]
    bench_args = "{} --timeout={} --jobs={}".format(prefix, timeout, jobs)
    cmd = [GRADLEW, ":superopt:smtBenchmarks",
           "-PbenchArgs=" + bench_args, "--console=plain"]
    print("\n=== {}: gradle smtBenchmarks {} ===".format(name, bench_args),
          flush=True)

    if config_name == "sqlsolver":
        set_pipeline_modified(False)
    try:
        subprocess.run(cmd, cwd=SQLSOLVER_DIR, check=True)
    finally:
        if config_name == "sqlsolver":
            set_pipeline_modified(True)

    # the runner lists files relative to the SQLSolver root
    # (../benchmarks/...); comparison.csv uses names relative to
    # benchmarks/, and lowercase results throughout
    results = {}
    with open(os.path.join(SQLSOLVER_DIR, test_csv), newline="") as f:
        for row in csv.DictReader(f):
            path = os.path.normpath(
                os.path.join(SQLSOLVER_DIR, row["filename"]))
            benchmark = os.path.relpath(path, BENCHMARKS_DIR)
            results[benchmark] = (row["result"].lower(),
                                  float(row["duration"]))

    section = next(s for s in SECTIONS if s.prefix == prefix)
    missing = [b for b in section.benchmarks if b not in results]
    if missing:
        print("  WARNING: {} has no result for {} benchmarks (e.g. {})"
              .format(test_csv, len(missing), missing[0]))
    write_run_file(name, sorted(results), results, out_dir)


# ---------------------------------------------------------------------------
# Updating comparison.csv
# ---------------------------------------------------------------------------

def parse_results(path):
    """Parse a <name>.csv results file into {benchmark: (result,
    duration)}, stripping any padding spaces."""
    results = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            try:
                float(row["duration"])
            except (KeyError, TypeError, ValueError):
                print("  WARNING: skipping unparseable row: {!r}".format(row))
                continue
            results[row["filename"].strip()] = (row["result"].strip(),
                                                row["duration"].strip())
    return results


def update_rows(section_rows, results, column, label):
    """Write result/duration into one configuration's columns of the given
    rows, matching by the benchmark name in the config's file column."""
    updated, missing = 0, []
    for row in section_rows:
        benchmark = row[column].strip()
        if benchmark in results:
            row[column] = benchmark
            row[column + 1], row[column + 2] = results[benchmark]
            updated += 1
        else:
            missing.append(benchmark)

    print("  {}: updated {}/{} rows".format(label, updated,
                                            len(section_rows)))
    if missing:
        print("  {}: WARNING: no result for {} benchmarks (e.g. {})"
              .format(label, len(missing), missing[0]))


def set_file_column(section_rows, benchmarks, column):
    """Set one configuration's file column to the names of the files that
    configuration runs, in section order (rows correspond across
    configurations by position). This also migrates rows recorded under
    older naming schemes."""
    for row, benchmark in zip(section_rows, benchmarks):
        row[column] = benchmark


def build_comparison(path):
    """Construct a fresh comparison.csv skeleton: header + one row per
    benchmark, file columns filled, results empty."""
    rows = [list(HEADER)]
    for section in SECTIONS:
        for benchmark in section.benchmarks:
            row = [""] * len(HEADER)
            for config in CONFIGS:
                row[config.column] = benchmark
            rows.append(row)
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    write_comparison(path, rows)
    print("constructed {} from scratch ({} benchmark rows)".format(
        path, TOTAL_BENCHMARKS))
    return rows


def read_comparison(path):
    """Read comparison.csv, constructing it from scratch if missing."""
    if not os.path.exists(path):
        return build_comparison(path)
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    expected = 1 + TOTAL_BENCHMARKS
    if len(rows) != expected:
        sys.exit("error: {} has {} rows, expected {} -- delete the file "
                 "to rebuild it from scratch".format(
                     path, len(rows), expected))
    return rows


def write_comparison(path, rows):
    # comparison.csv uses CRLF line endings; preserve them
    with open(path, "w", newline="") as f:
        csv.writer(f, lineterminator="\r\n").writerows(rows)


def update_from_results(rows, csv_path, out_dir, name, section_rows,
                        column):
    """Parse out_dir/<name>.csv into the given comparison.csv rows and
    save the file, so every finished configuration is persisted
    immediately."""
    results_csv = os.path.join(out_dir, name + ".csv")
    if not os.path.exists(results_csv):
        print("  {}: WARNING: {} not found, skipping".format(
            name, results_csv))
        return
    update_rows(section_rows, parse_results(results_csv), column, name)
    write_comparison(csv_path, rows)


# ---------------------------------------------------------------------------
# Command line interface
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("timeout", metavar="TIMEOUT", nargs="?", type=int,
                   default=100,
                   help="timeout per benchmark in seconds, applied to all "
                        "six configurations (default: 100)")
    p.add_argument("-j", "--jobs", type=int, default=None,
                   help="number of benchmarks to run in parallel (default: "
                        "all cpus but two, here {}; 1 -- i.e. sequential "
                        "-- for the fast sql section)".format(DEFAULT_JOBS))
    p.add_argument("--csv", default=DEFAULT_CSV,
                   help="comparison.csv to update, constructed from "
                        "scratch if missing (default: ./comparison.csv)")
    p.add_argument("--out-dir", default=DEFAULT_OUT_DIR,
                   help="directory for the per-configuration result csvs "
                        "(default: ./output)")
    p.add_argument("--parse-only", action="store_true",
                   help="do not run the benchmarks; just parse existing "
                        "result csvs and update comparison.csv")
    p.add_argument("--only", choices=sorted(ONLY_TO_PREFIX),
                   help="run/update only one section: sets (bapa), "
                        "bags (mapa) or sql")
    p.add_argument("--configs", metavar="NAME[,NAME...]", default=None,
                   help="run/update only these configurations ({}; "
                        "default: all)".format(
                            ", ".join(c.name for c in CONFIGS)))
    args = p.parse_args()
    args.configs = args.configs.split(",") if args.configs else None
    return args


def main():
    args = parse_args()
    if not args.parse_only:
        preflight()
    rows = read_comparison(args.csv)

    for section in SECTIONS:
        if args.only and ONLY_TO_PREFIX[args.only] != section.prefix:
            continue
        section_rows = rows[1 + section.row:
                            1 + section.row + len(section.benchmarks)]
        jobs = args.jobs or (1 if section.prefix == "sql"
                             else DEFAULT_JOBS)

        for config in CONFIGS:
            if args.configs and config.name not in args.configs:
                continue
            name = "{}_{}".format(section.prefix, config.name)

            # the SLS configurations of sets/bags run the native
            # benchmarks through lia_star_solver.py; everything else runs
            # the benchmarks/ files (see the module docstring)
            benchmarks, solver, extra_args = (
                section.benchmarks, solve_sls, [])
            if (config.name not in SQLSOLVER_FLAVORS
                    and config.name != "cvc5"
                    and section.prefix != "sql"):
                benchmarks = SLS_NATIVE_BENCHMARKS
                solver = solve_lia_star
                extra_args = ["--mapa"] if section.prefix == "mapa" else []

            if not args.parse_only:
                if config.name in SQLSOLVER_FLAVORS:
                    run_sqlsolver_pipeline(config.name, section.prefix,
                                           name, args.out_dir,
                                           args.timeout, jobs)
                elif config.name == "cvc5":
                    run_configuration(name, section.benchmarks, solve_cvc5,
                                      args.timeout, config.solver_args,
                                      jobs, args.out_dir)
                else:
                    run_configuration(name, benchmarks, solver,
                                      args.timeout,
                                      config.solver_args + extra_args,
                                      jobs, args.out_dir)
            set_file_column(section_rows, benchmarks, config.column)
            update_from_results(rows, args.csv, args.out_dir, name,
                                section_rows, config.column)

    print("\nAll done: {}".format(args.csv))


if __name__ == "__main__":
    main()
