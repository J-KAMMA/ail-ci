# prog29: typed reach of eight real programs

CPython 3.12.3, `python3 -m cProfile`, each program on its largest task input
(`lab/corpus/tasks/<t>/in2.txt`) or no input for the self-contained `gdev` programs.  Times are tiny
because the published inputs are tiny; the tables list every project function by own time and the
share is of the whole profiled run (including interpreter/compile builtins).  For the 80% cut the
project functions are `main` plus the helpers/lambdas below; where the whole-run share is dominated
by compile/import builtins the project functions are nevertheless the only ones there are.

"Typed" is per function: it is `yes` when `--strict` has no blocker naming that function, so mixed
mode can compile it while another function stays general.  `no` carries the first blocker that names
it.  `t161`, `g08_004` and `t188` already passed `--strict`; `g17_010`'s three arithmetic helpers were
already typed, while `g17_026` is the program that moves here.

| program | hot function (own time) | own share | cum share | typed before | typed now | first reason before |
| --- | --- | ---: | ---: | --- | --- | --- |
| g17_010 | `numbers` | 0.2% (1 us) | 0.2% | no | no (follow-up) | `call to range(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one.` |
| g17_010 | `main` | 1.2% (4 us) | 10.9% | no | no (follow-up) | `builtins and codecs do not accept function values` (the `map(square, filter(is_odd, ...))` chain) |
| g17_010 | `is_odd` | 1.7% (5 us) | 1.7% | yes | yes | -- |
| g17_010 | `add` | 0.8% (3 us) | 0.8% | yes | yes | -- |
| g17_010 | `square` | 0.8% (2 us) | 0.8% | yes | yes | -- |
| t161 | `main` | 11.3% (135 us) | 30.8% | yes | yes | -- |
| t161 | `<lambda>` line 21 | 0.5% (6 us) | 0.5% | yes | yes | -- |
| t161 | `Row` (`__init__`/`__repr__` generated, 2.1% + 0.6%) | 0.1% | 0.1% | yes | yes | -- |
| t475 | `main` | 4.0% (31 us) | 6.8% | no | no (follow-up) | `str() of a list is not built; only str(<int>) and str(<float>) are` |
| t475 | `to_bytes_list` | 1.0% (8 us) | 1.4% | yes* | yes* | -- |
| g16_006 | `sliding_windows` | 2.2% (5 us) | 2.3% | no | no (follow-up) | `yield: this language has no generators.` |
| g16_006 | `main` | 2.0% (5 us) | 7.3% | no | no (follow-up) | same `yield` reason |
| g08_004 | `is_valid` | 30.5% (14.5 ms) | 60.5% | yes | yes | -- |
| g08_004 | `solve` | 22.8% (10.8 ms) | 97.9% | yes | yes | -- |
| g08_004 | `find_empty` | 14.6% (7.0 ms) | 14.6% | yes | yes | -- |
| g08_004 | `<genexpr>` line 28 | 14.4% (6.9 ms) | 14.4% | yes | yes | -- |
| g08_004 | `format_grid` | 0.1% (39 us) | 0.1% | yes | yes | -- |
| g08_004 | `main` | 0.0% (7 us) | 98.0% | yes | yes | -- |
| g17_026 | `distinct_vowel_count` | 6.5% (28 us) | 8.2% | no | **yes** | `` `{ch for ch in text.lower() if ch in V...` cannot be walked inline here; bind it to a name first `` |
| g17_026 | `main` | 2.2% (9 us) | 15.1% | no | **yes** | same set-comprehension reason (second: `'VOWELS' is a module-level name assigned to a Call`) |
| g17_026 | `<lambda>` line 14 | 1.0% (4 us) | 6.1% | no | **yes** | same set-comprehension reason (through `sort_by_distinct_vowels`) |
| g17_026 | `sort_by_distinct_vowels` | 0.3% (1 us) | 7.7% | no | **yes** | same set-comprehension reason |
| t188 | `parse_line` | 15.4% (115 us) | 28.8% | yes | yes | -- |
| t188 | `main` | 11.2% (84 us) | 48.8% | yes | yes | -- |
| g14_020 | `main` | 2.0% (23 us) | 5.2% | no | no (follow-up) | `hash() of a Point instance: instances as set elements or dict keys (__hash__) are not built on the typed path` |
| g14_020 | generated `__hash__`/`__eq__`/`__repr__` | 0.9% (7 us) | 0.9% | no | no (follow-up) | same instance-key reason |

