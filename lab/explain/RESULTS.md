# `ail explain FILE`: per-function typed / general status and the reason

Probe set: `lab/explain/progs/` — 30 programs of 10–30 lines, ordinary annotated Python 3.12.
Ten are fully typed, ten have one function off the typed path, and ten have blockers in two or
three functions (methods and nested functions included). Every file starts with
`# expect: name=typed name=general ...` for each top-level function and method.

Measured on the fdexp1 branch (base `origin/integ`), CPython 3.12.3, gcc.

## Before

There is no per-function answer. The default build prints one program-level line and nothing
more, for example:

```
note: lab/explain/progs/g08_method_dict.py:6:5: built on the general path (about 20x slower)
because Counter__snapshot() typed dict return disagrees with its annotation; run with --strict to see why
```

`--strict --json` (`ail.strict/1`) gives `blocker_count` blockers with `function`, `line`,
`construct`, `why`, `write_instead`. It finds several blockers in one pass, but when a blocker is
a whole function it stops early (`"incomplete": "a refusal without a position; fix it and run
--strict again for the rest"`) and misses functions the collector never reaches. It also names
methods and nested functions the way the compiler mangles them (`Counter__snapshot`,
`outer__inner__0`), not by their source name.

| program | default build | note's `because …` (one reason only) | blocker_count | names in the first blocker list | functions actually off the typed path | lists every one? |
|---|---|---|---|---|---|---|
| g01_dictbuild.py | general | counts() typed dict return disagrees with its annotation | 1 | counts | counts | yes |
| g02_sorted.py | general | returning Call as a list | 1 | ordered | ordered | yes |
| g03_generator.py | general | yield: this language has no generators | 1 | evens | evens | yes |
| g04_mixed.py | general | a str constant 'many' used where a number is needed | 1 | label | label | yes |
| g05_nonret.py | general | the constant None | 1 | maybe_positive | maybe_positive | yes |
| g06_slice.py | general | 'ys' is declared list | 1 | tail | tail | yes |
| g07_reverse.py | general | xs.reverse(): 'xs' is a list parameter, which is read-only here | 1 | flip | flip | yes |
| g08_method_dict.py | general | Counter__snapshot() typed dict return disagrees with its annotation | 1 | Counter__snapshot | Counter.snapshot, main | no |
| g09_nested.py | general | a str constant 's' used where a number is needed | 1 | outer__inner__0 | outer | yes (as the nested def) |
| g10_method_reverse.py | general | returning Call as a list | 2 | Bag__dump | Bag.dump | no (stops early) |
| m01.py | general | returning Call as a list | 3 | label, ordering, show | ordering, label, show | yes |
| m02.py | general | returning Call as a list | 2 | Stack__flip | Stack.flip, pick | no |
| m03.py | general | a str constant 's' used where a number is needed | 2 | evens, outer__inner__0 | outer, evens | yes |
| m04.py | general | Store__as_dict() typed dict return disagrees with its annotation | 1 | Store__as_dict | Store.as_dict, tail | no |
| m05.py | general | returning Call as a list | 3 | evens, maybe, ordering | ordering, evens, maybe | yes |
| m06.py | general | returning Call as a list | 2 | Box__dump | Box.dump, outer | no |
| m07.py | general | counts() typed dict return disagrees with its annotation | 3 | Ledger__flip, counts | Ledger.flip, counts | no |
| m08.py | general | a str constant 's' used where a number is needed | 2 | Chain__grow, outer__inner__0 | Chain.grow, outer | yes |
| m09.py | general | a str constant 's' used where a number is needed | 3 | Vault__report, evens, outer__inner__0 | Vault.report, outer, evens | yes |
| m10.py | general | Registry__view() typed dict return disagrees with its annotation | 1 | Registry__view | Registry.view, maybe, ordered, show | no |
| t01–t10 | typed | — (no fallback note) | 0 | — | none | yes |

Baseline for the number this moves: 0 of 117 functions reported individually (the command did
not exist); the "names in the first blocker list" column names 29 of the 36 functions that are
actually off the typed path, and nothing at all for functions the collector never reaches.

## The command

`python3 -m ail_lang.explain FILE [--json]` (from `packaging/`). It builds twice:

1. the default build — the program status: `typed` (no fallback note), `general` (the fallback
   note), or `refused` with the refusal message;
2. `--strict --json` — the blockers. Each blocker is attributed to the top-level function or
   method it sits in (a blocker on a nested function belongs to its enclosing top-level
   function).

