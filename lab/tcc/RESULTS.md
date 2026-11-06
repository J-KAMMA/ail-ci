# tcc1 — quick-run probe: AIL's generated C with TinyCC instead of gcc -O2

Measured 2026-11-06 on the 4-core GitHub Actions runner (Ubuntu 24.04), on
`job-tcc1-11070326`. Nothing in the compiler, runtime or default build is changed: tcc is only ever
invoked by `lab/tcc/run.py`, directly on the saved C or through `PIPE_CC`. Release builds stay on
`gcc -O2`.

- **tcc (apt, as asked):** `tcc version 0.9.27 (x86_64 Linux)`, package
  `0.9.27+git20200814.62c30a4a-1` — the Ubuntu 24.04 package.
- **tcc (upstream):** `tcc version 0.9.28rc 2026-10-16 HEAD@e23dabed (x86_64 Linux)`, built from
  `TinyCC/tinycc` at `e23dabe` with `./configure --prefix=/tmp/tcc-install && make -j2 && make install`.
  The apt package is from 2020 and is too old to be a candidate; this is the version `lab/tccdev`
  used, reported separately so the two are not confused.
- gcc `13.3.0`, python `3.12.3`. 3 cold builds and 3 runs per program, median.
- Sample: the ten `lab/compare/src/<task>/main.py` sources and 50 `corpus/gdev` programs
  (seed 20261106, shuffled; 54 candidates tried until 50 built with `gcc -O2`). Two compare sources
  are refused by AIL itself (`tally_lang`: `field 'v' is a list or dict that gets bools and numbers`,
  plus tuple-shape-comparison and `re` notes; `tree_fold`: `import of 're' with a use that is not
  built`, plus `cannot tell the type of element 0 of this tuple` notes at lines 44/72/85/89), so 8 compare programs enter the
  census. Four corpus candidates were also refused
  and replaced. Total: **58 programs**.

`run.py` generates each program's C once through `ail_chatgpt.py compile --debug-dir` (which writes
the exact translation unit and the recorded compiler command line), then builds that same C with
gcc -O2, gcc -O0 and tcc. The tcc builds use only `-I/-D/-L/-O/-g/-l` (gcc-only flags dropped) and,
for the prelude variant, prepend `lab/tcc/tcc_prelude.h`. Multi-unit programs compile each unit with
`-c` and link, as the build does.

## The numbers

| | apt tcc 0.9.27 | upstream 0.9.28rc | 0.9.28rc + prelude |
|---|---:|---:|---:|
| generated C that builds (58 programs) | **0** | **5** | **35** |
| … of the 8 compare `main.py` | 0 | 0 | **2** |
| … of the 50 corpus | 0 | 5 | **33** |
| byte-identical stdout/stderr/exit to gcc -O2 | — | 5/5 | **35/35** |
| wrong output | 0 | 0 | **0** |
| median C-compile wall (the 35 that build) | n/a | n/a | **0.026 s** |
| gcc -O2 / gcc -O0 on the same C | 3.1217 s | 0.8283 s | — |

On the 35 that tcc builds, the C compiler part is **121x faster than gcc -O2** (median 3.12 s →
0.026 s) and 32x faster than gcc -O0. Every one of the 35 printed the same bytes and returned the
same exit status as the gcc -O2 binary on the public case (or no input, for a corpus program). The
run is slower: median 3.4 ms vs 2.0 ms (**1.7x**), because tcc does no optimisation.

The runner was shared and loaded: a repeated single-program check measured `berth_sim` gcc -O2 at
1.2079 s, against 2.8022 s in this run. Absolute times are inflated about 2.3x; the ratios are the
stable part.

## Blocker list (first error per program, grouped and counted)

tcc stops at its first error, so each program is counted once under the construct that stopped it;
these are lower bounds on the incompatible constructs per file.

**apt tcc 0.9.27 — 0/58** (this tcc cannot be used at all):

