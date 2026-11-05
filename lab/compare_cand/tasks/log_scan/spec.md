# log_scan

Write a command-line program:

    prog < access.log

It reads an access log from standard input and prints a one-pass summary.

## Input

Every line has exactly this form:

    IP - - [DD/Mon/YYYY:HH:MM:SS +0000] "METHOD PATH HTTP/1.1" STATUS BYTES

The fields are:

- `IP` is four decimal octets separated by single dots. Each octet is 1 to 3 digits with no sign and
  a value 0 .. 255. Leading zeros are allowed; the value is what the digits denote. Distinct IPs are
  counted by value, so `001.002.003.004` and `1.2.3.4` are the same IP.
- The literal ` - - ` follows the IP: one space, a hyphen, a space, a hyphen, one space.
- `DD` is exactly two digits with a value 01 .. 31 (calendar validity is not checked), then `/`.
- `Mon` is exactly one of `Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec` (case-sensitive), then `/`.
- `YYYY` is exactly four digits.
- `:` then `HH` is exactly two digits with a value 00 .. 23, `:`, `MM` exactly two digits 00 .. 59,
  `:`, `SS` exactly two digits 00 .. 59, then the literal ` +0000]`.
- One space, `"`, `METHOD` is exactly one of `GET POST PUT DELETE`, one space, `PATH`, one space, the
  literal `HTTP/1.1`, `"`.
- One space, `STATUS` is exactly three decimal digits with a value 100 .. 599.
- One space, `BYTES` is either the single byte `-` (which counts as 0) or one or more decimal digits
  with no sign and a value 0 .. 10^12. Leading zeros are allowed.

`PATH` is 1 to 64 characters from `[A-Za-z0-9/._-]` and starts with `/`.

A line is **bad** and is skipped when it does not match exactly. Any deviation makes the line bad:
two spaces between fields, a missing or extra field, a lowercase method, an octet above 255 such as
`256.1.1.1`, a 65-character path, status `600`, a `\r` before the newline, a timezone other than
`+0000`, and so on. A bad line contributes nothing to any count.

Lines are separated by `\n`; the final line may lack the terminating `\n`. An empty input (zero
bytes) has no lines. An input of a single `\n` is one empty bad line.

## Output

Print, each value separated by one space:

1. `lines <good> bad <bad>` where `<good>` is the number of good lines and `<bad>` the number of bad
   lines.
2. `status 2xx <n> 3xx <n> 4xx <n> 5xx <n>` where each `<n>` is the number of good lines whose
   status is in that class. A 1xx line is good but is not counted on this line.
3. `bytes <sum>` where `<sum>` is the total `BYTES` over the good lines (`-` counts as 0).
4. For each hour `00` .. `23` that has at least one good line, in ascending order:

       hour <HH> <count> <bytes>

   where `<count>` is the number of good lines in that hour and `<bytes>` their total `BYTES`.
5. The top 10 distinct paths by count descending, ties by path ascending in byte order:

       path <path> <count> <bytes>

   where `<bytes>` is the total `BYTES` of that path. If there are fewer than 10 distinct paths,
   print all of them; if there are none, print none.
6. `ips <distinct IP count>` over the good lines.

Every line ends with `\n`. The exit status is 0 for every input; a bad line is data, not a usage
error.

For empty input print exactly:

    lines 0 bad 0
    status 2xx 0 3xx 0 4xx 0 5xx 0
    bytes 0
    ips 0

The perf input keeps every sum inside a signed 64-bit integer.

## The algorithm (same in every language)

One pass over the input with a hand-written field scanner (no regex library), a hash map keyed by
the path holding its count and byte total, a hash set for the distinct IPs, 24 hour buckets, then a
sort of the paths for the top-10 list.
