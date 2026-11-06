# par_collatz

threads: 4

Write a command-line program. It reads `N` and `W` from standard input (two integers,
whitespace separated, nothing else) and writes one line to standard output:

    <largest step count> <smallest n that reaches it> <sum of all step counts>

The step count of `n` is the number of steps of the Collatz map that reach 1: start with `m = n`
and `c = 0`; while `m != 1`, replace `m` by `m / 2` when `m` is even and by `3 * m + 1` when it is
odd, and add 1 to `c`. The step count of 1 is 0.

The program fills a results array of `N` entries, the entry for `n` (1 <= n <= N) holding the step
count of `n`, using `W` workers: every `n` is computed exactly once. It then reduces the array
sequentially, in index order, into the three numbers above. The largest step count and the smallest
`n` that reaches it refer to step counts only; ties keep the smallest `n`. The sum is the sum of all
`N` step counts and can exceed 32 bits.

`W` workers means `W` threads (or goroutines); when `W` is greater than `N`, the program may use
fewer workers because there are fewer items of work. The worker count never changes the result.

Input guarantees: `1 <= N <= 20000000` and `1 <= W <= 1024`. All values the Collatz map reaches for
`n <= N` stay below 2^63, so int64 arithmetic is exact; `gen.py` asserts this for every case it
generates.

Examples:

    1 1      -> 0 1 0
    3 8      -> 7 3 8          (0, 1, 7)
    6 1      -> 8 6 23         (0, 1, 7, 2, 5, 8)
