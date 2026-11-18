"""
The voice-over script, as data. Each scene is a list of beats; a beat is a sentence or a
few sentences that one group of animations is timed to. Everything else (VO_SCRIPT.md,
captions, YouTube chapters, scene timing) is generated from this file.

Edit the words here, then run `video/build.py script` to regenerate VO_SCRIPT.md.
"""

SCENES = [
    dict(id="01_cold_open", chapter="Intro", beats=[
        "This number has fourteen million, four hundred thousand digits.",
        "Nobody knows yet whether it's prime. But if it is, it would knock out one of the last five "
        "obstacles to answering a question first asked in 1960.",
        "This is the story of that question, of the volunteers who have spent more than twenty years "
        "chasing it, and of a new way to make their search faster.",
    ]),
    dict(id="02_sierpinski", chapter="Sierpiński's question", beats=[
        "Pick any odd number, and call it k. Double it and add one. Then multiply k by four and add one. "
        "Then by eight, by sixteen, by thirty-two, always adding one at the end.",
        "For k equals three, you get seven, thirteen, twenty-five, forty-nine, ninety-seven. Some crack "
        "into smaller factors, but primes turn up straight away. Try almost any k and the same thing "
        "happens. Sooner or later, a prime appears.",
        "In 1960, the Polish mathematician Wacław Sierpiński proved something surprising. There are "
        "values of k for which a prime never appears. Not in the first million terms. Not ever.",
        "Two years later, John Selfridge found one: seventy-eight thousand, five hundred and fifty-seven. "
        "Every number in its list is divisible by one of just seven small primes: three, five, seven, "
        "thirteen, nineteen, thirty-seven or seventy-three. They take turns, in a pattern that repeats "
        "every thirty-six steps, forever, so no prime can ever slip through.",
        "Numbers like this are called Sierpiński numbers. And the Sierpiński problem asks something "
        "simple: is seventy-eight thousand, five hundred and fifty-seven the smallest one?",
    ]),
    dict(id="03_elimination", chapter="A sky of candidates", beats=[
        "Picture every odd number below it as a star in the night sky. To prove seventy-eight thousand, "
        "five hundred and fifty-seven is the smallest, every one of those stars has to be lit, by finding "
        "a prime in its list.",
        "For most stars, that's easy. A prime appears within the first handful of terms. Over the "
        "following decades, computer searches lit almost all of the rest.",
        "By 2002, just seventeen stars were still dark. They were dark precisely because their primes, "
        "if they exist, are enormous.",
    ]),
    dict(id="04_seventeen_or_bust", chapter="Seventeen or Bust", beats=[
        "That year, a project called Seventeen or Bust invited anyone with a computer to help. "
        "Volunteers around the world donated their machines' spare time to test candidates.",
        "It worked. Between 2002 and 2007, volunteers found eleven primes, and eleven stars came on. "
        "Several of those primes had millions of digits.",
        "In 2016 the project lost its server and shut down. The search carried on at PrimeGrid, another "
        "volunteer computing project, and that October it found the twelfth: ten thousand, two hundred "
        "and twenty-three, times two to the thirty-one million, one hundred and seventy-two thousand, one "
        "hundred and sixty-five, plus one. A prime with more than nine million digits. Testing it took "
        "a home computer almost nine days.",
        "Primes like these, with more than a million digits, that light one of the remaining stars, are "
        "nicknamed Colbert numbers, a tongue-in-cheek tribute to Stephen Colbert.",
        "Five stars are still dark. Light all five, and seventy-eight thousand, five hundred and "
        "fifty-seven is confirmed as the smallest Sierpiński number.",
    ]),
    dict(id="05_scale", chapter="How big is enormous?", beats=[
        "The search has now walked past every exponent up to about forty-seven point nine million. "
        "So the next numbers to test have around fourteen point four million digits.",
        "Printed in small type, just one of them would fill about three thousand pages.",
        "You can't test a number like that by trying to divide it by everything smaller. "
        "There isn't enough time left in the universe.",
    ]),
    dict(id="06_proth", chapter="One long calculation", beats=[
        "Instead, there's a shortcut, found by François Proth in 1878. For numbers of exactly this "
        "form, one long calculation settles the question.",
        "Start with a small number, like three. Square it. Square the result. Keep going, about "
        "forty-eight million times, and after every step keep only the remainder after dividing by "
        "the number you're testing.",
        "If the very last remainder is one less than the number itself, the remainder that stands "
        "for minus one, the number is prime. Anything else, and it isn't.",
        "There's a catch. Each squaring needs the result of the one before, so the work can't be "
        "shared out across many computers. Making a single squaring faster is the only way to make "
        "the test faster.",
    ]),
    dict(id="07_fft", chapter="Multiplying giants", beats=[
        "So how do you square a fourteen-million-digit number quickly? Not the way we learned at "
        "school. Long multiplication multiplies every digit by every other digit: about two hundred "
        "trillion small multiplications, for a single squaring.",
        "Forty-eight million of those would take thousands of years, even on a fast computer.",
        "The trick computers use is called the Fast Fourier Transform. Think of a number as a row of "
        "digits. Multiplying two numbers smears one row across the other, and overlapping columns add up.",
        "The transform works like a prism. It splits each row of digits into its frequencies, the way "
        "a prism splits light into colours. In that form, the messy smearing becomes simple: multiply "
        "matching colours, one pair at a time. Then recombine them, and tidy up the carries.",
        "The work now grows only a little faster than the number of digits, instead of with its square. "
        "Each squaring drops from many minutes to a fraction of a millisecond.",
    ]),
    dict(id="08_round_table", chapter="The round table", beats=[
        "There's one more saving to be had. We never need the whole product, only its remainder. "
        "And for some special numbers, that remainder comes almost for free.",
        "The transform naturally works in a circle. It seats the digits around a round table, so "
        "anything that overflows past the last seat simply walks round to the first.",
        "For Mersenne numbers, two to some power minus one, that's exactly right: overflow at the top "
        "really should reappear at the bottom. In 1994, Richard Crandall and Barry Fagin showed how to "
        "make it work cleanly, using a set of multipliers called weights. It's a big part of why the "
        "hunt for Mersenne primes is so efficient.",
    ]),
    dict(id="09_the_k_problem", chapter="Why k makes it hard", beats=[
        "Our numbers are different. For k times two to the n, plus one, overflow should reappear at "
        "the first seat divided by k, with its sign flipped.",
        "Divide by twenty-one thousand, one hundred and eighty-one, and you don't get a whole number. "
        "The guest crumbles. The round table no longer fits.",
        "Programs have handled this in two ways. The first is to use a table twice as big, with enough "
        "empty seats that nothing ever wraps. It's exact, but every squaring has to move twice the "
        "data. proth20, the existing graphics-card tester for these numbers, works this way.",
        "The second, from Colin Percival in 2002, and used in George Woltman's gwnum library, builds k "
        "into the weights. The table stays small. But now the weights involve fractional powers of k, "
        "so the arithmetic has to use decimals, and the size of k eats into the precision available. "
        "This is how LLR2, the program PrimeGrid runs on ordinary processors, works.",
    ]),
    dict(id="10_exact", chapter="Exact arithmetic", beats=[
        "Decimal arithmetic on a computer keeps a fixed number of significant digits, like a calculator "
        "display. Tiny rounding errors creep in, and programs have to leave a safety margin so that "
        "they never change the answer.",
        "The kind these programs need, double precision, is something gaming graphics cards are very "
        "bad at. They run it thirty-two to sixty-four times slower than their everyday arithmetic. "
        "But they're superb at plain whole numbers.",
        "So graphics-card testers use the number-theoretic transform: the same idea, done in clock "
        "arithmetic. Count up to a fixed number, then wrap back to zero, like the hours on a clock. "
        "No fractions, no rounding. Every result is exact.",
        "The catch is that the weights must exist on the clock too, as whole numbers. On a seven-hour "
        "clock, only some hours have a square root: one, two and four do; three, five and six don't. "
        "Our weights need something far harder: a millionth root of minus k times two to the n. On most "
        "clocks, for most numbers, there isn't one.",
        "As recently as 2024, Yves Gallot, whose programs power much of PrimeGrid's graphics-card work, "
        "noted that no fast method of this kind existed for numbers like ours.",
    ]),
    dict(id="11_pair_world", chapter="A clock made of pairs", beats=[
        "Colbert's clock has two to the sixty-one, minus one hours. That's a Mersenne prime, and as "
        "we'll see, that choice is the whole secret.",
        "On this clock, colbert doesn't count with single numbers. It uses pairs, and multiplies them "
        "the way complex numbers multiply. The second half of each pair plays the part of i, a square "
        "root of minus one, which a clock of this size doesn't otherwise have.",
        "To see what that buys, shrink the clock to seven hours. Seven is a Mersenne prime too: two "
        "cubed, minus one. Now every pair is a point on a seven-by-seven grid, and the ordinary numbers "
        "are just the bottom row.",
        "Multiplying by a pair moves you around the grid. Multiply by the pair three-and-one, over and "
        "over, and after exactly eight hops, you land on the ordinary number three. So three-and-one is "
        "an eighth root of three. A whole-number root, on a clock, with nothing left over.",
    ]),
    dict(id="12_why_roots", chapter="Why a root always exists", beats=[
        "Is that a lucky accident? No. It works for every number on every clock like this, and the "
        "reason takes just two steps.",
        "Step one. On a seven-hour clock, only four hours are squares: zero, one, two and four. Now take "
        "a target, say three, and subtract each square from it. That gives another four hours. Two sets "
        "of four can't fit on a clock of seven without sharing an hour. Here they share two, and two "
        "is three squared. Three minus two is one, which is one squared. So three equals three squared "
        "plus one squared. The same counting works on any prime clock, however large.",
        "In the language of pairs, a squared plus b squared is just the pair a-and-b, multiplied by its "
        "mirror image, a-and-minus-b. So every ordinary number is some pair times its own reflection.",
        "Step two is where the Mersenne prime earns its place. On a clock of two to the p, minus one "
        "hours, multiplying a pair by itself that many times turns it into its mirror image. One more "
        "multiplication gives the pair times its mirror, which is the number we started from. So the "
        "pair, multiplied by itself two to the p times, lands exactly on the target.",
        "And two to the p is a power of two, which is precisely what the transform needs. On colbert's "
        "clock, a pair raised to the power two to the sixty-one gives minus k times two to the n. Raise "
        "it to a smaller power of two instead, and you get a millionth root, or a two-millionth, "
        "whatever size the transform calls for.",
        "Every k, every n: the root always exists, as an exact pair of whole numbers, and colbert "
        "finds it in a fraction of a second before the test begins.",
    ]),
    dict(id="13_the_fit", chapter="The pieces fit", beats=[
        "With those roots in hand, Percival's method works in exact clock arithmetic. Colbert gets the "
        "small table of the decimal method, together with the exactness and speed of whole numbers on "
        "a graphics card.",
        "Almost every piece was built by others: Crandall and Fagin, Percival, Woltman, Gallot. To our "
        "knowledge, the new part is seeing that this clock always contains the roots Percival's method "
        "needs, so that the pieces finally fit together.",
    ]),
    dict(id="14_results", chapter="What it buys", beats=[
        "On a graphics card, a squaring this size spends most of its time moving data in and out of "
        "memory, not doing arithmetic. So the amount of data is what matters.",
        "At the search frontier, the padded approach hauls sixty-four megabytes per squaring. The "
        "decimal method, about thirty-four. Colbert, twenty-four.",
        "On a GeForce RTX 4090, that makes colbert about two and a half times faster than proth20 on "
        "the same card. A full test at the frontier takes about three hours, instead of seven.",
        "And for the first time, a graphics card beats a processor on energy, not just on speed: "
        "nearly three times as many tests per kilowatt-hour as a high-end CPU running LLR2. For a "
        "project run by volunteers, electricity is the cost that counts.",
    ]),
    dict(id="15_trust", chapter="Making sure it's right", beats=[
        "A test runs for hours, and a single flipped bit, from a cosmic ray or a card running hot, "
        "would silently ruin it. Colbert guards against that in two ways.",
        "First, exactness is proven, not hoped for. Before every run, colbert checks mathematically "
        "that no intermediate value can outgrow the arithmetic, even for the worst possible input. "
        "If the check fails, it refuses to start.",
        "Second, a running checksum, called the Gerbicz–Li check. Alongside the main calculation, "
        "colbert keeps a cleverly chosen product that can be recomputed a different way. If the two "
        "ever disagree, it rewinds to the last verified point, and redoes the work.",
    ]),
    dict(id="16_impact", chapter="What it means for the search", beats=[
        "Faster arithmetic doesn't make a prime any more likely to be there. Primes this large are rare. "
        "Between where the search stands today and an exponent of fifty-seven and a half million, we "
        "expect about one fifth of a prime, across all five k combined.",
        "Finding one takes, on average, about half a million tests like these. No transform can shrink "
        "that number. What it can shrink is the cost of each test, in time and in electricity.",
        "And that matters, for a search run by volunteers. Every graphics card that can join efficiently "
        "widens the circle of people who can help, and brings the answer to a sixty-year-old question "
        "a little closer.",
        "Five dark stars. The prime that lights one of them might already be sitting in the next block "
        "of candidates, waiting for someone's computer to find it.",
    ]),
    dict(id="17_credits", chapter="Credits", beats=[
        "Colbert is open source. The code, the mathematics, and the measurements are linked in the "
        "description. Thanks for watching.",
    ]),
]

TITLE = "The Last Five"
SUBTITLE = "Exact arithmetic, graphics cards, and the hunt for the final Colbert primes"
