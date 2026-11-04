# Census of the compiler on the typed path

Measured 2026-11-04 on this branch's base (`staging:integ`).  This is measure-only: no compiler file
was edited.  The earlier measurement on the 2026-11-03 base gave the same accepted count, 21 of 3152,
so the share is unchanged to two decimals; the current base has seven more top-level functions.

**Two numbers.**

- **21 of 3159 top-level functions (0.66%)** are accepted by the typed path
  (`ail_cpython_hybrid._analysis` + `_select`) when each file is analysed whole.
- **0 of 30** of the hottest compiler functions (top 30 by summed `tottime` over three cold builds)
  are accepted.

## What was measured

The unit is one top-level `def` (the unit of the CPython hybrid, `docs/design/CPYTHON_HYBRID.md` section 1).
Methods are counted separately and get no verdict.  Every file was read whole with
`ail_cpython_hybrid._analysis` and `_select` — the hybrid's own selection, with no extension built.
The census is `lab/selfhost/census.json` (`schema: ail.selfhost_census/1`).

Scope: `AIL_CURRENT/python/pkg-v12/*.py` (153 files), `AIL_CURRENT/ail_chatgpt.py`,
`AIL_CURRENT/ail_syntax.py` and `AIL_CURRENT/ail_modules.py` — 156 files, 205201 lines.

Each file ran in its own process under a 1.5 GB address-space limit (`RLIMIT_AS`), two at a time.
The first batched pass used a 300 s timeout; two files hit it, and both finish whole with a longer
limit (`dtrt.py` takes about 230 s here), so the final census was produced by one whole-file pass
with a 600 s timeout (`timeout_seconds` in the JSON).  No file is recorded as `chunked`.

The chunk fallback (used only for a file that does not finish) now keeps every module-level
statement — imports, assignments, classes — as well as the top-level functions in the range.  The
earlier chunk text dropped module-level code, so a later module-level name made the slice reject
every function in it; that was an artefact of the slice, not a property of the functions.  A chunk
is labelled `file:start-end` and `chunked` is set in the JSON.

## Totals

| measure | count |
|---------|-------|
| files | 156 |
| top-level functions | 3159 |
| accepted | 21 |
| rejected | 3138 |
| share accepted | 0.66% |
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
| `pyfunc.py` | 41212 | 829 | 0 | 0.0% |
| `cruntime.py` | 30991 | 21 | 0 | 0.0% |
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

Counted over the 3138 rejected functions; the analysis run's temporary source name is
replaced by `<source>` and the `; built here: ...` tail of each note is dropped (the tool
normalises the name so a rerun is comparable).

| count | share of rejections | reason |
|-------|--------------------|--------|
| 940 | 30.0% | `write instead: drop the import and write what you need by hand with plain lists, dicts and loops` |
| 828 | 26.4% | `write instead: import it under another name (from ... import ast as other)` — a name is imported and also assigned/defined again |
| 497 | 15.8% | `not emitted by the typed path` (no mix unit and no explicit rejection) |
| 234 | 7.5% | `cannot tell the type of element 0 of this tuple` |
| 220 | 7.0% | `os.environ.get() with these arguments is not built` |
| 112 | 3.6% | `write instead: give each function its own name and call the right one` — duplicate function names |
| 57 | 1.8% | `re.compile()` used other than `NAME = re.compile(literal)` |
| 32 | 1.0% | `os.stat() with these arguments is not built` |
| 24 | 0.8% | `not in the subset: raising URLError` |
| 21 | 0.7% | `re.sub()`: the pattern has to be a string literal, not an expression |

The top two reasons alone are 56% of all rejections, and both are module-level: the typed path
accepted the program's shape and then refused one import binding for the whole file.

## The 30 hottest compiler functions

Three cold builds (`lab/compare/src/{chain_relax,tree_fold,tally_lang}/typed.py`), each with a fresh
`AIL_CACHE` and `TMPDIR` and `AIL_SERVER=0`.  Both the CLI (`python3 -m cProfile ail_chatgpt.py compile …`)
and its `pyc.py` child (profiled in-process through `sitecustomize`) were profiled; `tottime` is
summed over parent and child and over the three builds.  Generated by
`lab/selfhost/hot_functions.py` into `lab/selfhost/hot.json`.

The child command line, printed once from a scratch copy of `ail_chatgpt.py` (not committed):

```
/usr/bin/python3 AIL_CURRENT/python/pkg-v12/pyc.py --file <tmp>/ailc-*/combined.ail \
    <tmp>/ailc-*/program --strict
```

