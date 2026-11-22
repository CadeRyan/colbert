#!/usr/bin/env bash
# What "Start Colbert.command" (macOS) and "Start Colbert.sh" (Linux) run: make sure Python and
# an up-to-date engine are there, then open the app. Safe to run any number of times; after the
# first run it only checks for updates and starts the app.
#
# Set COLBERT_NO_UPDATE=1 to skip the update check. Arguments are passed to the app
# (for example --headless, see docs/APP.md).
set -u
cd "$(dirname "$0")/.." || exit 1
OS=$(uname -s)

finish() {
  echo
  read -r -p "Press Enter to close this window. " _ </dev/tty 2>/dev/null || true
  exit "${1:-0}"
}
ask() {
  local a
  read -r -p "$1 [Y/n] " a </dev/tty 2>/dev/null || a=n
  case "$a" in ""|y|Y|yes|Yes) return 0 ;; *) return 1 ;; esac
}
has() { command -v "$1" >/dev/null 2>&1; }

echo "== Colbert =="

# ---------------------------------------------------------------- Python 3.8+
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then
  echo "Colbert needs Python 3.8 or newer."
  if [ "$OS" = Darwin ]; then
    echo "macOS will now offer to install Apple's command line tools, which include Python."
    echo "When that has finished, start Colbert again."
    xcode-select --install >/dev/null 2>&1
  elif has apt-get; then
    echo "Install it with:  sudo apt-get install python3"
  else
    echo "Install Python 3 with your system's package manager, then start Colbert again."
  fi
  finish 1
fi

# ---------------------------------------------------------------- updates
if [ -z "${COLBERT_NO_UPDATE:-}" ] && [ -d .git ] && has git; then
  # only a clean checkout that tracks a remote branch is updated, and only fast-forward
  if [ -z "$(git status --porcelain --untracked-files=no 2>/dev/null)" ] && git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
    echo "Checking for updates..."
    before=$(git rev-parse HEAD)
    GIT_TERMINAL_PROMPT=0 git pull --ff-only --quiet >/dev/null 2>&1 || echo "  (couldn't check; carrying on with this version)"
    [ "$(git rev-parse HEAD)" != "$before" ] && echo "  Updated to $(git describe --always --tags)."
  fi
fi

# ---------------------------------------------------------------- engine
have_engine() { [ -x ./colbert ] || [ -x ./colbert-cpu ] || ls app/engine/colbert* >/dev/null 2>&1; }

deps_ok() {
  if [ "$OS" = Darwin ]; then
    xcode-select -p >/dev/null 2>&1 && has brew && [ -d "$(brew --prefix)/opt/gmp" ] && [ -d "$(brew --prefix)/opt/libomp" ]
  else
    has make && has g++ && echo '#include <gmpxx.h>' | g++ -E -x c++ - >/dev/null 2>&1
  fi
}

install_deps() {
  if [ "$OS" = Darwin ]; then
    if ! xcode-select -p >/dev/null 2>&1; then
      echo "Building the engine needs Apple's command line tools. macOS will now offer to install them;"
      echo "when that has finished, start Colbert again."
      xcode-select --install >/dev/null 2>&1
      return 1
    fi
    if ! has brew; then
      echo "Building the engine needs two small libraries from Homebrew (https://brew.sh)."
      echo "Install Homebrew with the one command on that page, then start Colbert again."
      open https://brew.sh >/dev/null 2>&1
      return 1
    fi
    ask "Install the libraries the engine needs (brew install gmp libomp)?" && brew install gmp libomp
  elif has apt-get; then
    ask "Install what the engine needs to build (sudo apt-get install build-essential libgmp-dev ocl-icd-opencl-dev opencl-headers)? You'll be asked for your password." &&
      sudo apt-get install -y build-essential libgmp-dev ocl-icd-opencl-dev opencl-headers
  elif has dnf; then
    ask "Install what the engine needs to build (sudo dnf install gcc-c++ make gmp-devel ocl-icd-devel opencl-headers)?" &&
      sudo dnf install -y gcc-c++ make gmp-devel ocl-icd-devel opencl-headers
  else
    echo "Install a C++ compiler, make, and the GMP development package (see docs/SETUP.md), then start Colbert again."
    return 1
  fi
}

if [ -f Makefile ]; then
  if ! deps_ok; then
    if have_engine; then
      echo "Can't rebuild the engine on this computer, so using the one already here."
    else
      echo "First run: the engine has to be built on this computer (a minute or two)."
      install_deps || finish 1
      deps_ok || { echo "The build tools are still missing; see docs/SETUP.md."; finish 1; }
    fi
  fi
  if deps_ok; then
    echo "Building the engine if anything changed..."
    # -k: if the GPU (OpenCL) build fails, the CPU-only build still gets made
    if ! make -s -k colbert colbert-cpu >build.log 2>&1; then
      if have_engine; then
        echo "  Part of the build failed (details in build.log); using what was built."
      else
        tail -15 build.log
        echo "The engine didn't build. The full output is in build.log; docs/SETUP.md has help."
        finish 1
      fi
    fi
  fi
fi
if ! have_engine; then
  echo "No engine found next to the app. See docs/APP.md."
  finish 1
fi

# ---------------------------------------------------------------- the app
echo
echo "Starting Colbert. It opens in your web browser."
echo "Keep this window open while Colbert works. Closing it saves progress and stops."
echo
python3 app/run.py "$@"
code=$?
[ "$code" -ne 0 ] && finish "$code"
exit 0
