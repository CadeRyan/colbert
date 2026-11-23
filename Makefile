CXX ?= g++
# ARCH is the only flag a portable (release) build needs to change: -march=native makes the
# binary crash with "illegal instruction" on older CPUs. Release builds use e.g.
#   make ARCH=-march=x86-64-v2        (x86-64)      make ARCH=-mcpu=apple-m1   (Apple Silicon)
ARCH ?= -march=native
WARN = -Wall -Wextra -Wno-unknown-pragmas
CORE = src/main.cpp src/proth.cpp src/pm1.cpp src/layout.cpp src/cpu_engine.cpp
HDR = $(wildcard src/*.h)

# Version stamped into the binary and into every result line. The ledger uses it to tell
# results from different builds apart (for example to re-test after a kernel bug is found).
# A build from uncommitted engine changes is "<commit>-dirty.<hash of the diff>", so every
# distinct edit of src/ gets its own version (and is re-validated by the app).
GIT_VERSION := $(shell git describe --always --tags 2>/dev/null || echo unknown)
SRC_DIFF := $(shell git diff HEAD --stat -- src Makefile 2>/dev/null)
ifeq ($(strip $(SRC_DIFF)),)
  VERSION ?= $(GIT_VERSION)
else
  VERSION ?= $(GIT_VERSION)-dirty.$(shell git diff HEAD -- src Makefile | (shasum 2>/dev/null || sha1sum) | cut -c1-8)
endif

UNAME := $(shell uname -s 2>/dev/null || echo Windows)

ifeq ($(UNAME),Darwin)
  # Apple clang has no -fopenmp driver flag; use Homebrew's libomp:  brew install gmp libomp
  CXX = clang++
  BREW ?= $(shell brew --prefix 2>/dev/null || echo /opt/homebrew)
  OMPFLAGS = -Xpreprocessor -fopenmp -I$(BREW)/opt/libomp/include -I$(BREW)/opt/gmp/include
  ifeq ($(STATIC),1)
    # self-contained: depends only on system libraries and the OpenCL framework
    OMPLIB = $(BREW)/opt/libomp/lib/libomp.a
    LIBS = $(BREW)/opt/gmp/lib/libgmpxx.a $(BREW)/opt/gmp/lib/libgmp.a $(OMPLIB)
  else
    OMPLIB = -L$(BREW)/opt/libomp/lib -lomp
    LIBS = -L$(BREW)/opt/gmp/lib -lgmpxx -lgmp $(OMPLIB)
  endif
  OCLLIB = -framework OpenCL
else ifeq ($(UNAME),Linux)
  OMPFLAGS = -fopenmp
  OCLLIB = -lOpenCL
  ifeq ($(STATIC),1)
    # release build that runs on other distributions: GMP and the C++ runtime are linked in;
    # libgomp.so.1 travels next to the binary (found through rpath $ORIGIN); the OpenCL loader
    # stays a system library (without it the app falls back to colbert-cpu)
    LIBS = $(shell $(CXX) -print-file-name=libgmpxx.a) $(shell $(CXX) -print-file-name=libgmp.a)
    LDFLAGS += -static-libstdc++ -static-libgcc -Wl,-rpath,'$$ORIGIN'
  else
    LIBS = -lgmpxx -lgmp
  endif
else
  OMPFLAGS = -fopenmp
  LIBS = -lgmpxx -lgmp
  OCLLIB = -lOpenCL
  ifeq ($(STATIC),1)
    # MSYS2/MinGW release builds: no runtime DLLs except OpenCL.dll, which GPU drivers install
    LDFLAGS += -static
  endif
endif

CXXFLAGS ?= -O3 $(ARCH) -std=c++17 $(OMPFLAGS) $(WARN)
DEFS = -DCOLBERT_VERSION=\"$(VERSION)\"

# OPENCL=0 builds a CPU-only `colbert`
OPENCL ?= 1
ifeq ($(OPENCL),1)
  SRC = $(CORE) src/ocl_engine.cpp
  OCLDEP = src/kernels.inc
  ALLLIBS = $(LIBS) $(OCLLIB)
else
  SRC = $(CORE) src/ocl_stub.cpp
  ALLLIBS = $(LIBS)
endif

all: colbert sieve

colbert: $(SRC) $(HDR) $(OCLDEP)
	$(CXX) $(CXXFLAGS) $(DEFS) -o $@ $(SRC) $(LDFLAGS) $(ALLLIBS)

# CPU-only companion. The app falls back to it where the OpenCL loader library is missing,
# which would otherwise stop `colbert` from starting at all.
colbert-cpu: $(CORE) src/ocl_stub.cpp $(HDR)
	$(CXX) $(CXXFLAGS) $(DEFS) -o $@ $(CORE) src/ocl_stub.cpp $(LDFLAGS) $(LIBS)

# the OpenCL program is embedded in the binary as a raw string literal
src/kernels.inc: src/kernels.cl
	( printf 'R"CLSRC(\n'; cat $<; printf ')CLSRC"\n' ) > $@

sieve: tools/sieve.cpp
	$(CXX) $(CXXFLAGS) -o $@ $< $(LDFLAGS) $(OMPLIB)

check: colbert
	./colbert selftest
	python3 tools/check_protocol.py ./colbert
	python3 proto/weighted_ntt.py > /dev/null

clean:
	rm -f colbert colbert-cpu sieve src/kernels.inc

.PHONY: all check clean
