#!/usr/bin/env python3
"""
Reference model of the transform used by colbert: an irrational-base discrete
weighted transform (IBDWT) for Proth moduli  P = k*2^n + 1  carried out exactly
in GF(q^2), q a Mersenne prime (2^31-1 and 2^61-1), with NO zero padding.

Slow, tiny sizes, pure Python: this file exists to pin the mathematics down and
to be checked against plain big-integer arithmetic.  The C++/OpenCL engines are
tested against the same identities.

Representation.  x = sum_{j<N} x_j 2^{s_j},  s_j = ceil(j*b),  b = (n+log2 k)/N.
Word j holds s_{j+1}-s_j bits, except the top word whose base is k*2^(n-s_{N-1}),
so that the product of all word bases is exactly k*2^n == -1 (mod P).

Multiplication.  With theta^N = c := -k*2^n in GF(q^2) and a_j = 2^{s_j} theta^-j,
the length-N cyclic convolution of (a_j x_j) equals a_m d_m / k where
    d = k*x*y   (as digit vectors, before carry)
is an INTEGER vector.  So one transform computes  x o y := k*x*y mod P, and
phi(x) = k*x is an isomorphism (Z/P, o) -> (Z/P, *): a Proth test runs unchanged.

Half length.  The inputs are "real" (in GF(q)), so only N/2 points are needed:
  c non-residue in GF(q):  fold x_j + gamma x_{j+N/2}   (right-angle structure)
  c residue     in GF(q):  real weights, pack (even,odd), untangle conjugate pairs
Which case applies depends on the Legendre symbol (k/q) -- both occur among the
five remaining Sierpinski k for q = M31, M61, so both are implemented.
"""
import math, random, sys
from fractions import Fraction

