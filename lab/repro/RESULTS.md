# Reproducible builds, measured

Measured 2026-11-06 on `origin/integ` (branch `job-ffrepro1-11061145`) with
`tools/repro_check.py`. Measure-only: no compiler file was edited, so no instruction count moved.

Question: does one source give one byte-identical executable when it is built in a short path and
in a long path, with a different `TMPDIR`, its own `HOME`, a different `PYTHONHASHSEED` and two
different `SOURCE_DATE_EPOCH` values?

## Method

Corpus = the 10 `lab/compare/src/*/main.py` programs, every `lab/stdlib/*/*.py` program and every
`examples/**/*.py` program: **467 programs** (10 compare, 390 stdlib, 67 examples).

Each program is built twice:

| | setup A | setup B |
|---|---|---|
| working directory | `/tmp/a/x/<slug>` | `/tmp/b/longer/path/x/<slug>` |
| `TMPDIR` | `/tmp/a/tmp` | `/tmp/b/tmp` |
| `HOME` | `/tmp/a/home` | `/tmp/b/home` |
| `SOURCE_DATE_EPOCH` | `1000000000` | `2000000000` |
| `PYTHONHASHSEED` | `0` | `1` |

The rest of the environment is only `PATH`, `LANG`, `LC_ALL`, `PYTHONUTF8=1`,
`PYTHONDONTWRITEBYTECODE=1` and `AIL_NO_CACHE=1`; nothing is inherited from the caller. The source
is copied into each working directory under its own name, so the file *name* is the same and only
the directory differs. Both builds pass `--debug-dir`, so `program.c` is compared as well as the
executable; both are compared by sha256. Every built executable is run once under both builds and
the stdout and exit status must agree. Builds run under a 1.5 GB address-space limit, at most two
at a time.

On a difference the tool prints the first differing line of `program.c` (with the two lines) and,
when only the executable differs, the first differing ELF section and byte offset; it sorts a C
difference into `hash order`, `absolute path`, `temporary name`, `time`, `counter` or `other`.

## Headline numbers

The clock stopped the first run after 100 of the 467 programs (36 minutes at two builds at a time on
a shared runner; `compare/scar_life` alone is a 4-minute build): all 10 compare programs and 90
stdlib programs in 8 modules. The follow-up measurement below then covered every corpus program that
reads `__file__` (10 linecache programs, 3 examples), because that is the one place an absolute path
reaches the C. The 354 unmeasured programs are the subject of the follow-up in the last section;
this document does not claim a result for them.

| measure | baseline (first 100) | after the `__file__` sweep | after |
|---------|---------------------:|---------------------------:|------:|
| programs measured | **100** | **113** | **113** |
| identical in both setups (`program.c` **and** executable sha256) | **82** | **83** | **83** |
| different in either | **0** | **9** | **9** |
| not built in at least one setup | **18** | **21** | **21** |
| programs whose two builds printed different stdout or exited differently | **0** | **0** | **0** |
| remaining unmeasured | 367 | 354 | 354 |

The “identical before/after” count for the compiler is **82 before and 82 after** on the baseline
set: no compiler file is edited by this job, so a fix cannot move it. The sweep adds one more
identical program (`linecache/08_checkcache_rewrite`) and finds 9 differences, all the same cause
(see the next section); it does not turn any previously identical program into a difference.

By family:

| family | measured | identical | not built | different |
|--------|---------:|----------:|----------:|----------:|
| compare | 10 | 6 | 4 | 0 |
| stdlib (array, base64, bisect, collections, colorsys, csv, datetime, decimal, linecache) | 100 | 77 | 14 | 9 |
| examples | 3 | 0 | 3 | 0 |

Module by module (identical measured / module size): `array` 9/12, `base64` 10/12, `bisect` 12/12,
`collections` 9/12, `colorsys` 13/13, `csv` 9/12, `datetime` 9/12, `decimal` 5/12, `linecache` 1/10.

