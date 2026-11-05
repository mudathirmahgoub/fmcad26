#!/usr/bin/env python3
"""Fuse an arm64 and an x86_64 macOS wheel into one universal2 wheel.

    python3 fuse_wheels.py ARM64.whl X86_64.whl OUT_DIR

Both wheels must contain the same files. Mach-O files are combined with
`lipo -create`; every other file must be byte-identical (except WHEEL,
whose tag becomes universal2). RECORD is regenerated.

The input file names' platform tags are ignored: the output tag is
macosx_<max minos of all Mach-O files>_universal2, and every Mach-O file
must be single-arch arm64 / x86_64 in the respective input.
"""
import base64
import filecmp
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import zipfile

MACHO = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf",
         b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}
NAME = re.compile(r"(.*)-macosx_\d+_\d+_\w+\.whl$")


def is_macho(path):
    with open(path, "rb") as f:
        return f.read(4) in MACHO


def archs(path):
    return subprocess.run(["lipo", "-archs", path], check=True,
                          capture_output=True, text=True).stdout.split()


def minos(path):
    out = subprocess.run(["otool", "-l", path], check=True,
                         capture_output=True, text=True).stdout
    # LC_BUILD_VERSION's minos (its tool entries also have "version" lines)
    vers = re.findall(r"^\s*minos (\d+)\.(\d+)", out, re.M)
    if not vers:
        sys.exit("no LC_BUILD_VERSION minos in " + path)
    return max((int(a), int(b)) for a, b in vers)


def files(root):
    return {os.path.relpath(os.path.join(d, f), root)
            for d, _, fs in os.walk(root) for f in fs}


def main():
    arm, x86, out = sys.argv[1:4]
    ma, mx = NAME.match(os.path.basename(arm)), NAME.match(os.path.basename(x86))
    assert ma and mx and ma.group(1) == mx.group(1), (arm, x86)

    tmp = tempfile.mkdtemp()
    da, dx, du = (os.path.join(tmp, d) for d in ("arm64", "x86_64", "u"))
    zipfile.ZipFile(arm).extractall(da)
    zipfile.ZipFile(x86).extractall(dx)
    fa, fx = files(da), files(dx)
    if fa != fx:
        sys.exit("file sets differ: only arm64 {}, only x86_64 {}".format(
            sorted(fa - fx), sorted(fx - fa)))

    record = next(f for f in fa if f.endswith(".dist-info/RECORD"))
    machos = sorted(f for f in fa if is_macho(os.path.join(da, f)))
    for rel in machos:
        a, x = os.path.join(da, rel), os.path.join(dx, rel)
        if archs(a) != ["arm64"] or archs(x) != ["x86_64"]:
            sys.exit("{}: archs {} / {}".format(rel, archs(a), archs(x)))
    major, minor = max(minos(os.path.join(d, rel))
                       for rel in machos for d in (da, dx))
    plat = "macosx_{}_{}_universal2".format(major, minor)
    for rel in sorted(fa - {record}):
        a, x, u = (os.path.join(d, rel) for d in (da, dx, du))
        os.makedirs(os.path.dirname(u), exist_ok=True)
        if is_macho(a):
            # drop absolute LC_RPATHs left from the build tree (dependencies
            # resolve via @loader_path/.dylibs), then re-sign each slice
            for f in (a, x):
                lc = subprocess.run(["otool", "-l", f], check=True,
                                    capture_output=True, text=True).stdout
                for path in re.findall(r"cmd LC_RPATH\n.*\n\s*path (/\S+)", lc):
                    subprocess.run(["install_name_tool", "-delete_rpath", path, f],
                                   check=True, capture_output=True)
                subprocess.run(["codesign", "-f", "-s", "-", f], check=True,
                               capture_output=True)
            subprocess.run(["lipo", "-create", a, x, "-output", u], check=True)
            os.chmod(u, os.stat(a).st_mode)
        elif rel.endswith(".dist-info/WHEEL"):
            text = open(a).read()
            text = re.sub(r"macosx_\d+_\d+_\w+", plat, text)
            open(u, "w").write(text)
        else:
            if not filecmp.cmp(a, x, shallow=False):
                sys.exit("non-binary file differs between arches: " + rel)
            with open(a, "rb") as src, open(u, "wb") as dst:
                dst.write(src.read())

    lines = []
    for rel in sorted(fa - {record}):
        data = open(os.path.join(du, rel), "rb").read()
        digest = base64.urlsafe_b64encode(
            hashlib.sha256(data).digest()).rstrip(b"=").decode()
        lines.append("{},sha256={},{}".format(rel, digest, len(data)))
    lines.append(record + ",,")
    open(os.path.join(du, record), "w").write("\n".join(lines) + "\n")

    os.makedirs(out, exist_ok=True)
    wheel = os.path.join(out, "{}-{}.whl".format(ma.group(1), plat))
    with zipfile.ZipFile(wheel, "w", zipfile.ZIP_DEFLATED) as z:
        # dist-info last, RECORD very last (wheel convention)
        for rel in sorted(fa, key=lambda r: (".dist-info/" in r, r == record, r)):
            z.write(os.path.join(du, rel), rel)
    print(wheel)


if __name__ == "__main__":
    main()