\* `t475.to_bytes_list` has no strict blocker of its own and the typed emitter accepts it, but its
`list[int]` result is outside the hybrid ABI; the program's `import struct` and `main` keep the whole
program on the general path, so it is not accelerated.  The `lab/compare` comparison still shows the
program matching CPython under `build --cpython`, where it runs as plain CPython.

## Fixed here

1. **Module-level `frozenset` of str literals** (`python/pkg-v12/pyfunc.py`,
   `python/pkg-v12/pyc.py`).  `VOWELS: Final[frozenset[str]] = frozenset("aeiou")`
   (and the unannotated form, or `frozenset([...])` of str literals) was refused as "a module-level
   name assigned to a Call".  `_scan_module_consts` now stores the ordered, duplicate-free `list[str]`
   of its characters/items as a read-only module constant.  CPython's frozenset is unordered, so a
   read that could observe order is refused by name: every read must be `x in VOWELS`,
   `x not in VOWELS` or `len(VOWELS)`.  `pyc._rewrite_script` was also moving the assignment into the
   synthesised `main` (the old "read before it is assigned" bug); it now keeps exactly this shape at
   module scope.  Empty `frozenset("")`, one-character, duplicate and non-ASCII literals all work.
2. **`len()` of a set comprehension** (`python/pkg-v12/pyfunc.py`).  `len({e for v in xs if c})` was
   refused as "a set comprehension".  The `len` lowering now builds the existing eager list
   comprehension, creates a private `set[int]`/`set[str]` table, adds the list elements to it, and
   returns its length.  Duplicates collapse exactly as CPython's set does, and the result is an
   ordinary expression usable in `+=`, comparisons and calls.  Only int and str elements are built;
   a float set comprehension is still refused by name.

`g17_026` now builds wholly typed and matches CPython 3.12.  All ten `lab/compare` `main.ail` builds
were compiled with the base compiler and this tree: `program.c` is byte-identical for every one
(`berth_sim`, `chain_relax`, `echo_pack`, `ledger_bin`, `rail_transfer`, `scar_life`, `tally_lang`,
`term_rank`, `ticket_audit`, `tree_fold`).

## Probes

Every probe below was run with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`; "same" means both the
`g` (`AIL_UNIFIED_FORCE=1`) and `d` builds exited 0 and matched CPython stdout.

| probe | strict build | cmp.sh result |
| --- | --- | --- |
| `prog29_setcomp_len.py` | pass | same |
| `prog29_setcomp_routes.py` (argument, list item, attribute, dict value, `+=`, comparison, empty, duplicates, negative ints) | pass | same |
| `prog29_frozenset.py` (str and list literals, duplicates, `in`/`not in`/`len`) | pass | same |
| `prog29_frozenset_edges.py` (empty string, single, duplicate, non-ASCII) | pass | same |
| `prog29_frozenset_iter.py` (`for ch in VOWELS`) | refused by name: `'VOWELS' is a module-level frozenset; only \`x in VOWELS\` and \`len(VOWELS)\` are built on the typed path (iteration order of a frozenset is not preserved)` | strict refusal as named; without `--strict` both builds take the general path, whose frozenset iteration is the documented A2 insertion order (identical to the base commit) |
| `prog29_setcomp_float.py` (`len({x / 2 ...})`) | refused by name: `len() of a set comprehension with float elements is not built` | -- (expected refusal) |

## Follow-ups (left by name)

* `lab/corpus/programs/deepseek-v4.1-flash-free/t475.py`: needs typed `struct.pack` and
  `str(<list>)`.  Exact first messages:
  `str() of a list is not built; only str(<int>) and str(<float>) are` and
  `import of 'class' is not available: this compiler builds only the modules it models (math, sys, collections, itertools, functools, heapq, bisect, re, json).`
* `lab/census/programs/gdev/g16_006.py`: needs generators.  Exact first message:
  `yield: this language has no generators.`
* `lab/census/programs/gdev/g17_010.py`: `numbers` returns `range(...)` and `main` builds a
  `map`/`filter`/`reduce` pipeline.  Exact first messages:
  `call to range(); this compiler builds only the builtins it names, and refuses the rest by name rather than guessing at one.`
  and `builtins and codecs do not accept function values`.
* `lab/census/programs/gdev/g14_020.py`: needs dataclass instance `__hash__`/`__eq__` as dict keys and
  set elements.  Exact first message:
  `hash() of a Point instance: instances as set elements or dict keys (__hash__) are not built on the typed path`.
