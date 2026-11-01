# A tcc development build: what it would win, measured

Owner request, 2026-11-01. This page measures and prices a development build that compiles the generated C
with TinyCC (`tcc`) instead of `gcc -O2`. Nothing here changes a default: release builds stay on
`gcc -O2`, and tcc is only ever reached through the `PIPE_CC` shim in `lab/tccdev/`.

## 1. Setup

The Ubuntu 24.04 package is `tcc 0.9.27+git20200814` (2020). It is too old to rely on for this C, so the
measurements use the upstream mob branch instead:

    tcc version 0.9.28rc 2026-10-16 mob@e23dabe (x86_64 Linux)

It was built from the source tree already present in the runner image at `/tmp/tinycc`, commit
`e23dabe` ("stdatomic: fix store argument evaluation and signal fence macros"), with

    ./configure --prefix=/tmp/tcc-install && make -j 2 && make install

`lab/tccdev/measure.py --tcc /tmp/tcc-install/bin/tcc` is the complete run. It takes about 25-30 minutes on
this 4-core runner (the ten tasks, five cold builds per mode, the runtime runs, the per-task checks and the
resident-server runs). `lab/tccdev/results.json` is the raw output of the run below; every median and spread
in this page comes from it.

The runner was shared with other agents. The load average moved between about 0.7 and 4.2 over the run, and
the spreads below show it: the Python front end is the part most sensitive to CPU contention. The
build-phase comparisons are still apples-to-apples because `gcc` and `tcc` were measured in the same loop,
but the absolute wall times, especially `berth_sim`, are higher than on an idle runner. A first complete run
on the same machine before the busiest period gave lower absolute totals (for example `chain_relax`
1.33 s gcc, 1.18 s tcc); the conclusion did not change.

## 2. Cold compile time, gcc -O2

`gcc total` is one cold `ail_chatgpt.py compile` with `AIL_SERVER=0`, a fresh `AIL_CACHE` and `TMPDIR`.
`front` is that same build with a shim that splits the driver call into `gcc -c` and a link, so
`front = wall - compile - link`; `compile` is `gcc -c`, `link` is the driver's link step. All values are
medians of five runs in seconds; the brackets are min-max. `bound` is Amdahl's limit for this task: even a
free C compiler leaves the front end, so the best possible total is `front` and the best possible speedup is
`total / front`.

| task | gcc total | AIL front end | gcc -c | link | front share | bound |
|---|---:|---:|---:|---:|---:|---:|
| berth_sim | 4.845 [4.793-5.041] | 4.230 [4.045-4.312] | 0.878 [0.858-0.944] | 0.012 | 87% | 1.21x |
| chain_relax | 1.752 [1.381-1.874] | 1.572 [1.545-1.603] | 0.491 [0.463-0.503] | 0.020 | 90% | 1.33x |
| echo_pack | 1.906 [1.854-1.998] | 2.172 [1.745-2.448] | 0.453 [0.346-0.476] | 0.017 | 114%* | 1.22x |
| ledger_bin | 1.975 [1.946-2.076] | 1.462 [1.456-1.495] | 0.633 [0.617-0.643] | 0.012 | 74% | 1.44x |
| rail_transfer | 2.397 [2.270-2.757] | 1.604 [1.510-1.769] | 1.016 [0.996-1.281] | 0.018 | 67% | 1.65x |
| scar_life | 1.993 [1.387-2.061] | 1.268 [1.129-1.751] | 0.560 [0.409-0.583] | 0.016 | 64% | 1.47x |
| tally_lang | 2.069 [2.033-2.127] | 1.371 [1.345-1.452] | 0.758 [0.739-0.797] | 0.012 | 66% | 1.56x |
| term_rank | 1.907 [1.873-1.960] | 1.191 [1.177-1.202] | 0.874 [0.848-0.887] | 0.013 | 62% | 1.74x |
| ticket_audit | 2.764 [2.707-2.816] | 1.571 [1.563-1.623] | 1.344 [1.311-1.385] | 0.013 | 57% | 1.86x |
| tree_fold | 2.876 [2.831-2.927] | 1.978 [1.928-2.064] | 1.020 [0.973-1.044] | 0.013 | 69% | 1.53x |

