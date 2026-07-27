#!/usr/bin/env python3
"""Per smt2 file: number of ite expressions, and a lower-bound estimate of
the disjuncts their elimination forces (ignoring or/=>-induced splits).

    python3 count_ite.py FILE.smt2 [FILE.smt2 ...]

Standalone -- not part of the run.py pipeline. E.g. to analyze the cvc5
timeouts of comparison.csv:

    python3 count_ite.py $(python3 -c "import csv; print(' '.join(
        'benchmarks/'+r[3] for r in list(csv.reader(open('comparison.csv')))[1:]
        if r[4]=='timeout'))")

Counting rules (sharing-aware "least" estimate):
  cases(atom)          = 1
  cases(ite c a b)     = cases(c) * (cases(a) + cases(b))
  cases(f t1 .. tn)    = prod cases(ti)     -- and, =, arithmetic, lambda...
  cases(let ((x tx)..) = prod cases(tx_i) * cases(body), x free in body
A repeated identical subterm only pays its splits on first occurrence
(memoized on its printed form), so textually duplicated ites -- as produced
by min/max encodings -- are split once, and asserts multiply (conjunction).
"""

import sys


def tokenize(text):
    out = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == ';':
            while i < n and text[i] != '\n':
                i += 1
        elif c in '()':
            out.append(c)
            i += 1
        elif c.isspace():
            i += 1
        elif c == '|':
            j = text.index('|', i + 1)
            out.append(text[i:j + 1])
            i = j + 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '();':
                j += 1
            out.append(text[i:j])
            i = j
    return out


def parse(tokens):
    pos = 0

    def read():
        nonlocal pos
        tok = tokens[pos]
        pos += 1
        if tok != '(':
            return tok
        lst = []
        while tokens[pos] != ')':
            lst.append(read())
        pos += 1
        return lst

    exprs = []
    while pos < len(tokens):
        exprs.append(read())
    return exprs


def render(t):
    return t if isinstance(t, str) else '(' + ' '.join(map(render, t)) + ')'


def analyze(path):
    with open(path) as f:
        exprs = parse(tokenize(f.read()))

    def count_ites(t):
        if isinstance(t, str) or not t:
            return 0
        me = 1 if t[0] == 'ite' and len(t) == 4 else 0
        return me + sum(count_ites(c) for c in t)

    memo = {}

    def cases(t, env):
        if isinstance(t, str):
            return 1
        if not t:
            return 1
        head = t[0]
        if head == 'ite' and len(t) == 4:
            key = render(t)
            if key in memo:
                return 1
            n = cases(t[1], env) * (cases(t[2], env) + cases(t[3], env))
            memo[key] = n
            return n
        if head == 'let':
            n = 1
            for _, bound in t[1]:
                n *= cases(bound, env)
            return n * cases(t[2], env)
        if head in ('forall', 'exists', 'lambda'):
            return cases(t[2], env)
        if head == '!':  # annotations
            return cases(t[1], env)
        return_val = 1
        for child in (t if isinstance(head, list) else t[1:]):
            return_val *= cases(child, env)
        return return_val

    total, n_ites = 1, 0
    for e in exprs:
        if isinstance(e, list) and e and e[0] == 'assert':
            n_ites += count_ites(e[1])
            total *= cases(e[1], {})
    return n_ites, total


def main():
    print("{:<35} {:>5} {:>22}".format("file", "ites", "least disjuncts"))
    for path in sys.argv[1:]:
        n_ite, est = analyze(path)
        name = "/".join(path.split("/")[-3:])
        print("{:<35} {:>5} {:>22}".format(name, n_ite, est))


if __name__ == "__main__":
    main()
