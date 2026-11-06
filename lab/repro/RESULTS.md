# Reproducible builds, measured

Measured 2026-11-06 on `origin/integ` (branch `job-ffrepro1-11061516`) with
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
the directory differs. Both builds pass `--debug-dir`, so the generated C is compared as well as the
executable; both are compared by sha256. The C file is `program.c` on the ordinary path and
`entry.c` on an FFI build; a build that saved no C is a finding, never an accidental match of two
missing files. Every built executable is run once under both builds and the stdout and exit status
must agree. Builds run under a 1.5 GB address-space limit, at most two at a time.

On a difference the tool prints the first differing line of the generated C (with the two lines)
and, when only the executable differs, the first differing ELF section and byte offset; it sorts a
C difference into `hash order`, `absolute path`, `absolute path hash`, `temporary name`, `time`,
`counter` or `other`.

## Headline numbers

The completed corpus run covers all **467** programs:

| measure | complete run | after comparing `entry.c` |
|---------|-------------:|--------------------------:|
| programs measured | **467** | **467** |
| identical in both setups (C **and** executable sha256) | **392** | **392** |
| different in either | **14** | **14** |
| differences visible in the generated C | **9** | **14** |
| identical C but different executable | **5** | **0** |
| not built in at least one setup | **61** | **61** |
| programs whose two builds printed different stdout or exited differently | **0** | **0** |

The “before/after” count for the compiler is **392 before and 392 after**: this job does not edit a
compiler file, so its changes cannot move that number.

The 14 differences have two causes, both listed below: 9 `stdlib/linecache` programs compile the
absolute source path into a `__file__` string literal, and 5 `examples/ffi*` programs put
`sha1(absolute source path)[:6]` in their FFI symbol names.

An earlier partial pass stopped after 100 programs and then added every program that reads
`__file__` (113 total). Those partial counts are superseded by the complete run above and are no
longer used as the result. The earlier “0 executable-only differences” claim is also withdrawn:
the tool looked only for `program.c`, which an FFI build does not write, so it compared two missing
files and called them equal. With `entry.c` compared, the five FFI rows are ordinary C differences.

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
there; it also changes the C and therefore the linker's `.note.gnu.build-id`.

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
result either way; the reviewer named them, so they are measured and listed.

## The 5 FFI differences: the absolute path is hashed into symbol names

`AIL_CURRENT/ail_ffi_lower.py:519` computes

```python
tag = hashlib.sha1(str(path).encode()).hexdigest()[:6]
```

from the resolved source path and uses it in every generated FFI symbol (`ffi_put_<tag>`,
`ffi_widen_<tag>`, `ffi_<tag>_c_strlen`, `ail_object_<hash>_ffi_<tag>_c_strlen`, ...). Short and
long build directories therefore get different tags. The FFI build saves its generated C as
`entry.c`; the first difference is a declaration such as

```c
/* A */ int64_t ffi_put_7a7acd(ail_bytearray *v_dst, ail_bytes v_src, int64_t v_at);
/* B */ int64_t ffi_put_093756(ail_bytearray *v_dst, ail_bytes v_src, int64_t v_at);
```

where `sha1("/tmp/a/x/examples_ffi_libc_text.py/libc_text.py")[:6] == 7a7acd` and the setup-B path
gives `093756`. The executable then differs in `.symtab` because the names themselves differ.

| program | status | first diff |
|---------|--------|-----------|
| `examples/ffi/libc_text.py` | different | `entry.c` line 5203, absolute path hash |
| `examples/ffi/libm_math.py` | different | `entry.c` line 4113, absolute path hash |
| `examples/ffi/sqlite_count.py` | different | `entry.c` line 4205, absolute path hash |
| `examples/ffi/zlib_check.py` | different | `entry.c` line 4198, absolute path hash |
| `examples/ffi_quick/step1_sqrt.py` | different | `entry.c` line 2877, absolute path hash |

`-ffile-prefix-map` cannot remove this: the tag is a Python-computed identifier, not the C
`__FILE__` macro. The fix belongs at `ail_ffi_lower.py:519`, which is outside this job's edit list
(the only compiler files this job may touch are `python/pkg-v12/cruntime.py`, `filert.py` and
`ir/emit_c.py`). **Named follow-up: `ffrepro4`** — derive the tag from a reproducible program
identity (the module path relative to the build root, or a hash of its contents) instead of
`str(absolute path)`, and keep the generated symbols unique per program.

## Difference classes

The `class` column is what `tools/repro_check.py` names from the first differing C line (or the
first differing ELF section when only the executable differs).

