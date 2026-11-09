# gradebook

Write a command-line program:

    prog

It reads one score row per line from standard input and prints per-student statistics. It takes no
arguments (extra arguments are ignored).

## Input

Each non-empty line is split on whitespace into exactly three tokens:

    NAME ASSIGNMENT SCORE

- `NAME` and `ASSIGNMENT` are non-empty tokens without whitespace (Unicode is allowed).
- `SCORE` is an ASCII decimal integer in 0 .. 1000000000000 (10^12), leading zeros allowed.
- A line with a different token count, or with an invalid or out-of-range score, is bad and is
  counted; blank lines are skipped and are not bad.
- Every row counts, even if the same NAME/ASSIGNMENT pair occurs more than once.

## Statistics

For each name, `count` is its number of rows, `sum` is the sum of its scores, and `avg` is
`sum // count` (integer floor). Sums fit in a signed 64-bit integer for every valid input.

## Output

    bad <B>
    <name> count <C> sum <S> avg <A>        (one line per name)

The name lines are ordered by `avg` descending, ties by name ascending in byte order. When there are
no good rows only the `bad` line is printed. Every line ends with `\n`; exit status 0.
