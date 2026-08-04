
## Example input and expected output

Pre-built static cvc5 binaries are included in `bin/`, so the artifact
can be exercised with no setup at all. Pick the binary matching your
platform (`cvc5-static-linux-x86_64`, `cvc5-static-mac-arm64`,
`cvc5-static-mac-x86_64`, `cvc5-win64-x86_64.exe`,
`cvc5-win64-arm64.exe`) and run it on a benchmark:

```bash
chmod +x bin/cvc5-static-mac-arm64
bin/cvc5-static-mac-arm64 benchmarks/sql/linear/calcite-query013-call-0.smt2
bin/cvc5-static-mac-arm64 benchmarks/arith/cvc5_bapa/fol_0000001.smt2
```

Expected output: the first command prints `unsat`, the second prints
`sat`; both finish in well under a second.


# fmcad — LIA* experiments (FMCAD 2026 artifact)

1. **Verify the paper's results from the committed logs** — minutes, no
   build required (see "Verifying the paper's results" below).
2. **Rerun everything from source** — one command downloads all tools,
   builds them, runs every experiment, and produces `comparison.csv`
   plus the paper plots:

```bash
git clone https://github.com/mudathirmahgoub/fmcad26.git
cd fmcad26
python3 run.py
```

## Test system

The artifact was tested on:

- **Machine:** MacBook Pro (Mac17,6), Apple M5 Max, 18 cores
  (6 Super + 12 Performance), 64 GB RAM
- **OS:** macOS 26.5.2 (arm64)
- **Toolchain:** Apple clang 21.0.0, cmake 4.3.2, ninja 1.13.0,
  Python 3.9.6, JDK 26.0.1

Expect roughly 30–60 minutes for the one-time cvc5 build and about
12–13 hours for the experiments, which run sequentially by default for
accurate timings (the per-benchmark times in the committed logs sum to
≈12.7 h). A parallel run (`-j N`, see "The experiments") finishes in 1–2
hours on a many-core machine at some cost in timing accuracy.
`python3 run.py` is
restartable: completed setup steps are skipped and `comparison.csv` is
saved after every configuration.

## Resource requirements

- **RAM:** ≥ 16 GB recommended. 
- **CPU cores:** any number; the experiments run one benchmark at a time
  by default (`-j N` runs N in parallel).
- **Disk:** ~16 GB. Internet access is required for the setup step.


## Verifying the paper's results from the committed logs

The raw logs from the paper's experiment runs are committed, so the
paper's table and plots can be regenerated without rerunning anything:

- `output/<section>_<config>.csv` — raw per-benchmark logs
  (`filename,result,duration`), one file per benchmark section ×
  configuration.
- `comparison.csv` — the merged result table built from those logs.

From the repository root, with any python3 ≥ 3.9:

```bash
python3 latex_table.py    # paper's summary table -> comparison_table.tex (stdlib only)
python3 -m pip install pandas numpy matplotlib
python3 plot.py           # cactus_plot.png + the two scatter plots
```

Both take seconds; `latex_table.py` reproduces the committed
`comparison_table.tex` exactly. To rebuild `comparison.csv` itself from
the logs in `output/`, run
`sls-reachability/.venv/bin/python3 update_comparison.py --parse-only`
(needs the venv created by setup, see below).

## Prerequisites

Linux, macOS or Windows with:

