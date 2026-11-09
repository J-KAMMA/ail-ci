# wedge3c: two more real libraries against the guarded hybrid

Branch `job-obs5-op1109` at `69e2dcd0a82580fa06e26b275352fbedfb7d31e1` (observed-types work, not yet
integrated).  CPython 3.12.3, PyPy 3.10.14 (7.3.17), 4-core GitHub runner, every measured process
under `ulimit -v 2500000`, one workload at a time.

Libraries (pip-installed into venvs; never vendored):

| library | pure column | native column |
| --- | --- | --- |
| `jellyfish` | 0.8.9 pure-Python fallback (`_jellyfish.py`; `*cjellyfish*` removed) | 1.1.0 (Rust) |
| `msgpack` | 1.0.7 fallback (`MSGPACK_PUREPYTHON=1`) | 1.0.7 C extension (no Rust rewrite exists) |

**Headline:** AIL's guarded hybrid selected **0 of 14 jellyfish functions and 0 of 35 msgpack units**,
so it ran at CPython speed (0.98-0.99x) while PyPy was 3.3-5.4x and the native rewrite 10.5-14.1x
faster.

## 1. Results

Times are the median of 5 runs; every column's stdout and exit status matched CPython byte for byte.
`hybrid+obs` is the same build with kinds written by `ail_observe annotate`.

| library | units | native | CPython s | PyPy s | hybrid s | hybrid+obs s | native s | hybrid/CPython | hybrid/PyPy | hybrid/native |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| jellyfish | 14 | 0 | 2.893 | 0.529 | 2.839 | 2.840 | 0.270 | 0.981 | 5.368 | 10.523 |
| msgpack | 35 (3 module-level + 32 methods) | 0 | 2.223 | 0.673 | 2.209 | 2.211 | 0.157 | 0.994 | 3.282 | 14.056 |

The sub-1.0 `hybrid/CPython` ratios are run-to-run noise: **no function was selected**, so the hybrid
column is the unmodified pure library.  The native column is the only real speedup: 10.7x over CPython
for jellyfish's Rust extension and 14.1x for msgpack's C extension.  PyPy needs no rewrite and gets
5.5x and 3.3x respectively.

### What observation changed

Observation annotated every executed function (parameters and returns) but **moved no function into
the native column**.  Its value was diagnostic: jellyfish went from `unresolved-param` (all six units)
to `unresolved-return` (all six), which names the real remaining gate.  msgpack's method reasons only
changed wording (which `self` attribute was blamed).  In the observed jellyfish build `_normalize` was
selected, but that is the one body the harness had to neutralise for the entry build (it is not a
native rewrite of the real function and is never deployed).

## 2. How the hybrid was applied

`ailc ext` does not exist in this build; the command is
`ail_chatgpt.py build --cpython SOURCE -o DIR` (the same entry the lab tools use).  The harness copies
the installed package to a temp dir, prepares the hot module as an AIL entry file, builds it twice
(plain, then with `ail_observe annotate`), and compares stdout/exit with CPython.

* **jellyfish**: `_jellyfish.py` is not a valid entry file as installed.  `import unicodedata` stops
  the build (`unicodedata.normalize is not supported`) and `from .porter import Stemmer` is a
  package-relative import of an unsupported name.  The harness removes those two imports and makes
  `_normalize` return its argument for the analysis.  The unannotated full module also stops on
  `damerau_levenshtein_distance`'s `defaultdict` (element kind unknowable), so the build source is the
  slice the workload actually calls plus its two helpers: `_normalize`, `_check_type`,
  `levenshtein_distance`, `_jaro_winkler`, `jaro_winkler_similarity`, `soundex`.  The other eight
  functions are never executed by the workload (0 s of profile time) and do not enter the count of
  selected functions.  `functions_total` stays 14 for the whole module.
* **msgpack**: `fallback.py`'s two relative imports are rewritten to `msgpack.exceptions` /
  `msgpack.ext`; the copied package is on `PYTHONPATH`.  The whole module is analysed (3 module-level
  functions and 32 methods).
* Because nothing was selected, the timed package is the untouched pure library.  The harness asserts
  that no unsound helper is counted and refuses to continue if a real function is ever selected
  without a deployment step.

## 3. Refusal reasons, ranked by the CPython self time they keep interpreted

cProfile on the pure CPython run; the profile base is larger than wall time (per-call overhead), so
the numbers rank the functions, they are not addends of the wall clock.

### jellyfish (no observed kinds)

