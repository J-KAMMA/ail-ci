# rail_transfer

Write a command-line program:

    prog

The program reads a rail network and a list of trip queries from standard input and prints, for
every query, the best trip under the cost rules below. It takes no arguments (extra arguments
are ignored).

## Input

The input is always well-formed; your program does not need to check it. All numbers are
non-negative decimal integers, fields are separated by single spaces, every line ends with `\n`.

    N M Q
    X_0 X_1 ... X_{N-1}
    M lines:  U V L T
    Q lines:  S D

- N stations numbered 0 .. N-1 (1 <= N <= 300000), M track segments (0 <= M <= 1000000),
  Q queries (0 <= Q <= 1000).
- X_i (0 <= X_i <= 1000) is the *transfer time* of station i.
- Segment U V L T: a two-way connection between stations U and V (U may equal V) served by line L
  (0 <= L < 100000) taking T minutes (0 <= T <= 100000) in either direction. Several segments may
  connect the same pair of stations, with the same or different lines.
- Query S D: travel from station S to station D.

## Trips and their cost

A trip is a sequence of rides. A *ride* is a non-empty walk along consecutive segments that all
belong to one line L (a ride may use the same segment more than once and may go back and forth).
The trip starts at S, each ride starts where the previous one ended, and the last ride ends at D.
Consecutive rides may use the same line or different lines.

- The *time* of a trip is the sum of T over all segments used (counted every time they are used)
  plus, for every ride except the first, the transfer time X of the station where that ride
  starts.
- The *boardings* of a trip is its number of rides.

Among all trips from S to D, the best trip has the smallest time; among those, the fewest
boardings. If S = D the best trip is the empty trip: time 0, 0 boardings.

## Output

For each query, in input order, print one line: `T B` (the time and boardings of the best trip)
or `none` if no trip from S to D exists (and S != D). Every line ends with `\n`. Exit status 0.
(The best time never exceeds 2^62, so signed 64-bit integers are enough.)
