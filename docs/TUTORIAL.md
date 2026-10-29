# AIL tutorial

About 15–20 minutes. You need a working setup from [INSTALL.md](INSTALL.md), including the
`ailc` shell function defined there:

```sh
ailc() { python3 ~/ail-ci/AIL_CURRENT/ail_chatgpt.py "$@"; }
mkdir -p ~/ail-tutorial && cd ~/ail-tutorial
```

AIL compiles a subset of Python 3.12 to C. Its rule: a compiled program prints exactly what
CPython 3.12 prints, or the compiler refuses it. There are two code paths:

- the **typed path**: fast, plain C code;
- the **general path**: slower, but covers more of Python (dynamic values, big integers, printing
  a dict, and so on). When the typed path cannot take a program, the compiler builds it on the
  general path and says so.

Every command below was run on 2026-10-30 (Ubuntu 24.04 under WSL 2, Python 3.12.3, gcc 13.3.0)
and its output is pasted as printed. Paths and hashes in the `compile` lines will differ on your
machine.

## 1. Hello world

`hello.py`:

```python
print("Hello, AIL!")
```

```text
$ ailc compile hello.py -o hello
{"output": "/home/bluec/ail-tutorial/hello", "bytes": 16192, "sha256": "bd9bd02b429a6b681aec9344bdc4a482ee3b369680f710f7601f688b7c460b49"}
$ ./hello
Hello, AIL!
```

The result is a 16 KB native executable. `compile` will not overwrite an existing `-o` file; delete
it first when you rebuild.

## 2. A typed program, and checking that it took the fast path

Annotate function parameters, results and empty containers. `stats.py`:

```python
def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def main() -> None:
    temps: list[float] = [21.5, 19.0, 23.25, 18.75, 22.0]
    print(f"days: {len(temps)}")
    print(f"mean: {mean(temps):.2f}")
    print(f"max:  {max(temps)}")
    warm = [t for t in temps if t > 20.0]
    print("warm days:", warm)


main()
```

```text
$ ailc compile stats.py -o stats
{"output": "/home/bluec/ail-tutorial/stats", "bytes": 25760, "sha256": "d131f82a2b8dac7279bce34c4e2ea19ce3e24ddf5f365d3e358c6144cb516a06"}
$ ./stats
days: 5
mean: 20.90
max:  23.25
warm days: [21.5, 23.25, 22.0]
```

**How to tell which path was used:** if `compile` prints no `note:` line, the program is on the
typed path. To make sure, build with `--strict`. Strict mode never falls back to the general path:
it builds a typed program exactly as before (same bytes, same hash here) and refuses anything else.

```text
$ rm stats
$ ailc compile stats.py --strict -o stats
{"output": "/home/bluec/ail-tutorial/stats", "bytes": 25760, "sha256": "d131f82a2b8dac7279bce34c4e2ea19ce3e24ddf5f365d3e358c6144cb516a06"}
```

Now a program the typed path cannot take. `counts.py`:

```python
def main() -> None:
    counts: dict[str, int] = {"b": 1, "a": 2}
    print(counts)


main()
```

```text
$ ailc compile counts.py -o counts
note: counts.py:3:5: built on the general path (about 20x slower) because print() given a dict[str, int], not a number or a str. write instead: print an element or a measurement (`print(xs[0])`, `print(len(xs))`), or one line per element (`for x in xs: print(x)`); run with --strict to see why
{"output": "/home/bluec/ail-tutorial/counts", "bytes": 63624, "sha256": "c624d913ae0b3d88032d0ba14339ed8d5fac50ff4e2babd95570a4b734df7ccd"}
$ ./counts
{'b': 1, 'a': 2}
```

It still prints what CPython prints; it is just built on the slower path. With `--strict` the
same program is not built, and you get the blocker with a rewrite:

```text
$ ailc compile counts.py --strict -o counts_strict
strict: 1 typed-path blocker; nothing was built (ranked by the code each one keeps off the typed path)

1. counts.py:3:5  blocks 4 lines (main)
   code:          print(counts)
   construct:     print() given a dict[str
   why not typed: print() given a dict[str, int], not a number or a str.
   write instead: print an element or a measurement (`print(xs[0])`, `print(len(xs))`), or one line per element (`for x in xs: print(x)`)
```

Following the hint, print one line per element. `counts2.py`:

```python
def main() -> None:
    counts: dict[str, int] = {"b": 1, "a": 2}
    for key in sorted(counts):
        print(key, counts[key])


main()
```

```text
$ ailc compile counts2.py --strict -o counts2
{"output": "/home/bluec/ail-tutorial/counts2", "bytes": 25976, "sha256": "266faf1edab912b34998be34ae4ab9ec2ffe40bfa6a5c4b8633b736652da5ed0"}
$ ./counts2
a 2
b 1
```

Note the output changed because the program changed (sorted lines instead of a dict repr); it
still matches what CPython prints for `counts2.py`.

## 3. A refusal

Some programs neither path can build. Those are refused at compile time, by name, with
`file:line:col` and a `write instead:` hint. Nothing is built. `double.py`:

