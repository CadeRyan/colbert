CXX ?= g++
CXXFLAGS ?= -O3 -march=native -std=c++17 -fopenmp -Wall -Wextra -Wno-unknown-pragmas
LIBS = -lgmpxx -lgmp
SRC = src/main.cpp src/proth.cpp src/layout.cpp src/cpu_engine.cpp
HDR = $(wildcard src/*.h)

# OPENCL=0 builds a CPU-only binary
OPENCL ?= 1
ifeq ($(OPENCL),1)
  SRC += src/ocl_engine.cpp
  LIBS += -lOpenCL
  OCLDEP = src/kernels.inc
else
  SRC += src/ocl_stub.cpp
endif

all: colbert sieve

colbert: $(SRC) $(HDR) $(OCLDEP)
	$(CXX) $(CXXFLAGS) -o $@ $(SRC) $(LIBS)

# the OpenCL program is embedded in the binary as a raw string literal
src/kernels.inc: src/kernels.cl
	( printf 'R"CLSRC(\n'; cat $<; printf ')CLSRC"\n' ) > $@

sieve: tools/sieve.cpp
	$(CXX) $(CXXFLAGS) -o $@ $< 

check: colbert
	./colbert selftest
	python3 proto/weighted_ntt.py > /dev/null

clean:
	rm -f colbert sieve src/kernels.inc

.PHONY: all check clean
