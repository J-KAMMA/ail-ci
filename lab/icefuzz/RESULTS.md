# icefuzz: compiler crash fuzzing

Command: `python3 lab/icefuzz/run.py --seed 0 --count 2000 --jobs 2 --out /tmp/icefull2 --budget 3300`

**The run stopped at 1745/2000** because seed 1744 produced silent wrong output (section below). The job's stop rule says to stop the run and report at once, so the remaining 255 seeds were not started.

Corpus: a fast subset of `lab/stdlib/*/*.py` (<=18 lines, files importing `re`/`decimal`/`datetime`/`tomllib` omitted; regex/decimal/datetime and other high-lowering modules omitted so each mutant fits the 60 s budget), `lab/compare/src/*/main.py` (<=120 lines), `lab/limits/*.py` (<=40 lines). Each seed mutates one program; every mutant parses and runs in CPython 3.12 for <=5 s.

| class | count |
|---|---|
| built and matching | 957 |
| built and different | 65 |
| refused by name | 668 |
| internal error | 55 |
| discarded (no valid mutant) | 0 |
| **classified** | **1745** |

Internal errors per 2000 mutants: **63.0** (observed 55 in 1745). Elapsed 2370 s.

## Silent differences (built, stdout differs)

These stop the run; they are listed before crashes as the job requires.

| seed | corpus mutation | first difference |
|---|---|---|
| 1744 | add_global, shadow_builtin, insert_walrus | line 1: cpython='keyword if True' ail='missing NotImplemented' |

Seed 1744 mutates `lab/stdlib/keyword/03_iskeyword.py`. Both builds exit 0, but AIL
prints `missing NotImplemented` where CPython prints `keyword if True`: the loop
variable `NotImplemented` is never bound, and the builtin constant is used instead.

Minimal reproducer (`lab/icefuzz/crashes/silent-01-notimplemented-global.py`):

```python
def main() -> None:
    global name
    NotImplemented = 'local'
    print(NotImplemented)
main()
```

```sh
ulimit -v 1500000
python3 -B AIL_CURRENT/ail_chatgpt.py compile \
    lab/icefuzz/crashes/silent-01-notimplemented-global.py --syntax python -o /tmp/silent.bin
/tmp/silent.bin
```

CPython 3.12 prints `local` (rc 0); the AIL build prints `NotImplemented` (rc 0).
The `global name` names a module variable with no module-level binding, and the
compiler then ignores the local assignment to the builtin constant
`NotImplemented`. Without the `global` line (`NotImplemented = 'local'` alone, or
with `name = 1` at module level) AIL prints `local` correctly; `Ellipsis` and
ordinary builtins such as `len` shadow correctly too. This is a silent
difference in the general path; the compiler was not changed in this job.

## Built and different (not silent: loud int64 stop or exit status only)

