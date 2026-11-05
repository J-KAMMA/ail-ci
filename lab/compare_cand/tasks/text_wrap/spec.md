# text_wrap

Write a command-line program:

    prog < input

It reads a width and a block of ASCII text from standard input, wraps every paragraph greedily, and
prints a checksum of the wrapped text instead of the text itself.

## Input

Line 1 is the width `W`: an int in 10 .. 200.

The rest of the input is ASCII text. Paragraphs are separated by one or more empty lines (a line
that is empty or only spaces). Words are maximal runs of bytes other than space, tab and newline.

A first line is valid when it is 1 to 3 ASCII digits whose value is 10 .. 200; otherwise the input
is bad. Anything after the first `\n` is the text; an input with no `\n` at all has an empty text
part.

## Wrapping

Wrap each paragraph greedily: put words on a line, separated by one space, while the line length
stays at most `W`; a word longer than `W` goes alone on its own line. A paragraph contributes to the
counts only when it contains at least one word (a run of lines that holds only tabs has no words).
Do not print the wrapped text.

The wrapped output is the paragraphs joined with one empty line, and each paragraph is its lines
joined with `\n`; there is no final newline. Compute over that output:

    h = (h * 131 + byte) % 1000000007

starting from `h = 0`, where `byte` is each byte of the wrapped output in order.

## Output

Print one line, ending with `\n`, with values separated by one space:

    paragraphs P lines L words N longest K hash H

where `P` is the number of contributing paragraphs, `L` the number of output lines, `N` the number
of words, `K` the length of the longest output line, and `H` the hash above.

An input with no words prints exactly:

    paragraphs 0 lines 0 words 0 longest 0 hash 0

A bad first line exits 2 with nothing on stdout.

## The algorithm (same in every language)

One pass over the input: validate the width, scan the text a line at a time, treat a line of only
spaces as a paragraph break, extract words as maximal runs outside space/tab/newline, and wrap them
on the fly while hashing each emitted output line. No list of output lines is built.