| self s | reason | functions |
| ---: | --- | --- |
| 1.793 | `unresolved-param: s1, s2` | `levenshtein_distance` |
| 1.022 | `unresolved-param: s1, s2, long_tolerance` | `_jaro_winkler`, `jaro_winkler_similarity` |
| 0.595 | `unresolved-param: s` | `_check_type`, `_normalize`, `soundex` |

### jellyfish (observed kinds)

| self s | reason | functions |
| ---: | --- | --- |
| 3.248 | `unresolved-return: return branches require distinct tags` | `_jaro_winkler`, `jaro_winkler_similarity`, `levenshtein_distance`, `soundex` |
| 0.130 | `unresolved-return: no return, or contradictory returns` | `_check_type` |
| 0.032 | selected by the build (sanitised helper, not deployed) | `_normalize` |

The dominant gate is the same for all four measured functions: pymix cannot give every return one
kind.  `levenshtein_distance` initialises `prev = None` before overwriting it with a list, and
`_jaro_winkler`/`soundex` mix int and float/str paths in a way the inference does not merge.  No
annotation the recorder can write changes that: it is a body-inference gate, not a missing hint.

### msgpack (plain build; the observed build only regroups the `_buffer` fields)

| self s | reason | functions |
| ---: | --- | --- |
| 3.477 | `method of a class with decorators, bases, a metaclass or class attributes` | `Unpacker.__init__`, `_got_extradata`, `_read`, `_read_header`, `_reserve`, `_unpack`, `feed` |
| 2.348 | `a decorated, dunder or non-plain-signature method` | `Packer.__init__`, `_pack`, `_pack_map_pairs` |
| 0.294 | `method: field self._use_bin_type has no scalar or int/float list kind` | `_pack_bin_header`, `_pack_raw_header` |
| 0.101 | `method: field self._buffer has no scalar or int/float list kind` | `_pack_array_header`, `_pack_map_header` |
| 0.015 | not reported (class bodies, `<lambda>`) | — |
| 0.001 | `not a typed candidate` | `_get_data_from_buffer`, `unpackb` |
| 0.000 | `method: field self._autoreset ...` | `pack` |

With observed kinds the same methods are refused; the `_buffer` group grows to 0.395 s because
`pack` and the two header writers are blamed on the buffer instead of `_use_bin_type`/`_autoreset`.

`Unpacker` has a class-level alias (`next = __next__`), which is enough to stop its methods;
`Packer._pack` has callable default arguments (`check=isinstance`, `check_type_strict=...`).  The rest
carry a `StringIO`/`bytearray` buffer in `self`, which the method ABI supports only for scalar fields
or int/float lists.

## 4. Instruction counts

Not available on this runner.  `tools/icount.c` builds, but `perf_event_open` is denied
(`/proc/sys/kernel/perf_event_paranoid = 4`), and `valgrind` is not installed.  Wall times above are
the only time measurement; both workloads are under 3 s, so they are inside the range where icount was
requested, but the kernel forbids it here.

## 5. Probes (mandatory self-check)

Probes are kept in `probes/`; each prints deterministic output over empty, equal, long, numeric,
negative, punctuation, list-item, dict-value, attribute and argument-channel inputs.

| probe | CPython pure | PyPy pure | hybrid | native | `cmp.sh` |
| --- | --- | --- | --- | --- | --- |
| `jellyfish_edges.py` | exit 0 | identical | identical | identical (Rust 1.1.0) | both builds refused by name: `import of 'jellyfish' is not available` |
| `msgpack_edges.py` | exit 0 | identical | identical | identical (C extension) | both builds refused by name: `import of 'msgpack' is not available` |

The hybrid column is the identical pure package because the build selected nothing; the benchmark's
own byte-for-byte check (`output_sha` in `results.json`) covers the full workloads for all five
columns.  `cmp.sh` cannot compile a probe that imports a third-party package, and it refuses it by
name on the general and default builds — which is the expected result, not a behaviour change.

## 6. Reproduce

```sh
python3 -m venv /tmp/wedge3venv && /tmp/wedge3venv/bin/pip install -r requirements.txt
python3 -m venv /tmp/wedge3native && /tmp/wedge3native/bin/pip install -r requirements-native.txt
git -C <repo> fetch origin job-obs5-op1109
git -C <repo> worktree add ../obs5 FETCH_HEAD     # used AIL_CURRENT
/tmp/wedge3venv/bin/python lab/wedge3/wedge3c/bench.py -o lab/wedge3/wedge3c/results.json
```

`results.json` records the build reports (every function's reason, plain and observed), the five
medians, the stdout digests, and the profile.  `bench.py` is the only harness; it never vendored a
library and every timed run is under the memory limit.
