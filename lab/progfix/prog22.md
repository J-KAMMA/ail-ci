# prog22 typed reach: eight real programs (2026-11-02)

Hot functions from `python3 -m cProfile -s tottime`.  One run of these programs is shorter than
the profiler's resolution, so each module was imported once and its `main` was then called many
times (2000-3000; 500 for the two input-heavy ones) with stdout discarded and stdin reset.  The
shares are `tottime` (own time) of that profile; `write` is the profiler's own sink and is left
out of the table.  The listed program functions plus the C/CPython builtins they call make up the
rest of the 80% cutoff.

"Typed" is the default `compile --syntax python` path (the note "built on the general path" means
it was not taken).  A program that builds typed compiles every hot function in it; a function
whose program is still general is not accelerated by the CPython hybrid either.

| Program | Hot function(s) (own time) | Typed? | First reason / action |
| --- | --- | --- | --- |
| `census/programs/dev/t366.py` | `main` 39% (plus `print` 21%, `list.sort` 8%) | **yes** | Fixed: a local `list[tuple[str, float, str]]` annotation was `a records annotation whose field type is 'str'; a row holds int64 or float fields only`.  It now names the `ail_srows` shape `_mark_srow_lists` already built from `.append()`, and `enumerate(records, start=1)` walks it. |
| `census/programs/gdev/g12_018.py` | `main` 26%, `review` 5%, `in_transit` 4%, `receive` 4%, `fulfill` 4% (plus `print` 12%, `Random.randrange` 7%, `_randbelow_with_getrandbits` 4%, `sum` 4%, `len` 3%, `Random.seed` 3%) | no | `Random.randrange must take plain positional arguments, no defaults, *args or **kwargs` at line 138 of the lowered `random` module.  The other `Random` methods (`choices`, `triangular`, `gauss`, `normalvariate`, `expovariate`) and the `self.mt` alias follow. |
| `census/programs/gdev/g21_002.py` | `main` 12% (plus `json.encoder.iterencode` 29%, `json.encoder.encode` 19%, `print` 13%, `json.dumps` 4%) | no | `[None, True, False]` mixes bools and numbers; Python keeps each value's own type and a number would print as 1 / 0.  Even with that, `json.dumps(data)` of a `list[object]` has no declared kind. |
| `census/programs/gdev/g15_006.py` | `main` 31%, `validate_age` 25% (plus `print` 17%, `isinstance` 4%, `len` 3%) | no | `only a class type can be None: write \`Node \| None\`` for the `Union[int, float, str, None]` parameter.  The mixed sample list is the second blocker. |
| `corpus/programs/deepseek-v4.1-flash-free/t347.py` | `sieve` 48%, `<genexpr>` 38% (the `sum(1 for ...)` count) | **yes** | Already typed; kept as a regression. |
| `census/programs/gdev/g16_034.py` | `main` 21%, `<genexpr>` 17% (plus `print` 28%, `len` 12%) | no | `class list iteration needs one name` at the `return ( ... for position, word in enumerate(text.split()) ... )` generator expression.  A generator/iterator result is not a typed value yet. |
| `census/programs/gdev/g14_034.py` | `main` 26%, `average` 16%, `letter_grade` 6%, `build_students` 5% (plus `print` 13%, `sum` 9%, `len` 7%) | **yes** | Fixed: `max(students, key=lambda s: s.average())` was `max() does not accept a class; read a numeric field`.  A numeric `key=` lambda over a list of class instances is now folded directly (same first-max tie rule as CPython). |
| `census/programs/dev/t318.py` | `main` 43%, `add` 22%, `query` 15%, `rank` 8% | **yes** | Already typed; kept as a regression. |

Typed after this job: t366, t347, t318 and g14 (4/8).  Still general: g12_018, g21_002,
g15_006 and g16_034.

## Compiler changes

* `python/pkg-v12/pyfunc.py`: a local `list[tuple[...]]` annotation with a `str` field now returns
  the `srows` kind (`_local_srow_annotations`, `_check_local_assignment`), so an annotated
  str-field records list does not have to be inferred from `.append()` alone.  The `srows`
  `append` path is not confused with the scalar-list path, and `enumerate(rows, start)` over
  `srows` binds the index and every typed field (`_for_enumerate_srows`).
* `python/pkg-v12/pyfunc.py`: `max`/`min` with a numeric `key=` lambda over a list of class
  instances lowers to one retained source walk (`_struct_key_fold`); it returns the first
  element with the winning key, and an empty source stops with CPython's
  `max()/min() arg is an empty sequence`.  A non-numeric key (for example a tuple) keeps the
  existing general-path fallback.
* `python/pkg-v12/cruntime.py`: the `ail_srows` sort key check now refuses a NaN key with a named
  `ValueError` (the `ail_flist_sort`/KEYSORT rule), instead of returning a permutation CPython's
  Timsort does not reproduce.

## Follow-ups (not fixed here; exact first message)

* `g12_018` needs the stdlib `random.Random` methods with defaults: `Random.randrange must take
  plain positional arguments, no defaults, *args or **kwargs` (then `choices`, `triangular`,
  `gauss`, `normalvariate`, `expovariate`, and `self.mt` sharing).
* `g21_002` needs a heterogeneous `list[object]` and JSON of `None`/`bool`:
  `` `[None, True, False]` mixes bools and numbers; Python keeps each value's own type and a
  number would print as 1 / 0.``  A `list[object]` still has no kind for `json.dumps`.
* `g15_006` needs a union of scalar types and `None`: `only a class type can be None: write
  \`Node | None\``.
* `g16_034` needs generator/iterator values: `class list iteration needs one name` for the
  returned generator expression.

## Verification

* `AIL_CURRENT/test_ail_prog22.py` (registered through `AIL_CURRENT/tests.d/test_ail_prog22.txt`)
  builds t366, t347, t318 and g14 typed and compares stdout/exit with CPython; it also builds a
  str-field records program, a `max`/`min` key program (argument, list field, ties, negative and
  int64-edge keys) and an empty-`max` program, and checks the NaN sort refusal.
* Probes in `/tmp/probes`: `p22_srows.py`, `p22_maxkey.py`, `p22_maxkey_empty.py`,
  `p22_maxkey_tuple.py`; all match CPython on both `cmp.sh` builds (the tuple key takes the
  general path and matches).
* All ten `lab/compare` tasks (`src/<task>/main.ail`) generate byte-identical C against the
  pre-change tree (`cmp dnew/program.c dold/program.c` for each).
