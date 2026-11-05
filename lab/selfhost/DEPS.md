# Front-end dependency graph (self-hosting prep)

Measurement only: this report was produced by reading `AIL_CURRENT` sources with `ast`; no
compiler file was edited and nothing was compiled.

- Tool: `tools/selfhost_deps.py`
- Data: `lab/selfhost/deps.json` (schema `ail.selfhost_deps/1`)
- Entry: `AIL_CURRENT/ail_chatgpt.py` (what the `compile` command loads)
- Base: the `job-shdeps1` export of `staging:integ`, commit recorded as `base_commit` in the JSON
- Reproduce: `python3 tools/selfhost_deps.py`

Two graphs are recorded. **eager** follows imports that run at import time — the module body
plus module-level `if`/`try`/`with`/`class` statements; **full** adds imports inside function
and lambda bodies (marked `lazy`). Standard-library imports are listed per module in the JSON
and not followed.

## Two graphs

| graph | modules | lines | edges | layers | cycles | modules in cycles |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| eager | 6 | 17,006 | 6 | 3 | 0 | 0 |
| full | 163 | 215,462 | 419 | 9 | 4 | 69 |

The eager graph is tiny: `ail_chatgpt.py` imports `ail_syntax`, `ail_sexpr`, `ail_modules`
and `fastwalk` at module level, and its `if __name__ == "__main__"` block imports `ail_server`
on the documented `compile` invocation (`ail_sexpr` also imports `ail_syntax`). Every
compiler pass and back end module is reached through function-level imports, so eager lines
are 7.9% of the front end.

Layer sizes (full), layer 0 = leaves: `62, 22, 7, 3, 60, 2, 1, 1, 5` — 9 layers. Layer sizes
(eager): `4, 1, 1`.

## Cycles (full graph)

Four strongly connected components have more than one module; there are no self-loops. A cycle
has to be rewritten as one unit.

| size | modules |
| ---: | --- |
| 2 | `ir.effects`, `ir.rtc` |
| 2 | `ir.passes`, `ir.passes.licm` |
| 60 | `ail_syntax`, `ailarray`, `boxclosure`, `c_api_bridge`, `c_object`, `cruntime`, `csvgen`, `csvlib`, `devcc`, `dtlib`, `dunders`, `enumlib`, `exctext`, `filelib`, `filelower`, `filert`, `fmtlib`, `funclib`, `genlib`, `gpu`, `hashlower`, `ir.driver`, `ir.emit_c`, `ir.lower`, `itlib`, `jsonlib`, `modtables`, `module_object`, `ntlib`, `numberslib`, `pathlower`, `pipeline`, `proclib`, `pyboxed`, `pyboxed2`, `pyc`, `pyfront`, `pyfunc`, `pymix`, `randlib`, `safetyrt`, `smalllib5`, `statlib`, `stdlib3`, `stdlib4`, `stdlib5`, `stdtop`, `stubcalls`, `timelib`, `tupcalls`, `tupcommon`, `tupexpr`, `tuplam`, `tuplegen`, `tuplib`, `tupstmt`, `unified`, `urllower`, `userexc`, `withlib` |
| 5 | `ail_api_contracts`, `ail_chatgpt`, `ail_server`, `ail_source_context`, `ail_source_edit` |

The 60-module component contains the whole typed path and the traditional code generator; it
also contains the entry's own component (`ail_chatgpt` is in the 5-module component, which
points into it). `ail_syntax` alone is 5,811 lines. The dynamic fallbacks in `jsonlib` and
`stdlib4` (which load `ail_syntax.py` by path when it is not already in `sys.modules`) are
counted as edges here, so `ail_syntax` is reachable from both.

## Highest in-degree (15, full graph)

`in-degree` counts distinct importing modules; eager is the same count on import-time imports.

