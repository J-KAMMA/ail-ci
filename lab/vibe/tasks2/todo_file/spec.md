# todo_file

Write a command-line program:

    prog FILE

FILE is a UTF-8 text file of todo commands, one per line. The program applies them in order and
prints one or more lines for each command. Extra arguments are ignored.

## Lines and commands

Each line is examined as it is. A line is split at its first two spaces:

- the first token is the command name;
- for `add`, the second token is the ID and everything after the second space is the TEXT;
- for `done`, `remove`, `show` the rest of the line is the ID only (no further spaces);
- `list` and `stats` take no arguments.

A blank line is skipped and is not an error.

`ID` is an ASCII decimal integer in 1 .. 2147483647. Leading zeros are allowed. Any other ID is
malformed.

`TEXT` is everything after the single space that follows the ID. It may be empty only for a
malformed `add`; a non-empty TEXT may contain spaces, tabs and any other characters, and its
leading and trailing spaces are part of the text.

A command whose arguments are malformed, a known command with extra arguments, an unknown command,
a duplicate `add` ID, or `done`/`remove`/`show` of an ID that does not exist is rejected: it prints
`error OP` (OP is the command word, or `error` when the line has no command word) and does not
change the state. `done` of an item that is already done is also rejected. Rejections are counted.

Successful commands print:

- `add` -> `added ID`
- `done` -> `done ID`
- `remove` -> `removed ID`
- `show` -> `todo ID open TEXT` or `todo ID done TEXT`
- `list` -> `list N`, then one `todo ID open TEXT` line for every open item in ascending ID order
  (nothing after the first line when there are none)
- `stats` -> `stats total T open O done D chars C errors E`, where T is the number of current items
  (open plus done, not removed), C is the sum of `len(TEXT)` over those items, and E is the number
  of rejected commands so far.

`remove` removes an open or done item. A removed ID may be added again later (the new text replaces
the old). ID order is numeric order.

TEXT is written exactly as it was read. `len(TEXT)` counts Unicode code points. Every printed line
ends with `\n`; the exit status is 0.
