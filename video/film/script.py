"""
The voice-over script, as data. Each scene is a list of beats; a beat is a sentence or a
few sentences that one group of animations is timed to. Everything else (VO_SCRIPT.md,
captions, YouTube chapters, scene timing) is generated from this file.

Edit the words here, then run `video/build.py script` to regenerate VO_SCRIPT.md.
"""

SCENES = [
    dict(id="01_cold_open", chapter="Intro", beats=[
        "This number has fourteen million, four hundred thousand digits.",
        "Nobody knows yet whether it's prime. But if it is, or if any one of the numbers like it is, "
        "it would knock out one of the last five obstacles to answering a question first asked in 1960.",
        "This is the story of that question, of the volunteers who have spent more than twenty years "
        "chasing it, and of a new way to make their search faster.",
    ]),
    dict(id="02_sierpinski", chapter="Sierpiński's question", beats=[
        "Pick any odd number, and call it k. Multiply it by two and add one. Then multiply k by four "
        "and add one. Then by eight, by sixteen, by thirty-two, always adding one at the end.",
        "For k equals three, you get seven, thirteen, twenty-five, forty-nine, ninety-seven, and primes "
        "turn up straight away. Try almost any k and the same thing happens. Sooner or later, a prime appears.",
        "In 1960, the Polish mathematician Wacław Sierpiński proved something surprising. There are "
        "values of k for which a prime never appears. Not in the first million terms. Not ever.",
        "Two years later, John Selfridge found one: seventy-eight thousand, five hundred and fifty-seven. "
        "Every number in its list is divisible by one of just seven small primes: three, five, seven, "
        "thirteen, nineteen, thirty-seven or seventy-three. The pattern repeats every thirty-six steps, "
        "forever, so no prime can ever slip through.",
        "Numbers like this are called Sierpiński numbers. And the Sierpiński problem asks something "
        "simple: is seventy-eight thousand, five hundred and fifty-seven the smallest one?",
    ]),
    dict(id="03_elimination", chapter="Crossing off candidates", beats=[
        "To prove it is, you have to show that every odd k below it is not a Sierpiński number. "
        "And the only practical way to do that is to find a prime in each k's list.",
        "For most k, that's easy. A prime appears within the first handful of terms. Over the following "
        "decades, computer searches crossed off almost all of the rest.",
        "By 2002, just seventeen values of k remained. They were hard precisely because their primes, "
        "if they exist, are enormous.",
    ]),
    dict(id="04_seventeen_or_bust", chapter="Seventeen or Bust", beats=[
        "That year, a project called Seventeen or Bust invited anyone with a computer to help. "
        "Volunteers donated their machines' spare time to test candidates for the seventeen remaining k.",
        "It worked. Between 2002 and 2007, volunteers found eleven primes, each one eliminating a k. "
        "Several had millions of digits.",
        "In 2016 the project lost its server and shut down. The search carried on at PrimeGrid, another "
        "volunteer computing project, and that October it found the twelfth: ten thousand, two hundred "
        "and twenty-three, times two to the thirty-one million, one hundred and seventy-two thousand, one "
        "hundred and sixty-five, plus one. A prime with more than nine million digits. Testing it took "
        "a home computer almost nine days.",
        "Primes like these, with more than a million digits, that eliminate a remaining k, are nicknamed "
        "Colbert numbers, a tongue-in-cheek tribute to Stephen Colbert.",
        "Five k remain. Find a prime for each one, and seventy-eight thousand, five hundred and "
        "fifty-seven is confirmed as the smallest Sierpiński number.",
    ]),
    dict(id="05_scale", chapter="How big is enormous?", beats=[
        "The search has now checked every exponent up to about forty-seven point nine million. "
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
        "The trick computers use is called the Fast Fourier Transform. Think of a number as a list of "
        "digits. Multiplying two numbers smears one list across the other, and overlapping columns add up.",
        "The transform re-expresses each list as a set of frequencies, the way an equalizer splits music "
        "into bass, mid and treble. In that form, the messy smearing becomes simple: multiply matching "
        "frequencies, one pair at a time. Then convert back, and tidy up the carries.",
        "The work now grows only a little faster than the number of digits, instead of with its square. "
        "Each squaring drops from many minutes to a fraction of a millisecond.",
    ]),
    dict(id="08_round_table", chapter="The round table", beats=[
        "There's one more saving to be had. We never need the whole product, only its remainder. "
        "And for some special numbers, that remainder comes almost for free.",
        "The transform naturally works in a circle. It treats the list of digits as if the end were "
        "joined to the beginning, like guests around a round table. Anything that overflows past the "
        "last seat wraps around to the first.",
        "For Mersenne numbers, two to some power minus one, that wrap-around is exactly right: overflow "
        "at the top really should reappear at the bottom. In 1994, Richard Crandall and Barry Fagin "
        "showed how to make it work cleanly, using a set of multipliers called weights. It's a big part "
        "of why the hunt for Mersenne primes is so efficient.",
    ]),
    dict(id="09_the_k_problem", chapter="Why k makes it hard", beats=[
        "Our numbers are different. For k times two to the n, plus one, overflow should reappear at "
        "the bottom divided by k, with its sign flipped.",
        "Divide by twenty-one thousand, one hundred and eighty-one, and you don't get a whole number. "
        "The round table no longer fits.",
        "Programs have handled this in two ways. The first is to use a table twice as big, with enough "
        "empty seats that nothing ever wraps. It's simple and exact, but every squaring has to move "
        "twice the data. proth20, the existing graphics-card tester for these numbers, works this way.",
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
        "The catch is that the weights must exist in clock arithmetic too. For our numbers, that means "
        "finding a number which, multiplied by itself about a million times over, gives minus k times "
        "two to the n. In most clock systems, most numbers have no such root, just as no whole number "
        "squares to two.",
        "As recently as 2024, Yves Gallot, whose programs power much of PrimeGrid's graphics-card work, "
        "noted that no fast method of this kind existed for numbers like ours.",
    ]),
    dict(id="11_key_idea", chapter="The key observation", beats=[
        "Colbert uses a particular clock. Its size is a Mersenne prime, two to the sixty-one, minus one. "
        "And its numbers are pairs, multiplied the way complex numbers are. Richard Crandall studied "
        "this system in 1999, and computers love it: wrapping around two to the sixty-one minus one "
        "is just a shift and an addition.",
        "Here is the observation everything rests on. In this system, every ordinary clock number has "
        "all the roots we need. Whatever k is, whatever n is, the millionth root of minus k times two "
        "to the n exists, and can be worked out in advance.",
        "Informally, the pairs form a bigger world, where every ordinary number can be written as a pair "
        "times its own mirror image. That extra room guarantees a root can always be found, much as "
        "allowing the imaginary number i guarantees that minus one has a square root.",
        "With those roots in hand, Percival's method works in exact clock arithmetic. Colbert gets the "
        "small table of the decimal method, together with the exactness and speed of whole numbers on "
        "a graphics card.",
        "Almost every piece was built by others: Crandall and Fagin, Percival, Woltman, Gallot. To our "
        "knowledge, the new part is noticing that this clock always contains the roots Percival's "
        "method needs, so that the pieces finally fit together.",
    ]),
    dict(id="12_results", chapter="What it buys", beats=[
        "On a graphics card, a squaring this size spends most of its time moving data in and out of "
        "memory, not doing arithmetic. So the amount of data is what matters.",
        "At the search frontier, the padded approach moves sixty-four megabytes per squaring. The "
        "decimal method, about thirty-four. Colbert moves twenty-four.",
        "On a GeForce RTX 4090, that makes colbert about two and a half times faster than proth20 on "
        "the same card. A full test at the frontier takes about three hours, instead of seven.",
        "And for the first time, a graphics card beats a processor on energy, not just on speed: "
        "nearly three times as many tests per kilowatt-hour as a high-end CPU running LLR2. For a "
        "project run by volunteers, electricity is the cost that counts.",
    ]),
    dict(id="13_trust", chapter="Making sure it's right", beats=[
        "A test runs for hours, and a single flipped bit, from a cosmic ray or a card running hot, "
        "would silently ruin it. Colbert guards against that in two ways.",
        "First, exactness is proven, not hoped for. Before every run, colbert checks mathematically "
        "that no intermediate value can outgrow the arithmetic, even for the worst possible input. "
        "If the check fails, it refuses to start.",
        "Second, a running checksum, called the Gerbicz–Li check. Alongside the main calculation, "
        "colbert keeps a cleverly chosen product that can be recomputed a different way. If the two "
        "ever disagree, it rewinds to the last verified point, and redoes the work.",
    ]),
    dict(id="14_impact", chapter="What it means for the search", beats=[
        "Faster arithmetic doesn't make a prime any more likely to be there. Primes this large are rare. "
        "Between where the search stands today and an exponent of fifty-seven and a half million, we "
        "expect about one fifth of a prime, across all five k combined.",
        "Finding one takes, on average, about half a million tests like these. No transform can shrink "
        "that number. What it can shrink is the cost of each test, in time and in electricity.",
        "And that matters, for a search run by volunteers. Every graphics card that can join efficiently "
        "widens the circle of people who can help, and brings the answer to a sixty-year-old question "
        "a little closer.",
        "Five numbers. The prime that settles one of them might already be sitting in the next block of "
        "candidates, waiting for someone's computer to find it.",
    ]),
    dict(id="15_credits", chapter="Credits", beats=[
        "Colbert is open source. The code, the mathematics, and the measurements are linked in the "
        "description. Thanks for watching.",
    ]),
]

TITLE = "The Last Five"
SUBTITLE = "Exact arithmetic, graphics cards, and the hunt for the final Colbert primes"
