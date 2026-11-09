# expense_split

Write a command-line program:

    prog

It reads expense lines from standard input and prints each person's net balance. It takes no
arguments (extra arguments are ignored).

## Input

Each non-empty line is split on whitespace (spaces and tabs):

    PAYER AMOUNT P1 P2 ... Pk

- `PAYER` and every `Pi` is a non-empty name token (any characters except whitespace, so Unicode
  names are allowed). The participants P1 .. Pk must be distinct; a repeated participant makes the
  line bad. The payer need not be one of the participants.
- `AMOUNT` is an ASCII decimal integer in 0 .. 1000000000000 (10^12). Leading zeros are allowed.
- A line with fewer than 3 tokens, an invalid or out-of-range amount, or a repeated participant is
  bad: it is counted and ignored. Blank lines are skipped and are not bad.

## Splitting

For a good line with k participants, let `q, r = divmod(AMOUNT, k)`. Participant i (counting from
0 in input order) owes `q + 1` if `i < r`, otherwise `q`. The payer's net balance increases by
`AMOUNT`, and each participant's net balance decreases by the amount they owe. The sum of all net
balances is therefore 0 (this fits in a signed 64-bit integer for every valid input).

## Output

    bad <B>
    balance <name> <net>        (one line per person, names ascending)
    total <sum>

- B is the number of bad lines.
- Persons are the names that occur as payer or participant on at least one good line; a person who
  only owes money still appears with a negative balance.
- Name order is ascending order of the name strings (Unicode code point order; for ASCII this is
  byte order). Print only the lines that exist: with no good lines the output is just `bad 0` and
  `total 0`.
- Every line ends with `\n`; exit status 0.
