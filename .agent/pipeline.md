# job job-wedge2-11081603  started 2026-11-08T07:04:12Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Implemented on `job-wedge2-11081603` (`origin/integ` is absent in this checkout; the task branch already existed). Commit: `1e18def`.

## What changed
- `_unsafe_body` now permits non-slice `Subscript` for list/dict indexing.
- The emitted clone’s index/key runtime stop is patched to a per-call thread-local trap + `setjmp` wrapper; the Python wrapper re-runs the original function, so CPython supplies the exact `IndexError`/`KeyError` message and caller `try/except`.
- Slice indexing, attribute stores, list-parameter mutation and simple list aliases still stay in CPython.
- Wedge1’s silent refusals are fixed: `build.json` and build stderr now name every top-level refusal, including `pymix`/emitter refusals. Silent refusals: `54/73` → `0/97`.

## Measurements (`ulimit -v 2500000`, `-j 2`)
Native share: **24/97 (24.7%) → 29/97 (29.9%)**.
Added: `edit_dist.bigram_overlap`, `edit_dist.common_prefix`, `edit_dist.hamming`, `matrix.trace`, `tokenizer.count_keywords`.

Hybrid/CPython wall time per module, before → after:

| module | ratio | module | ratio |
|---|---:|---|---:|
| ast_lint | 1.025 → 0.989 | bitset_bloom | 1.030 → 0.939 |
| csv_parse | 0.979 → 0.983 | dataframe_group | 0.951 → 0.931 |
| edit_dist | 1.003 → 0.997 | field_valid | 1.077 → 1.155 |
| float_loops | 1.009 → 1.033 | graph_search | 0.855 → 1.004 |
| hashing | 0.999 → 1.008 | json_parse | 0.909 → 0.906 |
| matrix | 1.007 → 0.995 | rolling_stats | 0.885 → 0.905 |
| sort_rank | 1.027 → 1.019 | tokenizer | 0.969 → 0.992 |
| tree_build | 0.996 → 0.943 | geomean | **0.980x → 0.985x** |

Coverage improved without a measurable speed-up; parity is unchanged. `measure.py` already printed `hybrid/cpython`.

Top remaining refusal reasons by profiled self time: not-a-top-level-function 20.9%, unresolved-return 20.4%, call-can-raise 13.0%, unresolved params `node`/`adj`/`words`/`data` 10.6/10.3/5.0/3.0%, module-constant 3.1%, typed-clone ABI 2.5%, tuple-parameter 2.3%, division 2.3%, list-parameter 1.3%. Indexing is no longer a reason.

## Probes
All `/tmp/probes/hybrid_*.py` run with `bash ~/tools/cmp.sh <probe> $PWD` for the general and default builds, plus the hybrid build:
- `hybrid_index`, `hybrid_dict`, `hybrid_nested`, `hybrid_strindex`, `hybrid_types`, `hybrid_values`, `hybrid_dictkinds`: stdout/exit match CPython; successful list/float/str/dict/nested indexing is native, while unsupported attribute/dict-list/parameter cases are refused by name.
- `hybrid_alias`: list-parameter alias and direct mutation refused by name; matches CPython.
- `hybrid_reasons`: every refusal named; matches.
- `hybrid_uncaught_index`: uncaught `IndexError: list index out of range` matches.
- `hybrid_keyerror`: caught `KeyError` type/message matches.

## Tests on the final tree
`python3 tools/par_check.py -j 2 test_ail_cpython_hybrid test_ail_safetynet test_ail_files test_ail_corpus_findings3`:
- `test_ail_cpython_hybrid` 16.8s
- `test_ail_files` 62.2s
- `test_ail_safetynet` 81.3s
- `test_ail_corpus_findings3` 134.3s
- **4/4, 0 failed, 214s**