| module | in-degree | in-degree (eager) | lines |
| --- | ---: | ---: | ---: |
| `ir` | 19 | 18 | 11 |
| `ir.ir` | 18 | 18 | 469 |
| `iterlower` | 17 | 15 | 1,191 |
| `stdlib4` | 17 | 15 | 231 |
| `pyfront` | 15 | 11 | 1,456 |
| `stdlib5` | 12 | 10 | 289 |
| `ir.effects` | 9 | 9 | 349 |
| `pipeline` | 9 | 7 | 343 |
| `pyfunc` | 8 | 4 | 42,062 |
| `ail_syntax` | 8 | 3 | 5,811 |
| `bigcap` | 8 | 2 | 1,699 |
| `intmode` | 8 | 2 | 35 |
| `biggate` | 7 | 3 | 348 |
| `cruntime` | 7 | 3 | 31,094 |
| `classname` | 6 | 6 | 182 |

## First 20 in leaf-first order (candidates for the first AIL rewrites)

Order = layer, then name; every module in a cycle shares its component's layer. "census"
marks whether the typed-path census in `lab/selfhost/census.json` accepts any top-level
function of that file.

| # | module | lines | layer | in-degree | census |
| ---: | --- | ---: | ---: | ---: | --- |
| 1 | `ail_builtin_syntax_forms` | 779 | 0 | 1 | no |
| 2 | `ail_export` | 204 | 0 | 1 | no |
| 3 | `ail_manifest` | 140 | 0 | 2 | no |
| 4 | `ail_native_build` | 146 | 0 | 1 | no |
| 5 | `ail_slow_patterns` | 396 | 0 | 1 | no |
| 6 | `aliasrefuse` | 818 | 0 | 1 | no |
| 7 | `biggate` | 348 | 0 | 7 | no |
| 8 | `bigint_core` | 351 | 0 | 1 | no |
| 9 | `bigint_obj` | 729 | 0 | 1 | no |
| 10 | `boolkind` | 1,451 | 0 | 1 | no |
| 11 | `borrowed_callback` | 87 | 0 | 1 | no |
| 12 | `boundbuiltin` | 227 | 0 | 1 | no |
| 13 | `buildcache` | 600 | 0 | 5 | no |
| 14 | `callable_types` | 132 | 0 | 3 | no |
| 15 | `ccsplit` | 348 | 0 | 1 | no |
| 16 | `classname` | 182 | 0 | 6 | no |
| 17 | `clockrt` | 271 | 0 | 2 | no |
| 18 | `compscope` | 319 | 0 | 1 | no |
| 19 | `dictviews` | 339 | 0 | 5 | no |
| 20 | `fastwalk` | 49 | 0 | 2 | no |

None of the first 20 is accepted by the typed-path census: its 21 accepted top-level functions
live in six files (`dtrt`, `hash_prelude`, `prelude_ailarray`, `prelude_array`,
`prelude_fraction`, `strt`) that are deeper in the order. So the typed path currently helps
none of the earliest self-hosting candidates; those rewrites start from no accepted function.

## Dynamic imports (stop-rule check)

20 import expressions build their target at run time. Sixteen of them resolve to a file this
tool follows; the rest are listed here. Two resolved targets matter for the graph: the
`ail_syntax.py` fallbacks in `jsonlib` and `stdlib4` (loaded by path when `ail_syntax` is not
already in `sys.modules`) add the edges that join the 4-, 13- and 40-module components into the
single 60-module cycle reported above. The other unresolved cases are standard library
(`builtins`, `sys`), a fallback to a module already imported statically (`compscope`, imported
by `shadowing` at line 321), or a loop variable.