When the blocker list stops early, the named defs are replaced in a temporary copy by typed
stubs that keep their signature *and their decorators* (`return <a literal of the annotated
type>` — a class in the program builds as `Cls(0)` — or `print(0)` for a void def), and the
build is run again, at most ten rounds. Keeping `@staticmethod` / `@classmethod` / `@property`
matters: a hidden `@property` that lost its decorator would turn into a plain method and make
its callers look `general`. The builds also run with `AIL_QUIET_FALLBACK`, `AIL_UNIFIED_FORCE`
and `AIL_NO_GENERAL` removed from the environment, so the program's status always describes the
default build rather than the caller's tuning. A blocker found in a later round is
marked `(found after hiding f)`. A function no round named is `typed` only when the last round
built on the typed path; otherwise `unknown` — never a guess. Temporary copies live in a
temporary directory; the source file is only read.

```
$ python3 -m ail_lang.explain ../lab/explain/progs/g08_method_dict.py
g08_method_dict.py  general
g08_method_dict.py:3 Counter.__init__  typed
g08_method_dict.py:6 Counter.snapshot  general  Counter.snapshot() typed dict return disagrees with its annotation; ...
g08_method_dict.py:11 Counter.get  typed
g08_method_dict.py:15 main  general  print() given a dict[str, int]; write instead: ...
```

`--json` prints `ail.explain/1` with the same fields (`status`, `message`, `functions[]` with
`name`, `line`, `kind`, `status`, `construct`, `why`, `write_instead`, `statement`, `after` —
the list of functions hidden to reach that blocker, or `null` in the first round).

## After

All 30 programs, 117 functions listed by their `# expect:` lines:

- **117/117 correct (100%)**
- **0 functions reported `typed` that the build does not compile on the typed path** — every
  function marked `typed` was in the last hiding round that built with `--strict`, and every
  function marked `general` was named by a real blocker.
- 10/10 fully typed programs report program status `typed` and no general function.
- 10/10 one-general programs report the expected function as `general` (nine report exactly
  one; `g08` also reports `main`, correctly, because `print()` of a dict is refused).
- 10/10 multi-blocker programs report every blocked function, including methods, nested
  functions (attributed to the enclosing function), and callers poisoned by a general callee
  (e.g. `main` printing a dict, `show` assigning a call result to an annotated list).
- Checked outside the probe set (reviewer probes, run with the same command): a blocker in a
  `@staticmethod` / `@classmethod` is attributed to `Cls.method` (the compiler names them
  `Cls__static__m` / `Cls__classmethod__m`), a hidden `@property` keeps its decorator so its
  callers stay `typed`, and `AIL_QUIET_FALLBACK=1` / `AIL_UNIFIED_FORCE=1` in the caller's
  environment no longer change the program status line (`g01` stays `general`, `t01` stays
  `typed`).

Two expectations were corrected against the build while checking (the build is the oracle):
`m02`/`m06`/`m07`'s callers are `typed` once the blocked callee is stubbed (assigning to an
annotated local from a call is fine when the callee is typed), and `g08`'s `main` is `general`
because `print()` of a `dict` is refused. `m01`'s `show` is `general` because it receives a
`list` from the general `ordering()`.

### Build facts this probe set pinned down

- `dict` built with `d = {}` then returned, `return sorted(xs)`, a `yield`, a list mixing an
  `int` and a `str`, `return None` from an `-> int` function, a parameter sliced (`xs[1:]`), and
  `xs.reverse()` on a parameter all fall to the general path; the same slice/reverse on a local
  list is typed.
- A name bound to a type (`t = int`) is refused by *both* builds (`the general path could not
  build this program either`), so it is not usable as a "general path" probe; hence no probe
  uses it.
- `str | None` and untyped `out = []` containers are already typed here, so the probe set uses
  the constructs above instead.
- A function with no parameters and no `print()`/`assert` is refused by the typed path ("no way
  to show its return value"), which is why every `main()` in the probe set prints something.

## Test

`AIL_CURRENT/test_ail_explain.py` runs explain on 8 fast programs, compares the status column
with each `# expect:` line, and checks that `--json` parses and agrees. It skips without a C
compiler. Registered with `AIL_CURRENT/tests.d/test_ail_explain.txt`.

```
$ python3 AIL_CURRENT/test_ail_explain.py
Ran 2 tests in 7.4s
OK
```
