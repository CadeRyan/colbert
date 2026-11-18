# colbert, explained without the mathematics

This is a guide for readers who are curious but not number theorists. It builds up the
ideas behind colbert one at a time. No step needs more than school arithmetic, plus a
willingness to take a few facts on trust. [DESIGN.md](DESIGN.md) has the precise version
of each step.

## 1. The question

Take an odd number `k` and look at the sequence

    k·2 + 1,   k·4 + 1,   k·8 + 1,   k·16 + 1,  …     (k times a power of 2, plus 1)

For most `k`, a prime number turns up somewhere in that list, usually quite early. In 1960
Wacław Sierpiński proved that for some `k` it never happens: every number in the list is
composite, forever. Those `k` are called *Sierpiński numbers*. The smallest known one is
78,557. The **Sierpiński problem** asks whether it is the smallest of all.

To prove that, you need to show every odd `k` below 78,557 is *not* Sierpiński, which means
finding a prime in each list. Volunteers have now done this for all but five:

    21181   22699   24737   55459   67607

A prime of the form `k·2^n + 1` for one of these five, with over a million digits, would be
a **Colbert number** (or Colbert prime). The name is a whimsical tribute to Stephen
Colbert. Each one found crosses a `k` off the list. Find all five and the problem is solved.

The catch is size. The search has checked every `n` up to about 47.9 million. The next
candidate numbers have about **14.4 million digits**. Printed in small type, one of them
would fill about 3,000 pages.

## 2. How do you test a 14-million-digit number?

You can't try dividing by everything; there isn't time in the universe. Instead there is a
shortcut called **Proth's theorem**: for numbers of this form, a single long calculation
decides the question. You take a small number, typically 3, and square it, then square the
result, then square that, about `n` times (47.9 million times here), keeping only the
remainder after dividing by the candidate each time. If the final remainder comes out as
"−1", the number is prime; otherwise it isn't.

So the whole job is: **square a 14-million-digit number, 48 million times in a row**. Each
squaring depends on the one before, so they can't be shared out across machines. Whatever
makes one squaring faster makes the whole test faster by the same factor.

## 3. Multiplying enormous numbers quickly

School long multiplication of two 14-million-digit numbers takes about 200 trillion
digit-times-digit steps. Doing that 48 million times would take thousands of years, even
on a fast computer.

The fast method is the **Fast Fourier Transform (FFT)**. The idea, roughly:

* Think of a number as a list of digits, like `3, 1, 4, 1, 5`.
* Multiplying numbers is like "smearing" one digit list along the other (each digit
  multiplies each digit, and results that land in the same column add up). Mathematicians
  call this a *convolution*.
* The FFT re-expresses each digit list as a set of "frequencies", much as a music equalizer
  splits sound into bass, mid and treble. In frequency form, the messy smearing becomes
  simple: just multiply matching frequencies together, one pair at a time.
* Convert back, tidy up the carries, and you have the product.

This takes roughly *(number of digits) × log(number of digits)* steps instead of *(number
of digits)²*, which brings a 14-million-digit squaring down from many minutes to a few
milliseconds or less.

## 4. The wrap-around, and why some numbers are easier than others

We never need the full product, only its remainder when divided by the candidate `P`. For
some special `P` that remainder comes almost for free.

The FFT naturally works **in a circle**. It treats the digit list as if the end joined back
onto the beginning, so anything that overflows off the top wraps around to the bottom.
Imagine people seated at a round table: pass something past the last seat and it arrives
at the first.

For **Mersenne numbers** (`2^p − 1`, the kind the famous GIMPS project searches), that
wrap-around is exactly "take the remainder by `P`", because `2^p` is the same as `1` when
you are working modulo `2^p − 1`. Overflow at the top really should reappear at the bottom.
In 1994 Richard Crandall and Barry Fagin showed how to make this work cleanly even when the
digits are of slightly unequal sizes, using a set of multipliers called **weights**. It is
why Mersenne testing is so efficient.

## 5. Why `k` makes it hard

For our numbers, `k·2^n + 1`, the rule is different. Overflow off the top should reappear
at the bottom **divided by `k`** (and with its sign flipped). Dividing by 21,181 does not
give a whole number, so the "round table" no longer fits.

Programs have dealt with this in two ways:

1. **Use a table twice as big** (*zero padding*): leave room so nothing wraps, then take
   the remainder separately. Simple and exact, but every squaring handles twice the data.
   proth20, the existing GPU tester for these numbers, does this.
