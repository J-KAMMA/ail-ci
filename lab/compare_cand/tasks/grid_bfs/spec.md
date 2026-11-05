# grid_bfs

Write a command-line program:

    prog < grid

It reads a character grid and a list of shortest-path queries, runs one breadth-first search per
query, and prints the distance and how many cells the search dequeued.

## Input

Line 1 is three decimal integers separated by single spaces:

    H W Q

with `1 <= H, W <= 2000` and `0 <= Q <= 20`.

Then exactly `H` lines follow, each exactly `W` bytes long, over the alphabet `.` (open) and `#`
(wall). No other byte is allowed on a grid line.

Then exactly `Q` lines follow, each four decimal integers separated by single spaces:

    r1 c1 r2 c2

Each value is 0-based and must satisfy `0 <= r1, r2 < H` and `0 <= c1, c2 < W`.

Lines are separated by `\n`. A final `\n` after the last line is optional (and is not an extra
line). There is no other trailing data: the input has exactly `1 + H + Q` lines.

A **malformed** input is: a line 1 that is not three in-range integers, any grid line whose length
is not exactly `W` or that contains a byte other than `.` or `#`, a query line that is not four
integers, a query outside the grid, a missing or an extra line. For a malformed input the program
prints nothing on standard output and exits with status 2.

## The search (same in every language)

For each query `(r1, c1, r2, c2)`, in input order:

- If the start cell or the target cell is a wall, no search runs: the distance is `-1` and `seen`
  is `0`.
- Otherwise run a breadth-first search from the start cell with 4-neighbour moves in the order
  **up, down, left, right** (that is `(r-1,c)`, `(r+1,c)`, `(r,c-1)`, `(r,c+1)`), using one flat
  array of distances indexed by `r * W + c` (initialised to `-1`, reset for every query) and one
  array used as a FIFO queue. A cell is enqueued at most once. `seen` counts the cells taken from
  the queue (dequeued). The search stops when the target is dequeued (its distance is the answer)
  or when the queue becomes empty (the target is unreachable, distance `-1`).

The distance `D` is the number of moves on the shortest path, or `-1` when the target is
unreachable or either endpoint is a wall. The target is tested when it is dequeued, not when it is
enqueued, so `seen` includes the target's dequeue.

## Output

For each query, in input order, print one line:

    dist <D> seen <S>

where `<D>` is the distance and `<S>` is `seen` for that query. After the last query print:

    total <T>

where `<T>` is the sum of all `D` that are not `-1`. Every line ends with `\n`. The exit status is
0 for a well-formed input.

## The algorithm (same in every language)

Read all of standard input, split it into lines, validate every line, then for each query reset the
flat distance array to `-1`, run the BFS above with a FIFO queue over the grid bytes, and accumulate
the total. No hash map, no priority queue, no heuristic: the queue order is exactly the four
neighbours in the order given above.
