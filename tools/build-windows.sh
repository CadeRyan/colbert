#!/usr/bin/env bash
# Build the Windows engine inside MSYS2 (UCRT64). "Start Colbert.bat" runs this; it can also be
# run by hand from an MSYS2 UCRT64 shell. Copies the engine and the DLLs it needs into
# app/engine/, so the app can run it from an ordinary Windows window.
set -euo pipefail
cd "$(dirname "$0")/.."
pacman -S --needed --noconfirm make git mingw-w64-ucrt-x86_64-gcc mingw-w64-ucrt-x86_64-gmp \
  mingw-w64-ucrt-x86_64-opencl-icd mingw-w64-ucrt-x86_64-opencl-headers >/dev/null
make -s -k colbert colbert-cpu || true
mkdir -p app/engine
for exe in colbert.exe colbert-cpu.exe; do
  [ -f "$exe" ] || continue
  cp "$exe" app/engine/
  # MinGW runtime, GMP, OpenMP and the Khronos OpenCL loader
  for dll in $(ldd "$exe" | awk '/ucrt64/ {print $3}'); do cp -u "$dll" app/engine/; done
done
ls app/engine/colbert*.exe >/dev/null