2. **Build `k` into the weights** (Colin Percival, 2002; used by George Woltman's gwnum
   library, which PrimeGrid's LLR2 program uses). The table stays small, but the weights
   now involve fractional powers of `k` such as `k^(1/1000000)`. Those are not whole
   numbers, so this only works with ordinary decimal ("floating-point") arithmetic, and
   the extra size of `k` eats into the precision available.

## 6. Exact arithmetic, and why graphics cards care

Floating-point numbers carry a limited number of significant digits, like a calculator
display, and small rounding errors creep in. Programs keep those errors comfortably below
the level that would change the answer, which costs some efficiency.

The kind of floating point these programs need, **double precision**, is something
consumer graphics cards are very bad at. A gaming GPU typically does it 32 to 64 times
slower than its normal arithmetic. They are excellent at plain whole-number arithmetic.

So GPU programs use the **Number-Theoretic Transform (NTT)**: the same FFT idea, but in
**clock arithmetic** instead of decimals. In clock arithmetic you count up to some fixed
number and wrap back to zero, like hours on a clock face. There are no fractions and no
rounding: every result is exact.

The catch is that the NTT needs the weights from step 5 to exist *in clock arithmetic*.
For our numbers that means you need a number that, multiplied by itself a million times
over, gives `−k·2^n`. Call it a "millionth root". In ordinary integers such roots almost
never exist: there is no whole number whose square is 2. In a given clock system, some
numbers have them and most don't. This is why, as recently as 2024, the author of the
leading GPU testers wrote that "no fast algorithm exists for k·b^n ± 1" using NTTs.

## 7. The key observation

colbert uses a particular clock system. The clock size is a Mersenne prime,
`q = 2^61 − 1`, and the numbers are *pairs* `(a, b)`, multiplied the way complex numbers
are. Crandall studied this system in 1999; it is very fast on computers because "wrap
around 2^61 − 1" is just a shift and an addition.

The fact colbert relies on is that **in this system every ordinary clock number has all
the roots we need**. Whatever `k` is, whatever `n` is, the millionth root of `−k·2^n`
exists and can be computed in advance. The reason, informally: the pairs form a bigger
world in which every ordinary number can be "factored" as a pair times its mirror image.
That flexibility guarantees a root can always be found, much as allowing the imaginary
number `i` guarantees that `−1` has a square root.

With those roots in hand, Percival's no-padding method (step 5, option 2) works in exact
clock arithmetic. colbert gets the small table of the floating-point method together with
the exactness and GPU-friendliness of the NTT.

To be clear about credit: the round-table transform, Percival's method, the clock system,
and the tricks colbert uses inside it all existed before. The new part is noticing that
this particular clock system always contains the roots Percival's method needs, so the
pieces fit together. See [NOVELTY.md](NOVELTY.md) for the full accounting and its limits.

## 8. What it buys

On a GPU, the time for one squaring is mostly the time spent moving data in and out of the
card's memory, not doing arithmetic. So the size of the table is what matters. At the
current search frontier, each squaring handles:

| method | data per squaring |
|---|---|
| zero padding, exact (proth20) | 64 MiB |
| `k` in floating-point weights (gwnum / llrCUDA) | about 34 MiB |
| **colbert** | **24 MiB** |

That should make colbert about **2.5 times faster than proth20 on the same graphics card**,
once its code is tuned as carefully. It should also make it the first GPU option that uses
less electricity per test than a CPU. [PERFORMANCE.md](PERFORMANCE.md) gives the reasoning
and its uncertainties. No GPU has run it yet.

## 9. Making sure the answer is right

A test runs for hours, and a single flipped bit anywhere (a cosmic ray, an overheating card)
would silently ruin it. colbert guards against that two ways:

* **Exactness is proven, not hoped for.** Before each run, colbert checks mathematically
  that no intermediate value can ever grow too large for the arithmetic to hold it, for the
  worst possible input. If the check fails it refuses to run.
* **A running checksum** (the *Gerbicz–Li check*). Alongside the main calculation, colbert
  keeps a cleverly chosen running product that can be recomputed a different way. If the
  two disagree, something went wrong; it rewinds to the last verified point and redoes the
  work. Its test suite deliberately flips a bit mid-run to make sure this works.

## 10. What it doesn't change

Primes this large are rare. Across all five `k`, the expected number of primes between
`n` = 47.9 million and 57.5 million is about **0.21**. Finding one takes, on average,
about **half a million** tests of 14-million-digit numbers. A faster transform shrinks the
cost of each test; it can't shrink how many tests there are. Faster arithmetic makes the
search cheaper and greener. It does not make a prime any more likely to be there.

## Glossary

* **Prime**: a whole number with no divisors except 1 and itself.
* **Composite**: not prime.
* **Proth test**: the one-long-calculation primality test for `k·2^n + 1` (step 2).
* **Squaring modulo P**: multiply a number by itself and keep only the remainder after
  dividing by `P`.
* **FFT**: Fast Fourier Transform, the fast way to multiply huge numbers (step 3).
* **Convolution**: the "smearing" pattern of digits that multiplication produces.
* **Weights / DWT**: multipliers applied before and after an FFT so that its natural
  wrap-around matches the remainder we want (step 4).
* **Zero padding**: making the FFT twice as long so nothing wraps (step 5).
* **Floating point / double precision**: calculator-style arithmetic with limited
  significant digits; double precision carries about 16 decimal digits.
* **NTT**: the FFT done in clock arithmetic, exact (step 6).
* **Clock (modular) arithmetic**: arithmetic that wraps around at a fixed number.
* **Mersenne prime**: a prime of the form `2^p − 1`.
* **GF(q²)**: the "pairs" clock system of step 7 (*GF* stands for Galois field).
* **Gerbicz–Li check**: the running checksum of step 9.
* **Sieve**: cheap trial division that removes candidates with small factors before the
  expensive test.
