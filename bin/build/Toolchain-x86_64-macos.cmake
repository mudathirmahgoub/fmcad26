# Toolchain file for building for x86_64 macOS on an arm64 Mac (mirrors the
# Darwin branch of Toolchain-aarch64.cmake).
#
# Use: cmake .. -DCMAKE_TOOLCHAIN_FILE=../cmake/Toolchain-x86_64-macos.cmake

set(CMAKE_SYSTEM_NAME Darwin)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

set(TOOLCHAIN_PREFIX x86_64-apple-darwin)

set(CMAKE_CROSSCOMPILING_MACOS TRUE)
set(CMAKE_OSX_ARCHITECTURES x86_64 CACHE INTERNAL "")
