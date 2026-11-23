#!/usr/bin/env bash
# The Linux download: dist/Colbert as a .tar.gz, which keeps the executable bits a zip can lose.
#
#   tools/package-linux.sh dist/Colbert Colbert-Linux-x64.tar.gz
set -euo pipefail
DIST=$1
OUT=$2
HERE=$(cd "$(dirname "$0")" && pwd)

cp "$HERE/../app/icons/colbert.png" "$DIST/colbert.png"
cat > "$DIST/README.txt" <<'EOF'
Colbert for Linux (x86-64)

Start it:      ./Colbert
               It opens the app in your web browser. Quit from the app, or with Ctrl-C.

Servers:       ./Colbert --headless --owner YOURNAME
               joins the project and works without a window (more options: ./Colbert --help).

Graphics cards need their OpenCL driver (NVIDIA: the proprietary driver; AMD: ROCm;
Intel: intel-opencl-icd) and the OpenCL loader (ocl-icd-libopencl1, or your
distribution's equivalent). Without them Colbert uses the CPU: that works, but slowly.

Source code and documentation: https://github.com/CadeRyan/colbert
EOF
tar -C "$(dirname "$DIST")" -czf "$OUT" "$(basename "$DIST")"