| construct | count | generated C / emitted by |
|---|---:|---|
| C11 `_Thread_local` storage class | 41 | `static _Thread_local void *ail__rep_stk[512];` — `cruntime.py:17347-17348` (repr stack), `jsonrt.py:858`. 0.9.27 has no TLS (`__thread` fails too); fixed in 0.9.28rc. |
| unsized struct-array compound literal from runtime values | 6 | `ail_stdout_parts((ail_str[]){a, b}, 2);` — `pyfunc.py:24977` (f-string print call site). tcc: `index too large`. |
| unsized struct-array declaration from runtime values | 5 | `ail_bytes spans[] = {h, old, repl};` — `cruntime.py:6450,6508,6538` (bytes replace/translate). tcc: `index too large`. |
| unsupported `__builtin_*` | 4 | `__builtin_unreachable` / `__builtin_*_overflow`. |
| `__int128` | 2 | `ail__idiv_exact` / the general runtime's 128-bit sites (see below). |

**upstream 0.9.28rc, no prelude — 5/58:**

| construct | count | note |
|---|---:|---|
| unsupported `__builtin_*` | 30 | link: `unresolved reference to '__builtin_{add,sub,mul}_overflow'`. The prelude fixes these. |
| `__int128` | 23 | see below; in the sampled corpus programs the first stop is `ail__idiv_exact`. |

**upstream 0.9.28rc + prelude — 35/58.** The only remaining blocker is **`__int128` (23 programs:
6/8 compare, 17/50 corpus)**. In the corpus-blocked programs sampled (`g03_030`, `g11_038`,
`g11_026`) the first error is `'__uint128_t' undeclared` / `cannot convert 'unsigned long' to
'struct __uint128__'` at `__uint128_t num, den;` / `(__uint128_t)ua << shift` inside
`ail__idiv_exact`, `cruntime.py:3835-3844` — the exactly-rounded int `/` helper, which the typed
path emits and calls. On the general path (`chain_relax`) the first error is the range slice
`__int128 nn = (__int128)n;` at `cruntime.py:16995`. The general runtime's other 128-bit sites are
int-only `pow` (`cruntime.py:19127-19143`, `29615-29622`), random `randrange`/floordiv
(`29811-29819`) and the sum reducers (`31094`). tcc has no 128-bit integer
type and no `__int128` mode. 0.9.28rc already parses `_Thread_local`, the `__attribute__`s,
statement expressions, `__typeof__`, `__builtin_expect/unreachable/constant_p/memcpy/clz`, and the
sized aggregate forms; the `vector_size`/`avx2` paths are already `#if defined(__GNUC__)`-guarded,
so they never fire.

`lab/tcc/tcc_prelude.h` is the measurement-only shim: portable `int64_t` add/sub/mul overflow
helpers behind `#ifdef __TINYC__`. It was checked against GCC's builtins over 588 boundary cases
(0, ±1, ±2, `INT64_MIN/MAX`, and near-boundary pairs) — identical output.

## C compile and run, per program (median of 3)