# ---------------------------------------------------------------- GF(q), GF(q^2)
class Field:
    def __init__(self, e):
        self.e = e; self.q = (1 << e) - 1
        q = self.q
        # element of order 2^(e+1) in GF(q^2)*  (|GF(q^2)*| = 2^(e+1) * (2^(e-1)-1)*... )
        rnd = random.Random(12345 + e)
        odd = (q * q - 1) >> (e + 1)
        while True:
            g = (rnd.randrange(1, q), rnd.randrange(1, q))
            h = self.cpow(g, odd)
            if self.cpow(h, 1 << e) != (1, 0):
                break
        self.h = h                       # order exactly 2^(e+1)
    # complex ops, elements are (re, im) with i^2 = -1
    def cmul(self, a, b):
        q = self.q
        return ((a[0]*b[0] - a[1]*b[1]) % q, (a[0]*b[1] + a[1]*b[0]) % q)
    def cpow(self, a, n):
        r = (1, 0)
        while n:
            if n & 1: r = self.cmul(r, a)
            a = self.cmul(a, a); n >>= 1
        return r
    def cinv(self, a):
        q = self.q; d = pow((a[0]*a[0] + a[1]*a[1]) % q, q - 2, q)
        return (a[0]*d % q, (-a[1])*d % q)
    def root_of_unity(self, M):
        """primitive M-th root, M | 2^e, with conj(w) = w^-1 (norm 1)."""
        assert M & (M - 1) == 0 and M <= (1 << self.e)
        return self.cpow(self.h, (1 << (self.e + 1)) // M)
    def is_qr(self, c):
        return pow(c % self.q, (self.q - 1) // 2, self.q) == 1
    def sqrt(self, c):                    # q = 3 mod 4
        r = pow(c, (self.q + 1) // 4, self.q); assert r*r % self.q == c % self.q
        return r
    def nth_root_real(self, c, N):
        """N-th root in GF(q) of a quadratic residue c (N a power of two)."""
        m = (self.q - 1) // 2             # odd order of the QR subgroup
        return pow(c, pow(N, -1, m), self.q)
    def nth_root(self, c, N):
        """some N-th root in GF(q^2) of ANY c in GF(q)*:  c = norm(h),  root = h^((q+1)/N)."""
        q = self.q; rnd = random.Random(c)
        while True:
            a = rnd.randrange(q); t = (c - a*a) % q
            if t == 0 or self.is_qr(t): break
        hh = (a, self.sqrt(t) if t else 0)
        return self.cpow(hh, (q + 1) // N)

def fft(F, z, w):
    """plain recursive DFT over GF(q^2): Z_k = sum z_j w^(jk)."""
    M = len(z)
    if M == 1: return z[:]
    w2 = F.cmul(w, w)
    E = fft(F, z[0::2], w2); O = fft(F, z[1::2], w2)
    out = [None] * M; t = (1, 0); q = F.q
    for k in range(M // 2):
        u = F.cmul(t, O[k])
        out[k] = ((E[k][0] + u[0]) % q, (E[k][1] + u[1]) % q)
        out[k + M//2] = ((E[k][0] - u[0]) % q, (E[k][1] - u[1]) % q)
        t = F.cmul(t, w)
    return out

# ---------------------------------------------------------------- number layout
class Layout:
    def __init__(self, k, n, N):
        self.k, self.n, self.N = k, n, N
        self.P = k * (1 << n) + 1
        # exact ceil(j*(n+log2 k)/N) without floats: 2^(s*N) >= k^j * 2^(j n)
        self.s = [self._ceil(j) for j in range(N)]
        assert self.s[0] == 0
        self.top_shift = n - self.s[N - 1]
        assert self.top_shift >= 0, "words too small for this k"
        self.base = [1 << (self.s[j+1] - self.s[j]) for j in range(N - 1)] + [k << self.top_shift]
    def _ceil(self, j):
        k, n, N = self.k, self.n, self.N
        s = (j * (n + math.log2(k))) / N
        s = max(0, int(s) - 2)
        while (1 << (s * N)) < (k ** j) << (j * n): s += 1
        return s
    def to_digits(self, x):
        """balanced digits of x (taken mod P)."""
        x %= self.P; d = []
        for j in range(self.N):
            B = self.base[j]; r = x % B
            if r > B // 2: r -= B
            d.append(r); x = (x - r) // B
        # carry out of the top word sits at k*2^n == -1
        if x: d = self.carry([d[0] - x] + d[1:])
        return d
    def value(self, d):
        return sum(dj << sj for dj, sj in zip(d, self.s)) % self.P
    def carry(self, d):
        d = list(d)
        while True:
            c = 0
            for j in range(self.N):
                v = d[j] + c; B = self.base[j]; r = v % B
                if r > B // 2: r -= B
                d[j] = r; c = (v - r) // B
            if c == 0: return d
            d[0] -= c                      # wrap: k*2^n == -1

# ---------------------------------------------------------------- one prime
class Transform:
    def __init__(self, L, e):
        self.L = L; F = self.F = Field(e); q = F.q
        k, n, N = L.k, L.n, L.N; M = self.M = N // 2
        c = (-k * pow(2, n, q)) % q
        self.neg = not F.is_qr(c)          # True: fold ("negacyclic-like") structure
        kq = k % q; iM = pow(M, -1, q)
        self.wM = F.root_of_unity(M); self.wMi = F.cinv(self.wM)
        p2 = lambda s: pow(2, s, q); ip2 = lambda s: pow(2, -s, q)
        if self.neg:
            th = F.nth_root(c, N); thi = F.cinv(th)       # theta^N = c
            gam = F.cpow(thi, M)                          # gamma'^2 = 1/c, purely imaginary
            assert gam[0] == 0, "gamma must be imaginary when c is a non-residue"
            g = gam[1]; gi = pow(g, -1, q)
            self.W1, self.W2, self.U, self.V = [], [], [], []
            t, ti = (1, 0), (1, 0)                        # theta^-j, theta^j
            for j in range(M):
                self.W1.append(F.cmul(t, (p2(L.s[j]), 0)))
                self.W2.append(F.cmul(t, (0, g * p2(L.s[j + M]) % q)))
                self.U.append(F.cmul(ti, (kq * ip2(L.s[j]) * iM % q, 0)))
                self.V.append(F.cmul(ti, (kq * ip2(L.s[j + M]) * iM * gi % q, 0)))
                t = F.cmul(t, thi); ti = F.cmul(ti, th)
        else:
            rho = F.nth_root_real(pow(c, -1, q), N)       # rho^N = 1/c, real
            rhoi = pow(rho, -1, q)
            self.a = [p2(L.s[j]) * pow(rho, j, q) % q for j in range(N)]
            self.ai = [kq * iM * ip2(L.s[j]) * pow(rhoi, j, q) % q for j in range(N)]
            self.tw = [F.cpow(self.wM, kk) for kk in range(M)]
    def forward(self, x):
        F, M, q = self.F, self.M, self.F.q
        if self.neg:
            z = [((self.W1[j][0]*x[j] + self.W2[j][0]*x[j+M]) % q,
                  (self.W1[j][1]*x[j] + self.W2[j][1]*x[j+M]) % q) for j in range(M)]
        else:
            z = [(self.a[2*j]*x[2*j] % q, self.a[2*j+1]*x[2*j+1] % q) for j in range(M)]
        return fft(F, z, self.wM)
    def pointwise(self, X, Y):
        F, M, q = self.F, self.M, self.F.q
        if self.neg:
            return [F.cmul(a, b) for a, b in zip(X, Y)]
        i2 = pow(2, -1, q); conj = lambda a: (a[0], (-a[1]) % q)
        def EO(Z, kk):
            a, b = Z[kk], conj(Z[(M - kk) % M])
            E = ((a[0]+b[0])*i2 % q, (a[1]+b[1])*i2 % q)
            iO = ((a[0]-b[0])*i2 % q, (a[1]-b[1])*i2 % q)
            return E, (iO[1], (-iO[0]) % q)               # O = iO / i
        out = [None] * M
        for kk in range(M):
            E1, O1 = EO(X, kk); E2, O2 = EO(Y, kk)
            a = F.cmul(E1, E2); b = F.cmul(self.tw[kk], F.cmul(O1, O2))
            Ep = ((a[0]+b[0]) % q, (a[1]+b[1]) % q)
            u = F.cmul(E1, O2); v = F.cmul(E2, O1)
            Op = ((u[0]+v[0]) % q, (u[1]+v[1]) % q)
            out[kk] = ((Ep[0] - Op[1]) % q, (Ep[1] + Op[0]) % q)   # E' + i O'
        return out
    def inverse(self, Z):
        F, M, q = self.F, self.M, self.F.q
        z = fft(F, Z, self.wMi)                           # un-normalised; 1/M is in the tables
        d = [0] * (2 * M)
        if self.neg:
            for j in range(M):
                d[j] = F.cmul(z[j], self.U[j])[0]
                d[j + M] = F.cmul(z[j], self.V[j])[1]
        else:
            for j in range(M):
                d[2*j] = z[j][0] * self.ai[2*j] % q
                d[2*j+1] = z[j][1] * self.ai[2*j+1] % q
        return d

class Engine:
    def __init__(self, k, n, N, primes=(61, 31)):
        self.L = Layout(k, n, N)
        self.T = [Transform(self.L, e) for e in primes]
        self.Q = math.prod(t.F.q for t in self.T)
        b = (n + math.log2(k)) / N
        self.bound_bits = 2 * b + math.log2(N) + math.log2(k)   # |d_m| <= k N 2^(2b)
        assert self.bound_bits < math.log2(self.Q) - 1, "convolution could overflow the CRT modulus"
    def mul(self, x, y):
        """digits of  k*x*y mod P  (x o y)."""
        res = [t.inverse(t.pointwise(t.forward(x), t.forward(y))) for t in self.T]
        qs = [t.F.q for t in self.T]; Q = self.Q
        d = []
        for m in range(self.L.N):
            v = 0
            for r, q in zip(res, qs):
                Qi = Q // q; v += r[m] * Qi * pow(Qi, -1, q)
            v %= Q
            if v > Q // 2: v -= Q
            d.append(v)
        return self.L.carry(d)

# ---------------------------------------------------------------- self test
def proth(k, n, N, primes):
    """returns (is_prime, a) using the weighted transform only."""
    E = Engine(k, n, N, primes); L = E.L; P = L.P
    a = next(a for a in (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37) if jacobi(a, P) == -1)
    x = L.to_digits(pow(a, k, P) * pow(k, -1, P))       # x0 = a^k / k
    for _ in range(n - 1):
        x = E.mul(x, x)
    return L.value(x) == pow(2, n, P), a                # k*x == -1  <=>  x == 2^n

def jacobi(a, n):
    a %= n; r = 1
    while a:
        while a % 2 == 0:
            a //= 2
            if n % 8 in (3, 5): r = -r
        a, n = n, a
        if a % 4 == 3 and n % 4 == 3: r = -r
        a %= n
    return r if n == 1 else 0

if __name__ == "__main__":
    rnd = random.Random(1)
    cases = 0
    for primes in ((61,), (31, 61)):
        for k in (21181, 22699, 24737, 55459, 67607, 3, 10223, 46157):
            for (n, N) in ((300, 16), (600, 32), (2300, 128)) if primes == (61,) else ((1000, 32), (4099, 128)):
                E = Engine(k, n, N, primes); L = E.L; P = L.P
                for _ in range(3):
                    x, y = rnd.randrange(P), rnd.randrange(P)
                    got = L.value(E.mul(L.to_digits(x), L.to_digits(y)))
                    assert got == k * x * y % P, (k, n, N, primes)
                    cases += 1
                kinds = "/".join("fold" if t.neg else "real" for t in E.T)
                print(f"ok  k={k:6d} n={n:5d} N={N:4d} primes={primes} structure={kinds} "
                      f"bits/word={(n+math.log2(k))/N:5.2f} bound={E.bound_bits:5.1f}/{math.log2(E.Q):.0f}")
    print(cases, "random products match big-integer arithmetic")
    # end-to-end Proth tests against GMP, both outcomes, k of the real size
    import gmpy2
    todo = [(3, 189), (3, 190), (5, 127), (7, 120), (13, 114), (21181, 404), (67607, 411)]
    found = 0
    for k in range(20001, 70000, 2):                       # a few genuine Proth primes with 15-17 bit k
        for n in range(300, 330):
            if found < 6 and gmpy2.is_prime(k * 2**n + 1):
                todo.append((k, n)); todo.append((k, n + 1)); found += 1
    for k, n in todo:
        N = 2
        while (n + math.log2(k)) / (2 * N) >= math.log2(k) + 2 and N < 16: N *= 2
        got, a = proth(k, n, N, (31, 61))
        want = bool(gmpy2.is_prime(k * 2**n + 1))
        print(f"proth k={k} n={n} N={N} base={a}: transform says {'prime' if got else 'composite'}, gmp says {'prime' if want else 'composite'}")
        assert got == want
    print("all Proth verdicts agree with GMP")
