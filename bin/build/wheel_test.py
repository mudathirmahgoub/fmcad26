#!/usr/bin/env python3
"""Solve benchmarks through an installed cvc5 wheel and compare the answers
with comparison.csv's cvc5 column.

    python wheel_test.py FMCAD_DIR TLIMIT_S [BENCHMARK ...]

Without BENCHMARK names it runs every benchmark the recorded cvc5 solved
within 1 second.
"""
import csv
import os
import platform
import sys

import cvc5

fmcad, tlimit = sys.argv[1], int(sys.argv[2])
with open(os.path.join(fmcad, "comparison.csv"), newline="") as f:
    rows = [(r[3].strip(), r[4].strip(), float(r[5] or 0))
            for r in list(csv.reader(f))[1:]]
wanted = set(sys.argv[3:])
rows = [(b, e) for b, e, d in rows
        if (b in wanted if wanted else e in ("sat", "unsat") and d < 1)]


def solve(path):
    tm = cvc5.TermManager()
    solver = cvc5.Solver(tm)
    solver.setOption("tlimit", str(tlimit * 1000))
    parser = cvc5.InputParser(solver)
    parser.setFileInput(cvc5.InputLanguage.SMT_LIB_2_6, path)
    symbols = parser.getSymbolManager()
    answer = "unknown"
    while True:
        cmd = parser.nextCommand()
        if cmd.isNull():
            break
        if str(cmd).strip() == "(check-sat)":
            r = solver.checkSat()
            answer = "sat" if r.isSat() else "unsat" if r.isUnsat() else "unknown"
        else:
            cmd.invoke(solver, symbols)
    return answer


print("python", platform.machine(), "cvc5", cvc5.__file__)
bad = [(b, e, a) for b, e in rows
       for a in [solve(os.path.join(fmcad, "benchmarks", b))] if a != e]
print("{} benchmarks, {} disagreements".format(len(rows), len(bad)))
for x in bad[:10]:
    print("  ", *x)
sys.exit(1 if bad else 0)