| program | kind | C KiB | gcc -O2 s | gcc -O0 s | tcc s | gcc run ms | tcc run ms | same |
|---|---|---:|---:|---:|---:|---:|---:|---|
| berth_sim | compare | 391 | 2.8022 | 1.5350 | 0.0410 | 2.2 | 3.4 | yes |
| echo_pack | compare | 322 | 1.0762 | 0.6919 | 0.0197 | 3.0 | 3.2 | yes |
| g17_004 | corpus | 568 | 1.8667 | 0.5388 | 0.0257 | 2.1 | 3.9 | yes |
| g05_030 | corpus | 579 | 3.3376 | 0.6925 | 0.0212 | 1.5 | 3.5 | yes |
| g14_014 | corpus | 604 | 3.0402 | 0.7239 | 0.0209 | 1.5 | 3.5 | yes |
| g00_034 | corpus | 694 | 3.9019 | 1.5464 | 0.0315 | 1.8 | 3.4 | yes |
| g18_008 | corpus | 210 | 0.5976 | 0.4241 | 0.0111 | 1.5 | 1.5 | yes |
| g00_036 | corpus | 137 | 0.2086 | 0.2544 | 0.0079 | 1.5 | 1.4 | yes |
| g04_006 | corpus | 568 | 3.2518 | 0.7230 | 0.0198 | 1.5 | 1.4 | yes |
| g14_004 | corpus | 586 | 2.4156 | 0.5774 | 0.0423 | 1.5 | 3.6 | yes |
| g19_028 | corpus | 205 | 1.1427 | 0.5454 | 0.0182 | 2.0 | 1.4 | yes |
| g02_014 | corpus | 755 | 3.8961 | 1.3816 | 0.0659 | 1.4 | 4.0 | yes |
| g23_036 | corpus | 627 | 3.9190 | 0.8989 | 0.0331 | 2.5 | 3.5 | yes |
| g10_010 | corpus | 604 | 3.7630 | 0.8149 | 0.0216 | 3.6 | 3.3 | yes |
| g20_008 | corpus | 723 | 4.7198 | 1.7833 | 0.0519 | 2.5 | 4.0 | yes |
| g13_008 | corpus | 617 | 4.1999 | 0.9968 | 0.0217 | 1.5 | 2.9 | yes |
| g23_030 | corpus | 943 | 4.1396 | 1.7443 | 0.1319 | 1.5 | 2.9 | yes |
| g08_014 | corpus | 585 | 3.4816 | 1.2129 | 0.0449 | 2.1 | 2.8 | yes |
| g04_004 | corpus | 567 | 2.7458 | 0.7949 | 0.0202 | 2.1 | 3.5 | yes |
| g22_006 | corpus | 37 | 0.1616 | 0.1270 | 0.0117 | 3.7 | 2.9 | yes |
| g23_004 | corpus | 560 | 2.6520 | 0.8639 | 0.0207 | 2.4 | 3.1 | yes |
| g11_008 | corpus | 563 | 3.1217 | 1.0377 | 0.0443 | 2.9 | 2.9 | yes |
| g06_020 | corpus | 587 | 3.1039 | 0.8330 | 0.0265 | 3.4 | 3.5 | yes |
| g13_026 | corpus | 608 | 2.9312 | 0.8432 | 0.0442 | 1.4 | 1.4 | yes |
| g06_034 | corpus | 696 | 3.5696 | 0.8283 | 0.0486 | 1.5 | 3.7 | yes |
| g00_000 | corpus | 164 | 0.4721 | 0.4120 | 0.0084 | 2.8 | 1.9 | yes |
| g11_000 | corpus | 183 | 0.5045 | 0.4248 | 0.0217 | 15.7 | 33.3 | yes |
| g18_000 | corpus | 264 | 0.7582 | 0.6804 | 0.0258 | 1.5 | 1.4 | yes |
| g16_012 | corpus | 629 | 3.7010 | 1.0727 | 0.0459 | 1.4 | 5.0 | yes |
| g20_036 | corpus | 601 | 4.1864 | 1.4912 | 0.0228 | 3.9 | 3.5 | yes |
| g08_028 | corpus | 571 | 5.9209 | 1.4110 | 0.0678 | 1.6 | 4.1 | yes |
| g21_016 | corpus | 632 | 5.1138 | 1.3840 | 0.0499 | 3.5 | 7.6 | yes |
| g05_022 | corpus | 570 | 3.6966 | 0.8191 | 0.0449 | 1.5 | 4.1 | yes |
| g10_006 | corpus | 632 | 5.1822 | 1.1727 | 0.0499 | 1.5 | 1.5 | yes |
| g00_038 | corpus | 183 | 0.5586 | 0.5854 | 0.0094 | 2.4 | 2.8 | yes |

Medians over the 35: gcc -O2 **3.1217 s**, gcc -O0 **0.8283 s**, tcc **0.0258 s**; run **2.0 ms**
(gcc) vs **3.4 ms** (tcc). Emitted C is 38.7 MB for the 58 programs (median 616 KiB).

## The edit-run loop (the headline)

Full AIL `compile` (Python front end + C compiler) followed by a run on the small input (the first
public `gen.py` case, or no input for a corpus program). Cold: fresh `AIL_CACHE` each repetition.
Warm: the same source rebuilt from the existing `AIL_CACHE`. Repetitions: 2 (median). Measured on
the 14 tcc-buildable programs taken in sample order (2 compare + 12 corpus); the rest are censused
but not timed.