| class | count | file that would emit it | hook that would remove it |
|-------|------:|-------------------------|---------------------------|
| absolute path | **9** | `ail_modules.py:300-305` (`__file__` = `str(mod.path)`; `Program.__init__` resolves it) | `ffrepro3`: reproducible logical path for `__file__` in `ail_chatgpt.py` (see above); `-ffile-prefix-map` does not apply to a runtime literal |
| absolute path hash | **5** | `ail_ffi_lower.py:519` (`sha1(str(path))[:6]` in FFI symbol names) | `ffrepro4`: derive the FFI tag from a reproducible program identity (see above) |
| hash order | 0 | `python/pkg-v12/pyfunc.py` (sets around lines 7, 92, 221, 504, 2109) | sort the set before iterating (line 415 already sorts `kinds`) |
| temporary name | 0 | `c_api.py:253`, `c_export.py:226`, `c_object.py:356`, `c_api_bridge.py:165` (`tempfile` names) | derive the name from the program, not from the temp directory |
| time | 0 | `buildcache.py:152` (`time.time()`), `clockrt.py` | take the clock from `SOURCE_DATE_EPOCH` |
| counter | 0 | `python/pkg-v12/pyfunc.py` (`ctx.tmp += 1` at 1384, 3157) | renumber per function, not per compiler run |
| other | 0 | — | — |

The 14 rows above are the only differences observed in the complete 467-program run; every other
program that built in both setups is identical in both setups.

## Why there are no executable-only differences

The compile/link command recorded in `native_report.json` is

```
/usr/bin/cc -O2 -fno-tree-slp-vectorize -ffp-contract=off -fopenmp-simd
   -Werror=implicit-function-declaration -Werror=implicit-int
   -Werror=incompatible-pointer-types -fno-asynchronous-unwind-tables
   -o <TMPDIR>/ailc-XXXXXXXX/program  <TMPDIR>/ailc-XXXXXXXX/<entry>.c
```