| requirement | notes |
|---|---|
| git, bash | |
| python3 ≥ 3.9 with `venv` | Debian/Ubuntu: `sudo apt install python3-venv python3-dev` |
| C++ compiler, `cmake`, `ninja` | Debian/Ubuntu: `sudo apt install build-essential cmake ninja-build`; macOS: Xcode CLT + `brew install cmake ninja` |
| JDK 21+ (`java` on PATH) | for the SQLSolver gradle build; Debian/Ubuntu: `sudo apt install openjdk-21-jdk` (then `sudo update-alternatives --config java` if an older JDK is the default) |
| ~4 GB disk, internet access | cvc5 `--auto-download` fetches its own dependencies |
| Windows only: MSYS2 | run everything inside the MSYS2 shell matching your CPU — `clang64` on x86-64, `clangarm64` on ARM64 — so `bash`, `cmake`, `ninja` and a clang toolchain are available for the cvc5 build. Install the toolchain with the matching package prefix: `pacman -S git mingw-w64-clang-x86_64-{clang,cmake,ninja,python}` (x86-64) or `pacman -S git mingw-w64-clang-aarch64-{clang,cmake,ninja,python}` (ARM64). The JDK can be a native Windows one ([adoptium.net](https://adoptium.net); for ARM64 the [Microsoft Build of OpenJDK](https://learn.microsoft.com/java/openjdk/download) ships windows-aarch64). Note: `pip install z3-solver` on MSYS2 python has no matching binary wheel and will build z3 from source (slow but automatic); this affects both architectures. |

## Artifact structure / what setup.py does

Everything is created inside this directory (relative paths only):

```
fmcad/
├── run.py                # the one command: setup + experiments + plots
├── setup.py              # idempotent: clone + build everything
├── update_comparison.py  # experiment orchestrator (see its docstring)
├── plot.py               # renders cactus + scatter plots from comparison.csv
├── latex_table.py        # renders the paper's summary table from comparison.csv
├── bin/                  # pre-built static cvc5 binaries (smoke test only)
├── benchmarks/           # canonical smt2 benchmark set (in this repo)
│   ├── arith/cvc5_bapa/  # sets, 120 files      ┐ one comparison.csv row
│   ├── arith/cvc5_mapa/  # bags, 120 files      │ per benchmark file
│   ├── card/cvc5_bapa/   # sets, 120 files      │ (509 rows total)
│   ├── card/cvc5_mapa/   # bags, 120 files      │
│   └── sql/linear/       # sql, 29 files        ┘
├── sls-reachability/     # cloned: SLS solver (branch cvc5) + .venv
├── SQLSolver/            # cloned: SQLSolver pipeline (branch cvc5)
├── cvc5/                 # cloned: cvc5 (branch liastar), built from source
├── output/               # per-configuration result logs (committed: the
│                         # paper's runs; rewritten by new runs)
└── comparison.csv        # the merged result table (committed; rebuilt by runs)
```

Steps, in order:

1. Clone `sls-reachability` (branch `cvc5`), `SQLSolver` (branch `cvc5`)
   and `cvc5` (branch `liastar`).
2. Build cvc5:
   `./configure.sh production --prefix=build/install --tracing --ninja
   --auto-download --all-bindings --normaliz`, then `ninja install` in
   `cvc5/build`. This also produces the python wheel in
   `cvc5/build/repaired-wheel/`.
3. Create `sls-reachability/.venv` and install `z3-solver==5.0.0.0`,
   `pandas`, `numpy`, `matplotlib`, and the cvc5 wheel from step 2.
4. Copy the cvc5 java bindings produced by the cvc5 build (the jar from
   `cvc5/build/install/share/java/` and the JNI/shared libraries from
   `cvc5/build/install/lib/`) into `SQLSolver/lib/` — no pre-existing
   cvc5 binding files are assumed on any platform; the jar is installed
   under the name `cvc5-1.3.4.jar` that `build.gradle` expects. Then
   compile the SQLSolver test classes with gradle.

## The experiments

Three benchmark sections × six configurations = 18 runs; each
configuration owns one file/result/duration column triple of
`comparison.csv` (rows correspond across columns by position). Full
details live in the `update_comparison.py` docstring; the short version:

| configuration | tool and input |
|---|---|
| `unfold0`, `unfold5`, `no_interp` | **SLS solver.** Sets/bags: `lia_star_solver.py` on the *native* benchmarks in `sls-reachability/benchmarks/bapa/` (`--mapa` for bags) — running SLS through the smt2 translator was measured to hurt it badly (bapa unfold0: 53 vs 35 timeouts). Sql: `smt_to_sls.py` on `benchmarks/sql/linear/` (no native form exists). |
| `cvc5` | `cvc5/build/install/bin/cvc5 <file> --tlimit=<ms>` on `benchmarks/` |
| `sqlsolver` | SQLSolver pipeline, **original** (modification commit reverted during the run — see below) |
| `modified_sqlsolver` | SQLSolver pipeline, **modified** (clone HEAD) |

The two SQLSolver flavors run the same benchmark runner
(`SmtBenchmarksMain`, via the gradle task `:superopt:smtBenchmarks`,
reading `../benchmarks` relative to the SQLSolver clone — i.e. this
repository's `benchmarks/`), which receives the orchestrator's timeout
and job count. The modification
is commit `e2acacee35...` ("overapproximation unknown"); `sqlsolver`
reverse-applies its diff before running and restores it afterwards. Both
flavors abort unless `SQLSolver/superopt/src/main` has no uncommitted
changes. **Do not edit the SQLSolver clone while a run is in progress.**
If that commit is ever rebased, update `MODIFICATION_COMMIT` in
`update_comparison.py`.

Partial runs, e.g.:

```bash
python3 run.py --only sql                       # one section: sets | bags | sql
python3 run.py --configs cvc5,modified_sqlsolver
python3 run.py 60 -j 8                          # timeout 60s, 8 parallel jobs
sls-reachability/.venv/bin/python3 update_comparison.py --parse-only
```

Benchmarks run sequentially by default (`-j 1`), which gives the most
accurate timings: many benchmarks are solved within a second, and CPU
contention from parallel jobs measurably inflates such short measured
durations. The full sequential run takes about 12–13 hours. Pass `-j N`
to run N benchmarks in parallel when wall-clock matters more than timing
fidelity — with all cores but two, the full run finishes in 1–2 hours.
The TIMEOUT and `-j`
arguments apply to all configurations, including the two SQLSolver ones
(forwarded to their benchmark runner).

## Outputs

- `comparison.csv` — one file/result/duration column triple per
  configuration, 509 data
  rows (240 sets, 240 bags, 29 sql), CRLF line endings, lowercase results
  (`sat`, `unsat`, `unknown`, `timeout`, `error`). Constructed from
  scratch when missing; delete it to force a clean rebuild.
- `output/<section>_<config>.csv` — per-run results
  (`filename,result,duration`), what `--parse-only` re-reads.
- `cactus_plot.png`, `scatter_cvc5_vs_unfold5.png`,
  `scatter_cvc5_vs_modified_sqlsolver.png` — rendered by `plot.py` from
  `comparison.csv` at the end of `python3 run.py`.

## Sanity checking a run

A row where one tool answers `sat` and another `unsat` indicates a
soundness bug somewhere:

```bash
awk -F, 'NR>1 {s=0; u=0; for (i=2; i<=20; i+=3) {if ($i=="sat") s=1; if ($i=="unsat") u=1}
               if (s&&u) print "CONTRADICTION: " $1}' comparison.csv
```

Known instances (July 2026 runs, present in the committed
`comparison.csv`): four sets benchmarks — `card/cvc5_bapa/fol_0000055`,
`fol_0000078`, `fol_0000116` and `fol_0000120` — where the original
SQLSolver answers `sat` while cvc5 proves `unsat`; the modified pipeline
returns `unknown` on all four, which is the point of the modification.

## Troubleshooting

- `error: setup is incomplete -- run python3 setup.py first` — a tool is
  missing; the message lists which one.
- cvc5 wheel fails to install: the wheel in `cvc5/build/repaired-wheel/`
  is built for the python that configured the build; recreate the venv
  with that same `python3`.
- `UnsatisfiedLinkError` from the SQLSolver tests: re-run `python3 setup.py`
  so the cvc5 java bindings built by the cvc5 step are (re)copied into
  `SQLSolver/lib/` (step 4).
- `error: invalid source release: N` from gradle: your JDK is older than
  the level SQLSolver targets (21) — install JDK 21+ and make it the
  default (`setup.py` checks this up front and refuses to start
  otherwise). Re-running `python3 run.py` also fast-forwards the existing
  clones, so upstream fixes arrive automatically.
- gradle "up-to-date" confusion never affects results: the orchestrator
  passes `--rerun-tasks` so tests always execute.

## Licensing

The artifact uses cvc5's license, [cvc5/COPYING](cvc5/COPYING). Each
bundled tool keeps its own license (the `cvc5/`, `sls-reachability/` and
`SQLSolver/` trees are created by setup, so these paths exist after
`python3 run.py`):

| component | license | description |
|---|---|---|
| cvc5 | [cvc5/COPYING](cvc5/COPYING) (modified BSD) | the SMT solver evaluated in the paper; covers the `cvc5/` clone and the pre-built binaries in `bin/` |
| Normaliz | [cvc5/build/deps/src/Normaliz-EP/COPYING](cvc5/build/deps/src/Normaliz-EP/COPYING) (GPL-3.0) | discrete convex geometry library that the cvc5 build downloads and links (`--normaliz`) |
| SLS solver | [sls-reachability/LICENSE](sls-reachability/LICENSE) (MIT) | the SLS LIA\* solver behind the `unfold0`/`unfold5`/`no_interp` configurations |
| SQLSolver | [SQLSolver/LICENSE](SQLSolver/LICENSE) (Apache-2.0) | the SQL equivalence prover behind the `sqlsolver`/`modified_sqlsolver` configurations |
