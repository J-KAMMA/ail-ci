# prog17: typed reach of eight real programs

Method: each program ran under CPython 3.12 with `cProfile` (one entry of `main`, repeated enough
for the clock; the stdin programs on `lab/corpus/tasks/<t>/in2.txt`). The table lists the
program's **own** functions in own-time order until they hold 80% of the program's own function
time; library/builtin frames are excluded because the CPython hybrid leaves them in CPython.
Times are tiny on the published inputs, so the shares are what matter.

"Typed" is per function: `compile --syntax python --strict` must have no blocker naming that
function, so mixed mode can compile it while another function stays general. "First reason" is the
first strict refusal that names the function (or, for an unannotated `main`, the refusal that
stops the program). The hybrid ABI (int/bool/float/str results) is a separate filter: a `main`
that returns `None` still compiles typed but is not wrapped.

| Program | Hot functions (own time) | Typed before | First reason before | Typed after |
| --- | --- | --- | --- | --- |
| `gdev/g15_030.py` | `main` 52.4%, `parse_dates` 47.6% | **yes** | -- | yes, unchanged |
| `dev/t374.py` | `main` 92.9% | no | `a declared str-field records list requires matching rows` (line 11); after that, `enumerate() with a start inside a comprehension or a fold` | **yes**, whole program typed |
| `gdev/g21_016.py` | `main` 76.5%, `round_floats` 19.3% | no | `'value' is annotated Any, which this compiler has no rule for.` / `json.dumps of rounded: the type of this value is not known here ...` | no, follow-up |
| `gdev/g02_016.py` | `main` 55.2%, `int_to_roman` 38.2% | `int_to_roman` yes, `main` no | `.upper() on a str is not built.` -- the real gap is `for char in reversed(<str>)` (the method report hides the iterable refusal); with only the loop pre-binding fixed it names `'char' is an int and is being assigned a str` | **yes**, whole program typed |
| `gdev/g03_032.py` | `main` 34.7%, `estimate_se_of_median` 34.3%, `bootstrap_medians` 31.0% | `bootstrap_medians` yes | `statistics.stdev of floats needs CPython's exact fractions over floats, which is not built`; `main` also `statistics.fmean: the element type of the data is not known here` | no, follow-up |
| `corpus/.../t394.py` | `main` 100% | no | `Random.choices must take plain positional arguments, no defaults, *args or **kwargs` (the lowered `random.Random` class; `main` itself is not named) | no, follow-up |
| `gdev/g05_010.py` | `main` 73.1%, `tokenize` 14.4% | **yes** | -- | yes, unchanged |
| `dev/t100.py` | `main` 100% | **yes** | -- | yes, unchanged |

No program file was edited.

## Fixed in the compiler

1. **`for c in reversed(<str>)`** (`python/pkg-v12/pyfunc.py`). The `reversed()` loop branch knew
   `ail_slist` and numeric sequences but not a plain str, so `reversed(numeral.upper())` fell
   through to `_seq`, which refuses a str; the same loop target was also pre-bound `int` by
   `_promote_floats`'s default, so even the typed `reversed()` branch would have fought a stale
   INT. The branch now captures the source once and walks it backwards with `ail_str_prev_unit`
   (already in the runtime), binding a one-code-point str view exactly like the forward
   `for c in s:` door, and the pre-pass binds such a target STR. This is what makes `g02_016`
   fully typed (`main` + `roman_to_int`).
2. **`enumerate(..., start=...)` inside a comprehension/fold and a str-field records list built
   by a comprehension** (`python/pkg-v12/pyfunc.py`). t374's `main` failed twice: an annotated
   `list[tuple[int, str]]` assigned a comprehension was refused ("requires matching rows") and the
   pair plan refused any `enumerate` start inside a comprehension. `_pair_plan` now evaluates the
   start once (after the iterable, CPython's order) into a temp and adds it with the overflow-
   checked `ck_add`; `_listcomp_srows_into_temp` builds one `ail_srow` per element with the field
   kinds the destination annotation settled. This is what makes `t374` fully typed.
   A probe of the same path found a pre-existing gcc error in
   `sum(i for i, w in enumerate(<list[str]>))` (`int64_t v_w = ail_str`): `_inline_pair_fold`
   hardcoded `int64_t` for both pair bindings; it now uses the key/value kinds from `_pair_plan`.

## Follow-ups (large features, left as exact messages)

* `g21_016`: `Any` parameters/results and `dict[str, Any]` locals:
  `'value' is annotated Any, which this compiler has no rule for.` and
  `unsupported local annotation dict[str, Any].`
* `g03_032`: CPython-exact `statistics.stdev` over floats:
  `statistics.stdev of floats needs CPython's exact fractions over floats, which is not built; ...`
  (and `statistics.fmean: the element type of the data is not known here` in `main`, which follows
  from the same helper staying general).
* `t394`: the lowered `random.Random` class needs default parameters / `*args` / `**kwargs` and a
  shared `self.mt` alias:
  `Random.choices must take plain positional arguments, no defaults, *args or **kwargs`,
  `Random.randrange must take plain positional arguments, no defaults, *args or **kwargs`,
  `line 23: 'mt = self.mt' makes a second reference to the same container ...`.