| program | kind | gcc cold s | gcc warm s | tcc cold s | tcc warm s | gcc edit+run s | tcc edit+run s | speedup |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| berth_sim | compare | 16.722 | 0.530 | 14.267 | 0.798 | 16.725 | 14.270 | 1.17x |
| echo_pack | compare | 3.729 | 0.719 | 3.248 | 0.582 | 3.733 | 3.252 | 1.15x |
| g17_004 | corpus | 3.582 | 0.288 | 1.632 | 0.284 | 3.583 | 1.634 | 2.19x |
| g05_030 | corpus | 5.932 | 0.560 | 2.972 | 0.608 | 5.934 | 2.976 | 1.99x |
| g14_014 | corpus | 4.363 | 0.378 | 2.107 | 0.512 | 4.368 | 2.108 | 2.07x |
| g00_034 | corpus | 15.324 | 1.949 | 11.969 | 2.416 | 15.326 | 11.970 | 1.28x |
| g18_008 | corpus | 1.815 | 0.285 | 1.019 | 0.270 | 1.817 | 1.020 | 1.78x |
| g00_036 | corpus | 0.903 | 0.279 | 1.424 | 0.363 | 0.905 | 1.426 | 0.63x |
| g04_006 | corpus | 4.763 | 0.395 | 1.941 | 0.337 | 4.764 | 1.942 | 2.45x |
| g14_004 | corpus | 3.976 | 0.360 | 1.968 | 0.496 | 3.978 | 1.971 | 2.02x |
| g19_028 | corpus | 4.477 | 0.704 | 4.063 | 1.095 | 4.478 | 4.065 | 1.10x |
| g02_014 | corpus | 8.989 | 0.367 | 5.542 | 0.464 | 8.993 | 5.547 | 1.62x |
| g23_036 | corpus | 7.654 | 0.399 | 4.698 | 0.417 | 7.656 | 4.701 | 1.63x |
| g10_010 | corpus | 6.104 | 0.522 | 2.873 | 0.794 | 6.108 | 2.877 | 2.12x |

Medians: gcc cold **4.620 s**, tcc cold **2.923 s**; edit+run **4.621 s → 2.926 s**, a **1.58x**
ratio of medians (median per-program speedup **1.70x**, range 0.63-2.45x). Two program outputs are
the same in both builds. The gains are uneven: the tcc/gcc cold ratio in the table runs 41-158%
(median 59%), with `g00_036` the 158% case where the fixed Python front end dominates and tcc is
slower. Where the C stage dominates (`g17_004`,
`g04_006`, `g10_010`, 41-47%) tcc roughly halves the build, and where the front end dominates
(`berth_sim`, `g19_028`, 85-91%) or the program is small (`g00_036`, where tcc is slower) it is a
wash or worse.

**Cached re-run:** with the build cache warm, gcc is 0.397 s and tcc 0.504 s (medians). The cache
stores the finished front end + executable, so the C compiler is not run at all; tcc has nothing to
win on an unchanged rebuild. The tcc advantage exists only on a cold build (the first build after an
edit).

## Would a `--quick` mode be worth it?

For the programs that tcc can build, yes as an opt-in loop mode, but the win is modest and the scope
is limited. Swapping the C compiler removes essentially all of the C stage (3.12 s → 0.026 s, 121x)
and makes the **cold** edit-run **1.6-1.7x** faster (4.62 s → 2.93 s median); it does not change the
warm/cached build (both ~0.4-0.5 s) and it makes the program **1.7x slower** at run time, so it is
only defensible for the loop, never the final build. It is not the 4-10x the owner wants, because
the Python front end is a fixed cost: tcc's cold build is 41-158% of gcc's (median 59%, the 158%
being `g00_036`, where tcc is slower).

The blockers divide into cheap and expensive:

- **`__builtin_{add,sub,mul}_overflow`** — free: a `#if defined(__TINYC__)` prelude or fallback in
  `cruntime.py` (the shim here is 30 lines and was checked over 588 boundary cases). This is the
  only construct that stops raw 0.9.28rc.
- **apt tcc 0.9.27** — unusable: no `_Thread_local`, unsized runtime aggregates, no builtins. A
  quick mode must pin 0.9.28rc or later (the repo already documents building it).
