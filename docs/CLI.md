# The `ail` command

`ail` wraps the compiler (`ail_chatgpt.py`, bundled as `sdk/` inside the wheel) with the commands a
program needs while it is being written:

```text
ail run prog.py [args...]      compile to a temporary executable and run it
ail build prog.py [-o prog]    compile to an executable (default: the file name without .py)
ail check prog.py              strict source/type check, no C compiler needed
ail check --perf prog.py       static advice about slow algorithms in loops (--json, --strict)
ail new NAME                   create a project (ail.toml, src/main.py)
ail build | run | check        no source file: the project of the current directory
ail lsp                        language server on stdio
```

Everything after the source file of `ail run` goes to the program; options before it go to the
compiler. `ail build --debug`, `ail build --lib`, `ail run --strict` and the pass-through commands are
described in [QUICKSTART.md](QUICKSTART.md) and in `ail --help`.

## `ail run --diff`: run the program twice and compare

AIL is Python syntax, so CPython is a free oracle for a program's behaviour. `ail run --diff` builds
the program exactly as `ail run` does, runs it natively, then runs the same source under CPython on
the same input, and stops loudly on any difference:

```text
ail run --diff [--python PATH] [--timeout SEC] [--json] prog.py [args...]
```

1. **Build** as `ail run` does.
2. **One input for both runs.** If stdin is not a TTY it is read fully, once, into a temp file, and
   the same bytes are fed to both runs. An interactive stdin is inherited untouched, so prompts keep
   working.
3. **Run the native program**, then `PATH prog.py args...` with the same working directory, the same
   arguments, the same environment and the same timeout. `PATH` defaults to the `python3` that runs
   `ail` (`sys.executable`); override it with `--python PATH` (an executable file) or `--python NAME`
   (looked up on `PATH`). The timeout defaults to 60 seconds per run.
4. **Compare** stdout bytes and the exit code. For an uncaught exception only the exception *type
   name* is compared, taken from the last line of stderr; the traceback text is not.
5. **Report** one line on stderr after the program's own output, prefixed `ail diff:`.

The native program's stdout and stderr are shown live, exactly as in `ail run`. CPython's output is
captured and not shown, except where the report line quotes it.

`--diff`, `--python`, `--timeout` and `--json` are read only from the words *before* the source file
(`--timeout=5` and `--python=/path/to/python3` are accepted too). Every other word before the source is
passed to the build exactly as `ail run` passes it, a two-word compiler option together with its value
(`-I .`, `--syntax python`, `--debug-dir DIR`). `ail run prog.py --diff` still passes `--diff` to the
program, and `ail run` without `--diff` behaves exactly as before.

If the build itself stops, there is no native run to compare. A *recognised* refusal (the last three
rows of the table) is `loud stop by design` whatever CPython does with the same input, because no
native program exists for any input. Any other build stop — a broken link, a bad compiler option, a
toolchain defect — is a `DIFFER` that quotes the build's first message, whether or not CPython runs
the program, since there is no native exit code to compare against and the failure is not one of
AIL's documented limits.

### Outcomes and exit codes

| report line | meaning | exit code |
| --- | --- | --- |
| `ail diff: agree` | stdout and exit code (and exception type) match | the program's own exit code |
| `ail diff: DIFFER: stdout line N: native '...', cpython '...'` | the first line that differs, each side truncated to 200 characters | `3` |
| `ail diff: DIFFER: exit code A vs B` | both runs finished, but with different exit codes | `3` |
| `ail diff: DIFFER: exception A vs B` | both raised an uncaught exception, of different types | `3` |
| `ail diff: DIFFER: no native program, the build stopped (exit A) where CPython exited B: <message>` | the build stopped for a reason that is not one of the recognised loud stops | `3` |
| `ail diff: loud stop by design: <reason>` | the native run stopped with one of AIL's documented loud errors where CPython continued | `4` |
| `ail diff: timeout: native` | the native run hit `--timeout` | `124` |
| `ail diff: timeout: cpython` | the CPython run hit `--timeout` | `124` |

**Exit code 3 is reserved for a difference and 4 for a by-design loud stop**, so a script or an AI
agent can tell "the compiler is wrong here" (3) from "this program uses a documented AIL limit" (4)
without parsing the text. `124` is the usual timeout code.

`--json` replaces the stderr line with one JSON object printed on stdout at the end:

```json
{"outcome": "differ", "line": 1, "native": "hello", "cpython": "HELLO", "exit": [0, 0], "seconds": [0.002, 0.018]}
```

`outcome` is `agree`, `differ`, `loud stop by design`, `timeout: native` or `timeout: cpython`;
`line` is the differing stdout line number or `null`; `native` and `cpython` are the two values the
outcome is about (the differing lines, the two exit codes, the two exception names, or the loud-stop
reason); `exit` is the pair of exit codes (the side that did not finish is `null`) and `seconds` the
two wall times. The JSON object is printed on its own line after the program's output, even when that
output did not end with a newline.

### Loud stops that are not differences

