#!/bin/bash
# Rebuild the cvc5 files in bin/ (cvc5 main 967404925f, GPL build with
# Normaliz) on an arm64 Mac. See README.md next to this script.
#
#   bin/build/build.sh TARGET        TARGET: mac-arm64 mac-x86_64
#                                    win64-x86_64 win64-arm64 py-arm64 py-x86_64
#   bin/build/build.sh collect DIR   copy the results into DIR under bin/ names
#
# Environment: CVC5_SRC (cvc5 checkout, default ./cvc5-967404925f; cloned and
# patched if missing), CVC5_REPO (clone URL), LLVM_MINGW (llvm-mingw's bin/
# directory, for win64-*), J (parallel jobs, default 8).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
COMMIT=967404925f557ace252fb1cc14a37c5894c90ec9
SRC=${CVC5_SRC:-$PWD/cvc5-967404925f}
J=${J:-8}

prepare() {
  [ -d "$SRC" ] && return
  git clone "${CVC5_REPO:-https://github.com/cvc5/cvc5.git}" "$SRC"
  # branch name main, so the version reads 1.4.3.dev+main@967404925f-modified
  git -C "$SRC" checkout -B main $COMMIT
  git -C "$SRC" apply "$HERE/cross.patch"
  cp "$HERE"/Toolchain-*.cmake "$SRC/cmake/"
}

build() {
  local t=$1
  local static="unrestricted --static --auto-download --gpl --normaliz --ninja --name=build-$t"
  local shared="unrestricted --auto-download --gpl --normaliz --python-bindings --ninja --name=build-$t --prefix=$SRC/build-$t/install"
  local mac_x86="-DCMAKE_TOOLCHAIN_FILE=$SRC/cmake/Toolchain-x86_64-macos.cmake"
  # run on macOS 11+, not only on the build host's macOS; exported so the
  # autotools-built dependencies pick it up too
  case $t in mac-*|py-*) export MACOSX_DEPLOYMENT_TARGET=11.0 ;; esac
  case $t in win64-*) export PATH="${LLVM_MINGW:?set LLVM_MINGW to llvm-mingw/bin}:$PATH" ;; esac
  if [ "$t" = py-x86_64 ]; then
    # setup.py takes the target arch from these (it assumes arm64 when
    # cross-compiling); libtool's partial link `$CC -r` of C++ shared
    # libraries gets no flags, so the arch must be in $CC itself
    export ARCHFLAGS="-arch x86_64" _PYTHON_HOST_PLATFORM=macosx-11.0-x86_64
    export CC="cc -arch x86_64" CXX="c++ -arch x86_64"
  fi
  cd "$SRC"
  case $t in
    mac-arm64)    ./configure.sh $static --java-bindings ;;
    mac-x86_64)   ./configure.sh $static --java-bindings $mac_x86 ;;
    win64-x86_64) ./configure.sh $static --static-binary --win64 ;;
    win64-arm64)  ./configure.sh $static --static-binary \
                    -DCMAKE_TOOLCHAIN_FILE=$SRC/cmake/Toolchain-mingw-arm64.cmake ;;
    py-arm64)     ./configure.sh $shared ;;
    py-x86_64)    ./configure.sh $shared $mac_x86 ;;
    *) echo "unknown target $t" >&2; exit 2 ;;
  esac
  cd "build-$t"
  case $t in
    py-*) ninja -j"$J" install ;;  # leaves the wheel in build-$t/repaired-wheel/
    *)    ninja -j"$J" ;;
  esac
}

collect() {
  local out=$1 tmp
  mkdir -p "$out"
  cp "$SRC/build-mac-arm64/bin/cvc5" "$out/cvc5-static-mac-arm64"
  cp "$SRC/build-mac-x86_64/bin/cvc5" "$out/cvc5-static-mac-x86_64"
  cp "$SRC/build-win64-x86_64/bin/cvc5.exe" "$out/cvc5-win64-x86_64.exe"
  cp "$SRC/build-win64-arm64/bin/cvc5.exe" "$out/cvc5-win64-arm64.exe"
  cp "$SRC/build-mac-arm64/src/api/java/cvc5.jar" "$out/cvc5.jar"
  # one jar with the JNI library of both macOS arches
  tmp=$(mktemp -d)
  (cd "$tmp" && unzip -q -o "$SRC/build-mac-arm64/src/api/java/cvc5-osx-aarch_64.jar" \
             && unzip -q -o "$SRC/build-mac-x86_64/src/api/java/cvc5-osx-x86_64.jar" \
             && jar --create --file "$out/cvc5-osx-universal.jar" \
                    --manifest META-INF/MANIFEST.MF -C . cvc5-libs)
  rm -rf "$tmp"
  python3 "$HERE/fuse_wheels.py" "$SRC"/build-py-arm64/repaired-wheel/*.whl \
    "$SRC"/build-py-x86_64/repaired-wheel/*.whl "$out"
  cp "$SRC/COPYING" "$out/cvc5 license"
}

case ${1:-} in
  collect) collect "$(mkdir -p "${2:?usage: build.sh collect DIR}" && cd "$2" && pwd)" ;;
  "")      sed -n 2,11p "$0"; exit 2 ;;
  *)       prepare; build "$1" ;;
esac
