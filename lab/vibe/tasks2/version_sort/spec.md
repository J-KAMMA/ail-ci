# version_sort

Write a command-line program:

    prog

It reads version strings, one per line, from standard input and prints them in precedence order.
It takes no arguments (extra arguments are ignored).

## Input and grammar

Split the input into lines on `\n` and remove one trailing `\r` from each line. Skip blank lines.
Every other line must match

    MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]

- `MAJOR`, `MINOR`, `PATCH` are one or more ASCII digits (leading zeros allowed) with value in
  0 .. 9223372036854775807.
- `PRERELEASE` and `BUILD`, when present, are one or more identifiers separated by `.`; every
  identifier is a non-empty run of ASCII letters, digits and `-`. A numeric identifier (all ASCII
  digits) must also fit in 0 .. 9223372036854775807; leading zeros are allowed.
- No other characters are allowed (so Unicode makes a line invalid).
- An invalid or empty line is counted as bad and skipped; blank lines are not bad.

## Precedence

Compare in this order:

1. MAJOR, then MINOR, then PATCH, numerically.
2. A version without `PRERELEASE` has higher precedence than one with it.
3. If both have `PRERELEASE`, compare identifiers from left to right:
   - two numeric identifiers compare numerically;
   - a numeric identifier has lower precedence than a non-numeric one;
   - two non-numeric identifiers compare in ASCII order;
   - if all shared identifiers are equal, the version with fewer identifiers has lower precedence.
4. `BUILD` is ignored for precedence.

Versions with equal precedence are ordered by the original line in ascending byte order. This makes
the output deterministic.

## Output

    bad <B> sorted <N>

then the N accepted lines in order, each exactly as it appeared after the trailing `\r` was
removed. Every line ends with `\n`; exit status 0.
