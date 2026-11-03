# Census of the compiler on the typed path

Measured 2026-11-03 on `origin/integ`.  This is measure-only: no compiler file was edited.

**Two numbers.**

- **16 of 3152 top-level functions (0.51%)** are accepted by the typed path
  (`ail_cpython_hybrid._analysis` + `_select`) when each file is analysed whole.
- **0 of 30** of the hottest compiler functions (top 30 by summed `tottime` over three cold builds)
  are accepted.

## What was measured

The unit is one top-level `def` (the unit of the CPython hybrid, `docs/design/CPYTHON_HYBRID.md` section 1).
Methods are counted separately and get no verdict.  Every file was read whole with
`ail_cpython_hybrid._analysis` and `_select` — the hybrid's own selection, with no extension built.
The census is `lab/selfhost/census.json` (`schema: ail.selfhost_census/1`).

Scope: `AIL_CURRENT/python/pkg-v12/*.py` (153 files), `AIL_CURRENT/ail_chatgpt.py`,
`AIL_CURRENT/ail_syntax.py` and `AIL_CURRENT/ail_modules.py` — 156 files, 204816 lines.

Each file ran in its own process under a 1.5 GB address-space limit (`RLIMIT_AS`) with a 300 s timeout,
two at a time.  Two files did not finish whole and were classified as one line-range chunk each: the
file's leading module preamble plus the top-level functions in the range.

| file | whole file | chunk | why |
|------|-----------|-------|-----|
| `dtrt.py` | timed out at 300 s | lines 59-2040 | 2,040 lines, 167 functions |
| `strt.py` | timed out at 300 s | lines 13-753 | 753 lines, 53 functions |

A chunk drops module-level statements after the first `def`, so a verdict from these two files is
weaker evidence than the others; both are recorded as `chunked` in the JSON.  No file errored.

## Totals

| measure | count |
|---------|-------|
| files | 156 |
| top-level functions | 3152 |
| accepted | 16 |
| rejected | 3136 |
| share accepted | 0.51% |
| methods (in a class, no verdict) | 3538 |
| chunked files | 2 |

The 16 accepted functions live in five files, all in the prelude/helper tier:

| file | accepted / functions |
|------|----------------------|
| `hash_prelude.py` | 5 / 53 |
| `prelude_ailarray.py` | 6 / 97 |
| `prelude_array.py` | 1 / 4 |
| `prelude_fraction.py` | 2 / 13 |
| `strt.py` (chunked) | 2 / 53 |

## Share accepted in the 15 largest files

| file | lines | top-level functions | accepted | share |
|------|-------|---------------------|----------|-------|
| `pyfunc.py` | 41059 | 828 | 0 | 0.0% |
| `cruntime.py` | 30939 | 21 | 0 | 0.0% |
| `pyboxed2.py` | 13849 | 81 | 0 | 0.0% |
| `ail_chatgpt.py` | 6652 | 166 | 0 | 0.0% |
| `ail_syntax.py` | 4596 | 44 | 0 | 0.0% |
| `unified.py` | 3381 | 94 | 0 | 0.0% |
| `collib.py` | 3225 | 21 | 0 | 0.0% |
| `ail_modules.py` | 3124 | 16 | 0 | 0.0% |
| `safetyrt.py` | 2989 | 19 | 0 | 0.0% |
| `pyboxed.py` | 2940 | 5 | 0 | 0.0% |
| `prelude_genlib.py` | 2886 | 114 | 0 | 0.0% |
| `dunders.py` | 2794 | 23 | 0 | 0.0% |
| `prelude_decimal.py` | 2545 | 85 | 0 | 0.0% |
| `pyc.py` | 2085 | 57 | 0 | 0.0% |
| `dtrt.py` | 2040 | 167 | 0 | 0.0% |

Every one of the 15 largest files is at 0%.  The typed path analyses a program whole, so one
unsupported module-level statement (an `import ast`, an `os.environ.get()`, a redefined import name)
rejects every top-level function in the file; the reason recorded for each function is that
module-level note.  This is the dominant fact of the census, not a per-function property.

## Top 10 rejection reasons

Counted over the 3136 rejected functions; the analysis run's temporary source name is
replaced by `<source>` (the tool normalises it so a rerun is comparable).

| count | share of rejections | reason |
|-------|--------------------|--------|
| 940 | 30.0% | `write instead: drop the import and write what you need by hand with plain lists, dicts and loops` |
| 828 | 26.4% | `write instead: import it under another name (from ... import ast as other)` — a name is imported and also assigned/defined again |
| 347 | 11.1% | `not emitted by the typed path` (no mix unit and no explicit rejection) |
| 234 | 7.5% | `cannot tell the type of element 0 of this tuple` |
| 219 | 7.0% | `os.environ.get() with these arguments is not built` |
| 167 | 5.3% | `not in the subset: the name 'AilStrp' is not a known function/class/builtin` |
| 114 | 3.6% | `write instead: give each function its own name and call the right one` — duplicate function names |
| 52 | 1.7% | `re.compile()` used other than `NAME = re.compile(literal)` |
| 32 | 1.0% | `os.stat() with these arguments is not built` |
| 24 | 0.8% | `not in the subset: raising URLError` |

