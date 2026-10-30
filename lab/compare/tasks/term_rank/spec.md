# term_rank

Write a command-line program:

    prog K

The program reads a text from standard input, splits it into documents, extracts terms with the
rules below, and prints the K best-scoring terms of every document and the K most frequent terms
overall. K is a decimal integer 1 .. 1000 written with digits only (no sign, leading zeros
allowed); anything else, or a wrong number of arguments (exactly one is required), is a usage
error: print nothing on standard output and exit with status 1.

The input is arbitrary bytes (it need not be valid UTF-8). All processing is byte-based.

## Documents

Standard input is split into lines at `\n`; if it ends with `\n`, the empty piece after the last
`\n` is not a line (empty input has no lines). A line that is exactly `%%`, or exactly `%%\r`, is
a *separator*. The separators cut the sequence of lines into documents: document 1 is the lines
before the first separator, document 2 the lines between the first and second separator, and so
on, the last document being the lines after the last separator. So there is always one more
document than there are separators (empty input is one empty document). Documents are numbered
from 1.

## Terms

Within each line (terms never span lines), find the *raw tokens*:

- A *word byte* is an ASCII letter `A-Z` `a-z`, an ASCII digit `0-9`, or any byte 0x80 .. 0xFF.
- A *joiner* is `'` (0x27) or `-` (0x2D). A joiner that has a word byte immediately on both sides
  is part of the token; any other joiner is a separator.
- Every other byte is a separator.
- A raw token is a maximal run of word bytes and joiners (as above) that starts and ends with a
  word byte. For example `don't`, `well-known` and `a-b-c` are single raw tokens, while
  `x--y` is the two tokens `x` and `y`, and `'tis` is the token `tis`.

Each raw token becomes a term through these steps, in this order:

1. Remove every `'`.
2. Change ASCII `A-Z` to lowercase (other bytes, including bytes 0x80 .. 0xFF, are unchanged).
3. If the token now consists only of ASCII digits, replace it with `#` followed by the number of
   digits in decimal (`2024` becomes `#4`, `007` becomes `#3`).
4. If the token is shorter than 2 bytes, drop it.
5. If the token is one of these stop words, drop it:
   `an and are as at be but by for from had has have he her his in into is it its not of on or
   our she so than that the their them then there these they this to was we were which will with
   you your`
6. Suffix rule, applied at most once: if the token has at least 5 bytes and ends with `ing`, remove
   those 3 bytes; otherwise, if it has at least 4 bytes, ends with `s` and does not end with `ss`,
   remove the final `s`.

The result is a term. (`Running` becomes `runn`; `class` stays `class`; `it's` becomes `its`,
which is a stop word and is dropped; `Things` becomes `thing`; `x-rays` becomes `x-ray`.)

## Scores

Let N be the number of documents, tf(t, d) the number of occurrences of term t in document d,
and df(t) the number of documents that contain t at least once. The score of term t in document d
(where tf(t, d) >= 1) is the integer

    score(t, d) = floor( tf(t, d) * 1000 * (N + 1) / ( df(t) * (tf(t, d) + 2) ) )

computed exactly (the numerator fits in a signed 64-bit integer for all tested inputs).

## Output

For each document d = 1 .. N print one line

    doc d: t1=s1 t2=s2 ...

listing the min(K, number of distinct terms of d) terms of d with the highest scores, ordered by
score descending, ties broken by the term's bytes in ascending order (plain byte-wise comparison,
where a proper prefix comes first). A document without terms prints `doc d:` with nothing after
the colon. Items are separated by single spaces, with one space after the colon.

Then print one line

    all: t1=c1 t2=c2 ...

with the min(K, number of distinct terms in the whole input) terms with the highest total number
of occurrences over all documents (c = that total), ties by term bytes ascending, in the same
format (`all:` alone if there are no terms at all).

Terms are printed as their raw bytes (non-ASCII bytes are written unchanged). Every line ends
with `\n`. Exit status 0.