## The 9 differences: `__file__` puts the build directory in the C

All nine are the same difference, at C line 27672 (or 28533 for `02_middle_line`): a string
constant whose bytes are the absolute path of the copied source.

```c
/* setup A: /tmp/a/x/.../01_first_line.py */   static struct { ... uint16_t d[59]; } _lit1 = { ... { 47, 116, 109, 112, 47, 97, 47, 120, ...
/* setup B: /tmp/b/longer/path/x/.../01_first_line.py */ static struct { ... uint16_t d[71]; } _lit1 = { ... { 47, 116, ... 47, 98, 47, 108, 111, 110, 103, 101, 114, ...
```

The value comes from `__file__`, which `AIL_CURRENT/ail_modules.py:300-305`
(`Program.dunder_node`) returns as `str(mod.path)`, and `Program.__init__` (line 278-280) resolves
the entry path to an absolute one. The linecache programs do
`here = os.path.dirname(__file__)` to find their `data/lines.txt`, so the path is *meant* to be
there; it is also why the two executables differ only in `.note.gnu.build-id` (a hash of the C).

| program | status | first diff |
|---------|--------|-----------|
| `stdlib/linecache/01_first_line.py` | different | C line 27672, absolute path |
| `stdlib/linecache/02_middle_line.py` | different | C line 28533, absolute path |
| `stdlib/linecache/03_last_line.py` | different | C line 27672, absolute path |
| `stdlib/linecache/04_out_of_range.py` | different | C line 27672, absolute path |
| `stdlib/linecache/05_missing_file.py` | different | C line 27672, absolute path |
| `stdlib/linecache/06_getlines.py` | different | C line 27672, absolute path |
| `stdlib/linecache/07_clearcache.py` | different | C line 27672, absolute path |
| `stdlib/linecache/09_no_final_newline.py` | different | C line 27672, absolute path |
| `stdlib/linecache/10_utf8.py` | different | C line 27672, absolute path |
| `stdlib/linecache/08_checkcache_rewrite.py` | identical | — (does not read `__file__`) |

`-ffile-prefix-map` does **not** remove this one: the path is an AIL string literal emitted by the
compiler, not the C `__FILE__` macro, so the C preprocessor never sees it. The fix belongs where
`__file__` is turned into a constant: `AIL_CURRENT/ail_modules.py:304-305` builds it from
`mod.path`, and `AIL_CURRENT/ail_chatgpt.py` makes that path absolute (`source = args.source.resolve()`
at lines 6035/6425). Neither file is in this job's edit list. **Named follow-up: `ffrepro3`** — in
`ail_chatgpt.py`, pass a reproducible logical source path (or rewrite the compiled-in `__file__`
literal under a `--file-prefix-map <build-dir>=.`/`SOURCE_DATE_EPOCH` rule) without changing the
value CPython prints for the same command. Until then these nine are recorded here, not silently
counted as identical.

The three `__file__`-reading examples do not build at all (below), so they have no reproducibility
result either way; the reviewers named them, so they are measured and listed.

## Difference classes

The `class` column is what `tools/repro_check.py` names from the first differing C line (or the
first differing ELF section when only the executable differs).

| class | count | file that would emit it | hook that would remove it |
|-------|------:|-------------------------|---------------------------|
| absolute path | **9** | `ail_modules.py:300-305` (`__file__` = `str(mod.path)`; `Program.__init__` resolves it) | `ffrepro3`: reproducible logical path for `__file__` in `ail_chatgpt.py` (see above); `-ffile-prefix-map` does not apply to a runtime literal |
| hash order | 0 | `python/pkg-v12/pyfunc.py` (sets around lines 7, 92, 221, 504, 2109) | sort the set before iterating (line 415 already sorts `kinds`) |
| temporary name | 0 | `c_api.py:253`, `c_export.py:226`, `c_object.py:356`, `c_api_bridge.py:165` (`tempfile` names) | derive the name from the program, not from the temp directory |
| time | 0 | `buildcache.py:152` (`time.time()`), `clockrt.py` | take the clock from `SOURCE_DATE_EPOCH` |
| counter | 0 | `python/pkg-v12/pyfunc.py` (`ctx.tmp += 1` at 1384, 3157) | renumber per function, not per compiler run |
| other | 0 | — | — |

