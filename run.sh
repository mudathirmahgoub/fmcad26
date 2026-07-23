#!/usr/bin/env bash
#
# The single entry point: installs everything (idempotent -- see setup.sh),
# runs all experiments, writes comparison.csv into this directory, and
# renders the paper plots from it.
#
#   ./run.sh                  # full run: 3 sections x 6 configurations
#   ./run.sh --only sql       # any update_comparison.py options pass through
#
# A full fresh run takes 1-2 hours of experiments on top of the one-time
# cvc5 build (~30-60 minutes).

set -euo pipefail
cd "$(cd "$(dirname "$0")" && pwd)"

./setup.sh

PYTHON=sls-reachability/.venv/bin/python3

"$PYTHON" update_comparison.py "$@"

# plot.py reads comparison.csv from the current directory and writes
# cactus_plot.png and the scatter plots next to it
"$PYTHON" plot.py

echo
echo "Done: comparison.csv, cactus_plot.png, scatter_*.png"