\* `echo_pack`'s split build ran during a load spike; its front estimate is above its plain total. The
front-share column uses the plain total; the bound uses the split total (`split_total / front`, which is
why it is 1.22x rather than below 1). The medians across tasks are 2.03 s gcc total, 1.57 s front, and a
front share of 68%. The link is 12-20 ms in every task and is not worth optimising.

The C compiler (compile plus link) is 17-47% of the cold build, median about 33%. The front end, the Python
work up to the emitted C, is the other two thirds and never goes away when the C compiler changes.

## 3. tcc build

The same AIL command with `PIPE_CC` running `tcc`; the generated C is prepended with
`lab/tccdev/tcc_prelude.h` (see section 5). `tcc -c` and the link are timed separately, then the whole build
is timed as `tcc total`. `C saved` is `gcc -c + link - tcc -c - tcc link`; `measured saved` is the
difference of the two total columns, including front-end noise. All values are medians of five runs.

| task | tcc -c | tcc link | tcc total | C saved | measured saved | tcc/gcc total |
|---|---:|---:|---:|---:|---:|---:|
| berth_sim | 0.007 | 0.002 | 4.636 [4.111-10.174] | 0.881 | 0.209 | 0.96x |
| chain_relax | 0.009 | 0.003 | 1.627 [1.614-1.655] | 0.499 | 0.125 | 0.93x |
| echo_pack | 0.005 | 0.002 | 1.972 [1.764-2.712] | 0.463 | -0.066 | 1.03x |
| ledger_bin | 0.008 | 0.002 | 1.496 [1.481-1.609] | 0.635 | 0.479 | 0.76x |
| rail_transfer | 0.012 | 0.004 | 1.658 [1.624-1.710] | 1.018 | 0.739 | 0.69x |
| scar_life | 0.012 | 0.003 | 1.864 [1.754-1.877] | 0.561 | 0.129 | 0.94x |
| tally_lang | 0.009 | 0.002 | 1.400 [1.384-1.461] | 0.759 | 0.669 | 0.68x |
| term_rank | 0.009 | 0.002 | 1.246 [1.229-1.264] | 0.876 | 0.661 | 0.65x |
| ticket_audit | 0.009 | 0.002 | 1.621 [1.582-1.647] | 1.346 | 1.143 | 0.59x |
| tree_fold | 0.009 | 0.002 | 2.044 [1.989-2.111] | 1.022 | 0.832 | 0.71x |

`tcc -c` is 5-12 ms against 0.35-1.34 s for `gcc -c`; the link is 2-4 ms. The C compiler part is gone. What
remains is the front end, exactly as the Amdahl bound said: the best measured total in this run is
`term_rank` at 1.25 s (bound 1.74x) and `ticket_audit` at 1.62 s (bound 1.86x). Across the ten tasks the sum
of the medians falls from 24.48 s to 19.56 s, about 20%; the median task falls from 2.03 s to 1.64 s.
That is 1.2-1.9x, not the 4-10x needed for Rust's 0.4-0.5 s. The measured `saved` column is noisier than
`C saved` because front-end time moved between the gcc and tcc phases; `C saved` is the part a compiler
swap can actually control.

### Runtime and correctness

`run` is the median of five runs on the task's performance input; `ratio` is tcc/gcc. The correctness
columns are the task's own `gen.py` cases compared with `reference.py` (three public, all hidden).

