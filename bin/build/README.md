# How the files in `bin/` were built

All from cvc5 `main` `967404925f` with `--gpl --normaliz` (cvc5's nightly
builds have no Normaliz, which the LIA\* solver needs), on an arm64 Mac
with macOS 11.0 as the minimum macOS:

```bash
for t in mac-arm64 mac-x86_64 py-arm64 py-x86_64; do bin/build/build.sh $t; done
LLVM_MINGW=~/toolchains/llvm-mingw-20260616-ucrt-macos-universal/bin bin/build/build.sh win64-x86_64
LLVM_MINGW=~/toolchains/llvm-mingw-20260616-ucrt-macos-universal/bin bin/build/build.sh win64-arm64
bin/build/build.sh collect bin/
```

`cvc5-static-linux-x86_64` was built on Ubuntu 24.04 by GitHub Actions
with `static-linux.yml`: in a cvc5 fork, put it in `.github/workflows/`
and `cross.patch` + `validate.py` in `.github/fmcad26/` on a branch named
`fmcad26-static-linux`, then push that branch. (Its shallow checkout makes
the binary print the short hash: `1.4.3.dev+main@9674049-modified`.)

| file | purpose |
|---|---|
| `cross.patch` | build-system fixes, the reason for `-modified` in the version: CaDiCaL archived with the target's `ar` when cross-compiling; Normaliz's static link keeps the bundled GMP's `-L`; Poly's Windows patch script runs under `LC_ALL=C` |
| `Toolchain-*.cmake` | cross-compiling to Windows arm64 and to macOS x86_64 |
| `static-linux.yml` | the GitHub Actions job behind the Linux binary (also checks its answers) |
| `fuse_wheels.py` | merges the arm64 and x86_64 wheels into one universal2 wheel |
| `validate.py`, `wheel_test.py` | check a binary / an installed wheel against the recorded cvc5 answers in `comparison.csv` |

Checking a binary, e.g. (no sat/unsat disagreement expected; timeouts
depend on the machine):

```bash
python3 bin/build/validate.py . 10 4 bin/cvc5-static-mac-arm64
# answers: {'sat': 280, 'unsat': 199, 'timeout': 30}
# sat/unsat disagreements: 0
```
