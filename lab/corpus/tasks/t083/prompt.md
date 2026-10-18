Write a complete Python 3.12 program that solves the task below.

Task: Check that each line is pure ASCII; print 'ascii' or 'non-ascii' for each, then the encoded bytes (as list of ints) of the first non-ASCII line in UTF-8.

Input (read from standard input): Several lines of text with single-space separators; some words contain non-ASCII letters (accents, CJK, Cyrillic, Greek, emoji); some end with punctuation; some lines may be empty.

Output: write the result to standard output exactly as described. Print nothing else.

Requirements: standard library only; ordinary readable Python with type hints where natural; define main() and end with
if __name__ == "__main__":
    main()

Reply with the program in a single ```python code block and nothing else.