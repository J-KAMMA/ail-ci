# berth_sim

Write a command-line program:

    prog

The program reads a harbour description and a list of ship arrivals from standard input,
simulates the harbour with the rules below, and prints statistics. It takes no arguments (extra
arguments are ignored).

## Input

The input is always well-formed; your program does not need to check it. All numbers are
non-negative decimal integers, fields are separated by single spaces, every line ends with `\n`.

    B S
    B lines:  CLASS RATE
    S lines:  ID ARRIVAL SIZE CARGO PRIORITY OPERATOR

- B berths (1 <= B <= 2000), numbered 0 .. B-1 in input order. CLASS is 1, 2 or 3; RATE
  (1 .. 1000) is the cargo the berth handles per minute.
- S ships (0 <= S <= 3000000), in no particular order. ID: unique, 0 .. 10^9. ARRIVAL: minute
  0 .. 10^9. SIZE: 1, 2 or 3. CARGO: 0 .. 10^6. PRIORITY: 0 .. 9 (0 is the most urgent).
  OPERATOR: 0 .. 10^6.

## Rules

Time is measured in whole minutes. A ship of size z can only use a berth whose class is at least z.
Every ship is eventually served (each size has a berth that fits it in all test inputs).

Service time of a ship at berth b: `ceil(CARGO / RATE_b) + setup`, where setup is 1 if the
previous ship served at berth b had the same OPERATOR, and 4 otherwise (also 4 for the first ship
of a berth). A ship that starts at minute t occupies the berth until minute t + service time, when
it departs and the berth becomes free.

The harbour changes state only at *event times*: minutes at which some ship arrives or some ship
departs. At each event time t, in this order:

1. All ships departing at t leave; their berths become free.
2. All ships arriving at t join the waiting set.
3. Assignment: go through the free berths in ascending order of (CLASS, berth number). Each such
   berth takes the best waiting ship that fits it, if there is any, and that ship starts service
   at t (the berth is then busy). "Best" means smallest PRIORITY, then earliest ARRIVAL, then
   smallest ID. A berth that finds no fitting ship stays free.

(So within one event time, a smaller-class berth chooses before a larger-class berth, and a berth
that becomes free at t can take a ship that arrives at t.)

## Output

    ships <S>
    makespan <M>
    wait total <W> max <X> ship <I>
    berth <b> ships <n> busy <u>        (one line for each berth b = 0 .. B-1)
    digest <G>

- M: the minute of the last departure (0 if S = 0).
- The wait of a ship is (start of service - ARRIVAL). W is the sum of all waits, X the largest
  wait and I the smallest ID among the ships with that largest wait (`wait total 0 max 0 ship -1`
  if S = 0).
- For each berth: n is the number of ships it served, u the total minutes it was busy (the sum of
  the service times of its ships).
- G: go through the ships in ascending order of ID; start with g = 0 and for each ship do
  g = (g * 1000003 + START * 31 + BERTH) mod 1000000007, where START is the minute the ship started
  service and BERTH its berth number. (All intermediate values fit in a signed 64-bit integer.)

All numbers are decimal, every line ends with `\n`. Exit status 0.
