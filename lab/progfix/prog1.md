# prog1: hot functions of eight real programs

Date: 2026-11-01.  CPython 3.12.3, gcc on the GitHub runner.  The typed path is the
default `ail_chatgpt.py compile`; a program is "typed" when stderr has no
`built on the general path` note.  Programs were not edited.

## Profile

The supplied inputs and the four self-contained programs finish in well under a
millisecond, so cProfile was repeated with the same input and a fresh `__main__`
globals dictionary; the table reports own time among that program's functions.
This keeps the ranking meaningful without changing the source.

| program | CPython input | reps | functions by own time (share) |
|---|---|---:|---|
| `t370.py` | `in2.txt` | 300 | `lambda` 49.2%, `main` 42.5% (91.7% together) |
| `t414.py` | `in2.txt` | 200 | `execute` 57.4%, `main` 40.8% (98.1% together) |
| `g06_012.py` | none | 500 | `main` 37.8%, `multiples_of` 30.0% (`<module>` 32.2%) |
| `g14_022.py` | none | 300 | `main` 45.3%, `format_cents` 25.4% (`<module>` 12.2%) |
| `g17_004.py` | none | 300 | `main` 65.3%, `scale` 18.8% |
| `t308.py` | `in2.txt` | 300 | `longest_common_substring` 97.4% |
| `t459.py` | `in2.txt` | 300 | `main` 97.0% |
| `g06_032.py` | none | 300 | `union` 24.8%, `find` 15.6%, `add` 15.1%, `compute_equivalence_classes` 14.7%, `main` 12.7% |

Reproduce with `/tmp/prof/prof2.py SRC INPUT REPS` (the harness compiles the file
once and executes it `REPS` times with stdout redirected).

## Result per hot function

| program | hot function | typed? | first refusal before | change / remaining |
|---|---|---|---|---|
| `t370` | `main` (and its lambda) | yes | none; whole program was already typed | none needed |
| `t414` | `execute`, `main` | no | `list[str] parameters are read-only; this method is not supported` | follow-up: a mutable `list[str]` parameter needs an ownership/write-back ABI |
| `g06_012` | `multiples_of` | yes | `set[int] is built from a list of int`, line 7 | `_set_literal` accepts a direct `range(...)` source; `main` became typed with it |
| `g14_022` | `format_cents` | yes (extracted actual function) | `tuple assignment from Call; ... literal tuple ...` for `dollars, remainder = divmod(...)` | tuple assignment now builds `divmod` from `pydiv`/`pymod` (or `ail_ffloormod` for floats) |
| `g14_022` | `main` | no | `itertools.groupby: key has to be a pure function ...`, line 28 | follow-up: `groupby` with a non-lambda callback; the whole program also notes `operator.attrgetter` and the general path cannot build it either |
| `g17_004` | `scale` | yes (already typed/accelerated) | none | none needed |
| `g17_004` | `main` | no | `functools.partial used here is not built ...`, line 13 | follow-up: `functools.partial` as a value/callback |
| `t308` | `longest_common_substring` | yes | `enumerate() with a start over something other than a named list of int, float or str` | plain `str` sources now walk one code point at a time and count code points, not bytes; a rebound index does not affect the walk |
| `t459` | `main` | yes | `'nums' is declared list; assigning int is unsupported.` | `_etype` types `xs[a:b]` of a named `LIST`/`FLIST` as that list, not `INT`; slice stores no longer look like int stores |
| `g06_032` | `union`, `find`, `add`, `compute_equivalence_classes`, `main` | no | `list[list[T]]: a nested list holds rows of int, float, str or a class; keep a list of class instances for anything else` | follow-up: generic class methods and nested-list storage |

The four follow-ups are named in the final census (not silent general-path
fallbacks).  `t414` and `g06_032` are the two programs whose hot functions remain
untyped; `g14_022.main` and `g17_004.main` also remain general while their helper
functions are typed.

## Compiler changes

- `AIL_CURRENT/python/pkg-v12/pyfunc.py:1715`: `_etype` for `xs[a:b]` of a named
  `LIST`/`FLIST` returns the list kind (excluding stride/row/handle/byte/str-list
  names).
- `AIL_CURRENT/python/pkg-v12/pyfunc.py:12538`: `_set_literal` treats a direct
  `range(...)` call as a walkable int source.
- `AIL_CURRENT/python/pkg-v12/pyfunc.py:26031`: `_for_enumerate_start` has a plain
  `str` branch; source then start are evaluated once, and the index is
  `ck_add(start, code_point_counter)`.
- `AIL_CURRENT/python/pkg-v12/pyfunc.py:20781`: tuple assignment recognises
  `q, r = divmod(a, b)`, evaluates both operands once into private temps, and uses
  `pydiv`/`pymod` for ints or `ail_ffloormod(..., 0/1)` for floats.

## Verification

- Typed census on the final tree: `t370`, `g06_012`, `t308`, `t459` are typed;
  `t414`, `g14_022`, `g17_004`, `g06_032` stop at the named refusals above.
- Whole-program outputs equal CPython for `t370`, `g06_012`, `t308`, `t459`;
  extracted actual functions equal CPython for `g14_022.format_cents` and
  `g17_004.scale`.
- Boundary probes (`/tmp/probes/p_slice_edges.py`, `p_setrange_edges.py`,
  `p_enum_str_edges.py`, `p_divmod_edges.py`, `p_divmod_zero.py`,
  `p_g14_format.py`) are typed and byte-equal on stdout via `~/tools/cmp.sh`;
  `divmod(1, 0)` stops loudly on both paths.
- Generated C for the buildable `lab/compare` tasks is byte-identical to the
  pre-change tree (`berth_sim`, `chain_relax`, `echo_pack`, `ledger_bin`,
  `rail_transfer`, `term_rank`, `ticket_audit`).  `scar_life`, `tally_lang` and
  `tree_fold` produce no C in either tree; their pre-existing refusals are
  unchanged.
