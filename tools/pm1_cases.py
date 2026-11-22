#!/usr/bin/env python3
"""Find small k*2^n+1 for the P-1 self-test: a factor found in stage 1, one found only in
stage 2, and none. Plain Python integers; the numbers have no factor below 1000, like real
(sieved) candidates. Prints the cases `colbert selftest` uses (src/main.cpp)."""
import math


def primes(n):
    s = bytearray([1]) * (n + 1); s[0] = s[1] = 0
    for i in range(2, int(n ** .5) + 1):
        if s[i]: s[i * i::i] = bytearray(len(s[i * i::i]))
    return [i for i in range(n + 1) if s[i]]


def exponent(B1):
    e = 1
    for p in primes(B1):
        q = p
        while q * p <= B1: q *= p
        e *= q
    return e


SMALL = math.prod(primes(1000))


def search(ks, ns, B1, B2, want):
    e1 = exponent(B1); ps2 = [p for p in primes(B2) if p > B1]
    for k in ks:
        for n in ns:
            N = k * 2 ** n + 1
            if math.gcd(N, SMALL) != 1: continue
            y = pow(3, e1, N)
            g1 = math.gcd(y - 1, N)
            if want == 1:
                if 1 < g1 < N: return k, n, g1
                continue
            if 1 < g1 < N: continue
            acc, prev, yq = 1, 0, 1
            for q in ps2:                         # prod (y^q - 1) over primes in (B1, B2]
                yq = yq * pow(y, q - prev, N) % N; prev = q
                acc = acc * (yq - 1) % N
            g2 = math.gcd(acc, N)
            if want == 2 and 1 < g2 < N: return k, n, g2
            if want == 0 and g2 == 1: return k, n


if __name__ == "__main__":
    ks = (21181, 22699, 24737, 55459, 67607)
    print("stage 1:", search(ks, range(2000, 4000), 600, 600, 1))
    print("stage 2:", search(ks, range(2000, 4000), 600, 30000, 2))
    print("none:   ", search(ks[:2], range(2000, 4000), 600, 30000, 0))
    print("larger: ", search((55459, 67607, 24737), range(30000, 31000), 1000, 60000, 2))
