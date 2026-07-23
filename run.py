#!/usr/bin/env python3
"""
The single entry point: installs everything (idempotent -- see setup.py),
runs all experiments, writes comparison.csv into this directory, and
renders the paper plots from it.

    python3 run.py                  # full run: 3 sections x 6 configurations
    python3 run.py --only sql       # any update_comparison.py options pass through

Works on Linux, macOS and Windows (see setup.py for the Windows notes). A
full fresh run takes 1-2 hours of experiments on top of the one-time cvc5
build (~30-60 minutes).
"""

import os
import subprocess
import sys

import setup

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    setup.main()

    python = setup.venv_python()
    subprocess.run(
        [python, os.path.join(ROOT, "update_comparison.py")] + sys.argv[1:],
        check=True)

    # plot.py reads comparison.csv from the current directory and writes
    # cactus_plot.png and the scatter plots next to it
    subprocess.run([python, os.path.join(ROOT, "plot.py")], cwd=ROOT,
                   check=True)

    print("\nDone: comparison.csv, cactus_plot.png, scatter_*.png")


if __name__ == "__main__":
    main()