AIL stops on purpose where CPython keeps going with a value the fixed-width build cannot represent.
`ail run --diff` recognises these on the native stderr (or, for a build-time refusal, on the
compiler's stderr) and reports `loud stop by design` with exit 4 instead of a difference:

| recognised message | why it is by design |
| --- | --- |
| `OverflowError: integer overflow in ...` | int64 overflow: ints are 64-bit; `--exact-int` gives exact ints ([LIMITATIONS.md](LIMITATIONS.md) section 2) |
| `negative exponent on an integer` | CPython returns a float ([MIGRATING.md](MIGRATING.md) section 14) |
| `re: the group did not take part in the match` | AIL has no `None` for `str` ([MIGRATING.md](MIGRATING.md) section 13) |
| `a negative number raised to a fractional power` | the answer is complex, which AIL does not build |
| `NaN used as a dict/set key` | CPython's NaN identity cannot be reproduced by unboxed doubles |
| `NaN used with 'in'` | the same NaN-identity limit |
| `NaN used with list.count` | the same NaN-identity limit |
| `AIL limit: ...` | a general-path runtime limit whose CPython answer cannot be reproduced |
| `AIL internal error: ...` | an uncatchable runtime error |
| `... ASCII-only in this runtime` | a non-ASCII code point in an ASCII-only text method |
| `... not in the subset ...` | a construct AIL does not build, refused at build time ([LIMITATIONS.md](LIMITATIONS.md)) |
| `... constant expression out of range ...`, `... int64 literal out of range ...` | an int64 constant beyond the fixed width ([LIMITATIONS.md](LIMITATIONS.md) section 1) |

Anything else is a real difference: one of the two answers is wrong (usually the compiler's, sometimes
the program's reliance on behaviour Python leaves unspecified). The "differ" list from a run over
`lab/compare` and the corpus is a compiler bug list — see `lab/rundiff/RESULTS.md`.

### Warning: the program runs twice

Both runs execute the same source with the same input, so **every side effect happens twice**: files
written, network requests made, rows inserted, money spent. Use `--diff` on a program whose side
effects are safe to repeat (a pure computation, a read-only analysis), or point its output at a
scratch directory. The stdin bytes are shared, so a program that reads stdin to the end sees the same
input both times; a program that consumes stdin only partially still starts from the same bytes.

## `ail check --perf`: find slow algorithms and give the fix

The wrong algorithm costs more than any gap to the hardware limit, and AI-written programs tend to
contain a few shapes over and over. `ail check --perf` reads the Python AST (it does not build or run
the program) and reports the first version of six rules when the pattern is inside a loop:

```text
ail check --perf [--json] [--strict] prog.py
```

| id | pattern inside a loop over n items | fix |
| --- | --- | --- |
| P1 | `x in L`, `L.index(x)` or `L.count(x)` where `L` is a list | build a `set`/`dict` once before the loop |
| P2 | `L.pop(0)`, `L.insert(0, x)` or `del L[0]` | `collections.deque` |
| P3 | `s += str` building a string | collect in a list and `''.join` once after the loop |
| P4 | `sorted(L)`, `L.sort()`, `min(L)`, `max(L)` or `sum(L)` of an unchanged list | hoist it out of the loop |
| P5 | nested loops comparing every pair to find matches by key | group by key in a dict |
| P6 | `L = L + [x]` or `L = [*L, x]` | `L.append(x)` |

"Loop" means a `for`, `while` or comprehension body; a nested function, lambda or class body is a new
scope and is not counted as running on each iteration. The rules are deliberately local: a name is
treated as a list or a string only when that is obvious from its annotations, literals, builtins or
list and string methods (for example the receiver of `text.split(",")` is a string, even though the
result is a list). A membership test on a `set` or dict, a call outside a loop, and a name that is
rebound or mutated in the loop (for P1, P3, P4 and P6), or a list mutated in the loop through an
alias (`view = items`, `box.items = items`, or a value read back from a container such as
`pair = [items]; view = pair[0]` or `d = {"xs": items}; view = d["xs"]`) (for P1, P4 and P6), are not
reported; P3 and P6 also stay silent when the name is the loop target, so a string or list that is
recreated each iteration is not called O(n^2). Rebinding an alias before the loop, or using it as the
loop target, does not change the shared list and does not suppress a hit.
P4 stays silent when the `key` or `reverse` value reads a loop variable, because hoisting would change
the result. P5 only looks at loops over items (not two
`range`/`enumerate`/`zip` index loops) and ignores subscript indices, so a dynamic-programming table
is not mistaken for a pairwise search.

Each hit is one line on stderr, with 1-based line and column:

```text
prog.py:12:9: perf P1: membership test on the list 'seen' inside a loop (O(n) per iteration); fix: build a set/dict once before the loop and test membership on it
```

`--json` prints one object per hit on stdout instead, so an agent can apply the fix directly:

```json
{"rule": "P1", "file": "prog.py", "line": 12, "col": 9, "message": "...", "fix": "...", "loop_line": 10}
```

`loop_line` is the line of the nearest loop the hit runs inside (for P5, the outer pair loop). The exit
status is always `0` when the advice ran, even when there are hits; `--strict` makes any hit exit `5`.
A source that cannot be read or parsed is a real error (exit `2`).
