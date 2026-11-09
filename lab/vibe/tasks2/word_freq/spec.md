# word_freq

Write a command-line program:

    prog

It reads UTF-8 text from standard input and prints the most frequent words. It takes no arguments
(extra arguments are ignored).

## Words

A word is a maximal run of ASCII letters `[A-Za-z]`. Every other character (spaces, punctuation,
digits, and any non-ASCII byte or character) is a separator. Counts are case-insensitive: uppercase
ASCII letters are lowered before counting. The total number of words counts every occurrence;
`unique` is the number of distinct lowercased words.

## Output

    words <total> unique <unique>
    <word> <count>        (up to 20 lines)

The word lines are ordered by count descending, ties by the word ascending in byte order. Only the
first 20 are printed. When the input has no words, only the first line is printed.

Every line ends with `\n`; exit status 0.
