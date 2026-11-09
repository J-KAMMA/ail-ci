# matrix_stats

Write a command-line program:

    prog

It reads a matrix from standard input and prints row sums, column sums and the position of the
first maximum. It takes no arguments (extra arguments are ignored).

## Input

The first line contains `R C`: two ASCII decimal integers `R` and `C` separated by whitespace, with
`0 <= R <= 10000`, `0 <= C <= 10000` and `R * C <= 1000000`. Leading zeros are allowed.

Then exactly R lines follow. Each contains exactly C integers separated by one or more spaces; every
integer is in the signed 64-bit range. For `C = 0` the R lines are empty (or contain nothing but
spaces). Trailing spaces are allowed; a single trailing newline after the last line is optional.

If the input is empty, the header is missing or malformed, R or C is out of range, the product is
too large, or any row does not contain exactly C valid integers, print exactly

    error

and exit with status 2. Otherwise exit status is 0.

Every row sum and column sum fits in a signed 64-bit integer for every valid input.

## Output

    row <i> <sum>        (for i = 0 .. R-1, in order)
    col <j> <sum>        (for j = 0 .. C-1, in order)
    max <value> at <r> <c>

The `max` line names the first maximum in row-major order (smallest r, then smallest c). When
R * C = 0 there is no element; print `max none` instead. Every line ends with `\n`.