```python
def main() -> None:
    x = 5
    print(eval("x * 2"))


main()
```

```text
$ ailc compile double.py -o double
double.py:3:5: not in the subset: call to eval(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one (the general path could not build this program either); general path: the name 'eval' is not a known function/class/builtin
  write instead: define `eval` yourself with a `def` and call that, or use the builtin that does the job (len, sum, min, max, sorted, abs, range, int, float, str)
```

The exit status is 3. Here the job of `eval` is a plain expression, so write it directly.
`double2.py`:

```python
def main() -> None:
    x = 5
    print(x * 2)


main()
```

```text
$ ailc compile double2.py -o double2
{"output": "/home/bluec/ail-tutorial/double2", "bytes": 16272, "sha256": "7e1a89186f5a50dc4ee2c7239b68fb9614cb712fae4cacf864aa210d9115e107"}
$ ./double2
10
```

Other things refused the same way include `exec`, `locals()`, `async def`, and imports of
third-party packages such as `numpy`. The full list of what is built is in
`AIL_CURRENT/AIL_REFERENCE.md` and `AIL_CURRENT/AIL_REFERENCE_MORE.md`.

## 4. Exact big integers

Python integers have no size limit, and neither do AIL's: results are exact, not wrapped at 64
bits. `bigint.py`:

```python
def factorial(n: int) -> int:
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def main() -> None:
    print(2 ** 100)
    print(factorial(30))
    x = 9223372036854775807
    print(x + 1)
    print(-7 // 2, -7 % 2)


main()
```

```text
$ ailc compile bigint.py -o bigint
note: built on the general path (about 20x slower) because the module code can need an int beyond int64 (it calls main(), which can need a big int (`**` with 2 ** 100 beyond int64)); the typed path has int64 only and the general path has exact big ints; run with --strict to see why
{"output": "/home/bluec/ail-tutorial/bigint", "bytes": 108896, "sha256": "6a12a6ca96b024c0d892f2d4078b950ed5d21726cc96183cfa4f1066b014ffe2"}
$ ./bigint
1267650600228229401496703205376
265252859812191058636308480000000
9223372036854775808
-4 1
$ python3 bigint.py
1267650600228229401496703205376
265252859812191058636308480000000
9223372036854775808
-4 1
```

Here the compiler saw `2 ** 100`, a value beyond 64 bits, at compile time, and built the program
on the general path, which has exact big integers. So `--strict` refuses this program:

```text
$ ailc compile bigint.py --strict -o bigint_strict
not in the subset: the module code can need an int beyond int64 (it calls main(), which can need a big int (`**` with 2 ** 100 beyond int64)); the typed path has int64 only and the general path has exact big ints
```

A value that only grows past 64 bits at run time is exact too. `grow.py`:

```python
import sys


def main() -> None:
    n = int(sys.argv[1])
    x = 1
    for i in range(n):
        x = x * 3
    print(x)


main()
```

```text
$ ailc compile grow.py --strict -o grow
{"output": "/home/bluec/ail-tutorial/grow", "bytes": 30944, "sha256": "d45d3588d39cc5d0921d1a9fd48780a1ea944f26cd2809bbd3226bc91a2a7856"}
$ ./grow 10
59049
$ ./grow 50
717897987691852588770249
$ python3 grow.py 50
717897987691852588770249
```

This one builds under `--strict`, and `3 ** 50` still comes out exact.

## 5. Reading a file and processing text

`words.py` counts the lines and the most common words of a file:

```python
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: words FILE", file=sys.stderr)
        return 2
    counts: dict[str, int] = {}
    lines = 0
    with open(sys.argv[1]) as f:
        for line in f:
            lines += 1
            for word in line.lower().split():
                word = word.strip(".,;:!?\"'()")
                if word != "":
                    counts[word] = counts.get(word, 0) + 1
    print("lines:", lines)
    print("distinct words:", len(counts))
    top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    for word, n in top[:5]:
        print(f"{n:4} {word}")
    return 0


sys.exit(main())
```

`poem.txt`:

```text
The cat sat on the mat.
The dog sat on the log.
A cat and a dog met on the mat;
the cat ran, the dog sat.
```

This one is on the typed path (`--strict` builds it):

```text
$ ailc compile words.py --strict -o words
{"output": "/home/bluec/ail-tutorial/words", "bytes": 64864, "sha256": "4ac75c1a39889c383099a28abb965b115119bf17f53e9027863af671c738075c"}
$ ./words poem.txt
lines: 4
distinct words: 11
   7 the
   3 cat
   3 dog
   3 on
   3 sat
$ python3 words.py poem.txt
lines: 4
distinct words: 11
   7 the
   3 cat
   3 dog
   3 on
   3 sat
```

`sys.argv`, `sys.exit`, `print(..., file=sys.stderr)`, `with open(...)`, `str.split`,
`str.strip`, `dict.get`, `sorted` with a `key` and f-string format specs all work as in CPython.

## 6. Speed and size against CPython

`collatz.py` finds the number below one million with the longest Collatz sequence:

