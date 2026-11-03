# json_lite

Read a JSON-like document from standard input, parse it by hand, and print the sum of every
integer number in it.

- The document is one value built from objects `{"key": value, ...}`, arrays `[value, ...]`,
  strings, integers, `true`, `false`, `null` and whitespace.
- Integers are an optional `-` followed by one or more decimal digits. There are no floats or
  exponents. Booleans and `null` contribute nothing to the sum.
- String contents are not numbers. A string is delimited by `"`; a backslash escapes the
  character after it, so `\"` and `\\` do not end the string.
- No `json`, `json5` or similar module may be used anywhere in the program: the parser is part
  of the source.
- Print the sum on one line. Empty or whitespace-only input prints `0`. The sum fits a signed
  64-bit integer.

The performance input is several MB of nested objects and arrays.
