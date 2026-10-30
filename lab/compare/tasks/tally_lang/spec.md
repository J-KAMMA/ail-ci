# tally_lang

Write a command-line program:

    prog SCRIPT

SCRIPT is the path to a text file containing a program in the small "Tally" language described
below. Your program parses the whole script, and only if it has no parse error, runs it.

## Values

Every value is an unsigned 32-bit integer (0 .. 4294967295). All arithmetic wraps modulo 2^32.

## Lines and characters

The file is split into lines at `\n`. A final line without a terminating `\n` counts as a line; the
empty piece after a final `\n` does not. Lines are numbered from 1.

- Every byte of the file must be a tab (0x09), `\n` (0x0A), `\r` (0x0D) or a printable ASCII byte
  0x20 .. 0x7E. Any other byte makes the line containing it a parse error.
- A line longer than 1000 bytes (not counting its `\n`) is a parse error.
- `;` starts a comment that runs to the end of the line. It is removed before anything else
  (after the two checks above).
- Space, tab and `\r` are whitespace. They separate tokens and are otherwise ignored.
- A line that is empty after removing the comment and whitespace is ignored.

## Tokens

- Number: one or more digits `0-9`, leading zeros allowed. Its value must be at most 4294967295,
  otherwise parse error.
- Word: a lowercase letter or `_`, followed by any number of lowercase letters, digits and `_`
  (`[a-z_][a-z0-9_]*`). The words `set`, `out`, `loop`, `when`, `else`, `end`, `break` are keywords;
  every other word is a variable name. A number immediately followed by a lowercase letter or `_`
  (`12ab`, `7_`) is a parse error.
- Operators and punctuation, matched longest first: `<>` `><` `==` `!=` `<` `>` `+` `-` `*` `/`
  `%` `~` `#` `!` `(` `)` `,` `=`. So `<>` is always one token, while `< >` (with a space) is the
  two tokens `<` and `>`.
- Any other character (uppercase letters, `.`, `"`, `&`, ...) is a parse error.

## Statements

Each non-ignored line holds exactly one statement. Anything left over on the line is a parse
error.

| statement | meaning |
|---|---|
| `set NAME = EXPR` | evaluate EXPR and store it in variable NAME |
| `out EXPR {, EXPR}` | evaluate the expressions left to right, then print their values in decimal separated by one space, followed by `\n` (at least one expression) |
| `loop EXPR` | evaluate EXPR once, giving n; run the block body n times (0 times if n = 0) |
| `when EXPR` | evaluate EXPR; if it is not 0 run the block body, otherwise run the `else` part if there is one |
| `else` | separates the two parts of a `when` block; at most one per `when` |
| `end` | closes the innermost open `loop` or `when` block |
| `break` | leave the innermost enclosing `loop` immediately (also from inside `when` blocks nested in it) |

Blocks nest. At most 16 blocks may be open at the same time; opening a 17th is a parse error
(on the line of the 17th opener). `else` is a parse error unless the innermost open block is a
`when` that has not had an `else` yet. `end` with no open block is a parse error. `break` that is
not inside any `loop` (counting all enclosing open blocks) is a parse error.

Variables are global (one namespace for the whole script; blocks do not create scopes). A variable
exists once it has been assigned by `set`.

## Expressions

From loosest to tightest binding:

| level | operators | associativity |
|---|---|---|
| 1 | `<>` (maximum of the two), `><` (minimum of the two) | left |
| 2 | `==` `!=` `<` `>` (result 1 if true, 0 if false) | none: at most one level-2 operator between two level-1 operators (or the ends of the expression), so `a < b < c` and `a == b != c` are parse errors, while `(a < b) < c` and `a < b <> c > d` are fine |
| 3 | `+` `-` | left |
| 4 | `*` `/` `%` | left |
| 5 | `~` | right: `a ~ b ~ c` is `a ~ (b ~ c)` |
| 6 | prefix `-` (negation, i.e. 2^32 - x, and 0 for 0), `#` (number of 1 bits), `!` (1 if the operand is 0, else 0) | prefix, any number may be stacked: `- -x`, `!#-x` |
| 7 | number, variable name, `( EXPR )` | |

- `+`, `-`, `*` wrap modulo 2^32. `/` is unsigned integer division rounding down, `%` the
  remainder of that division. A right operand of 0 for `/` or `%` is a runtime error.
- `a ~ b` rotates the 32 bits of `a` left by `b mod 32` positions (bits shifted out at the top
  re-enter at the bottom). `1 ~ 33` is 2, `2147483648 ~ 1` is 1.
- So level 6 binds tighter than level 5: `-1 ~ 4` is `(-1) ~ 4`, and `2 ~ -1` is `2 ~ (-1)`.
- Parentheses may be nested at most 32 deep within one expression; a 33rd level is a parse error.
- Evaluation always evaluates the left operand completely before the right operand; all operands
  are always evaluated (there is no short-circuiting).
- Reading a variable that has not been assigned yet is a runtime error.
- A keyword cannot be used as a variable name (`set end = 1` and `out loop` are parse errors).

## Running

The script is parsed completely before anything runs. Statements then run from top to bottom,
following the block structure.

## Output and exit status

- Success: everything printed by `out` statements; exit status 0.
- Parse error: print exactly one line `parse error line N` and nothing else, exit status 2. N is
  the number of the first line (lowest line number) that has a parse error when the lines are
  read from top to bottom. If no line has an error but blocks are still open at the end of the
  file, N is the line of the innermost (most recently opened) unclosed `loop` or `when`.
- Runtime error: everything printed by `out` before the error stays printed; then print
  `runtime error line N` (N = the line of the statement being executed: the `set`/`out` line, or
  the `loop`/`when` line while its expression is evaluated) and exit with status 3. An `out`
  statement whose expression fails prints nothing for that statement.
- Wrong number of arguments (exactly one is required) or unreadable file: print nothing on
  standard output, exit status 1.

Every printed line ends with `\n`.

## Example

    set x = 10
    loop 3        ; three times
      set x = x * 2 + 1
      when x > 50
        out x, x ~ 1, #x
        break
      end
    end
    out x <> 7 >< 3, -1, !0

prints

    87 174 5
    3 4294967295 1

(`x <> 7 >< 3` is `(87 <> 7) >< 3` = `87 >< 3` = 3, because level 1 is left-associative.)