There is no `-g` and no `__FILE__`, `__DATE__` or `__TIME__` in the generated C (grep on
`compare/echo_pack`'s 6282-line `program.c`: no hit), the generated C has a constant file name
inside the temp directory so even the assembler `.file` name is constant, and the linker's
build-id is a hash of the contents. The temp directory name therefore appears only in
`native_report.json`, never in the executable: `strings prog | grep -E '/tmp|ailc-|main.py'` finds
nothing.

The earlier version of this document said that every program with identical C also has an
identical executable, and that was false in the tool as written: for an FFI build it compared two
missing `program.c` files as equal. It now compares the actual generated file (`program.c` or
`entry.c`), so those five rows are reported as C differences and no measured program has identical
C with a different executable. That is a property of this corpus and toolchain, not a proof for
every future FFI symbol or C compiler.

## The 61 programs that were not built

The complete run reports 61 programs as `not built` in both setups (392 identical + 14 different +
61 not built = 467). A two-sided refusal is not a reproducibility result either way; the checker
records it as `not built`, never as `identical`.

The earlier partial pass named 21 of them: 4 compare programs for the reasons already recorded in
`lab/selfhost/DETERMINISM.md` (`chain_relax`: int64 literal out of range; `rail_transfer`: int64
literal, then an untyped tuple element; `tally_lang`: `re.match` pos/endpos; `tree_fold`: untyped
tuple element and `NODE` used as a value); 14 stdlib programs (`array/binary_packets.py`,
`array/float32_readings.py`, `array/unicode_codes.py`, `base64/b85_vectors.py`,
`base64/legacy_stream_api.py`, `collections/log_report.py`, `collections/lru_cache.py`,
`collections/point_records.py`, `csv/field_size_limit.py`, `csv/register_dialect.py`,
`csv/sniffer.py`, `datetime/calendar_export.py`, `datetime/epoch_convert.py`,
`datetime/iso_week.py`); and 3 examples (`examples/algos/run.py`,
`examples/ffi/bindgen/measure.py`, `examples/textcli/gen_big.py`). The rest lie outside the
earlier first-100 subset. All are loud, named refusals in both setups, not one-sided failures.

Limitation: the tool currently puts a named refusal and a traceback under the same `not built`
status. In particular the `tomllib` programs crash under the 1.5 GB/`-j 2` wrapper but build at
`-j 1`, so they are not named refusals. **Named follow-up: `ffrepro5`** — split `refused` from
`crashed` using the stderr (a `path:line:col:` refusal versus a traceback), and rerun the latter
serially before reporting it as `not built`.

## Ratchet

`AIL_CURRENT/test_ail_repro.py` (registered in `AIL_CURRENT/tests.d/test_ail_repro.txt`) builds five
programs from the complete corpus twice in the same two setups and asserts one sha256 for the
executable and one for the generated C, and that both builds print the same bytes and exit the same
way: `stdlib/bisect/alias_import.py`, `stdlib/heapq/closest_points.py`,
`examples/tutorial_project/step1.py`, `examples/algos/rpn.py`, `compare/echo_pack`.

It also has four checker unit tests: a `uint16_t[]` absolute path in the C must be classified
`absolute path` (not `other`); an FFI tag in a symbol must be classified `absolute path hash`; an
FFI `entry.c` must be found when `program.c` is absent, and a build that saved no C must not compare
as equal; and a program that builds in setup A but not in setup B must be a `diff` with `one_sided`,
never a two-sided `refused`. When a program with a difference is fixed, add its row here and to
`PROGRAMS`.

## Follow-up

- **`ffrepro3`: make `__file__` reproducible.** The nine linecache differences above come from the
  absolute source path that `AIL_CURRENT/ail_modules.py:304-305` puts in the `__file__` constant,
  after `AIL_CURRENT/ail_chatgpt.py` resolves the entry path (`source = args.source.resolve()`, lines
  6035/6425). Add a reproducible logical source path there (a `--file-prefix-map <build-dir>=.`
  applied to the compiled-in `__file__`, or record the path as given rather than absolute) and keep
  the value CPython prints for the same command. `-ffile-prefix-map` alone cannot do it: this is a
  runtime string literal, not the C `__FILE__` macro. Then move the nine rows to “identical” and
  name the fix in `DIFFERENCES.md` as `C?-ffrepro3-N`.
- **`ffrepro4`: make the FFI tag reproducible.** Replace `sha1(str(path))[:6]` at
  `AIL_CURRENT/ail_ffi_lower.py:519` with an identity that does not contain the build directory,
  keep symbol uniqueness, and move the five `examples/ffi*` rows to “identical”.
- **`ffrepro5`: separate a refusal from a crash.** Use the stderr shape to keep `not built` truthful
  and rerun limit-induced tracebacks (`tomllib`) serially; they are not named refusals.
- No compiler file was edited by this job: `git diff --stat origin/integ -- AIL_CURRENT` shows only
  the new test module and the measurement tool, so the instruction counts of the 10 compare-lab
  tasks are unchanged by construction.

## Reproducing

```
python3 tools/repro_check.py -j 2 --json /tmp/repro.json           # whole corpus
python3 tools/repro_check.py -j 2 --filter compare/                # the 10 compare programs
python3 tools/repro_check.py -j 2 --filter linecache               # the nine __file__ differences
python3 tools/repro_check.py -j 2 --filter examples/ffi            # the five FFI differences
python3 tools/repro_check.py -j 1 --filter examples/algos/run.py   # a two-sided refusal
python3 -B AIL_CURRENT/test_ail_repro.py                           # the ratchet
```

## Tests run on the final commit

All four required modules, on the final commit (the manifest was regenerated with
`python3 tools/update_manifest.py` and `--check` then exits 0):

| test | result |
|------|--------|
| `AIL_CURRENT/test_ail_repro.py` | **OK**, 6 tests, 36.3 s (5-program build ratchet + four checker tests; registered in `tests.d`) |
| `AIL_CURRENT/test_ail_safetynet.py` | **OK**, 5 tests, 179.2 s, without the shell memory limit (see below) |
| `AIL_CURRENT/test_ail_files.py` | **OK**, 18 tests (1 skipped), 103.1 s, under `ulimit -v 1500000` |
| `AIL_CURRENT/test_ail_corpus_findings3.py` | **OK**, 2 tests, 229.7 s, under `ulimit -v 1500000` |

`test_ail_safetynet` is the one module run without `ulimit -v 1500000`: under that wrapper
`S4_generators_gc` stops after its first line (the reviewer saw the same; it is the wrapper, not
this job — the compiler diff against `origin/integ` is only the new test module and the tool). Run
alone without the limit it passes.

## Probes

No compiler behaviour is changed, so the probes target the checker fixes and the two compiler
paths that the complete run found:

| probe | expected | actual |
|-------|----------|--------|
| `tools/repro_check.py -j 2 --filter examples/ffi` | 5 `diff`, class `absolute path hash`, first differing line `ffi_*_<tag>` / `ail_object_*_ffi_<tag>_*`, executable differs in `.symtab` | matches: 5 C diffs, 0 executable-only, `.symtab` +2164/+1468/+2520/+1828/+798 |
| `tools/repro_check.py -j 2 --filter linecache` | 9 `diff` (absolute path), 1 `identical` | matches, C line 27672/28533 |
| `tools/repro_check.py -j 1 --filter examples/algos/run.py` | two-sided `not built` (named refusal) | matches |
| `python3 -B AIL_CURRENT/test_ail_repro.py` | 6 tests OK incl. the four checker cases | matches |
| `bash ~/tools/cmp.sh /tmp/probes/path_join.py $PWD` (if present) | CPython and both builds agree | same stdout, exit 0/0/0 |

The earlier probe set (`checker_uint16.py`, `path_join.py`) still applies; no compiler file or
program output changed in this fix.
