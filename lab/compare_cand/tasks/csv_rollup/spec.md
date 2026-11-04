# csv_rollup

Write a command-line program:

    prog < data.csv

It reads one CSV file from standard input and rolls it up by `(region, product)`.

## Input

The first line is the header `region,product,qty,price`. If the input is empty (zero bytes) there is
no header and the program prints the empty report described below. Otherwise the first line is
dropped without being checked or counted, even if it is not exactly the header text.

Every later line has four comma-separated fields:

- `region` and `product` are 1 to 16 characters from `[a-z0-9_]`.
- `qty` is a decimal integer in -1000 .. 1000. A single leading `-` is allowed (so `-0` and `-007`
  are valid and mean 0 and -7); a leading `+` is not allowed. Leading zeros are allowed.
- `price` is a decimal integer in 0 .. 10000000 (cents). It has digits only; no sign is allowed.
  Leading zeros are allowed.

A line is **bad** and is skipped when any of these hold: it does not have exactly four fields, any
field is empty, any field contains a character outside its allowed set, or a number is not a valid
decimal integer or is outside its range.

Lines are separated by `\n`; the final line may lack the terminating `\n`. A `\r` is an ordinary
byte: it is not stripped, so a CRLF line has a `\r` in its last field and is bad. A blank line has
one field and is bad.

## Roll-up

For each distinct good `(region, product)` pair, collect:

- `qty_sum` = the sum of its `qty` values;
- `revenue` = the sum of `qty * price` over its rows.

The perf input keeps every sum inside a signed 64-bit integer; the arithmetic is integer
arithmetic. A line that is bad is counted as bad and contributes nothing.

## Output

Print, each value separated by one space:

1. `rows <good> bad <bad> groups <n>` where `<good>` is the number of good data rows, `<bad>` the
   number of bad lines and `<n>` the number of distinct groups.
2. The top 10 groups by `revenue` descending, ties by `region` then `product` ascending in byte
   order (a proper prefix comes first), one per line:

       <region> <product> <qty_sum> <revenue>

   If there are fewer than 10 groups, print all of them; if there are none, print none.
3. One line per region in ascending byte order:

       region <region> revenue <sum>

   where `<sum>` is the sum of that region's groups' revenues.
4. `total <sum of all revenue>`.

For empty input (no header, no data) print exactly:

    rows 0 bad 0 groups 0
    total 0

Header-only input and input whose data lines are all bad print the same first line with their own
bad count, no group or region lines, and `total 0`.

Every line ends with `\n`. The exit status is 0 for every input; a bad line is data, not a usage
error.

## The algorithm (same in every language)

One pass over the input, a hash map keyed by the `(region, product)` pair, then a sort of the groups
for the top-10 list and of the region names for the region list.