| task | gcc run ms | tcc run ms | ratio | stdout+exit same | checks public | checks hidden |
|---|---:|---:|---:|---|---:|---:|
| berth_sim | 2838 | 4840 | 1.71x | yes | 3/3 | 23/23 |
| chain_relax | 893 | 2406 | 2.69x | yes | 3/3 | 29/29 |
| echo_pack | 638 | 2799 | 4.39x | yes | 3/3 | 54/54 |
| ledger_bin | 556 | 4576 | 8.24x | yes | 3/3 | 52/52 |
| rail_transfer | 1038 | 3052 | 2.94x | yes | 3/3 | 21/21 |
| scar_life | 20424 | 122411 | 5.99x | yes | 3/3 | 50/50 |
| tally_lang | 800 | 6063 | 7.58x | yes | 3/3 | 72/72 |
| term_rank | 1440 | 4316 | 3.00x | yes | 3/3 | 40/40 |
| ticket_audit | 1105 | 4058 | 3.67x | yes | 3/3 | 88/88 |
| tree_fold | 1235 | 3249 | 2.63x | yes | 3/3 | 52/52 |

Every tcc binary printed byte-identical stdout and returned the same exit code as the gcc binary on the
performance input, and both binaries passed every public and hidden check (511 cases in total, zero
failures). So a tcc build is *correct* on this corpus; it is just 1.7-8.2x slower at run time because tcc
does no optimisation, and the AVX2/`__builtin_ia32` fast paths are compiled out (tcc does not define
`__GNUC__`, and the generated C already guards them).

## 4. The resident server

