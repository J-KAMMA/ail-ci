# jsonl_stats

Write a command-line program:

    prog

It reads JSON Lines from standard input and aggregates amounts by tag and counts rows per user. It
takes no arguments (extra arguments are ignored).

## Input

Split the input into lines on `\n` and remove one trailing `\r` from each line. A line that is empty
or contains only spaces and tabs is skipped and is not bad. Every other line must be one JSON
object with:

- `"user"`: a required string;
- `"amount"`: a required integer (a JSON boolean is not an integer) in the signed 64-bit range
  -9223372036854775808 .. 9223372036854775807;
- `"tag"`: an optional string; when it is missing the tag is the empty string.

A line is bad when it is not valid JSON, is not an object, has a missing or wrongly typed field, or
has an amount outside the signed 64-bit range. Extra fields are ignored. Bad lines are counted and
skipped. JSON escape sequences and Unicode are decoded normally.

## Output

    bad <B> tags <T> users <U>

- B is the number of bad lines, T the number of distinct tags, U the number of distinct users.
- Then one line per tag in ascending tag order:

      tag <tag> count <C> total <S>

  where C is the number of rows with that tag and S is the sum of their amounts (it fits in a
  signed 64-bit integer).
- Then up to 10 user lines, ordered by count descending and then user ascending:

      user <user> <C>

  where C is the number of good rows for that user.

Strings are printed decoded (not JSON-escaped). Every line ends with `\n`; exit status 0.
