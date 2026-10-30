# scar_life

Write a command-line program:

    prog RULE GENS

The program reads a starting grid from standard input, runs the cellular automaton described
below for GENS generations, and prints per-generation counts and the final grid.

## Arguments

- RULE has the form `B<digits>/S<digits>`, where each `<digits>` is a (possibly empty) list of
  *weight codes* in strictly increasing order. The weight codes are `0`-`9` for 0 .. 9 and the
  uppercase letters `A`, `B`, `C` for 10, 11, 12. Examples: `B5A/S34`, `B/S`, `B0123456789ABC/S`.
  Anything else (lowercase letters, repeated or decreasing codes, missing `B`, `/` or `S`, extra
  characters) is invalid.
- GENS is a decimal integer 0 .. 100000 written with digits only (leading zeros allowed).

## Input grid

Standard input is a text:

- line 1: `W H`, two decimal integers 1 .. 4096 (digits only, no leading zeros) separated by one
  space: the width and height;
- then exactly H lines of exactly W characters each, every character `.` (dead) or `o` (alive).

Every line ends with `\n`, except that the `\n` after the last grid line is optional. Nothing may
follow the last grid line (not even an empty line). There is no `\r`, no other whitespace, no other
character. The starting grid has no scars.

## The automaton

Every cell is in one of three states: *dead*, *alive*, or *scar*. The grid is a torus: column
W-1 is next to column 0 and row H-1 is next to row 0.

The *weight* of a cell is computed from its eight neighbour positions: the four orthogonal
neighbours (up, down, left, right) count 2 each if alive, the four diagonal neighbours count 1
each if alive; dead and scar cells count 0. So the weight is 0 .. 12. On narrow grids several
neighbour positions can be the same cell (or the cell itself, when W = 1 or H = 1); every position
counts separately with its own factor (for example on a 1 x 1 grid with its only cell alive the
weight is 4 * 2 + 4 * 1 = 12).

One generation computes the new state of every cell from the old states of all cells
(simultaneously):

- an alive cell stays alive if its weight is in the S list; otherwise it becomes a scar;
- a dead cell becomes alive if its weight is in the B list; otherwise it stays dead;
- a scar becomes dead (scars last exactly one generation and can never be born directly).

## Output

For each generation g = 1 .. GENS print one line

    g A S

where A is the number of alive cells and S the number of scars after generation g. Then print the
final grid (after GENS generations; the starting grid if GENS = 0): H lines of W characters,
`.` for dead, `o` for alive, `x` for scar. Every line ends with `\n`. Exit status 0.

## Errors

If the number of arguments is not exactly two, RULE or GENS is invalid, or the input grid does not
follow the format above: print nothing on standard output (anything on standard error is fine)
and exit with status 1. Nothing may be printed before all of this has been checked.