Server mode (`AIL_SERVER_DIR`, idle 30 s; #300/srvdef1) was measured with a cold server and then five warm
builds using the same server directory. Medians of the warm runs, min-max in brackets.

| task | gcc cold | gcc warm | tcc cold | tcc warm |
|---|---:|---:|---:|---:|
| berth_sim | 5.148 | 5.389 [5.192-5.437] | 4.538 | 4.968 [4.612-7.078] |
| chain_relax | 1.614 | 1.257 [1.129-1.634] | 1.129 | 1.433 [1.065-1.470] |
| echo_pack | 1.888 | 1.826 [1.779-3.751] | 1.792 | 1.726 [1.634-1.797] |
| ledger_bin | 2.088 | 2.058 [2.017-2.147] | 1.661 | 2.567 [1.632-3.228] |
| rail_transfer | 2.768 | 1.763 [1.472-2.694] | 1.511 | 1.390 [1.334-1.495] |
| scar_life | 1.382 | 1.570 [1.512-1.604] | 1.105 | 1.314 [1.302-1.390] |
| tally_lang | 2.051 | 1.992 [1.984-2.020] | 1.418 | 1.404 [1.399-1.411] |
| term_rank | 2.053 | 1.982 [1.893-2.036] | 1.299 | 1.249 [1.218-1.275] |
| ticket_audit | 2.813 | 2.773 [2.747-2.798] | 1.592 | 1.614 [1.587-1.634] |
| tree_fold | 2.986 | 2.985 [2.955-3.014] | 2.076 | 2.117 [2.090-2.156] |

Server mode saves little on these programs: gcc warm is typically 0-5% below gcc cold, with
`rail_transfer` the outlier at 36% (2.77 s -> 1.76 s) and `scar_life` above its cold value; several tcc
warm runs are also above tcc cold because of the shared runner. The best combination is tcc with a warm server: `term_rank`
1.25 s, `rail_transfer` 1.39 s, `tally_lang` 1.40 s, `scar_life` 1.31 s, `chain_relax` 1.06-1.43 s. That is
the closest any combination gets to 0.5 s in this run, and it is still about 2-3x away. On the quieter first
run the same script saw `chain_relax` at 0.99 s and `rail_transfer` at 0.97 s warm with tcc, still about 2x
0.5 s. The front end, not Python startup alone, is the remaining cost.

## 5. GCC-only constructs and the cost of guards

The ten generated programs total 3.39 MB of C. Counts are occurrences over all ten:

| construct | count | tcc 0.9.28 | guard needed? |
|---|---:|---|---|
| `__builtin_add_overflow` / `sub` / `mul` | 24 / 24 / 24 | not implemented; link fails with `unresolved reference to '__builtin_add_overflow'` | **yes**, `__TINYC__` prelude (below) |
| `__builtin_expect` | 351 | accepted | no |
| `__builtin_unreachable` | 90 | accepted | no |
| `__builtin_constant_p` | 20 | accepted | no |
| `__builtin_memcpy` | 7 | accepted | no |
| `__builtin_clz` / `__builtin_clzll` | 20 / 1 | accepted | no |
| `__attribute__` (noinline, noreturn, always_inline, cold, unused, returns_twice) | 528 | accepted/ignored | no; `always_inline` is ignored, which is part of the run-time loss |
| `__typeof__` | 10 | accepted | no |
| statement expressions `({ ... })` | 247 | accepted | no |
| `vector_size`, `may_alias`, `target("avx2")`, `__builtin_ia32_pmovmskb256`, `__builtin_cpu_supports` / `_init` | 14 / 7 / 7 / 7 / 7+7 | not used: the C already guards them with `defined(__GNUC__)`; tcc does not define `__GNUC__` | no new guard; scalar fallback already exists |
| fast setjmp/longjmp assembly | one block | skipped by the same `defined(__GNUC__)` guard | no new guard; libc `setjmp` fallback already exists |
| `_Generic` | one typedef | accepted | no |

Only the three checked-overflow builtins actually break the build. `lab/tccdev/tcc_prelude.h` replaces them
with portable `int64_t` helpers. It is measurement-only and is not part of any normal build. The helpers:
`add`/`sub` use the unsigned wrap and the sign-bit test; `mul` handles 0, `-1`, `INT64_MIN` and the four
quadrants explicitly. All call sites in the generated C pass `int64_t` values and an `int64_t *` result, so
the fallback's width matches the builtin. Compiling the same C with `gcc -O2 -D__TINYC__` (forced prelude)
versus plain `gcc -O2` changed run time by -1.6% to +11.8% (median +5.9%) on these tasks; the extra compile
cost was inside the noise (for example 0.906 s vs 0.925 s on `berth_sim`). A tcc build is already 1.7-8.2x
slower at run time, so this guard is not what makes it slow.

## 6. Recommendation

**Do not build a `--dev` tcc mode as a way to reach Rust's cold-compile time, and do not make it a default.**
The measurements say the C compiler is only 17-47% (median 33%) of a cold AIL build. Swapping in tcc removes
almost all of that 0.35-1.35 s, but leaves the 1.2-4.2 s front end untouched: the Amdahl bound is 1.21-1.86x
per task, and the measured median total is 2.03 s -> 1.64 s. Rust at 0.4-0.5 s needs a 4-10x cut, which no C
compiler can supply. The cost is also real: tcc binaries are 1.7-8.2x slower (8.2x on `ledger_bin`, 5.99x on
`scar_life`), so a developer would be trading a sub-second build win for a much slower program.

If an opt-in `--dev` mode is wanted anyway for edit-and-run loops, it should be a separate flag that writes
the prelude and invokes tcc through the same `PIPE_CC` path used here, with the slower run time stated in
`--help`. It should reuse the existing `__GNUC__` guards and the prelude in `lab/tccdev/tcc_prelude.h`, and
keep `gcc -O2` as the release path. But it does not close the gap.

To get near 0.5 s cold, the work has to go into the front end and the build protocol:

1. keep the resident server and measure it as the default path (it removes interpreter start-up and imports,
   worth a few percent on most tasks and up to 36% on `rail_transfer` in this run);
2. cache the front-end result (emitted C, or the IR before it) by source hash and flags, so an unchanged
   edit does not re-run the whole Python lowering; the 3.39 MB of C and 1.2-4.2 s of Python per build are
   the target;
3. only then combine that cache with tcc (5-12 ms compile, 2-4 ms link) for the C stage.

Even server + tcc is 1.1-2.1 s on eight of the ten tasks in this run (`berth_sim` 4.97 s). The gap to
0.4-0.5 s is front-end work, not the C compiler.
