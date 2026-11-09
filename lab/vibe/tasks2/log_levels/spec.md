# log_levels

Write a command-line program:

    prog

It reads log lines from standard input and prints per-level statistics. It takes no arguments
(extra arguments are ignored).

## Input

Split the input into lines on `\n` and remove one trailing `\r` from each line. A line that is
empty is skipped.

A non-empty line must have the form

    [LEVEL] MESSAGE

- The line starts with `[`. The first `]` ends the level; the text between the brackets must be one
  of `TRACE`, `DEBUG`, `INFO`, `WARN`, `ERROR`, `FATAL` (exactly, case-sensitive).
- If anything follows the `]`, its first character must be a space; the message is everything after
  that one space. The message may be empty and may contain any characters, including `]`, spaces
  and Unicode. The length of a message is counted in Unicode code points.
- Any other non-empty line is bad: it is counted and ignored.

## Output

    lines <N> bad <B>

where N is the number of good lines and B the number of bad lines. Then one line for every level in
the fixed order TRACE, DEBUG, INFO, WARN, ERROR, FATAL, including levels that did not occur:

    level <LEVEL> count <C> chars <L> longest <M>

- C is the number of lines at that level;
- L is the total length of their messages;
- M is the length of the longest message at that level (0 when there are none).

Every line ends with `\n`; exit status 0.