The top two reasons alone are 56% of all rejections, and both are module-level: the typed path
accepted the program's shape and then refused one import binding for the whole file.

## The 30 hottest compiler functions

Three cold builds (`lab/compare/src/{chain_relax,tree_fold,tally_lang}/typed.py`), each with a fresh
`AIL_CACHE` and `TMPDIR` and `AIL_SERVER=0`.  Both the CLI (`python3 -m cProfile ail_chatgpt.py compile …`)
and its `pyc.py` child (`python3 -m cProfile pyc.py --file …/combined.ail …/program --strict`) were
profiled; `tottime` is summed over parent and child and over the three builds.  Generated by
`lab/selfhost/hot_functions.py` into `lab/selfhost/hot.json`.

The child command line, printed once from a scratch copy of `ail_chatgpt.py` (not committed):

```
/usr/bin/python3 AIL_CURRENT/python/pkg-v12/pyc.py --file <tmp>/ailc-*/combined.ail \
    <tmp>/ailc-*/program --strict
```

| # | function | file | tottime s | verdict | first reason |
|---|----------|------|-----------|---------|--------------|
| 1 | `walk` | `fastwalk.py` | 4.529 | reject | os.environ.get() with these arguments is not built |
| 2 | `_etype` | `pyfunc.py` | 2.386 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 3 | `_is_str_expr` | `pyfunc.py` | 1.305 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 4 | `_promote_floats` | `pyfunc.py` | 0.439 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 5 | `_bind_object_types` | `pyfunc.py` | 0.390 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 6 | `_mark_str_containers` | `pyfunc.py` | 0.348 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 7 | `_is_slist_expr` | `pyfunc.py` | 0.336 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 8 | `_walk_own` | `bigcap.py` | 0.299 | reject | os.environ.get() with these arguments is not built |
| 9 | `_is_map_value` | `pyfunc.py` | 0.284 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 10 | `_is_bytes_expr` | `pyfunc.py` | 0.258 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 11 | `_mark_tuple_lists` | `pyfunc.py` | 0.254 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 12 | `_is_owned_bytes_call` | `pyfunc.py` | 0.230 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 13 | `_mark_bytes_containers` | `pyfunc.py` | 0.228 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 14 | `_param_kinds` | `pyfunc.py` | 0.225 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 15 | `_own_nodes` | `boolkind.py` | 0.220 | reject | os.environ.get() with these arguments is not built |
| 16 | `_map_value_kind` | `pyfunc.py` | 0.203 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 17 | `_mvk` | `pyfunc.py` | 0.186 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 18 | `_is_owned_str_call` | `pyfunc.py` | 0.181 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 19 | `_owned_method_name` | `pyfunc.py` | 0.164 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 20 | `_fn_kind` | `pyfunc.py` | 0.162 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 21 | `_lp_locals` | `bigcap.py` | 0.134 | reject | os.environ.get() with these arguments is not built |
| 22 | `_map_kind` | `pyfunc.py` | 0.130 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 23 | `_is_map_snapshot` | `pyfunc.py` | 0.117 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 24 | `_dynamic_result` | `pyfunc.py` | 0.113 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 25 | `_lp_eval` | `bigcap.py` | 0.112 | reject | os.environ.get() with these arguments is not built |
| 26 | `_record_walk` | `pyfunc.py` | 0.112 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 27 | `_is_utf8_codec_call` | `pyfunc.py` | 0.110 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 28 | `_numeric_field_kind` | `pyfunc.py` | 0.110 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 29 | `_class_method_name` | `pyfunc.py` | 0.107 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 30 | `_mark_bytes_rows` | `pyfunc.py` | 0.105 | reject | write instead: import it under another name (`from ... import ast as other`) |

Three hotter names are not census units and are not ranked: the nested helpers `wrapper` (0.947 s) and
`_walk_uncached` (0.738 s) inside `_query_memo`, and the method `Ctx.type_of` (0.195 s).

## Closest to accepted

All 30 are rejected, and none is one edit away: each takes AST nodes or compiler objects
(`node, ctx`, `fn`, `stmts`), which the typed path cannot pass, and every body has a local refusal
from `_unsafe_body`.  The three that are closest are the smallest bodies whose only local refusal is
a call to another front-end predicate, so the body itself needs no new language feature —
**`_mvk`** (3 lines, 0.186 s), **`_owned_method_name`** (3 lines, 0.164 s) and
**`_is_owned_str_call`** (5 lines, 0.181 s).  Their shared upstream blocker is the whole-file refusal
of `pyfunc.py` (an imported name that is also defined again, 828 functions share it); after that,
each needs its parameter types narrowed to a scalar/bool ABI and its one call either inlined or
cloned first.  A first rewrite step is therefore not "port one hot function" but "give the typed
path a home for these three scalar predicates, outside the file that cannot be analysed whole."