Manifest regenerated and `--check` passes; DEVLOG and DIFFERENCES (`C?-job-wedge2-11081603-1`) updated.
[cost $0.0000, opencode tokens {"total": 11478187, "input": 271076, "output": 31658, "reasoning": 49693, "cache.write": 0, "cache.read": 11125760}]
    tool time: bash 15.7 min
        235s bash   ulimit -v 2500000; python3 -B lab/wedge/census.py -j 2 -o /tmp/wedge-after-census.json > /tmp/wedge-after-cens
        228s bash   ulimit -v 2500000; python3 -B lab/wedge/census.py -j 2 -o /tmp/wedge-before-census.json > /tmp/wedge-before-ce
        214s bash   ulimit -v 2500000; /usr/bin/time -f 'elapsed=%e' python3 -B tools/par_check.py -j 2 test_ail_cpython_hybrid te
        120s bash   mkdir -p /tmp/wedgebase && (ulimit -v 2500000; cd /home/runner/work/ail-ci/ail-ci && python3 lab/wedge/census.
         30s bash   ulimit -v 2500000; python3 -B lab/wedge/boundary.py -o /tmp/wedge-after-boundary.json > /tmp/wedge-after-bound
         20s bash   for p in /tmp/probes/hybrid_*.py; do echo "##### $(basename $p)"; bash ~/tools/cmp.sh "$p" "$PWD"; done > /tmp
         18s bash   /tmp/probes/run_hybrid.sh /tmp/probes/hybrid_*.py > /tmp/hybrid_probes.log 2>&1; echo rc=$?; grep -E "^===|acc
         16s bash   ulimit -v 2500000; python3 -B AIL_CURRENT/test_ail_cpython_hybrid.py -v 2>&1 | tail -40

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
## Review report — wedge2 hybrid indexing

**What the change really does** (one line): it lets `_unsafe_body` admit non-slice subscripts and adds a `_trap_patch` that rewrites the clone unit's `ail_die("list index out of range"/"key error"/...)` calls into a thread-local `setjmp`/`longjmp` trap, so the wrapper abandons the native call and re-runs the original Python function; it also extends dict/list literal kind inference and names every refused top-level function. This matches the report.

**Probes** (`/tmp/rprobes/`, `hy.sh` = hybrid build, compared byte-for-byte with CPython; `cmp.sh` = general+default builds):
| probe | covers | result |
|---|---|---|
| r_index2, r_local, r_nestedkinds | in-range, negative, empty, out-of-range, `a[i][j]` | identical (native) |
| r_dict, r_dictkinds, r_containers | dict hit/miss, str keys, bool key, nested dict | identical; missing key = CPython `KeyError` text |
| r_liststr | list[str]/list[float] locals, IndexError, float/str result paths | identical (native) |
| r_alias, r_global, r_attr, r_slice | param mutation/alias, global list/dict store, attribute, slice | refused by name, output identical |
| r_floatidx | float index | named compile refusal (acceptable) |
| r_reuse, r_leak | list mutated between calls (`pop`), 300k trapping calls | identical; no leak (11.0 MB vs 10.9 MB base), no slowdown |
| r_noindex2, r_nolit, r_dictlit | feature unused (plain arith/str/list/dict literal, no subscript) | same accelerated set as base; unindexed unit C identical (`key error` unpatched because `indexes` is false) |

No wrong output, crash or wrong exit status on HEAD; the same probes cannot accelerate indexing on base, so nothing is pre-existing.

**Claims checked**
- `_unsafe_body` admits non-slice subscript; slices/attribute stores/param mutation still refused — verified.
- trap + wrapper re-run supplies CPython's IndexError/KeyError — verified (message, type, caller try/except).
- every top-level refusal named in build.json/stderr — verified in probes; census artifacts: 54/97 silent → 0/97.
- native share 24/97 → 29/97 — verified from the census/measure artifacts (`accelerated` sums 24 and 29).
- geomean 0.980x → 0.985x — recomputed from the artifacts (0.9797 → 0.9849).
- `measure.py` prints `hybrid/cpython` — verified (unchanged file, correct label).
- tests 4/4 — I re-ran `test_ail_cpython_hybrid` (16.9 s) and `test_ail_safetynet` (77.4 s): both pass. `test_ail_files`/`test_ail_corpus_findings3` not re-run (not edited; instruction says added/edited + safetynet).
- manifest `--check` — passes; DEVLOG/DIFFERENCES rows present.
- no bench/apps or language_examples edits (4a clean); only AIL_CURRENT hybrid files + docs + tests.

**Minor overstatement, not a defect**: str-*parameter* indexing (`s[i]`) is still refused (`unresolved-return`); native str indexing only works for local `list[str]`. Named refusal, output correct.

**Unverified**: top remaining refusal percentages by profiled self time; `ailc ext --why` path (build stderr verified instead); icount speed (the change cannot affect the default C build; gdev programs do not use the hybrid).

**Pre-existing**: none observed.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=42 out_tokens=37130]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T09:02:53Z