| container | line | form | value | target |
| --- | ---: | --- | --- | --- |
| `ail_chatgpt` | 68 | `spec_from_file_location` | `ROOT / 'python/pkg-v12/buildcache.py'` | `buildcache` |
| `ail_server` | 371 | `import_module` | `ail_chatgpt` | `ail_chatgpt` |
| `ail_server` | 374 | `import_module` | `name` (loop over `('pyc', 'pyfunc', 'pyboxed2', 'unified', 'ir.driver', 'cruntime', 'pymix')`) | — (all seven already in the graph) |
| `ail_syntax` | 71 | `spec_from_file_location` | `Path(__file__).parent / 'python' / 'pkg-v12' / 'callable_types.py'` | `callable_types` |
| `ail_syntax` | 87 | `spec_from_file_location` | `... / 'relib.py'` | `relib` |
| `ail_syntax` | 98 | `spec_from_file_location` | `... / 'raisefrom.py'` | `raisefrom` |
| `ail_syntax` | 109 | `spec_from_file_location` | `... / 'matchlower.py'` | `matchlower` |
| `ail_syntax` | 120 | `spec_from_file_location` | `... / 'nestfn.py'` | `nestfn` |
| `ail_syntax` | 131 | `spec_from_file_location` | `... / 'optlib.py'` | `optlib` |
| `ail_syntax` | 142 | `spec_from_file_location` | `... / 'tuplib.py'` | `tuplib` |
| `ail_syntax` | 153 | `spec_from_file_location` | `... / 'collib.py'` | `collib` |
| `dictviews` | 140 | `__import__` | `builtins` | — (stdlib) |
| `ir.lower` | 3170 | `__import__` | `intmode` | `intmode` |
| `ir.lower` | 3249 | `__import__` | `intmode` | `intmode` |
| `ir.lower` | 3298 | `__import__` | `intmode` | `intmode` |
| `jsonlib` | 633 | `spec_from_file_location` | `path` (= `pathlib.Path(__file__).resolve().parents[2] / 'ail_syntax.py'`, fallback) | `ail_syntax` |
| `pyfunc` | 41356 | `__import__` | `pipeline` | `pipeline` |
| `pyfunc` | 41987 | `__import__` | `sys` | — (stdlib) |
| `shadowing` | 325 | `spec_from_file_location` | `os.path.join(..., 'compscope.py')` | — (already imported statically) |
| `stdlib4` | 58 | `spec_from_file_location` | `path` (= `Path(__file__).resolve().parents[2] / 'ail_syntax.py'`, fallback) | `ail_syntax` |

## Unresolved imports (stop-rule check)

3 import lines cannot be resolved: `ail_chatgpt.py` lines 6311, 6314 and 6318 import
`ail_http_compare`, `ail_http_snapshot` and `ail_http_build` inside function bodies, and no
such module exists in the tree. Against 427 resolved import edges and 535 standard-library
imports, that is 0.3%, far below the 10% stop threshold. They are lazy CLI paths and are
listed under `unresolved` in the JSON.

## Spot check

Three modules picked at random from the graph were compared with a `grep` of their import
lines:

| module | JSON edges | import lines |
| --- | --- | --- |
| `collib` | eager `[]`, lazy `[dictviews]` | 17-19 `ast`, `re`, `copy` (stdlib); 3202 `import dictviews` in a function |
| `tupcalls` | eager `[tupcommon, tupexpr]`, lazy `[]` | 2 `import ast` (stdlib); 4 `from tupcommon import *`; 5 `from tupexpr import unopt` |
| `ail_syntax` | eager `[]`, lazy `[ailarray, callable_types, collib, matchlower, modtables, nestfn, optlib, raisefrom, relib, sqllower, stdlib4, stdlib5, threadlib, tuplib, typedpar]` | 2-15 standard library at top level; 167/176/187/198 `threadlib`/`ailarray`/`stdlib5`/`stdlib4`, 4046/4057 `sqllower`/`modtables`, 5757 `typedpar` in functions; 71-153 the codec files loaded by path |

All three match.

## Limits

- Imports in the module body and in module-level `if`/`try`/`with`/`class` statements are
  eager, matching what runs when the entry is executed. A module-level `if` whose condition is
  false at run time therefore still contributes an eager edge (e.g. `ail_server` via the
  `__main__` guard). Imports inside function and lambda bodies are lazy.
- `from package import name` adds an edge to `package.name` when that submodule exists and to
  the package itself (its `__init__` runs).
- The graph is of source-level imports. A name reached through `sys.modules` or a global
  registry is not an edge.
