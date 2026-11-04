# tsv_join

Write a command-line program:

    prog < data.tsv

It reads one two-section TSV file from standard input and joins orders to users.

## Input

The input has two sections. A line `#users` starts the first; each later line until `#orders` is

    user_id<TAB>name<TAB>country

A line `#orders` starts the second; each later line is

    order_id<TAB>user_id<TAB>amount

`<TAB>` is a single byte `\t`. `user_id` and `order_id` are decimal integers in 1 .. 2000000000
(digits only, no sign). `name` is 1 to 24 characters from `[A-Za-z0-9 ._-]` (letters, digits, space,
dot, underscore, hyphen). `country` is exactly 2 characters from `[A-Z]`. `amount` is a decimal
integer in 0 .. 100000000 (cents), digits only. Leading zeros are allowed in every number; the value
is what the digits denote.

Lines are separated by `\n`; the final line may lack the terminating `\n`. A `\r` is an ordinary
byte, so a CRLF line has a `\r` in its last field and is bad.

A line in the users section is **bad** and is skipped when any of these hold:

- it does not have exactly three tab-separated fields;
- any field is empty;
- `user_id` is not a decimal integer in 1 .. 2000000000;
- `name` is not 1 to 24 characters from the allowed set;
- `country` is not exactly 2 letters `[A-Z]`;
- its `user_id` is already known from an earlier good users line (the first one wins).

A line in the orders section is **bad** and is skipped when any of these hold:

- it does not have exactly three tab-separated fields;
- any field is empty;
- `order_id` is not a decimal integer in 1 .. 2000000000;
- `user_id` is not a decimal integer in 1 .. 2000000000;
- `amount` is not a decimal integer in 0 .. 100000000.

An order whose `user_id` is a decimal integer in range but is not a known user (no good users line
carries that id) is **unmatched**: it is a good order (it counts in `orders`) but contributes no
amount.

Lines before the first `#users` are ignored and are not counted. If the input contains no `#users`
line, or no `#orders` line after it, print the zero report below and exit 0.

## Output

Print, each value separated by one space, in this order:

1. `users <good> orders <good> bad <bad> unmatched <n>` where `<good>` after `users` is the number of
   good users lines (equal to the number of known users), `<good>` after `orders` is the number of
   good orders lines (matched and unmatched), `<bad>` is the total number of bad lines in both
   sections, and `<n>` is the number of unmatched orders.
2. One line per country with at least one matched order, by total amount descending, ties by country
   ascending in byte order:

       country <cc> orders <count> amount <sum>

   where `<count>` is the number of matched orders of users in that country and `<sum>` their total
   amount.
3. The top 10 users that have at least one matched order, by matched amount descending, ties by
   `user_id` ascending:

       user <id> <name> <amount>

   If fewer than 10 users have a matched order, print all of them; if none do, print none.
4. `total <sum of all matched amounts>`.

Every line ends with `\n`.

For input with no sections print exactly:

    users 0 orders 0 bad 0 unmatched 0
    total 0

The exit status is 0 for every input; a bad line is data, not a usage error.

## The algorithm (same in every language)

One pass builds a hash map from `user_id` to `(name, country)`. One pass over the orders looks each
`user_id` up in that map and accumulates, in hash maps, the amount and order count per user and per
country. Then both maps are sorted for the output: countries by amount then country, users by amount
then user id.

All sums fit in a signed 64-bit integer for every input this spec allows: at most 4,000,000 orders of
at most 100,000,000 each is 4 * 10^14.
