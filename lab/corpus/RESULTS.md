# Corpus results

## Generation

| model | tasks asked | ok | empty | no code block | timeout |
|---|---|---|---|---|---|
| deepseek-v4.1-flash-free | 499 | 164 | 331 | 0 | 4 |
| glm-5.3-flash-free | 499 | 55 | 440 | 0 | 4 |

About 1.5 hours into generation the free tier began answering every request with the error "free tier can only be used from within OpenCode" (no model reply, empty stdout, in a few seconds). Those requests are recorded as `empty` here because the first run did not tell them apart; `generate.py` now records them as blocked, waits and asks again (`--redo-empty`). The block had not lifted three-plus hours later, so the counts above are what the free tier delivered: the programs of the first ~100 (glm) and ~170 (deepseek) requests, plus a handful of genuinely empty replies among them. Nothing was done to get around the block.

## Programs by class (one count per program; worst class over its three inputs)

| model | mode | programs | same | refused | overflow | limit | DIFF | crash | timeout | skipped |
|---|---|---|---|---|---|---|---|---|---|---|
| deepseek-v4.1-flash-free | default | 164 | 88 | 66 | 1 | 1 | 6 | 2 | 0 | 0 |
| deepseek-v4.1-flash-free | ir | 164 | 88 | 66 | 1 | 1 | 6 | 2 | 0 | 0 |
| glm-5.3-flash-free | default | 55 | 23 | 29 | 1 | 0 | 1 | 1 | 0 | 0 |
| glm-5.3-flash-free | ir | 55 | 23 | 29 | 1 | 0 | 1 | 1 | 0 | 0 |
| all | default | 219 | 111 | 95 | 2 | 1 | 7 | 3 | 0 | 0 |
| all | ir | 219 | 111 | 95 | 2 | 1 | 7 | 3 | 0 | 0 |

## Runs by class (program x input)

| mode | same | refused | overflow | limit | DIFF | crash | timeout | skipped |
|---|---|---|---|---|---|---|---|---|
| default | 338 | 95 | 4 | 2 | 19 | 3 | 0 | 0 |
| ir | 338 | 95 | 4 | 2 | 19 | 3 | 0 | 0 |

Programs for which CPython itself exits non-zero on all three inputs (a bad program or a bad input; the comparison still counts them): 1.

## By category (mode default, programs of both models)

| category | programs | same | refused | overflow | limit | DIFF | crash | timeout | skipped | accepted % |
|---|---|---|---|---|---|---|---|---|---|---|
| collections | 16 | 12 | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 88 |
| dp | 28 | 18 | 8 | 0 | 0 | 2 | 0 | 0 | 0 | 71 |
| errors_classes | 42 | 10 | 29 | 2 | 0 | 1 | 0 | 0 | 0 | 31 |
| graphs | 12 | 4 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 33 |
| grids | 21 | 13 | 5 | 0 | 0 | 0 | 3 | 0 | 0 | 76 |
| numbers | 19 | 17 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 89 |
| parsing | 25 | 4 | 21 | 0 | 0 | 0 | 0 | 0 | 0 | 16 |
| simulation | 15 | 9 | 5 | 0 | 0 | 1 | 0 | 0 | 0 | 67 |
| sorting | 12 | 6 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 50 |
| strings | 29 | 18 | 9 | 0 | 1 | 1 | 0 | 0 | 0 | 69 |

## Refusal reasons, ranked (mode default; number of programs)

