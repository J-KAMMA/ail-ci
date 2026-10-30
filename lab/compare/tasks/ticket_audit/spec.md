# ticket_audit

Write a command-line program:

    prog FILE

FILE is a ticket-sales log in the "TKT" text format below. The program validates it record by
record, stops at the first error with an exact message and exit status, and otherwise prints a
summary.

## Lines

The file is split into lines at `\n`; a single final `\n` is optional (if the file ends with `\n`,
the empty piece after it is not a line). Lines are numbered from 1. Every byte is significant:
there is no whitespace trimming, and `\r`, tabs and non-ASCII bytes are just characters that do not
fit any field (so they cause syntax errors).

- Line 1 must be exactly `TKT/1`.
- Every following line is one record: fields separated by `|`, the first field being the record
  type. The last record must be an `END` record, and no line may follow it.

## Records

| type | fields after the type | meaning |
|---|---|---|
| `V` | code, name, capacity | defines a venue |
| `E` | event, venue code, date, time, price | defines an event at a venue |
| `S` | event, seat, buyer | sells a seat of an event |
| `R` | event, seat | refunds a sold seat |
| `END` | count, cents | closing record |

A record with an unknown type (including an empty line) or with the wrong number of fields is a
`syntax` error.

## Fields

Each field has a *syntax* rule (its shape) and possibly a *value* rule.

| field | syntax | value rule |
|---|---|---|
| venue code | exactly 3 letters `A-Z` | |
| name | 1 to 40 bytes from 0x20 .. 0x7E except `|`; the first and last byte are not a space | |
| capacity | 1 to 6 digits | no leading zero; 1 .. 100000 |
| event | exactly 6 digits d1 .. d6 | (3*d1 + d2 + 3*d3 + d4 + 3*d5 + d6) mod 10 = 0 |
| date | `YYYY-MM-DD` (4 digits, `-`, 2 digits, `-`, 2 digits) | year 2000 .. 2099; month 01 .. 12; day 01 .. last day of that month (February has 29 days when the year is divisible by 4, else 28) |
| time | `HH:MM` (2 digits, `:`, 2 digits) | HH 00 .. 23, MM 00 .. 59 |
| price | 1 to 4 digits, `.`, exactly 2 digits | no leading zero in the part before `.` unless that part is exactly `0`; the amount in cents is a multiple of 5 |
| seat | one letter `A-Z` followed by 1 to 3 digits | the number has no leading zero (so 1 .. 999) |
| buyer | 4 to 12 bytes from `a-z` `0-9`, the first one a letter | |
| count | 1 to 9 digits | no leading zero unless it is exactly `0` |
| cents | 1 to 12 digits | no leading zero unless it is exactly `0` |

## Rules per record

Records are processed in order. The state is: the defined venues, the defined events (each with
its venue and price), and for each event the set of seats currently sold.

- `V`: `duplicate` if a venue with this code is already defined.
- `E`: `reference` if its venue is not defined; then `duplicate` if an event with this number is
  already defined.
- `S`: `reference` if the event is not defined; then `duplicate` if the seat is currently sold for
  that event; then `capacity` if the event already has as many currently sold seats as its venue's
  capacity. Otherwise the seat becomes sold.
- `R`: `reference` if the event is not defined, or if the seat is not currently sold for that
  event. Otherwise the seat is no longer sold (it may be sold again later).
- `END`: `summary` if count is not the number of records before it (all `V`, `E`, `S`, `R`
  records; the header line and the END line are not counted), or if cents is not the current
  revenue in cents (the sum of the prices of all currently sold seats).

For one record, the checks happen in this order, and the first failing one is reported:
type and field count (`syntax`), the syntax of every field (`syntax`), the value rule of every
field (`value`), then the record's own rules in the order listed above.

## Errors

On the first error print exactly one line

    line N: CATEGORY

and exit with the status of the category:

| CATEGORY | exit status | when |
|---|---|---|
| `header` | 2 | line 1 is not exactly `TKT/1` (also for an empty file, with N = 1) |
| `syntax` | 3 | as above |
| `value` | 4 | as above |
| `reference` | 5 | as above |
| `duplicate` | 6 | as above |
| `capacity` | 7 | as above |
| `summary` | 8 | END mismatch (N = the END line); a line after the END record (N = that line); the file ends without an END record (N = number of lines + 1) |

Nothing else is printed on an error. Wrong number of arguments (exactly one is required) or an
unreadable file: print nothing, exit status 1.

## Output on success (exit status 0)

    venues V events E sold S refunds R
    revenue X
    CODE events=n tickets=t revenue=X        (one line per venue, in ascending code order)
    top EVENT t                              (up to 3 lines)

- V, E: numbers of venues and events. S: number of `S` records, R: number of `R` records.
- revenue: the current revenue (all currently sold seats).
- Per venue: n = number of its events, t = number of currently sold seats over its events,
  revenue = the revenue of those seats.
- `top` lines: the events with the most currently sold seats, at most 3, ordered by that number
  descending, ties by event number ascending (as a 6-digit string, i.e. numerically). Events with
  0 sold seats are included if needed to fill the 3 lines. t is that number.
- Money X is printed as whole units, `.`, two digits of cents (`0.05`, `12.30`, `1234567.85`).

Every line ends with `\n`.
