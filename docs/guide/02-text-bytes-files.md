# 2. Text, bytes, and files

Text is `str`, binary data is `bytes`. Both are built on the typed path. The samples that read
stdin are fed by `AIL_CURRENT/test_ail_guide.py`; a ```stdin block in this page shows that input.

## Strings

`strip`, `upper`, `len` and `count` work as in Python:

<!-- sample: c2_str -->
```python
def main() -> None:
    s: str = "  AIL compiles Python  "
    print(s.strip().upper())
    print(len(s), s.count("i"))


main()
```

```output
AIL COMPILES PYTHON
23 1
```

`split` returns a `list[str]`, and `join` puts text back together:

<!-- sample: c2_split_join -->
```python
def main() -> None:
    words: list[str] = "the quick brown fox".split()
    print(words[1:3])
    print("-".join(words))
    print("  padded  ".strip())


main()
```

```output
['quick', 'brown']
the-quick-brown-fox
padded
```

An f-string formats values in place:

<!-- sample: c2_fstring -->
```python
def main() -> None:
    n: int = 7
    x: float = 3.14159
    name: str = "ab"
    print(f"{n:03d}|{n:>4}|{x:.2f}|{name:<4}|{n + 1}")


main()
```

```output
007|   7|3.14|ab  |8
```

The `%` operator does the same job with a tuple of values:

<!-- sample: c2_percent -->
```python
def main() -> None:
    n: int = 7
    x: float = 3.14159
    print("%5d|%.1f|%s" % (n, x, "ok"))


main()
```

```output
    7|3.1|ok
```

## Bytes

`b"..."` is a bytes literal. Indexing gives an int, a slice is bytes, and `decode` turns UTF-8
bytes into text:

<!-- sample: c2_bytes -->
```python
def main() -> None:
    data: bytes = b"hello"
    print(len(data), data[0], data[1:4].decode())
    encoded: bytes = "AIL".encode()
    print(encoded.decode())


main()
```

```output
5 104 ell
AIL
```

## Reading stdin

`for line in sys.stdin` gives one line at a time, newline included. This program numbers the lines
and trims the newline with `strip`:

<!-- sample: c2_stdin_lines -->
```python
import sys


def main() -> None:
    n: int = 0
    for line in sys.stdin:
        n += 1
        print(f"{n}: {line.strip()}")


main()
```

```stdin
alpha beta
second line
```

```output
1: alpha beta
2: second line
```

Split each line into words and count them:

<!-- sample: c2_stdin_words -->
```python
import sys


def main() -> None:
    total: int = 0
    for line in sys.stdin:
        words = line.split()
        total += len(words)
    print(total)


main()
```

```stdin
one two three
four
```

```output
4
```

For binary input, read `sys.stdin.buffer`. Here the first byte and the first three bytes are shown:

<!-- sample: c2_stdin_bytes -->
```python
import sys


def main() -> None:
    data: bytes = sys.stdin.buffer.read()
    print(len(data), data[0], data[0:3].decode())


main()
```

```stdin
hello world
```

```output
12 104 hel
```

## Files

Open a file for writing with `with open(path, "w")`, then open it for reading and loop over its
lines. The test runs each sample in a fresh temporary directory, so `guide_tmp.txt` is temporary
too:

<!-- sample: c2_file -->
```python
def main() -> None:
    with open("guide_tmp.txt", "w") as f:
        f.write("alpha\nbeta\n")
    n: int = 0
    with open("guide_tmp.txt") as f:
        for line in f:
            n += 1
            print(line.strip().upper())
    print(n)


main()
```

```output
ALPHA
BETA
2
```

## Command-line arguments

`sys.argv` is a `list[str]`. The first item is the program name; the rest are the arguments. The
sample is run with two arguments:

<!-- sample: c2_argv args=Alice,42 -->
```python
import sys


def main() -> None:
    print(len(sys.argv))
    print(sys.argv[1], sys.argv[2])


main()
```

```output
3
Alice 42
```
