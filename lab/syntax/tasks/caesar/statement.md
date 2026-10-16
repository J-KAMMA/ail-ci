# caesar

Category: strings

Read standard input, write standard output, exit with status 0.

The first line holds an integer shift k >= 0. Every following line is text. Print each text line with every ASCII letter shifted forward by k positions in the alphabet (wrapping around, keeping upper/lower case); all other characters stay unchanged.

Example: shift `3`, text `abc xyz` gives `def abc`.
