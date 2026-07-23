#!/usr/bin/env python3
"""
One-time (idempotent) setup for the fmcad experiments: clones the three
tool repositories next to this script, builds cvc5, prepares the python
virtual environment inside sls-reachability, and compiles the SQLSolver
test classes. Everything lives under this directory; safe to re-run --
completed steps are skipped.

Works on Linux, macOS and Windows. On Windows run it inside an MSYS2
environment (e.g. the clang64 shell) so that bash, cmake and ninja are
available for the cvc5 build; the JDK can be a native Windows one.

Requirements (see README.md): git, python 3.9+ (with venv), a C++
compiler, cmake, ninja, JDK 21+.
"""

import glob
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
WINDOWS = os.name == "nt"

REPOSITORIES = [
    ("sls-reachability", "cvc5",
     "https://github.com/mudathirmahgoub/sls-reachability.git"),
    ("SQLSolver", "cvc5",
     "https://github.com/mudathirmahgoub/SQLSolver.git"),
    ("cvc5", "liastar",
     "https://github.com/mudathirmahgoub/cvc5.git"),
]


def step(title):
    print("\n=== {} ===".format(title), flush=True)


def run(cmd, cwd=ROOT):
    subprocess.run(cmd, cwd=cwd, check=True)


def venv_python():
    """The interpreter of the sls-reachability virtual environment
    (bin/python3 on POSIX, Scripts/python.exe on Windows)."""
    if WINDOWS:
        return os.path.join(ROOT, "sls-reachability", ".venv",
                            "Scripts", "python.exe")
    return os.path.join(ROOT, "sls-reachability", ".venv", "bin", "python3")


def cvc5_binary():
    return os.path.join(ROOT, "cvc5", "build", "install", "bin",
                        "cvc5.exe" if WINDOWS else "cvc5")


def check_prerequisites():
    """Fail fast on missing tools, before the long cvc5 build."""
    step("Checking prerequisites")
    tools = ["git", "cmake", "ninja", "java"] + (["bash"] if WINDOWS else [])
    missing = [t for t in tools if shutil.which(t) is None]
    if missing:
        sys.exit("error: not found on PATH: {} -- see README.md".format(
            ", ".join(missing)))

    out = subprocess.run(["java", "-version"], capture_output=True)
    text = (out.stderr + out.stdout).decode()
    match = re.search(r'version "(\d+)', text)
    major = int(match.group(1)) if match else 0
    if major < 21:
        sys.exit(
            "error: SQLSolver targets Java 21, but 'java' on PATH is\n"
            "       version {}. Please install JDK 21 or newer and make\n"
            "       it the default:\n"
            "  Debian/Ubuntu: sudo apt install openjdk-21-jdk\n"
            "                 sudo update-alternatives --config java\n"
            "  macOS:         brew install openjdk\n"
            "  Windows:       https://adoptium.net".format(major or "unknown"))
    print("git, cmake, ninja{}, java {}: OK".format(
        ", bash" if WINDOWS else "", major))


def clone_or_update():
    """Clone the tool repositories; existing clones are fast-forwarded so
    upstream fixes arrive on re-runs."""
    step("Cloning repositories")
    for directory, branch, url in REPOSITORIES:
        path = os.path.join(ROOT, directory)
        if os.path.isdir(path):
            result = subprocess.run(["git", "pull", "--ff-only"], cwd=path)
            if result.returncode != 0:
                print("warning: could not fast-forward {}; leaving it "
                      "as-is".format(directory))
        else:
            run(["git", "clone", "--branch", branch, url])


def build_cvc5():
    """Build cvc5 (the liastar branch; ~30-60 minutes on first run)."""
    if os.path.exists(cvc5_binary()):
        step("cvc5 already built ({}) -- skipping".format(
            os.path.relpath(cvc5_binary(), ROOT)))
        return
    step("Building cvc5")
    cvc5_dir = os.path.join(ROOT, "cvc5")
    # configure.sh is a bash script; invoking it through bash works on
    # every platform (on Windows: the MSYS2 bash)
    run(["bash", "configure.sh", "production", "--prefix=build/install",
         "--tracing", "--ninja", "--auto-download", "--all-bindings",
         "--normaliz"], cwd=cvc5_dir)
    run(["ninja", "install"], cwd=os.path.join(cvc5_dir, "build"))


def prepare_venv():
    """Python virtual environment inside sls-reachability: z3 for
    lia_star_solver.py, the freshly built cvc5 wheel for smt_to_sls.py,
    pandas/matplotlib for plot.py."""
    step("Preparing sls-reachability/.venv")
    python = venv_python()
    if not os.path.exists(python):
        run([sys.executable, "-m", "venv",
             os.path.join(ROOT, "sls-reachability", ".venv")])
    run([python, "-m", "pip", "install", "--quiet", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "--quiet",
         "z3-solver==4.16.0.0", "pandas", "numpy", "matplotlib"])

    wheels = glob.glob(os.path.join(ROOT, "cvc5", "build",
                                    "repaired-wheel", "*.whl"))
    if not wheels:
        sys.exit("error: no wheel found in cvc5/build/repaired-wheel/ -- "
                 "the cvc5 build should have produced one (python bindings "
                 "enabled by --all-bindings). Inspect the cvc5 build output.")
    run([python, "-m", "pip", "install", "--quiet", "--force-reinstall",
         wheels[0]])


def install_java_bindings():
    """Install the cvc5 java bindings that the cvc5 build just produced
    (jar + JNI library + shared libraries) into SQLSolver/lib. No
    pre-existing cvc5 binding files are assumed on any platform; the jar
    goes under the name cvc5-1.3.4 that build.gradle expects."""
    step("Installing the built cvc5 java bindings into SQLSolver/lib")
    install = os.path.join(ROOT, "cvc5", "build", "install")
    lib = os.path.join(ROOT, "SQLSolver", "lib")
    shutil.copy2(os.path.join(install, "share", "java", "cvc5.jar"),
                 os.path.join(lib, "cvc5-1.3.4.jar"))
    for subdir, pattern in [("lib", "*.dylib"), ("lib", "*.so*"),
                            ("lib", "*.dll"), ("bin", "*.dll")]:
        for src in glob.glob(os.path.join(install, subdir, pattern)):
            dst = os.path.join(lib, os.path.basename(src))
            if os.path.lexists(dst):
                os.remove(dst)
            shutil.copy2(src, dst, follow_symlinks=False)


def compile_sqlsolver():
    step("Compiling SQLSolver test classes")
    sqlsolver = os.path.join(ROOT, "SQLSolver")
    gradlew = os.path.join(sqlsolver,
                           "gradlew.bat" if WINDOWS else "gradlew")
    run([gradlew, ":superopt:testClasses", "--console=plain"],
        cwd=sqlsolver)


def main():
    check_prerequisites()
    clone_or_update()
    build_cvc5()
    prepare_venv()
    install_java_bindings()
    compile_sqlsolver()
    step("Setup complete")


if __name__ == "__main__":
    main()
