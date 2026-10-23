# Differences from CPython

## C?-job-fuzz72-10231542-1: general-path `str.casefold()` on non-ASCII text

The general (boxed) path emitted `ail_meth_str_casefold()` for `.casefold()`.  That helper was an
ASCII-only alias of `lower()`: a non-ASCII code point raised `AIL limit: str_lower_nonascii`
instead of returning CPython's folded text (`"Straße".casefold()` printed nothing where CPython
prints `strasse`).

The general path now calls `ail_boxed_casefold()`, which applies the same full Unicode casefold
table as the typed path over the boxed runtime's UTF-16 strings.  A casefold call with an argument
is still refused by name at compile time, matching the TypeError CPython raises.
