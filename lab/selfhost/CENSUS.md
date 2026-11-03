# Census of the compiler on the typed path

Measured 2026-11-03 on `origin/integ`.  This is measure-only: no compiler file was edited.

**Two numbers.**

- **21 of 3152 top-level functions (0.67%)** are accepted by the typed path
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
two at a time.  Two files recorded a 300 s timeout in that batched pass; both finish whole when given
a longer limit (`dtrt.py` takes about 150 s here), so each was rerun whole and the census uses the
whole-file verdict.  No file is recorded as `chunked`.

The chunk fallback (used only for a file that does not finish) now keeps every module-level
statement — imports, assignments, classes — as well as the top-level functions in the range.  The
earlier chunk text dropped module-level code, so a later module-level name made the slice reject
every function in it; that was an artefact of the slice, not a property of the functions.  A chunk
is labelled `file:start-end` and `chunked` is set in the JSON.

## Totals

| measure | count |
|---------|-------|
| files | 156 |
| top-level functions | 3152 |
| accepted | 21 |
| rejected | 3131 |
| share accepted | 0.67% |
| methods (in a class, no verdict) | 3538 |
| chunked files | 0 |

The 21 accepted functions live in six files, all in the prelude/helper tier:

| file | accepted / functions |
|------|----------------------|
| `prelude_ailarray.py` | 6 / 97 |
| `dtrt.py` | 5 / 167 |
| `hash_prelude.py` | 5 / 53 |
| `prelude_fraction.py` | 2 / 13 |
| `strt.py` | 2 / 53 |
| `prelude_array.py` | 1 / 4 |

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
| `dtrt.py` | 2040 | 167 | 5 | 3.0% |

Fourteen of the 15 largest files are at 0%; `dtrt.py` is 5/167 (3.0%).  The typed path analyses a
program whole, so one unsupported module-level statement (an `import ast`, an `os.environ.get()`, a
redefined import name) rejects every top-level function in most files; the reason recorded for each
function is that module-level note.  This is the dominant fact of the census, not a per-function
property.

## Top 10 rejection reasons

Counted over the 3131 rejected functions; the analysis run's temporary source name is
replaced by `<source>` and the `; built here: ...` tail of each note is dropped (the tool
normalises the name so a rerun is comparable).

| count | share of rejections | reason |
|-------|--------------------|--------|
| 940 | 30.0% | `write instead: drop the import and write what you need by hand with plain lists, dicts and loops` |
| 827 | 26.4% | `write instead: import it under another name (from ... import ast as other)` — a name is imported and also assigned/defined again |
| 497 | 15.9% | `not emitted by the typed path` (no mix unit and no explicit rejection) |
| 234 | 7.5% | `cannot tell the type of element 0 of this tuple` |
| 219 | 7.0% | `os.environ.get() with these arguments is not built` |
| 112 | 3.6% | `write instead: give each function its own name and call the right one` — duplicate function names |
| 52 | 1.7% | `re.compile()` used other than `NAME = re.compile(literal)` |
| 32 | 1.0% | `os.stat() with these arguments is not built` |
| 24 | 0.8% | `not in the subset: raising URLError` |
| 21 | 0.7% | `re.sub()`: the pattern has to be a string literal, not an expression |

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

All 30 are rejected, and none is one edit away.  Their files fall into two groups: the pyfunc.py
entries (25 of the 30) are refused at module level by an import name that is also defined again
(827 functions share that note), and the other five — `walk` in `fastwalk.py`, `_walk_own`,
`_lp_locals` and `_lp_eval` in `bigcap.py`, and `_own_nodes` in `boolkind.py` — are refused at
module level by an unsupported `os.environ.get()`.  Only `_mvk` takes a plain scalar (`kind: str`);
the other 29 take AST nodes or compiler objects (`node, ctx, ...`, `fn`, `stmts`).

The three closest are the smallest bodies whose own body is the least of the problem:
**`_mvk`** (3 lines, 0.186 s) takes one scalar `kind`, so it is the only one that fits the typed
path's scalar ABI as written — its remaining blockers are the pyfunc.py module note and the
module globals `MAPS`/`SETS` it reads plus its call to `_map_value_kind`;
**`_owned_method_name`** (3 lines, 0.164 s) and **`_is_owned_str_call`** (5 lines, 0.181 s) are
small, but they take `node`/`ctx` (and an ownership-name string), so they cannot be narrowed to a
scalar/bool ABI — they are candidates only if the rewrite starts from already-extracted scalars
rather than porting the predicate as-is.  A first rewrite step is therefore not "port one hot
function" but "give the typed path a home for scalar predicates like `_mvk` outside the file that
cannot be analysed whole."
