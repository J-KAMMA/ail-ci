# icefuzz: compiler crash fuzzing

Command: `python3 lab/icefuzz/run.py --seed 0 --count 2000 --jobs 2 --out /tmp/icefull2 --budget 3300`

Corpus: a fast subset of `lab/stdlib/*/*.py` (<=18 lines, files importing `re`/`decimal`/`datetime`/`tomllib` omitted; regex/decimal/datetime and other high-lowering modules omitted so each mutant fits the 60 s budget), `lab/compare/src/*/main.py` (<=120 lines), `lab/limits/*.py` (<=40 lines). Each seed mutates one program; every mutant parses and runs in CPython 3.12 for <=5 s.

| class | count |
|---|---|
| built and matching | 372 |
| built and different | 31 |
| refused by name | 273 |
| internal error | 25 |
| discarded (no valid mutant) | 0 |
| **classified** | **701** |

Internal errors per 2000 mutants: **71.3** (observed 25 in 701). Elapsed 241 s.

**The run stopped at the first silent difference (seed 699)**, after 701 mutants. The remaining seeds were not run.

## Silent differences (built, stdout differs)

These stop the run; they are listed before crashes as the job requires. A silent difference is a build that prints output CPython does not, whatever CPython itself exits with.

| seed | corpus mutation | first difference | reproducer |
|---|---|---|---|
| 699 | change_literal, swap_operands, swap_operands | line 1: cpython='<end>' ail='bytes 0' | `crashes/silent-01-seed699.py` |

Reproducer (`lab/icefuzz/crashes/silent-01-seed699.py`, seed 699):

```python
import hashlib
import sys

def main() -> None:
    digest = hashlib.sha256()
    chunk = sys.stdin.buffer.read('65536')
    total = 0
    while len(chunk) > 0:
        digest.update(chunk)
        total += len(chunk)
        chunk = sys.stdin.buffer.read(65536)
    print('bytes', total)
    print('sha256', digest.hexdigest())
main()
```

```sh
ulimit -v 1500000
python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/icefuzz/crashes/silent-01-seed699.py --syntax python -o /tmp/silent-01-seed699.bin
```


## Built and different (loud stop or exit status)

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

Rows whose stdout matches CPython but whose exit status differs are real oracle differences (CPython 3.12 compares stdout and exit status); they are not invalid comparisons.

## Internal errors grouped by the last traceback frame

| group | count | seeds | reproducer |
|---|---|---|---|
| `traceback:name_ref` | 25 | 16, 26, 98, 112, 117, 129, 168, 214, 237, 276, ... | `crashes/crash-01-traceback-name_ref.py` |

## Minimised reproducers

### `traceback:name_ref`

File: `lab/icefuzz/crashes/crash-01-traceback-name_ref.py` (4 lines, 18 compile probes).

```sh
ulimit -v 1500000
python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/icefuzz/crashes/crash-01-traceback-name_ref.py --syntax python -o /tmp/crash-01-traceback-name_ref.bin
```

Traceback head:

```
File "/home/runner/work/ail-ci/ail-ci/AIL_CURRENT/python/pkg-v12/pyboxed2.py", line 4073, in name_ref
```

## Top refusal reasons

- 18 x statistics.NormalDist used here is not built (mean, fmean, median, median_low, median_high, mode, multimode, p
- 17 x this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, 
- 12 x sys.stdin used as a plain value
- 12 x the file kind (text or binary) has to be known when the program is built.
- 12 x *args, **kwargs, positional-only and keyword-only parameters are refused, and a method may not take a default 
- 12 x the name 'eval' is not a known function/class/builtin; did you mean 'eval'?
- 10 x the decorator on def main (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are suppo
- 9 x a constant of t
- 8 x the decorator on def bump (only @staticmethod on a method and @functools.lru_cache/@lru_cache/@cache are suppo
- 8 x 18446744073709551615
