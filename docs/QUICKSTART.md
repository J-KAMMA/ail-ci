# AIL in 10 minutes, for Python programmers

AIL compiles a typed subset of Python 3.12 to C. It prints what CPython prints, or it refuses a
construct at compile time and names a supported rewrite. Setup is in [INSTALL.md](INSTALL.md).

Run the commands below from the repository root. Every example here is a complete program, and
its file is in `AIL_CURRENT/language_examples/quickstart/`.

## 1. Hello world

Save this as `hello.py` (it is already at
`AIL_CURRENT/language_examples/quickstart/hello.py`):

<!-- example: hello.py -->
```python
def main() -> None:
    print("Hello, AIL!")


main()
```

Compile with the Python-syntax front end, then run the executable:

```sh
python3 AIL_CURRENT/ail_chatgpt.py compile --syntax python AIL_CURRENT/language_examples/quickstart/hello.py -o hello
./hello
```

Output:

```text
Hello, AIL!
```

`--syntax python` selects the Python-syntax front end. The `check` subcommand type-checks the
same file without building C:

```sh
python3 AIL_CURRENT/ail_chatgpt.py check --syntax python AIL_CURRENT/language_examples/quickstart/hello.py
```

## 2. Functions, loops, lists and dicts

Annotate parameters, results, and empty containers. `list[str]`, `dict[str, int]`, loops and
`print` work as they do in Python.

<!-- example: word_counts.py -->
```python
def summarize(words: list[str]) -> None:
    counts: dict[str, int] = {}
    total = 0
    for word in words:
        counts[word] = counts.get(word, 0) + 1
        total += len(word)
    for word in sorted(counts):
        print(word, counts[word])
    print("total letters:", total)


def main() -> None:
    words = ["apple", "pear", "apple", "fig"]
    summarize(words)


main()
```

Compile and run it the same way:

```sh
python3 AIL_CURRENT/ail_chatgpt.py compile --syntax python AIL_CURRENT/language_examples/quickstart/word_counts.py -o word_counts
./word_counts
```

Output:

```text
apple 2
fig 1
pear 1
total letters: 17
```

## 3. A class

Methods are plain instance methods. Types for fields that start empty are written in
`__init__`; `self.values: list[int] = []` is enough.

<!-- example: counter.py -->
```python
class Counter:
    def __init__(self, name: str) -> None:
        self.name = name
        self.values: list[int] = []

    def add(self, value: int) -> None:
        self.values.append(value)

    def total(self) -> int:
        return sum(self.values)


def main() -> None:
    counter = Counter("demo")
    counter.add(3)
    counter.add(4)
    counter.add(5)
    print(counter.name, counter.total(), len(counter.values))


main()
```

```sh
python3 AIL_CURRENT/ail_chatgpt.py compile --syntax python AIL_CURRENT/language_examples/quickstart/counter.py -o counter
./counter
```

Output:

```text
demo 12 3
```

## 4. When a program is outside the subset

AIL refuses what it cannot compile and gives the location, the reason, and a rewrite. Some
programs are instead built on a slower general path with a `note: ... built on the general path`
line; `--strict` turns those into refusals too. The program below is refused on the default
build because neither path can build it:

<!-- refused: outside_subset.py -->
```python-refused
class Point:
    def __init__(self, x: int) -> None:
        self.x = x


def main() -> None:
    p = Point(3)
    match p:
        case Point(3):
            print("three")
        case _:
            print("other")


main()
```

Running `python3 AIL_CURRENT/ail_chatgpt.py compile --syntax python outside_subset.py -o outside_subset`
prints this message and exits 3:

```text
outside_subset.py:8:5: not in the subset: a `match` statement (the general path could not build this program either); general path: a match statement (not modelled by the general path)
  write instead: an `if` / `elif` / `else` chain (`if x == 1: ... elif x == 2: ... else: ...`)
note: outside_subset.py:8: a match statement left as written: positional sub-patterns of a class without __match_args__ (or with fewer names)
```

## 5. Where to read more

- `AIL_CURRENT/AIL_REFERENCE.md` is the short core reference: types, statements, imports,
  exceptions, and the main differences from CPython.
- `AIL_CURRENT/AIL_REFERENCE_MORE.md` has the longer sections, indexed from the end of the core.
- `AIL_CURRENT/LANGUAGE_QUICKSTART_JA.md` has many small examples of newer features (Japanese).
- `AIL_CURRENT/language_examples/quickstart/` contains the three programs above.
