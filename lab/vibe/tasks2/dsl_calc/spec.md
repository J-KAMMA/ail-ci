# dsl_calc

Write a command-line program:

    prog

It reads a small stack-language program from standard input, runs it, and prints the final stack.
It takes no arguments (extra arguments are ignored).

## Lines

Lines are split on `\n`; a trailing `\r` is removed. Leading and trailing spaces and tabs are
ignored. Blank lines and lines whose first character is `#` are comments and do nothing.

Every other line is one command: the first whitespace-separated token is the command, the rest are
its arguments.

| command | effect |
|---|---|
| `push N` | push N |
| `add` | pop b, pop a, push a+b |
| `sub` | pop b, pop a, push a-b |
| `mul` | pop b, pop a, push a*b |
| `dup` | push a copy of the top value |
| `swap` | exchange the top two values |
| `drop` | discard the top value |
| `store NAME` | pop the top value and store it under NAME |
| `load NAME` | push the value stored under NAME |
| `print` | print `value N` for the top value |
| `clear` | remove every value |

`N` is an optional `-` followed by one or more ASCII digits; leading zeros are allowed and the
value must fit in a signed 64-bit integer. `NAME` is any single non-empty token. Stores persist
across lines, and a later `store` replaces the value.

## Errors

An error prints one line `error <line> <reason>` where `<line>` is the 1-based physical line number
in the input and `<reason>` is one of:

- `stack` -- an operation needs more values than the stack holds (`dup`, `swap`, `drop`, `store`,
  `print`, `add`, `sub`, `mul`);
- `overflow` -- the result of `add`, `sub` or `mul` is outside the signed 64-bit range; the two
  operands are left on the stack unchanged;
- `var` -- `load` of a name that was never stored;
- `int` -- the `push` argument is not a valid signed 64-bit decimal integer;
- `cmd` -- an unknown command, or a missing or extra argument.

After an error the program continues with the next line. A failed `push`, `store` or `load` does not
change the stack or the stores. When a command has both the wrong number of arguments and too few
stack values, `cmd` is reported.

## Output

Errors and `print` lines appear in execution order. At the end print

    stack <k>
    <v1> <v2> ... <vk>

where `<k>` is the number of values and the values are listed from the bottom of the stack to the
top, separated by single spaces (no value line when k is 0). Every line ends with `\n`; exit
status 0.
