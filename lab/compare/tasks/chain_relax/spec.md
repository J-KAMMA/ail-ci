# chain_relax

Write a command-line program:

    prog N T SEED

The program fills a ring of N floating-point heights from a seeded generator, relaxes it with T
sweeps of the update rule below, and prints summary values. All floating-point values are IEEE-754
binary64 (`double`), and every operation must be performed exactly as written, one rounded
operation at a time, in the order given: no fused multiply-add, no reassociation, no "fast math",
no extended precision.

## Arguments

All three are decimal integers written with digits only (leading zeros allowed):
1 <= N <= 10000000, 0 <= T <= 1000000, 0 <= SEED <= 18446744073709551615. A wrong number of
arguments or an invalid value: print nothing on standard output and exit with status 1.

## Initial heights

Let x = SEED, an unsigned 64-bit integer. For i = 0, 1, ..., N-1 in this order:

    x = (x * 6364136223846793005 + 1442695040888963407) mod 2^64
    h[i] = (double)( ((x >> 33) mod 2001) - 1000 ) / 64.0

(`x >> 33` is a logical right shift by 33 bits; the subtraction is done on integers, giving a
value in -1000 .. 1000, which is converted exactly to a double and divided by 64.0.)

## Sweeps

For s = 1 .. T: if s is odd, visit i = 0, 1, ..., N-1; if s is even, visit i = N-1, N-2, ..., 0.
At each visited i, using the *current* contents of h (so neighbours already updated in this sweep
have their new values), do:

    l = h[(i + N - 1) mod N]
    r = h[(i + 1) mod N]
    c = h[i]
    d = (l + r) - (c + c)
    g = d / (1.0 + sqrt(d * d + 0.0625))
    h[i] = c + 0.375 * g

The parentheses give the exact evaluation order: `l + r`, `c + c`, their difference;
`d * d`, plus 0.0625, square root (IEEE correctly rounded), plus 1.0 on the left (`1.0 + root`),
division; `0.375 * g`, added to c (`c + product`). For N = 1 both neighbours are h[0] itself; for
N = 2 both neighbours are the other element.

## Output

After the sweeps compute, each with a running double starting at 0.0 and i going 0 .. N-1:

    sum    = sum + h[i]
    energy = energy + t * t     where t = h[(i + 1) mod N] - h[i]

and print these lines:

    sum <sum>
    energy <energy>
    min <smallest h[i]>
    max <largest h[i]>
    first <h[0]>
    middle <h[N / 2]>        (N / 2 rounded down)
    last <h[N - 1]>

Each value is printed in fixed-point notation with exactly 9 digits after the decimal point,
correctly rounded from the exact binary value (as C's `printf("%.9f")` does; the tests contain no
value that lies exactly halfway between two 9-digit results). If the printed digits are all zero,
print `0.000000000` without a minus sign (so a negative value that rounds to zero, or -0.0, prints
as `0.000000000`). Every line ends with `\n`. Exit status 0.
