# icefuzz: compiler crash fuzzing

Command: `python3 lab/icefuzz/run.py --seed 0 --count 2000 --jobs 2 --out /tmp/icefull2 --budget 3300`

Corpus: a fast subset of `lab/stdlib/*/*.py` (<=18 lines, files importing `re`/`decimal`/`datetime`/`tomllib` omitted; regex/decimal/datetime and other high-lowering modules omitted so each mutant fits the 60 s budget), `lab/compare/src/*/main.py` (<=120 lines), `lab/limits/*.py` (<=40 lines). Each seed mutates one program; every mutant parses and exits 0 in CPython 3.12 within 5 s (candidates CPython rejects are discarded).

| class | count |
|---|---|
| built and matching | 1022 |
| built and different | 74 |
| refused by name | 648 |
| internal error | 1 |
| discarded (no valid mutant) | 0 |
| **classified** | **1745** |

Internal errors per 2000 mutants: **1.1** (observed 1 in 1745). Elapsed 1438 s.

**The run stopped at the first silent difference (seed 1744)**, after 1745 mutants. The remaining seeds were not run.

## Silent differences (built, stdout differs)

These stop the run; they are listed before crashes as the job requires. A silent difference is a build where CPython exits 0 and AIL exits 0 but the stdout differs.

| seed | corpus mutation | first difference | reproducer |
|---|---|---|---|
| 1744 | add_global, shadow_builtin, insert_walrus | line 1: cpython='keyword if True' ail='missing NotImplemented' | `crashes/silent-01-notimplemented-global.py` |

Reproducer (`lab/icefuzz/crashes/silent-01-notimplemented-global.py`, seed 1744):

```python
import keyword

def main() -> None:
    for NotImplemented in keyword.kwlist:
        if not keyword.iskeyword(NotImplemented):
            if (__ice_w := 1):
                pass
            print('missing', NotImplemented)
main()
```

```sh
ulimit -v 1500000
python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/icefuzz/crashes/silent-01-notimplemented-global.py --syntax python -o /tmp/silent-01-notimplemented-global.bin
```


## Built and different (loud stop or exit status)

| seed | mutations | reason |
|---|---|---|
| 26 | add_global, insert_del | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
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
| 333 | shadow_builtin, insert_star_args | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 343 | insert_walrus, insert_star_args | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 362 | insert_lambda, insert_walrus, insert_match | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 393 | insert_del | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 403 | wrap_in_try | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 425 | swap_operands, insert_walrus | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 426 | insert_lambda, insert_star_args | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 464 | add_global, shadow_builtin, nest_comprehension | loud runtime stop: KeyError: NotImplemented |
| 466 | wrap_in_try | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 475 | insert_match | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 485 | nest_comprehension, insert_del | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 497 | add_global, add_global | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 555 | insert_star_args | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 571 | nest_comprehension | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 577 | insert_lambda, change_literal | loud runtime stop: AttributeError: '_AilHash' object has no attribute 'hexdigest' |
| 599 | insert_walrus | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 645 | nest_comprehension, change_literal | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 650 | insert_lambda, insert_match | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 652 | shadow_builtin, shadow_builtin | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 689 | insert_lambda | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 738 | wrap_in_try | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 740 | add_decorator, add_decorator, wrap_in_try | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 751 | add_global, insert_match, add_global | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 760 | add_global | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 763 | insert_star_args, insert_match | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 819 | shadow_builtin | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 875 | insert_walrus, insert_walrus | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 880 | insert_match, insert_walrus | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 881 | insert_match, insert_match | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 883 | insert_walrus, nest_comprehension | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 899 | nest_comprehension | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 917 | change_literal | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
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
| 1436 | insert_lambda | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1483 | insert_del | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1496 | insert_lambda | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 1536 | nest_comprehension, insert_lambda | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 1544 | insert_match | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1548 | insert_match, insert_star_args | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1549 | insert_walrus, swap_operands | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1575 | insert_match | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 1576 | nest_comprehension, nest_comprehension, nest_comprehension | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1591 | insert_lambda | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |
| 1606 | insert_walrus | loud runtime stop: OverflowError: integer overflow in + (ints are 64-bit; --exact-int gives exact ints) |
| 1692 | insert_match | loud runtime stop: OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints) |

## Internal errors grouped by the last traceback frame

| group | count | seeds | reproducer |
|---|---|---|---|
| `traceback:name_ref` | 1 | 1679 | `crashes/crash-01-traceback-name_ref.py` |

## Minimised reproducers

### `traceback:name_ref`

File: `lab/icefuzz/crashes/crash-01-traceback-name_ref.py` (6 lines, 16 compile probes).

```sh
ulimit -v 1500000
python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/icefuzz/crashes/crash-01-traceback-name_ref.py --syntax python -o /tmp/crash-01-traceback-name_ref.bin
```

Traceback head:

```
File "/home/runner/work/ail-ci/ail-ci/AIL_CURRENT/python/pkg-v12/pyboxed2.py", line 4073, in name_ref
```

## Top refusal reasons

- 41 x this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, 
- 34 x C
- 29 x statistics.NormalDist used here is not built (mean, fmean, median, median_low, median_high, mode, multimode, p
- 29 x *args, **kwargs, positional-only and keyword-only parameters are refused, and a method may not take a default 
- 26 x sys.stdin used as a plain value
- 24 x tempfile.mkdtemp (not yet published in NAMES_library.json)
- 23 x the name 'eval' is not a known function/class/builtin; did you mean 'eval'?
- 23 x the module sys used as a plain value
- 22 x the decorator on def bump (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are suppo
- 20 x a constant of t