| # | function | file | tottime s | verdict | first reason |
|---|----------|------|-----------|---------|--------------|
| 1 | `walk` | `fastwalk.py` | 2.264 | reject | os.environ.get() with these arguments is not built |
| 2 | `_etype` | `pyfunc.py` | 1.101 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 3 | `_is_str_expr` | `pyfunc.py` | 0.591 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 4 | `_shallow_walk` | `ail_chatgpt.py` | 0.241 | reject | write instead: drop the import and write what you need by hand with plain lists, dicts and loops |
| 5 | `_promote_floats` | `pyfunc.py` | 0.190 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 6 | `_binding_counts` | `ail_chatgpt.py` | 0.187 | reject | write instead: drop the import and write what you need by hand with plain lists, dicts and loops |
| 7 | `_bind_object_types` | `pyfunc.py` | 0.175 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 8 | `_is_slist_expr` | `pyfunc.py` | 0.163 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 9 | `_mark_str_containers` | `pyfunc.py` | 0.157 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 10 | `_walk_own` | `bigcap.py` | 0.146 | reject | os.environ.get() with these arguments is not built |
| 11 | `_walk_own_scope` | `ail_chatgpt.py` | 0.142 | reject | write instead: drop the import and write what you need by hand with plain lists, dicts and loops |
| 12 | `_is_map_value` | `pyfunc.py` | 0.136 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 13 | `_param_kinds` | `pyfunc.py` | 0.116 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 14 | `_mark_tuple_lists` | `pyfunc.py` | 0.110 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 15 | `_is_owned_bytes_call` | `pyfunc.py` | 0.107 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 16 | `_escaped_constant_statements` | `ail_chatgpt.py` | 0.107 | reject | write instead: drop the import and write what you need by hand with plain lists, dicts and loops |
| 17 | `_own_nodes` | `boolkind.py` | 0.105 | reject | os.environ.get() with these arguments is not built |
| 18 | `_is_bytes_expr` | `pyfunc.py` | 0.098 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 19 | `_mark_bytes_containers` | `pyfunc.py` | 0.093 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 20 | `_map_value_kind` | `pyfunc.py` | 0.088 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 21 | `_mvk` | `pyfunc.py` | 0.083 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 22 | `_is_owned_str_call` | `pyfunc.py` | 0.083 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 23 | `_owned_method_name` | `pyfunc.py` | 0.078 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 24 | `_fn_kind` | `pyfunc.py` | 0.074 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 25 | `_map_kind` | `pyfunc.py` | 0.068 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 26 | `_lp_locals` | `bigcap.py` | 0.059 | reject | os.environ.get() with these arguments is not built |
| 27 | `_is_map_snapshot` | `pyfunc.py` | 0.058 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 28 | `_numeric_field_kind` | `pyfunc.py` | 0.054 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 29 | `_is_utf8_codec_call` | `pyfunc.py` | 0.054 | reject | write instead: import it under another name (`from ... import ast as other`) |
| 30 | `_dynamic_result` | `pyfunc.py` | 0.054 | reject | write instead: import it under another name (`from ... import ast as other`) |

Six hotter names are not census units and are not ranked: the nested helpers `wrapper` (0.445 s),
`_walk_uncached` (0.383 s), two `visit` functions in `ail_chatgpt.py` (0.215 s and 0.090 s) and
`scan` (0.065 s), and the method `Ctx.type_of` (0.076 s).

## Closest to accepted

All 30 are rejected, and none is one edit away.  Their files fall into three groups: the pyfunc.py
entries (22 of the 30) are refused at module level by an import name that is also defined again (828
functions share that note); the four `ail_chatgpt.py` entries are refused at module level by an
unsupported import (940 share that note); and the other four — `walk` in `fastwalk.py`, `_walk_own`
and `_lp_locals` in `bigcap.py`, and `_own_nodes` in `boolkind.py` — are refused at module level by
an unsupported `os.environ.get()` (220 share that note).  Only `_map_value_kind` and `_mvk` take a
plain scalar (`kind: str`); the other 28 take AST nodes, statement lists or compiler objects
(`node, ctx, ...`, `fn`, `stmts`).

The three closest are the smallest bodies whose own body is the least of the problem:
**`_mvk`** (3 lines, 0.083 s) takes one scalar `kind`, so it fits the typed path's scalar ABI as
written — its remaining blockers are the pyfunc.py module note and the module globals `MAPS`/`SETS`
it reads plus its call to `_map_value_kind`;
**`_map_value_kind`** (6 lines, 0.088 s) also takes one scalar `kind`, but its body indexes the
module-level `MAPS`/`SETS` dicts; **`_owned_method_name`** (3 lines, 0.078 s) is small, but it takes
`node`/`ctx` and an ownership-name string, so it cannot be narrowed to a scalar/bool ABI — it is a
candidate only if the rewrite starts from already-extracted scalars rather than porting the
predicate as-is.  A first rewrite step is therefore not "port one hot function" but "give the typed
path a home for scalar predicates like `_mvk` and `_map_value_kind` outside the file that cannot be
analysed whole."