| n | reason | example |
|---|---|---|
| 7 | import of 'csv' | deepseek-v4.1-flash-free/t166 |
| 5 | json.loads(s): the type of the result is not declared here | deepseek-v4.1-flash-free/t176 |
| 3 | import of 'datetime' | deepseek-v4.1-flash-free/t388 |
| 3 | import of 'unicodedata' | deepseek-v4.1-flash-free/t489 |
| 3 | only a class type can be None: write `Node \| None` | deepseek-v4.1-flash-free/t188 |
| 2 | .bit_length(): an int has no method 'bit_length' here (or not with these arguments) | deepseek-v4.1-flash-free/t470 |
| 2 | `in` with a str | deepseek-v4.1-flash-free/t210 |
| 2 | a nested function captures 'tree', which is a container (or object), not a plain number | deepseek-v4.1-flash-free/t015 |
| 2 | a slice used where a single number is needed | deepseek-v4.1-flash-free/t095 |
| 2 | import of 'class' | deepseek-v4.1-flash-free/t475 |
| 2 | import of 'decimal' | deepseek-v4.1-flash-free/t419 |
| 2 | itertools.product: repeat= has to be a non-negative integer literal | deepseek-v4.1-flash-free/t341 |
| 2 | max() with keyword arguments | deepseek-v4.1-flash-free/t141 |
| 2 | random.Random is not built | deepseek-v4.1-flash-free/t391 |
| 2 | sorted(d.items()) is supported only as the iterable of `for k, v in sorted(d.items(), ...)` | deepseek-v4.1-flash-free/t456 |
| 2 | the result of __eq__() is declared bool, but `NotImplemented` is not a bool (Python would keep the number and print it as one) | deepseek-v4.1-flash-free/t432 |
| 1 | '<name>' is a blist | deepseek-v4.1-flash-free/t223 |
| 1 | '<name>' is annotated Matrix, which this compiler has no rule for | glm-5.3-flash-free/t251 |
| 1 | '<name>' is annotated Observers, which this compiler has no rule for | deepseek-v4.1-flash-free/t447 |
| 1 | '<name>' is annotated Point, which this compiler has no rule for | deepseek-v4.1-flash-free/t257 |
| 1 | '<name>' is annotated re.Match[str], which this compiler has no rule for | deepseek-v4.1-flash-free/t196 |
| 1 | '<name>' is declared slist | glm-5.3-flash-free/t095 |
| 1 | '<name>' is declared str | deepseek-v4.1-flash-free/t474 |
| 1 | '<name>' is read before it is assigned | deepseek-v4.1-flash-free/t382 |
| 1 | .casefold() on a str: ASCII-only case mapping is not what Python does and this compiler will not guess: 'ß'.upper() is 'SS' (one character b | deepseek-v4.1-flash-free/t081 |
| 1 | .join() on a str takes one list[str]: a named list of str or an inline .split()/.splitlines() result | deepseek-v4.1-flash-free/t112 |
| 1 | .ljust() on a str: it returns a MODIFIED str (padded, replaced, case-folded, ...) | deepseek-v4.1-flash-free/t493 |
| 1 | Fenwick.tree would hold a list, set or dict | deepseek-v4.1-flash-free/t328 |
| 1 | UnionFind.__init__ must consist only of `self.<name> = <expr>` assignments to establish the fixed shape | glm-5.3-flash-free/t284 |
| 1 | `zip(*rows)` cannot be walked inline here | deepseek-v4.1-flash-free/t385 |
| 1 | `zip(words, words[1:])` cannot be walked inline here | glm-5.3-flash-free/t108 |
| 1 | a class body statement other than a method (Assign, in class 'Node') | deepseek-v4.1-flash-free/t452 |
| 1 | a nested function captures 'seen', which is a container (or object), not a plain number | deepseek-v4.1-flash-free/t266 |
| 1 | a tuple used where a single value is needed | deepseek-v4.1-flash-free/t404 |
| 1 | bisect_left() is built as a statement or a value where it is evaluated unconditionally | deepseek-v4.1-flash-free/t319 |
| 1 | call to iter() | deepseek-v4.1-flash-free/t278 |
| 1 | comparing a str with a number | glm-5.3-flash-free/t264 |
| 1 | dijkstra() class list return type disagrees with its annotation | deepseek-v4.1-flash-free/t283 |
| 1 | field _AilT_b_b.fb0 is declared bool, but `letters` is not a bool (Python would keep the number and print it as one) | deepseek-v4.1-flash-free/t484 |
| 1 | functools cache: .cache_info is not built | deepseek-v4.1-flash-free/t440 |
| 1 | import of 'calendar' | deepseek-v4.1-flash-free/t198 |
| 1 | import of 'collections' with a use that is not built: Counter, defaultdict (int, float, str, list, lambda: <constant>), OrderedDict and dequ | deepseek-v4.1-flash-free/t172 |
| 1 | import of 'collections.abc' | glm-5.3-flash-free/t452 |
| 1 | import of 'enum' | deepseek-v4.1-flash-free/t449 |
| 1 | import of 'fractions' | deepseek-v4.1-flash-free/t483 |
| 1 | import of 're' with a use that is not built: the re module is built for string- or bytes-literal patterns only (match, fullmatch, search, fi | deepseek-v4.1-flash-free/t455 |
| 1 | import of 'statistics' | deepseek-v4.1-flash-free/t482 |
| 1 | import of 'textwrap' | deepseek-v4.1-flash-free/t116 |
| 1 | inheritance (class 'InsufficientFunds' names a base class) | deepseek-v4.1-flash-free/t139 |
| 1 | itertools.accumulate used here is not built: the itertools functions are built in a for statement, in a comprehension / generator expression | glm-5.3-flash-free/t014 |
| 1 | itertools: RunningAverage(numbers) is not known to be a list / str here (a list or str parameter or a variable bound only to lists / strs, a | glm-5.3-flash-free/t437 |
| 1 | itertools: combo holds a tuple in CPython | glm-5.3-flash-free/t339 |
| 1 | itertools: perm holds a tuple in CPython | deepseek-v4.1-flash-free/t338 |
| 1 | itertools: subset holds a tuple in CPython | deepseek-v4.1-flash-free/t339 |
| 1 | json.dumps of value: the type of this value is not known here | deepseek-v4.1-flash-free/t184 |
| 1 | key= must be a lambda or a function name | deepseek-v4.1-flash-free/t379 |
| 1 | list extend requires a matching list name or literal | glm-5.3-flash-free/t265 |
| 1 | list[list[tuple[int, int]]]: a nested list holds rows of int, float, str or a class | glm-5.3-flash-free/t278 |
| 1 | math.hypot() with these arguments is not built (see the note below) | glm-5.3-flash-free/t472 |
| 1 | nonlocal in a nested function ('dfs') is not available: a captured local cannot be rebound | deepseek-v4.1-flash-free/t271 |

## Refusal reasons, ranked (mode ir; number of programs)

| n | reason | example |
|---|---|---|
| 7 | import of 'csv' | deepseek-v4.1-flash-free/t166 |
| 5 | json.loads(s): the type of the result is not declared here | deepseek-v4.1-flash-free/t176 |
| 3 | import of 'datetime' | deepseek-v4.1-flash-free/t388 |
| 3 | import of 'unicodedata' | deepseek-v4.1-flash-free/t489 |
| 3 | only a class type can be None: write `Node \| None` | deepseek-v4.1-flash-free/t188 |
| 2 | .bit_length(): an int has no method 'bit_length' here (or not with these arguments) | deepseek-v4.1-flash-free/t470 |
| 2 | `in` with a str | deepseek-v4.1-flash-free/t210 |
| 2 | a nested function captures 'tree', which is a container (or object), not a plain number | deepseek-v4.1-flash-free/t015 |
| 2 | a slice used where a single number is needed | deepseek-v4.1-flash-free/t095 |
| 2 | import of 'class' | deepseek-v4.1-flash-free/t475 |
| 2 | import of 'decimal' | deepseek-v4.1-flash-free/t419 |
| 2 | itertools.product: repeat= has to be a non-negative integer literal | deepseek-v4.1-flash-free/t341 |
| 2 | max() with keyword arguments | deepseek-v4.1-flash-free/t141 |
| 2 | random.Random is not built | deepseek-v4.1-flash-free/t391 |
| 2 | sorted(d.items()) is supported only as the iterable of `for k, v in sorted(d.items(), ...)` | deepseek-v4.1-flash-free/t456 |
| 2 | the result of __eq__() is declared bool, but `NotImplemented` is not a bool (Python would keep the number and print it as one) | deepseek-v4.1-flash-free/t432 |
| 1 | '<name>' is a blist | deepseek-v4.1-flash-free/t223 |
| 1 | '<name>' is annotated Matrix, which this compiler has no rule for | glm-5.3-flash-free/t251 |
| 1 | '<name>' is annotated Observers, which this compiler has no rule for | deepseek-v4.1-flash-free/t447 |
| 1 | '<name>' is annotated Point, which this compiler has no rule for | deepseek-v4.1-flash-free/t257 |
| 1 | '<name>' is annotated re.Match[str], which this compiler has no rule for | deepseek-v4.1-flash-free/t196 |
| 1 | '<name>' is declared slist | glm-5.3-flash-free/t095 |
| 1 | '<name>' is declared str | deepseek-v4.1-flash-free/t474 |
| 1 | '<name>' is read before it is assigned | deepseek-v4.1-flash-free/t382 |
| 1 | .casefold() on a str: ASCII-only case mapping is not what Python does and this compiler will not guess: 'ß'.upper() is 'SS' (one character b | deepseek-v4.1-flash-free/t081 |
| 1 | .join() on a str takes one list[str]: a named list of str or an inline .split()/.splitlines() result | deepseek-v4.1-flash-free/t112 |
| 1 | .ljust() on a str: it returns a MODIFIED str (padded, replaced, case-folded, ...) | deepseek-v4.1-flash-free/t493 |
| 1 | Fenwick.tree would hold a list, set or dict | deepseek-v4.1-flash-free/t328 |
| 1 | UnionFind.__init__ must consist only of `self.<name> = <expr>` assignments to establish the fixed shape | glm-5.3-flash-free/t284 |
| 1 | `zip(*rows)` cannot be walked inline here | deepseek-v4.1-flash-free/t385 |
| 1 | `zip(words, words[1:])` cannot be walked inline here | glm-5.3-flash-free/t108 |
| 1 | a class body statement other than a method (Assign, in class 'Node') | deepseek-v4.1-flash-free/t452 |
| 1 | a nested function captures 'seen', which is a container (or object), not a plain number | deepseek-v4.1-flash-free/t266 |
| 1 | a tuple used where a single value is needed | deepseek-v4.1-flash-free/t404 |
| 1 | bisect_left() is built as a statement or a value where it is evaluated unconditionally | deepseek-v4.1-flash-free/t319 |
| 1 | call to iter() | deepseek-v4.1-flash-free/t278 |
| 1 | comparing a str with a number | glm-5.3-flash-free/t264 |
| 1 | dijkstra() class list return type disagrees with its annotation | deepseek-v4.1-flash-free/t283 |
| 1 | field _AilT_b_b.fb0 is declared bool, but `letters` is not a bool (Python would keep the number and print it as one) | deepseek-v4.1-flash-free/t484 |
| 1 | functools cache: .cache_info is not built | deepseek-v4.1-flash-free/t440 |
| 1 | import of 'calendar' | deepseek-v4.1-flash-free/t198 |
| 1 | import of 'collections' with a use that is not built: Counter, defaultdict (int, float, str, list, lambda: <constant>), OrderedDict and dequ | deepseek-v4.1-flash-free/t172 |
| 1 | import of 'collections.abc' | glm-5.3-flash-free/t452 |
| 1 | import of 'enum' | deepseek-v4.1-flash-free/t449 |
| 1 | import of 'fractions' | deepseek-v4.1-flash-free/t483 |
| 1 | import of 're' with a use that is not built: the re module is built for string- or bytes-literal patterns only (match, fullmatch, search, fi | deepseek-v4.1-flash-free/t455 |
| 1 | import of 'statistics' | deepseek-v4.1-flash-free/t482 |
| 1 | import of 'textwrap' | deepseek-v4.1-flash-free/t116 |
| 1 | inheritance (class 'InsufficientFunds' names a base class) | deepseek-v4.1-flash-free/t139 |
| 1 | itertools.accumulate used here is not built: the itertools functions are built in a for statement, in a comprehension / generator expression | glm-5.3-flash-free/t014 |
| 1 | itertools: RunningAverage(numbers) is not known to be a list / str here (a list or str parameter or a variable bound only to lists / strs, a | glm-5.3-flash-free/t437 |
| 1 | itertools: combo holds a tuple in CPython | glm-5.3-flash-free/t339 |
| 1 | itertools: perm holds a tuple in CPython | deepseek-v4.1-flash-free/t338 |
| 1 | itertools: subset holds a tuple in CPython | deepseek-v4.1-flash-free/t339 |
| 1 | json.dumps of value: the type of this value is not known here | deepseek-v4.1-flash-free/t184 |
| 1 | key= must be a lambda or a function name | deepseek-v4.1-flash-free/t379 |
| 1 | list extend requires a matching list name or literal | glm-5.3-flash-free/t265 |
| 1 | list[list[tuple[int, int]]]: a nested list holds rows of int, float, str or a class | glm-5.3-flash-free/t278 |
| 1 | math.hypot() with these arguments is not built (see the note below) | glm-5.3-flash-free/t472 |
| 1 | nonlocal in a nested function ('dfs') is not available: a captured local cannot be rebound | deepseek-v4.1-flash-free/t271 |

## Findings (DIFF, crash, timeout)

- deepseek-v4.1-flash-free t117 [default] input 0: **DIFF** exit code cpython=0 ail=1; line 1: cpython='No' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t117 [default] input 1: **DIFF** exit code cpython=0 ail=1; line 1: cpython='No' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t117 [default] input 2: **DIFF** exit code cpython=0 ail=1; line 1: cpython='No' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t117 [ir] input 0: **DIFF** exit code cpython=0 ail=1; line 1: cpython='No' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t117 [ir] input 1: **DIFF** exit code cpython=0 ail=1; line 1: cpython='No' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t117 [ir] input 2: **DIFF** exit code cpython=0 ail=1; line 1: cpython='No' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t130 [default] input 0: **DIFF** exit code cpython=0 ail=1; line 1: cpython='grace 99.10' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t130 [default] input 1: **DIFF** exit code cpython=0 ail=1; line 1: cpython='ivan 333.16' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t130 [default] input 2: **DIFF** exit code cpython=0 ail=1; line 1: cpython='mallory 533.39' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t130 [ir] input 0: **DIFF** exit code cpython=0 ail=1; line 1: cpython='grace 99.10' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t130 [ir] input 1: **DIFF** exit code cpython=0 ail=1; line 1: cpython='ivan 333.16' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t130 [ir] input 2: **DIFF** exit code cpython=0 ail=1; line 1: cpython='mallory 533.39' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t161 [default] input 0: **DIFF** line 1: cpython="Row(a=8, b=5, word='apple')" ail='<Row object>' (see `findings/`)
- deepseek-v4.1-flash-free t161 [default] input 1: **DIFF** line 1: cpython="Row(a=0, b=1, word='apple')" ail='<Row object>' (see `findings/`)
- deepseek-v4.1-flash-free t161 [default] input 2: **DIFF** line 1: cpython="Row(a=2, b=1, word='apple')" ail='<Row object>' (see `findings/`)
- deepseek-v4.1-flash-free t161 [ir] input 0: **DIFF** line 1: cpython="Row(a=8, b=5, word='apple')" ail='<Row object>' (see `findings/`)
- deepseek-v4.1-flash-free t161 [ir] input 1: **DIFF** line 1: cpython="Row(a=0, b=1, word='apple')" ail='<Row object>' (see `findings/`)
- deepseek-v4.1-flash-free t161 [ir] input 2: **DIFF** line 1: cpython="Row(a=2, b=1, word='apple')" ail='<Row object>' (see `findings/`)
- deepseek-v4.1-flash-free t256 [default] input -1: **crash** compiler rc=4: 3787:79: error: incompatible type for argument 2 of ‘ail_list_push’ (see `findings/`)
- deepseek-v4.1-flash-free t256 [ir] input -1: **crash** compiler rc=4: 3787:79: error: incompatible type for argument 2 of ‘ail_list_push’ (see `findings/`)
- deepseek-v4.1-flash-free t258 [default] input -1: **crash** compiler rc=4: 3398:79: error: incompatible type for argument 2 of ‘ail_list_push’ (see `findings/`)
- deepseek-v4.1-flash-free t258 [ir] input -1: **crash** compiler rc=4: 3398:79: error: incompatible type for argument 2 of ‘ail_list_push’ (see `findings/`)
- deepseek-v4.1-flash-free t310 [default] input 0: **DIFF** exit code cpython=0 ail=1; line 1: cpython='False' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t310 [default] input 1: **DIFF** exit code cpython=0 ail=1; line 1: cpython='False' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t310 [default] input 2: **DIFF** exit code cpython=0 ail=1; line 1: cpython='False' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t310 [ir] input 0: **DIFF** exit code cpython=0 ail=1; line 1: cpython='False' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t310 [ir] input 1: **DIFF** exit code cpython=0 ail=1; line 1: cpython='False' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t310 [ir] input 2: **DIFF** exit code cpython=0 ail=1; line 1: cpython='False' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t336 [default] input 2: **DIFF** line 1: cpython='187' ail='1' (see `findings/`)
- deepseek-v4.1-flash-free t336 [ir] input 2: **DIFF** line 1: cpython='187' ail='1' (see `findings/`)
- deepseek-v4.1-flash-free t437 [default] input 0: **DIFF** exit code cpython=0 ail=1; line 1: cpython='42.00' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t437 [default] input 1: **DIFF** exit code cpython=0 ail=1; line 1: cpython='-46.00' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t437 [default] input 2: **DIFF** exit code cpython=0 ail=1; line 1: cpython='31.00' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t437 [ir] input 0: **DIFF** exit code cpython=0 ail=1; line 1: cpython='42.00' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t437 [ir] input 1: **DIFF** exit code cpython=0 ail=1; line 1: cpython='-46.00' ail='<end>' (see `findings/`)
- deepseek-v4.1-flash-free t437 [ir] input 2: **DIFF** exit code cpython=0 ail=1; line 1: cpython='31.00' ail='<end>' (see `findings/`)
- glm-5.3-flash-free t243 [default] input -1: **crash** compiler rc=1: TypeError: not all arguments converted during string formatting (see `findings/`)
- glm-5.3-flash-free t243 [ir] input -1: **crash** compiler rc=1: TypeError: not all arguments converted during string formatting (see `findings/`)
- glm-5.3-flash-free t414 [default] input 0: **DIFF** exit code cpython=0 ail=1; line 1: cpython='54' ail='<end>' (see `findings/`)
- glm-5.3-flash-free t414 [default] input 1: **DIFF** exit code cpython=0 ail=1; line 1: cpython='70' ail='<end>' (see `findings/`)
- glm-5.3-flash-free t414 [default] input 2: **DIFF** exit code cpython=0 ail=1; line 1: cpython='5' ail='<end>' (see `findings/`)
- glm-5.3-flash-free t414 [ir] input 0: **DIFF** exit code cpython=0 ail=1; line 1: cpython='54' ail='<end>' (see `findings/`)
- glm-5.3-flash-free t414 [ir] input 1: **DIFF** exit code cpython=0 ail=1; line 1: cpython='70' ail='<end>' (see `findings/`)
- glm-5.3-flash-free t414 [ir] input 2: **DIFF** exit code cpython=0 ail=1; line 1: cpython='5' ail='<end>' (see `findings/`)