| seed | mutations | reason |
|---|---|---|
| 60 | add_global, insert_lambda | loud runtime stop: AttributeError: 'bytes' object has no attribute 'hex' |
| 78 | insert_match | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 85 | add_global, insert_lambda | loud runtime stop: AttributeError: '_AilHash' object has no attribute 'hexdigest' |
| 96 | change_literal | loud runtime stop: ValueError |
| 146 | wrap_in_try | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 153 | shadow_builtin | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 160 | wrap_in_try, add_decorator | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 190 | add_global, insert_lambda | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 194 | wrap_in_try, shadow_builtin, insert_star_args | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 215 | shadow_builtin | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 219 | swap_operands, add_decorator, shadow_builtin | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 277 | insert_walrus, insert_walrus | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 290 | insert_walrus, wrap_in_try | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 343 | insert_walrus, insert_star_args | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 385 | insert_del, insert_del | exit cpython=1 ail=0 |
| 393 | insert_del | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 402 | insert_del, insert_del | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 403 | wrap_in_try | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 425 | swap_operands, insert_walrus | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 426 | insert_lambda, insert_star_args | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 464 | add_global, shadow_builtin, nest_comprehension | loud runtime stop: KeyError: NotImplemented |
| 466 | wrap_in_try | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 475 | insert_match | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 485 | nest_comprehension, insert_del | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 497 | add_global, add_global | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 555 | insert_star_args | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 577 | insert_lambda, change_literal | loud runtime stop: AttributeError: '_AilHash' object has no attribute 'hexdigest' |
| 599 | insert_walrus | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 650 | insert_lambda, insert_match | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 689 | insert_lambda | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 699 | change_literal, swap_operands, swap_operands | line 1: cpython='<end>' ail='bytes 0' |
| 738 | wrap_in_try | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 760 | add_global | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 763 | insert_star_args, insert_match | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 819 | shadow_builtin | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 875 | insert_walrus, insert_walrus | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 880 | insert_match, insert_walrus | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 881 | insert_match, insert_match | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 883 | insert_walrus, nest_comprehension | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 899 | nest_comprehension | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 967 | insert_del | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 1048 | swap_operands | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1065 | insert_walrus | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 1090 | insert_match, change_literal | loud runtime stop: ValueError |
| 1104 | shadow_builtin | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1106 | insert_lambda | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1178 | shadow_builtin, wrap_in_try | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1245 | insert_walrus | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1249 | insert_del | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1250 | nest_comprehension, shadow_builtin | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1302 | insert_star_args, insert_lambda, insert_star_args | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 1361 | shadow_builtin, insert_match | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1363 | shadow_builtin, insert_lambda | loud runtime stop: AttributeError: '_AilHash' object has no attribute 'hexdigest' |
| 1371 | insert_match, insert_match, wrap_in_try | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1431 | insert_match, insert_walrus | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1483 | insert_del | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1496 | insert_lambda | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 1536 | nest_comprehension, insert_lambda | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 1544 | insert_match | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1548 | insert_match, insert_star_args | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1575 | insert_match | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 1576 | nest_comprehension, nest_comprehension, nest_comprehension | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1591 | insert_lambda | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1606 | insert_walrus | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |

Two of the rows above have `cpython_rc != 0`, so CPython itself failed and they are
not valid oracle comparisons: seed 385 (`exit cpython=1 ail=0`, same stdout) and
seed 699 (CPython raised with no stdout, AIL printed `bytes 0` and exited 0).
They are listed but not counted as silent differences.

## Internal errors grouped by the last traceback frame

| group | count | seeds | reproducer |
|---|---|---|---|
| `traceback:name_ref` | 55 | 16, 26, 98, 112, 117, 129, 168, 214, 237, 276, ... | `crashes/crash-01-traceback-name_ref.py` |

## Minimised reproducers

### `traceback:name_ref` (55/1745)

`lab/icefuzz/crashes/crash-01-traceback-name_ref.py` (4 lines, 22 compile probes):

```python
def main() -> None:
    global winners
main()
del person
```

```sh
ulimit -v 1500000
python3 -B AIL_CURRENT/ail_chatgpt.py compile \
    lab/icefuzz/crashes/crash-01-traceback-name_ref.py --syntax python -o /tmp/crash.bin
```

Traceback head (compile exits 1):

```
File ".../AIL_CURRENT/python/pkg-v12/pyboxed2.py", line 4073, in name_ref
    return ctx.slot_expr(ctx.slot_of[name])
                         ~~~~~~~~~~~^^^^^^
KeyError: 'person'
```

The essential trigger is a module-level `del` of a name that has no module-level
binding (a one-line `del person` reproduces the same KeyError).

## Top refusal reasons

- 37 x this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, 
- 35 x C
- 24 x *args, **kwargs, positional-only and keyword-only parameters are refused, and a method may not take a default 
- 24 x 18446744073709551615
- 23 x statistics.NormalDist used here is not built (mean, fmean, median, median_low, median_high, mode, multimode, p
- 23 x the name 'eval' is not a known function/class/builtin; did you mean 'eval'?
- 21 x sys.stdin used as a plain value
- 20 x the decorator on def bump (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are suppo
- 20 x tempfile.mkdtemp (not yet published in NAMES_library.json)
- 19 x os.getcwd chdir listdir mkdir makedirs remove unlink rmdir rename replace getenv environ walk, os.sep linesep 