- **`__int128`** — the real cost. It blocks **23/58 programs, including 6/8 compare `main.py`
  tasks**, and it cannot be shimmed by a header: tcc has no 128-bit type. Removing it means either a
  two-word int64 fallback for the exactly-rounded int division (`ail__idiv_exact`, a 55-bit quotient
  with a sticky remainder), the general runtime's range-slice and int-`pow` paths behind an `#if`
  (a correct signed 128-bit add/sub/mul/div/mod/compare, i.e. real code in `cruntime.py`, not a
  per-construct `#if` one-liner), or a different backend. Until that exists, a quick-run mode can
  only cover the typed-path subset — which is exactly the 33/50 corpus programs and 2/8 compare
  `main.py` that built here, not the general-path programs.

Recommendation: do not make tcc a default and do not sell it as the compile-time fix. If a
`--quick` flag is wanted for the edit loop, gate it on `__int128`-free output, add the overflow
prelude, pin tcc 0.9.28+, and state the slower run time in `--help`; the bigger win remains the
front-end/build cache (warm builds are already ~0.4 s).

## What this says and does not

- Two of the ten compare `main.py` sources (`tally_lang`, `tree_fold`) are refused by AIL before any
  C compiler is involved; they are outside this question.
- `main.py` is the general path and emits the full general runtime, including `__int128` for range
  slicing and int `pow`. The typed path (`typed.py`/`main.ail`) avoids those two, but it still emits
  `ail__idiv_exact` (with `__int128` for the 55-bit quotient) when the program divides ints; that
  helper is the first stop in the sampled corpus programs. `lab/tccdev` measured all
  ten typed programs building with 0.9.28rc + prelude, and this run's 33 corpus successes are the
  same story on the subset that used neither. So the blocker is the runtime's
  128-bit arithmetic, not tcc's parser.
- One tcc version was tested for timing (0.9.28rc at `e23dabe`). Nothing here says a later tcc fixes
  `__int128`; it has no such type today.
- Output equality is checked on the public case / no input, not on every hidden case. `lab/tccdev`
  already checked all public and hidden cases for the ten typed programs with the same tcc and
  found zero failures.
- Absolute times are inflated by runner load (~2.3x on a repeated check); ratios are the stable
  part.

## Probes run

No compiler or runtime behaviour was changed, so the `cmp.sh` loop (AIL program vs CPython) does not
apply to the measurement itself. Two kinds of probe were run:

| probe | what it checks | result |
|---|---|---|
| `/tmp/probes/overflow_prelude.c` | `tcc_prelude.h`'s add/sub/mul overflow helpers vs GCC's native builtins over 588 boundary combinations (0, ±1, ±2, `INT64_MIN/MAX`, near-boundary) | **588/588 identical** (tcc+prelude vs gcc) |
| `/tmp/probes/classify_probe.py` | the failure classifier maps each real tcc error (int128, builtin, `_Thread_local`, both unsized forms, vector, asm, link) to the right bucket; tcc flag filter drops gcc-only flags and gcc -O0 swaps `-O2` | **13/13 checks** |
| `/tmp/probes/fidelity_probe.py` | the C handed to the compiler equals `--debug-dir/program.c` (sha256); rebuilding it with the recorded gcc -O2 flags and with tcc+prelude reproduces the AIL binary's stdout and exit | **all OK** (`ff076ffc…` both ways) |
| `bash ~/tools/cmp.sh corpus/gdev/g18_008.py`, `g04_006.py` | sanity: the AIL compiler's own output still matches CPython on the general and default builds | both `same stdout`, both modes, exit 0 |

## Reproduce

```
sh lab/tcc/run.sh --out /tmp/tcc.json --runs 3 --ail-runs 2 --ail-limit 12
# or: python3 lab/tcc/run.py --tcc-apt /usr/bin/tcc \
#       --tcc-upstream /tmp/tcc-install/bin/tcc --excerpts lab/tcc
```

`lab/tcc/run.sh` installs the apt package and builds 0.9.28rc if `/tmp/tcc-install/bin/tcc` is
missing. `lab/tcc/tcc.yml` is the proposed workflow (not installed by the worker). Raw results:
`/tmp/tcc-full.json` (not committed; regenerate with the command above). `fail_*.txt` holds one
diagnostic per (variant, blocker).