The nine absolute-path rows are the only differences observed in the 113 measured programs; every
other measured program is identical in both setups.

## Why the executable follows the C here

The compile/link command recorded in `native_report.json` is

```
/usr/bin/cc -O2 -fno-tree-slp-vectorize -ffp-contract=off -fopenmp-simd
   -Werror=implicit-function-declaration -Werror=implicit-int
   -Werror=incompatible-pointer-types -fno-asynchronous-unwind-tables
   -o <TMPDIR>/ailc-XXXXXXXX/program  <TMPDIR>/ailc-XXXXXXXX/program.c
```

There is no `-g` and no `__FILE__`, `__DATE__` or `__TIME__` in the generated C (grep on
`compare/echo_pack`'s 6282-line `program.c`: no hit), the C is always named `program.c` inside the
temp directory so even the assembler `.file` name is constant, and the linker's build-id is a hash
of the contents. The temp directory name therefore appears only in `native_report.json`, never in
the executable: `strings prog | grep -E '/tmp|ailc-|main.py'` finds nothing. That is why every
program with identical C also has an identical executable — the binary adds no second source of
difference of its own in this toolchain. The one exception is a program that reads `__file__`: the
path becomes a normal AIL string literal in the C (not the `__FILE__` macro), so it changes the C
and the build-id with it (the nine programs above).

## The 21 programs that were not built

4 compare programs, for the reasons already recorded in `lab/selfhost/DETERMINISM.md`
(`chain_relax`: int64 literal out of range; `rail_transfer`: int64 literal, then an untyped tuple
element; `tally_lang`: `re.match` pos/endpos; `tree_fold`: untyped tuple element and `NODE` used as
a value).

14 stdlib programs: `array/binary_packets.py`, `array/float32_readings.py`,
`array/unicode_codes.py`, `base64/b85_vectors.py`, `base64/legacy_stream_api.py`,
`collections/log_report.py`, `collections/lru_cache.py`, `collections/point_records.py`,
`csv/field_size_limit.py`, `csv/register_dialect.py`, `csv/sniffer.py`,
`datetime/calendar_export.py`, `datetime/epoch_convert.py`, `datetime/iso_week.py`.

Each is a loud, named refusal (the module's coverage tests record the same refusals), not a crash
and not a timeout: a refused program emits no C, so it has no reproducibility result either way.

3 examples, also loud named refusals in both setups:
`examples/algos/run.py` (`os.environ.get()` / `os.path.getsize()` with these arguments),
`examples/ffi/bindgen/measure.py` (`re` pattern outside the built subset),
`examples/textcli/gen_big.py` (`Path.stat()` not built, and the general path cannot build it either).
All three read `__file__`, so they are in the sweep above; refusal is two-sided (the same stderr in
both setups), which the checker now reports as `not built`, never as `identical`.

## Ratchet

`AIL_CURRENT/test_ail_repro.py` (registered in `AIL_CURRENT/tests.d/test_ail_repro.txt`) builds five
of the programs above twice in the same two setups and asserts one sha256 for the executable and one
for `program.c`, and that both builds print the same bytes and exit the same way:
`stdlib/bisect/alias_import.py`, `stdlib/heapq/closest_points.py`,
`examples/tutorial_project/step1.py`, `examples/algos/rpn.py`, `compare/echo_pack`.
It also has two checker unit tests: a `uint16_t[]` absolute path in the C must be classified
`absolute path` (not `other`), and a program that builds in setup A but not in setup B must be a
`diff` with `one_sided`, never a two-sided `refused`. When a program with a difference is fixed, add
its row here and to `PROGRAMS`; when the corpus run below is finished, extend `PROGRAMS` from its
result.

## Follow-up

- **`ffrepro3`: make `__file__` reproducible.** The nine linecache differences above come from the
  absolute source path that `AIL_CURRENT/ail_modules.py:304-305` puts in the `__file__` constant,
  after `AIL_CURRENT/ail_chatgpt.py` resolves the entry path (`source = args.source.resolve()`, lines
  6035/6425). Add a reproducible logical source path there (a `--file-prefix-map <build-dir>=.`
  applied to the compiled-in `__file__`, or record the path as given rather than absolute) and keep
  the value CPython prints for the same command. `-ffile-prefix-map` alone cannot do it: this is a
  runtime string literal, not the C `__FILE__` macro. Then move the nine rows to “identical” and
  name the fix in `DIFFERENCES.md` as `C?-ffrepro3-N`.
- **`ffrepro2`: finish the corpus.** Run `python3 tools/repro_check.py -j 2 --json /tmp/repro.json`
  to completion on an idle runner (467 programs; at the observed 6 programs/min it needs about
  80 minutes) and replace the `measured` row above with the final count. If a `diff` row appears
  outside the `absolute path` class, route it with the hook column and name the fix in
  `DIFFERENCES.md` as `C?-ffrepro2-N`.
- No compiler file was edited by this job: `git diff --stat origin/integ -- AIL_CURRENT` shows only
  the new test module and the measurement tool, so the instruction counts of the 10 compare-lab
  tasks are unchanged by construction.

## Reproducing

```
python3 tools/repro_check.py -j 2 --json /tmp/repro.json           # whole corpus
python3 tools/repro_check.py -j 2 --filter compare/                # the 10 compare programs
python3 tools/repro_check.py -j 2 --filter linecache               # the nine differences
python3 tools/repro_check.py -j 1 --filter examples/algos/run.py   # a two-sided refusal
python3 -B AIL_CURRENT/test_ail_repro.py                           # the ratchet
```

## Tests run on the final commit

All four required modules, on commit `546cc4c` (the manifest pin for the changed test file is
`b69bb0b`; `python3 tools/update_manifest.py --check` then exits 0):

| test | result |
|------|--------|
| `AIL_CURRENT/test_ail_repro.py` | **OK**, 4 tests, 18.3 s (5-program build ratchet + the two checker tests; registered in `tests.d`) |
| `AIL_CURRENT/test_ail_safetynet.py` | **OK**, 158.8 s, run without the shell memory limit (see below) |
| `AIL_CURRENT/test_ail_files.py` | **OK**, 86.9 s, under `ulimit -v 1500000` |
| `AIL_CURRENT/test_ail_corpus_findings3.py` | **OK**, 190.6 s, under `ulimit -v 1500000` |

`test_ail_safetynet` is the one module run without `ulimit -v 1500000`: under that wrapper
`S4_generators_gc` stops after its first line (the reviewer saw the same; it is the wrapper, not
this job — the compiler diff against `origin/integ` is only the two new files). Run alone without
the limit it passes.

## Probes

No compiler behaviour is changed, so the probes target the two checker fixes and the one compiler
path that the sweep found:

| probe | expected | actual |
|-------|----------|--------|
| `/tmp/probes/checker_uint16.py` (real 59/71-byte `uint16_t[]` literals) | `absolute path`, one-sided = `diff`, both-failed = `refused`, corpus source unchanged | all OK |
| `/tmp/probes/path_join.py` via `bash ~/tools/cmp.sh … $PWD` | CPython and both builds agree | exit 0/0/0, same stdout in `g` and `d` |
| `tools/repro_check.py -j 2 --filter linecache` | 9 `diff` (absolute path), 1 `identical` | matches, C line 27672/28533, ELF `.note.gnu.build-id` |
| `tools/repro_check.py -j 1 --filter examples/algos/run.py` | two-sided `not built` (named refusal) | matches |

