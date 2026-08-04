#!/usr/bin/env python3

"""
Render the paper's result-summary table from comparison.csv.

    python3 latex_table.py [comparison.csv]

For every configuration the sat / unsat / timeout / unknown results are
counted over all benchmark rows and printed as LaTeX table rows (using the
paper's \\cvc, \\sqlSolver and \\slsReachability macros). The \\unknown
cell is left out of rows that have no unknown results, matching the paper.
The table is written to stdout and to comparison_table.tex next to the
input csv.
"""

import csv
import os
import sys

# (comparison.csv result-column header, LaTeX row label), in table order
ROWS = [
    ("cvc5 result",               "\\cvc"),
    ("sqlsolver result",          "\\sqlSolver"),
    ("modified_sqlsolver result", "Modified \\sqlSolver"),
    ("unfold5 result",            "\\slsReachability (unfold-5)"),
    ("unfold0 result",            "\\slsReachability (unfold-0)"),
    ("no_interp result",          "\\slsReachability (no-interpolation)"),
]


def latex_table(csv_path):
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))

    lines = ["\\toprule",
             "Solver & \\sat & \\unsat & \\timeout & \\unknown \\\\",
             "\\midrule"]
    for column, label in ROWS:
        counts = {}
        for row in rows:
            result = (row.get(column) or "").strip()
            if not result:  # configuration not run yet
                continue
            counts[result] = counts.get(result, 0) + 1
        unaccounted = {r: n for r, n in counts.items()
                       if r not in ("sat", "unsat", "timeout", "unknown")}
        if unaccounted:
            print("WARNING: {}: {} results not in the table: {}".format(
                column, sum(unaccounted.values()), unaccounted),
                file=sys.stderr)
        cells = [str(counts.get("sat", 0)), str(counts.get("unsat", 0)),
                 str(counts.get("timeout", 0))]
        if counts.get("unknown"):
            cells.append(str(counts["unknown"]))
        lines.append("{} & {} \\\\".format(label, " & ".join(cells)))
    lines.append("\\bottomrule")
    return "\n".join(lines) + "\n"


def main():
    csv_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "comparison.csv")
    table = latex_table(csv_path)
    tex_path = os.path.join(os.path.dirname(os.path.abspath(csv_path)),
                            "comparison_table.tex")
    with open(tex_path, "w") as f:
        f.write(table)
    sys.stdout.write(table)
    print("\nwrote {}".format(tex_path), file=sys.stderr)


if __name__ == "__main__":
    main()
