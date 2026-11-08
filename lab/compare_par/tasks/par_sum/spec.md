# par_sum

threads: 4

Write a command-line program. It reads one integer `N` from standard input (nothing else) and writes
one line to standard output:

    <sum>

where the sum is over `n` in `1..N` of `steps(n) * (n % 7 - 3)`, and `steps(n)` is the Collatz step
count of `n`: start with `m = n` and `c = 0`; while `m != 1`, replace `m` by `m / 2` when `m` is
even and by `3 * m + 1` when it is odd, and add 1 to `c`. The step count of 1 is 0. The sum for
`N = 0` is 0.

The program computes the terms with 4 workers (threads or goroutines) over contiguous chunks of
`1..N`, keeps one partial sum per worker, and adds the partials in chunk order. Every `n` is
computed exactly once and the worker count never changes the result.

Input guarantees: `0 <= N <= 20000000`. Ints are signed 64-bit. For every input in range the exact
sum fits int64 (the largest runnable sums are about 5e4 at `N = 1e5` and -1.2e5 at `N = 1e6`), so
the sum never leaves the range on any case this task runs. A case whose exact sum would exceed
int64 needs `N` around 1e16, which the task cannot iterate; `gen.py` records that boundary as
`OVERFLOW_N` and does not emit it as a runnable case. This task is therefore excluded from the
timing of that boundary. An implementation that does leave int64 must stop loudly (an empty stdout
and exit status 1) rather than wrap:

    OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints)

Examples:

    0   -> 0
    1   -> 0
    3   -> -1          (0*(-2) + 1*(-1) + 7*0)
    7   -> -13         (steps 0, 1, 7, 2, 5, 8, 16 with multipliers -2..3, then -3)
