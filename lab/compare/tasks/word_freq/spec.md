# word_freq

Read text from standard input and print the twenty most frequent words.

- A word is a maximal run of ASCII letters (`A`..`Z` and `a`..`z`). Every other byte,
  including digits, punctuation and bytes of non-ASCII characters, separates words.
- Words are compared after lowercasing ASCII letters. `Hello`, `HELLO` and `hello` are the
  same word.
- Print the top twenty words as `COUNT WORD`, one per line. Order by count descending, then by
  the lowercased word ascending. If there are fewer than twenty distinct words, print all of
  them.
- Empty input, or input without letters, prints nothing. Exit status 0.

The performance input is about 5 MB of text.
