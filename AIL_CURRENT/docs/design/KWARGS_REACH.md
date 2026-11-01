# Keyword-argument reach (2026-11-01)

Where keyword arguments stand in the Python-syntax front end.  A probe is `OK` when the default
build (typed, with a fallback to the general path) prints exactly what CPython 3.12 prints and
exits the same way; `REFUSED` means the compiler names the gap and builds nothing.  The
"before" column is the tree at the start of this cut; "after" is the same probe with the fix
below.  The 25 probes live in `/tmp/kwmeasure/p/` and are run by `/tmp/kwmeasure/measure.sh`.

| # | probe | shape | before | after | why |
|---|-------|-------|--------|-------|-----|
| 01 | `p01_basic` | `f(b=2, a=1)` | TYPED | TYPED | |
| 02 | `p02_defaults` | positional defaults | TYPED | TYPED | |
| 03 | `p03_default_expr` | default is an expression | GENERAL | GENERAL | |
| 04 | `p04_default_once_list` | mutable default evaluated once | GENERAL | GENERAL | |
| 05 | `p05_default_once_time` | default evaluated once | GENERAL | GENERAL | |
| 06 | `p06_kwonly` | required keyword-only | REFUSED | GENERAL | fixed here |
| 07 | `p07_kwonly_star` | `def f(*, x)` | REFUSED | GENERAL | fixed here |
| 08 | `p08_varargs` | `*args` | GENERAL | GENERAL | |
| 09 | `p09_varargs_after` | parameters after `*args` | GENERAL | GENERAL | |
| 10 | `p10_kwargs` | `**kwargs` | GENERAL | GENERAL | |
| 11 | `p11_kwargs_mixed` | `*args, **kwargs` | GENERAL | GENERAL | |
| 12 | `p12_star_unpack_call` | `f(*xs)` | GENERAL | GENERAL | |
| 13 | `p13_dict_unpack_call` | `f(**d)` | REFUSED | GENERAL | fixed here |
| 14 | `p14_dict_unpack_mixed` | `f(1, **d)` | REFUSED | GENERAL | fixed here |
| 15 | `p15_method` | keywords to a method | GENERAL | GENERAL | |
| 16 | `p16_nested_def` | keywords to a nested `def` | GENERAL | GENERAL | |
| 17 | `p17_lambda` | lambda used as a value | REFUSED | REFUSED | not a keyword gap |
| 18 | `p18_posonly` | positional-only `/` | GENERAL | GENERAL | |
| 19 | `p19_unexpected_kw` | unknown keyword, caught | REFUSED | REFUSED | static binding refusal |
| 20 | `p20_duplicate` | duplicate keyword, caught | REFUSED | REFUSED | static binding refusal |
| 21 | `p21_missing` | missing argument, caught | REFUSED | REFUSED | static binding refusal |
| 22 | `p22_extra_pos` | too many positional, caught | REFUSED | REFUSED | static binding refusal |
| 23 | `p23_dict_nonstr` | `f(**{1: 2})`, caught | REFUSED | GENERAL | fixed here |
| 24 | `p24_kwargs_forward` | `inner(**kw)` | REFUSED | GENERAL | fixed here |
| 25 | `p25_default_container` | default is a container | GENERAL | GENERAL | |

Before: 14 OK / 11 refused.  After: 20 OK / 5 refused.

## The top refusal

`a **kwargs call argument` was the largest single refusal in the set (p13, p14, p23, p24; the
task brief also names "calls passing **dict").  The general path saw `kw.arg is None` in
`expr_Call` and refused before binding anything.

## What changed

Only the general path (`python/pkg-v12/pyboxed2.py`) changed; the typed path still refuses
`**` (`pyfunc.py`), so the default build falls back to the general path for these programs.

* `expr_Call` detects a `**` keyword.  A call that also has `*args` is refused by name; a call
  through a name goes to `_call_name(..., kwseq=...)`, a call through `obj.method` goes to the
  new `_call_attribute_starstar`, and anything else is refused by name.
* `_call_name`/`_call_user_function`/`_call_class`/`_call_exc_class`/`_bind_args` take an
  optional `kwseq` (the keywords in source order, with `None` for each `**`).  Without it the
  old code path is unchanged.
* `_bind_args_dynamic` builds a runtime dict in source order, expands each `**` mapping into it
  (dict-tag check, string-key check, duplicate check), then binds positional parameters,
  defaults, required keyword-only parameters, `*args` and `**kwargs` with CPython's rules.
  Missing, unexpected, duplicate, non-string, non-mapping and surplus-positional cases raise
  `TypeError` at the call, so a `try/except TypeError` sees them.
* Required keyword-only parameters are now registered (the old check required a default for
  every keyword-only parameter).  A static call that omits one is still refused by name; a
  `**` call raises `TypeError` at run time.

Deliberately still refused by name: `**` to a builtin or to a function value, `**` to a
property / setter / virtual dispatch (a subclass may override it), and a call with both
`*args` and `**`.

## Boundaries checked

Direct, literal, mixed positional, multiple `**`, keyword before/after `**`, empty mapping,
forwarding through `**kwargs`, values read from a parameter / list item / attribute / dict
item, aliasing, defaults and mutable defaults, required keyword-only, methods and
constructors, evaluation order, duplicate across mappings and against an explicit keyword,
non-string key, non-mapping, positional-only passed by name, duplicate positional/keyword,
missing, unknown and surplus positional.  Each matches CPython on stdout and exit code.

## No change for programs without `**`

The new branch is taken only when `kw.arg is None` is present.  For the ten `lab/compare`
tasks the generated C is byte-identical before and after this change, for both the `.py` and
`.ail` sources (the three `.py` sources that do not build refuse identically in both trees).
