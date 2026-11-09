# ini_merge

Write a command-line program:

    prog

It reads one INI-like configuration file from standard input and prints the merged configuration.
It takes no arguments (extra arguments are ignored).

## Parsing

The input is UTF-8. Split it into lines on `\n`, then remove one trailing `\r` from each line
(so CRLF input is accepted). Trim spaces and tabs from both ends of every line. Then, line by line:

- A blank line is skipped.
- A line whose first character is `#` or `;` is a comment and is skipped.
- A section header starts with `[` and ends with `]`. Its name is the text between the brackets
  (it may be empty, and its inner spaces are kept as-is). A line that starts with `[` but does not
  end with `]` is bad.
- Otherwise the line must contain `=`. Split at the first `=`; the key is the text before it,
  trimmed, and the value is the text after it, trimmed. The key must be non-empty and must not
  contain spaces or tabs. Any other line is bad.
- Keys seen before the first section belong to the default section, whose name is the empty string.
- Within one section a later value for the same key replaces the earlier one.

Bad lines are counted and ignored; they do not stop the program.

## Output

    bad <B>

Then for each section in ascending name order print `[name]`, followed by one `key=value` line for
each key in that section in ascending key order. The default section is printed as `[]`. Sections
without keys are still printed if they were seen. Values are printed exactly as parsed; a value may
be empty or contain `=` or Unicode text. When there are no sections and no default keys, only the
`bad` line is printed.

Every line ends with `\n`; exit status 0.
