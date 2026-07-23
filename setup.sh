#!/usr/bin/env bash
#
# One-time (idempotent) setup for the fmcad experiments: clones the three
# tool repositories next to this script, builds cvc5, prepares the python
# virtual environment inside sls-reachability, and compiles the SQLSolver
# test classes. Everything lives under this directory; safe to re-run --
# completed steps are skipped.
#
# Requirements (see README.md): git, python3 (>= 3.9, with venv), a C++
# compiler, cmake, ninja, JDK 21+.

set -euo pipefail
cd "$(cd "$(dirname "$0")" && pwd)"

step() { printf '\n=== %s ===\n' "$*"; }

# --------------------------------------------------------------------------
# 0. Fail fast on missing prerequisites (before the long cvc5 build)
# --------------------------------------------------------------------------
step "Checking prerequisites"
for tool in git python3 cmake ninja java; do
    command -v "$tool" >/dev/null || {
        echo "error: '$tool' not found on PATH -- see README.md" >&2
        exit 1
    }
done
java_major=$(java -version 2>&1 | sed -n 's/.*version "\([0-9]*\).*/\1/p' | head -1)
if [ "${java_major:-0}" -lt 21 ]; then
    echo "error: SQLSolver targets Java 21, but 'java' on PATH is" >&2
    echo "       version ${java_major:-unknown}. Please install JDK 21" >&2
    echo "       or newer and make it the default:" >&2
    echo "  Debian/Ubuntu: sudo apt install openjdk-21-jdk" >&2
    echo "                 sudo update-alternatives --config java" >&2
    echo "  macOS:         brew install openjdk" >&2
    exit 1
fi
echo "git, python3, cmake, ninja, java $java_major: OK"

# --------------------------------------------------------------------------
# 1. Clone the tool repositories (existing clones are fast-forwarded so
#    upstream fixes arrive on re-runs)
# --------------------------------------------------------------------------
step "Cloning repositories"
clone_or_update() {
    local dir=$1 branch=$2 url=$3
    if [ -d "$dir" ]; then
        git -C "$dir" pull --ff-only ||
            echo "warning: could not fast-forward $dir; leaving it as-is"
    else
        git clone --branch "$branch" "$url"
    fi
}
clone_or_update sls-reachability cvc5 \
    https://github.com/mudathirmahgoub/sls-reachability.git
clone_or_update SQLSolver cvc5 \
    https://github.com/mudathirmahgoub/SQLSolver.git
clone_or_update cvc5 liastar \
    https://github.com/mudathirmahgoub/cvc5.git

# --------------------------------------------------------------------------
# 2. Build cvc5 (the liastar branch; ~30-60 minutes on first run)
# --------------------------------------------------------------------------
if [ -x cvc5/build/install/bin/cvc5 ]; then
    step "cvc5 already built (cvc5/build/install/bin/cvc5) -- skipping"
else
    step "Building cvc5"
    (
        cd cvc5
        ./configure.sh production --prefix=build/install --tracing --ninja \
            --auto-download --all-bindings --normaliz
        cd build
        ninja install
    )
fi

# --------------------------------------------------------------------------
# 3. Python virtual environment inside sls-reachability
#    (z3 for lia_star_solver.py, the freshly built cvc5 wheel for
#    smt_to_sls.py, pandas/matplotlib for plot.py)
# --------------------------------------------------------------------------
step "Preparing sls-reachability/.venv"
[ -x sls-reachability/.venv/bin/python3 ] || python3 -m venv sls-reachability/.venv
sls-reachability/.venv/bin/pip install --quiet --upgrade pip
sls-reachability/.venv/bin/pip install --quiet \
    z3-solver==4.16.0.0 pandas numpy matplotlib

wheel=$(ls cvc5/build/repaired-wheel/*.whl 2>/dev/null | head -1 || true)
if [ -z "$wheel" ]; then
    echo "error: no wheel found in cvc5/build/repaired-wheel/ -- the cvc5" >&2
    echo "build should have produced one (python bindings enabled by" >&2
    echo "--all-bindings). Inspect the cvc5 build output." >&2
    exit 1
fi
sls-reachability/.venv/bin/pip install --quiet --force-reinstall "$wheel"

# --------------------------------------------------------------------------
# 4. SQLSolver: on Linux, refresh the bundled cvc5 java bindings with the
#    freshly built, platform-matching ones (the repository ships
#    macOS-tested libraries); then compile the test classes.
# --------------------------------------------------------------------------
if [ "$(uname -s)" = "Linux" ]; then
    step "Refreshing SQLSolver cvc5 java bindings for Linux"
    # build.gradle expects the jar under the name cvc5-1.3.4
    cp cvc5/build/install/share/java/cvc5.jar SQLSolver/lib/cvc5-1.3.4.jar
    cp -a cvc5/build/install/lib/libcvc5*.so* SQLSolver/lib/ 2>/dev/null || true
    cp -a cvc5/build/install/lib/*.so* SQLSolver/lib/ 2>/dev/null || true
fi

step "Compiling SQLSolver test classes"
(cd SQLSolver && ./gradlew :superopt:testClasses --console=plain)

step "Setup complete"
