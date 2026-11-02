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
| `census/programs/gdev/g21_002.py` | `main` 12% (plus `json.encoder.iterencode` 29%, `json.encoder.encode` 19%, `print` 13%, `json.dumps` 4%) | no | The default build's first reason is `json.dumps(data)`: the type of this value is not known here (a `list[object]` has no declared kind).  `--strict` also reports `` `[None, True, False]` mixes bools and numbers; Python keeps each value's own type and a number would print as 1 / 0``, ranked by the code it blocks. |
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
  `srows` binds the index and every typed field (`_for_enumerate_srows`).  The layout has
  `AIL_SROW_MAXK` (4) slots, so a wider annotation is refused by name (``a records annotation
  with N fields; a str-field row holds at most 4 fields``) and the program takes the general
  path instead of silently dropping the extra fields.
* `python/pkg-v12/pyfunc.py`: `max`/`min` with a numeric `key=` lambda over a list of class
  instances lowers to one retained source walk (`_struct_key_fold`); it returns the first
  element with the winning key, and an empty source raises a catchable `ValueError` with
  CPython's `max()/min() iterable argument is empty` (previously an uncatchable `ail_die`).
  A non-numeric key (for example a tuple) keeps the existing general-path fallback.
* `python/pkg-v12/cruntime.py`: the `ail_srows` sort key check now refuses a NaN key with a named
  `ValueError` (the `ail_flist_sort`/KEYSORT rule), instead of returning a permutation CPython's
  Timsort does not reproduce.
* `python/pkg-v12/pyfunc.py`: `_bind_object_types` no longer types a name the function only reads
  and mutates as a local.  A module-level `gxs: list[Item] = []` appended or extended in `main`
  now refuses by name (`` `gxs` is a module-level value that this function changes; the typed
  path builds no mutable module-level container (the general path does) ``) and the function
  takes the general path.  Before this, the fold and the append both emitted `v_gxs` as if it were
  a local, and the default build failed at C compile time with `v_gxs undeclared` because the
  module body declares it in a different function.

## Follow-ups (not fixed here; exact first message)

* `g12_018` needs the stdlib `random.Random` methods with defaults: `Random.randrange must take
  plain positional arguments, no defaults, *args or **kwargs` (then `choices`, `triangular`,
  `gauss`, `normalvariate`, `expovariate`, and `self.mt` sharing).
* `g21_002` needs a heterogeneous `list[object]` and JSON of `None`/`bool`.  The default build's
  first reason is `json.dumps of data: the type of this value is not known here`; the second
  blocker (`--strict`) is `` `[None, True, False]` mixes bools and numbers; Python keeps each
  value's own type and a number would print as 1 / 0``.  A `list[object]` still has no kind for
  `json.dumps`.
* `g15_006` needs a union of scalar types and `None`: `only a class type can be None: write
  \`Node | None\``.
* `g16_034` needs generator/iterator values: `class list iteration needs one name` for the
  returned generator expression.

## Verification

* `AIL_CURRENT/test_ail_prog22.py` (registered through `AIL_CURRENT/tests.d/test_ail_prog22.txt`)
  builds t366, t347, t318 and g14 typed and compares stdout/exit with CPython; it also builds a
  str-field records program, a `max`/`min` key program (argument, list field, ties, negative and
  int64-edge keys), a caught empty `max`/`min` program (message and exit 0) and a five-field
  str-row program (general path, no truncation); the NaN sort refusal is checked too.  It also
  builds a module-level class list that is appended, and one that is appended and then passed to
  `max(key=)`, and asserts both take the general path and match CPython.
* Probes in `/tmp/probes` for both review defects: `p22_five.py`, `p22_six.py`,
  `p22_five_key.py`, `p22_five_str.py` (wide rows), `p22_catch_empty_max.py`,
  `p22_catch_empty_min.py`, `p22_empty_local_method.py`, `p22_empty_arg_method.py`,
  `p22_empty_attr_method.py`, `p22_empty_arg_attrkey.py`, `p22_empty_item.py`,
  `p22_empty_dict.py`, `p22_catch_silent.py`, `p22_maxmin_direct.py` (empty and non-empty
  `max`/`min`, both branches).  All match CPython on both `cmp.sh` builds.  In the probes re-run
  here, `p22_empty_dict.py` and `p22_maxmin_direct.py` take the general path (a dict value / list
  item source is not typed there yet); the rest are typed where the shape allows it.  A wider
  all-`str` annotation (five and six fields, annotated local or parameter, empty or literal
  initialised) is refused by name with ``a records annotation with N fields; a str-field row
  holds at most 4 fields`` and matches CPython on the general path.  A module-level annotated
  class list (append only, or append then `max(key=)`) is refused by the module-level reason above
  and matches CPython on the general path.
* All ten `lab/compare` tasks (`src/<task>/main.ail`) generate byte-identical C against the
  pre-change tree (`cmp dnew/program.c dold/program.c` for each).