```python
def steps(n: int) -> int:
    count = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        count += 1
    return count


def main() -> None:
    best = 0
    best_n = 0
    for n in range(1, 1000000):
        s = steps(n)
        if s > best:
            best = s
            best_n = n
    print(best_n, best)


main()
```

```text
$ ailc compile collatz.py -o collatz
{"output": "/home/bluec/ail-tutorial/collatz", "bytes": 22056, "sha256": "76b2cd4dcb606dd428f42a87c84fb3e66354ef957b642511b2e9d2aeee2162b3"}
$ ./collatz
837799 524
$ python3 collatz.py
837799 524
```

Time both, three runs each (`/usr/bin/time` is GNU time; `%M` is the peak resident memory):

```sh
for i in 1 2 3; do /usr/bin/time -f "AIL      %e s, max RSS %M KB" ./collatz >/dev/null; done
for i in 1 2 3; do /usr/bin/time -f "CPython  %e s, max RSS %M KB" python3 collatz.py >/dev/null; done
```

Measured on a laptop with an AMD Ryzen 7 8840U, Ubuntu 24.04 under WSL 2, Python 3.12.3,
gcc 13.3.0, while other compile jobs were running on the same machine (so the times are noisy):

```text
AIL      0.41 s, max RSS 1408 KB
AIL      0.33 s, max RSS 1280 KB
AIL      0.33 s, max RSS 1280 KB
CPython  8.77 s, max RSS 10240 KB
CPython  11.81 s, max RSS 10240 KB
CPython  8.74 s, max RSS 10240 KB
```

Size: the executable is 22,056 bytes and needs only the C library. Running the script under
CPython needs the interpreter (8,020,928 bytes here) plus its standard library.

```text
$ ls -l collatz
-rwxr-xr-x 1 bluec bluec 22056 Oct 30 00:06 collatz
$ ldd ./collatz
	linux-vdso.so.1 (0x00007ffc323b3000)
	libc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007af540200000)
	/lib64/ld-linux-x86-64.so.2 (0x00007af5405b4000)
$ ls -lL /usr/bin/python3
-rwxr-xr-x 1 root root 8020928 Aug 31 19:18 /usr/bin/python3
```

This program is on the typed path. To see what the general path costs, the measurement switch
`AIL_UNIFIED_FORCE=1` builds the same program on the general path:

```text
$ AIL_UNIFIED_FORCE=1 ailc compile collatz.py -o collatz_general
{"output": "/home/bluec/ail-tutorial/collatz_general", "bytes": 124752, "sha256": "8e11d03b025edb4aab1d93aab45fbf9530ff6acd93f315b01c91b1ac3687112e"}
```

On the same machine it took 9.33 to 16.26 s over three runs (max RSS 1664 to 1920 KB), which is
close to CPython. Keeping hot code on the typed path is what makes AIL fast; `--strict` is how you
check it.

One example on one machine is not a benchmark. Measure your own programs the same way.

## Known limitations

These were seen while writing this tutorial, or are stated in the reference:

- **No pip install.** Run the compiler from a git checkout (see [INSTALL.md](INSTALL.md)).
  `ail-lang` is not on PyPI, and the `ail` command described in
  `AIL_CURRENT/LANGUAGE_QUICKSTART_JA.md` is not available from this repository.
- **Big integers the compiler can see at compile time leave the typed path.** A program like
  `bigint.py` (section 4) is built on the slower general path, and `--strict` refuses it.
  `DIFFERENCES.md` lists open cases where a value beyond 64 bits stopped with `integer overflow`
  instead of printing the exact result.
- **Uncaught exceptions print less than CPython on stderr.** Running `./words missing.txt` printed
  only `OSError` and exited with status 1. CPython printed a traceback ending in
  `FileNotFoundError: [Errno 2] No such file or directory: 'missing.txt'`, also with status 1.
  Stdout matched; the stderr text did not.
- **Some refusals have no `file:line`.** `exec(...)`, `async def` and the big-integer refusal
  under `--strict` (section 4) were reported without a location in our tries.
- **Some `write instead:` hints are generic.** For an unknown builtin such as `eval` the hint is a
  general one (define it yourself or use a listed builtin), not a rewrite of your line.
- **The strict report can cut the construct short.** In section 2 the `construct:` line reads
  `print() given a dict[str`; the `why not typed:` line has the full text.
- **`check` needs at least one `def`.** On `hello.py` it reports `no def found` (exit 1); `compile`
  builds the same file normally.
- **Only the standard library modules AIL implements can be imported**, plus your own modules.
  Third-party packages such as `numpy` are refused.
- **Platforms.** Only Linux x86-64 runs the full test suite. Windows (MinGW-w64) and macOS run a
  representative subset in CI, and this tutorial was not run on them.
- Known individual differences from CPython are listed in [`DIFFERENCES.md`](../DIFFERENCES.md).

## Where to read more

- `AIL_CURRENT/AIL_REFERENCE.md`: the short core reference.
- `AIL_CURRENT/AIL_REFERENCE_MORE.md`: the longer sections, including strict mode and the standard
  library modules.
- `AIL_CURRENT/LANGUAGE_QUICKSTART_JA.md`: many small examples, in Japanese. Some of it describes
  the unpublished `ail-lang` package.
