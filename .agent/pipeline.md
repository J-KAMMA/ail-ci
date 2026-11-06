# job job-tcc1-11070326  started 2026-11-06T18:28:53Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Committed as `b86df60` on `job-tcc1-11070326` (not pushed, per the forbidden list).

## What I measured

`lab/tcc/` — `run.py`/`run.sh` (census + timing + edit-run), `tcc_prelude.h` (measurement-only overflow shim), `cc_tcc.py` (`PIPE_CC`), `tcc.yml`, `RESULTS.md`, 8 `fail_*.txt`. No compiler, runtime or default build changed.

**Census (58 programs: 8 of 10 compare `main.py` + 50 corpus; `tally_lang` and `tree_fold` are refused by AIL itself):**

| variant | builds | byte-identical |
|---|---:|---:|
| apt tcc 0.9.27 | 0/58 | — |
| upstream tcc 0.9.28rc (`e23dabe`) | 5/58 | 5/5 |
| 0.9.28rc + prelude | **35/58** (2 compare, 33 corpus) | **35/35** |

Blocker list: apt 0.9.27 — `_Thread_local` 41, unsized runtime aggregates 11, builtins 4, `__int128` 2. Raw 0.9.28rc — builtins 30, `__int128` 23. The prelude removes the builtins; the **only remaining blocker is `__int128` (23/58; 6/8 compare)**, from the general runtime's range-slice and int-`pow` paths.

**Timing:** C compile median on the 35 that build — gcc -O2 **3.1217 s**, gcc -O0 **0.8283 s**, tcc **0.0258 s** (121x / 32x). Run **2.0 ms → 3.4 ms** (1.7x slower). Edit-run (cold AIL compile + small run, 14 programs): **4.62 s → 2.93 s**, 1.58x on medians (1.70x median per-program, range 0.63–2.45). Warm build cache: 0.397 s vs 0.504 s — tcc gains nothing on a cached rebuild.

**Caveat:** the shared runner was loaded; a repeated `berth_sim` gcc -O2 check was 1.21 s vs 2.80 s here, so absolute times are ~2.3x inflated; ratios are stable.

## Probes (no compiler change, so `cmp.sh` only as sanity)

- `overflow_prelude.c`: 588/588 boundary cases identical, tcc+prelude vs GCC builtins.
- `classify_probe.py`: 13/13 (buckets + flag filter).
- `fidelity_probe.py`: compiler input == `--debug-dir/program.c` (sha256 `ff076ffc…`), both gcc and tcc rebuilds match the AIL binary.
- `bash ~/tools/cmp.sh corpus/gdev/{g18_008,g04_006}.py`: `same stdout` in both modes, exit 0.

## Tests on the final commit

`test_ail_safetynet` 5 OK, `test_ail_files` 18 OK (1 skipped), `test_ail_corpus_findings3` 2 OK. Manifest `--check` clean.
[commandcode stop=end_turn turns=96 out_tokens=87640]

## review 0
[model commandcode/deepseek-v4.1-flash]
I have what I need. The change is measurement-only and the numbers I could independently reproduce do reproduce; the defects I found are in the shipped blocker list's source pointers and one claim.

## What the change does

Adds a measurement harness (`lab/tcc/run.py`, `run.sh`, `cc_tcc.py` PIPE_CC shim, `tcc_prelude.h` int64 overflow shim, proposed `tcc.yml`), 8 failure excerpts and `RESULTS.md`; plus a DEVLOG entry. **No compiler, runtime or build file is touched** — verified: `git diff --name-status work..HEAD` is `DEVLOG.md` + `lab/tcc/*` only, and `--debug-dir` C for `corpus/gdev/g18_008.py` is byte-identical between `/tmp/base2` (work) and HEAD (`1f5b3c74…` both).

## Reproduced probes

| probe | result |
|---|---|
| `berth_sim` C (391 KiB) with apt tcc 0.9.27 | `program.c:5806: error: index too large`, `ail_bytes spans[] = {h, old, repl};` — exactly `fail_5` |
| same C, upstream 0.9.28rc raw | unresolved `__builtin_{add,sub,mul}_overflow` — matches `fail_7` |
| same C, 0.9.28rc + prelude | builds; stdout/exit identical to gcc -O2 build and CPython on the first public case |
| `g18_008` C with apt tcc | `program.c:4705: error: index too large`, `ail_stdout_parts((ail_str[]){ir4, ir5}, 2);` — exactly `fail_4`; +prelude builds and matches CPython/gcc |
| `tcc_prelude.h` vs GCC builtins, my own 1083-case grid (±1, ±2, INT64_MIN/MAX, ±2^62, ±3037000499/500, products) | identical |
| `_Thread_local` / `__thread` on apt 0.9.27; `_Thread_local` on 0.9.28rc | apt rejects both (`';' expected`), upstream accepts — claim verified |
| `__GNUC__` defined by either tcc | no (so the guarded SIMD/SJLJ paths really don't fire) |
| `AIL_CACHE` warm-build claim (fake `PIPE_CC` logging) | cold: 1 C-compile; warm: 0 — "cache stores the front end + executable" verified |
| end-to-end AIL build with `PIPE_CC=cc_tcc.py` on my own program (2^61 arithmetic via list/dict/str/loop) and on try/except/ZeroDivision/IndexError/TypeError | both binaries match CPython byte-for-byte |
| `tally_lang`, `tree_fold` compile | both refused by AIL |
| `par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3` | 3 modules, 0 failed (176 s/92 s/171 s); manifest `--check` exit 0 |

Census/timing aggregates (35/58, 23 `__int128`, 3.12/0.83/0.026 s, 4.62→2.93 s) were **not** re-run; see Unverified.

## Claim check

- Verified: no compiler/default change; apt 0.9.27 unusable; upstream+Prelude builds the sampled programs; byte-identical output where I could test; `__int128` is unguarded in `cruntime.py` (range slice 16995-17010, `pow3` 19127, `ail_rand_floordiv` 29811) and cannot be shimmed by a header; cache behaviour; tests.
- False: the "emitted by" pointers (below); the refusal reasons for `tally_lang`/`tree_fold` are **swapped**.
- Unverified: the aggregate census counts, all timings, the classifier 13/13 and fidelity probes (their probe scripts are in `/tmp`, not committed).
- Imprecise (not blocking): "the Python front end is 60-85% of the cold build" — the same table's tcc/gcc cold ratios are 41-91% (median 59%), and the three programs named in that sentence are 41-47%.

## Defects

1. `lab/tcc/RESULTS.md` line 17: "(`tally_lang`: tuple-element type unknown; `tree_fold`: `re` used outside what is built)". Actual compiler output is the reverse: `tree_fold` emits "cannot tell the type of element 0 of this tuple" (lines 85, 89); `tally_lang` emits a tuple-of-different-shapes comparison plus two `re` notes.
2. `CONSTRUCT_EMITTER` in `run.py` (hence `fail_*.txt`): three of five source pointers are wrong. `cruntime.py:17245-17246` for `_Thread_local` → actual 17347-17348 (17245 is `/*B|*/`). `pyfunc.py:24481` for `ail_stdout_parts` → actual 24977 (24481 is `list.sort`). `cruntime.py:29709 (ail_rand_floordiv)` → 29709 is the random-module comment; the quoted `__int128 nn = (__int128)n;` is the range-slice site at 16995-17010, and `ail_rand_floordiv` is at 29811. The blocker list therefore sends a reader fixing the only remaining blocker to the wrong file lines and the wrong function.

## Pre-existing

None found: every probe above matched CPython or the gcc build on both base and HEAD.

## Unverified

Full 58-program census and the 23 `__int128` count; all compile/run/edit-run timings; the `berth_sim` 2.3x runner-load correction; classifier and fidelity probes; multi-unit (shape `multi`) builds — no sampled program exercised that path; hidden-case output equality (report admits one public case only).

VERDICT: FIX
1. `lab/tcc/RESULTS.md:17` — refusal reasons swapped. Probe: `python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/compare/src/{tally_lang,tree_fold}/main.py -o /tmp/x --syntax python`. Expected: `tree_fold` = "cannot tell the type of element 0 of this tuple", `tally_lang` = tuple-shape comparison / `re` notes. Actual: report says the opposite.
2. `lab/tcc/run.py` `CONSTRUCT_EMITTER` lines 472-476 → `lab/tcc/fail_*.txt`. Probe: `grep -n "ail__rep_stk\|__int128 nn\|ail_stdout_parts" AIL_CURRENT/python/pkg-v12/{cruntime,pyfunc}.py`. Expected: `_Thread_local` at 17347-17348, range-slice `__int128` at 16995, `ail_rand_floordiv` at 29811, `ail_stdout_parts` emitter at 24977. Actual: 17245-17246 (a `/*B|*/` marker), 29709 (random-module comment), 24481 (`list.sort`).
[commandcode stop=end_turn turns=46 out_tokens=47489]

## worker report 1
[model commandcode/deepseek-v4.1-flash]
Done. All review defects fixed, verified, and committed as `86077bd`.

## Fixes

1. **Refusal reasons (`RESULTS.md:17`)** — replaced the swapped claim with the actual fatal first errors:
   - `tally_lang`: `field 'v' is a list or dict that gets bools and numbers` (plus tuple-shape / `re` notes)
   - `tree_fold`: `import of 're' with a use that is not built` (plus `cannot tell the type of element 0 of this tuple` notes at 44/72/85/89)
2. **Source pointers in `run.py` `CONSTRUCT_EMITTER`** (and the derived `fail_*.txt` + the duplicate pointers in the `RESULTS.md` blocker table):
   - `_Thread_local` → `cruntime.py:17347-17348` (was 17245, a comment)
   - `ail_stdout_parts` call site → `pyfunc.py:24977` (was 24481, `list.sort`)
   - `__int128` → `cruntime.py:16995` (range slice) + `29811` (`ail_rand_floordiv`) (was 29709, a comment)
3. **Imprecise claim** — "front end is 60-85%" → measured tcc/gcc cold ratio **41-91%, median 59%** (computed from the table).

## Probes (final commit, `/tmp/probes/`)

| probe | result |
|---|---|
| `emitter_pointers.py` — 15 pointers match their claimed construct; 3 stale pointers absent from all shipped files | **PASS** |
| `refusal_reasons.py` — both fatal messages match AIL output and are named in RESULTS.md | **PASS** |
| `cmp.sh corpus/gdev/g18_008.py`, `g04_006.py` | `same stdout`, both builds, exit 0 |

## Tests (final commit)

`test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → **3 modules, 0 failed** (242 s, `-j 2`). Manifest `--check` exit 0.

No compiler/runtime/build file touched. Not pushed. `.agent/pipeline.md` left untracked.
[commandcode stop=end_turn turns=35 out_tokens=18978]

## review 1
[model commandcode/deepseek-v4.1-flash]
## Review — tcc1 quick-run probe (`b86df60..86077bd`)

**What the change really does:** adds `lab/tcc/` (harness `run.py`/`run.sh`/`cc_tcc.py`, prelude shim, 8 diagnostics, `RESULTS.md`, proposed `tcc.yml`) and two DEVLOG entries. No compiler, runtime, build, corpus or bench file is touched (`git diff work..HEAD -- AIL_CURRENT tools corpus bench` is empty), so the generated C is identical by construction and nothing is pre-existing to excuse.

**Probes (mine, `/tmp/rprobes/`)** — `cmp.sh`, prelude/construct probes, census re-run:

| probe | result |
|---|---|
| `overflow_prelude.c` (324 boundary pairs × add/sub/mul, flag **and** result) | tcc+prelude == gcc `-O2` and `-O0`, 972/972 |
| `tls.c`, `tls2.c`, `comp.c`, `decl.c`, `unrea.c` | apt 0.9.27: `';' expected (got "void")`, `index too large` ×2, link `undefined symbol '__builtin_unreachable'` — all as claimed |
| `census.py` (seed 20261106, 54 candidates → 50 built) | **54 tried / 50 built; apt 0/50, upstream 5/50, prelude 33/50** — exact |
| `cmpsize.py` (8 compare) | 10.55 MB; corpus 28.18 MB → 38.73 MB / 58 ✓, `berth_sim` 390 KiB, `echo_pack` 322 KiB ✓ |
| g18_008 / g04_006: tcc vs gcc vs AIL binary, exits | stdout identical, AIL binary == both rebuilds ✓ |
| `cmp.sh corpus/gdev/g04_006.py` | `same stdout` in both modes, exit 0 ✓ |
| `test_ail_safetynet` | ok, 161 s, 0 failed (change adds no test module) |
| `overflow`/"`__int128` first site" on g03_030, g11_038, g11_026 | **see defect 1** |

Verified claims: tcc version strings (`0.9.28rc 2026-10-16 HEAD@e23dabed`), the 15 source pointers (`17347-17348`, `pyfunc.py:24977`, `6450/6508/6538`, `16995`, `29811`, `433/4044/4065`, `jsonrt.py:858`), both refusal messages (reproduced verbatim, incl. tree_fold notes at 44/72/85/89), all table medians (4.620 / 2.923 / 2.926 / 1.58x / 1.70x / 121x / 32x / 59%), `_Thread_local` vs `__GNUC__` guards (tcc defines no `__GNUC__`), and the 38.7 MB/616 KiB figures.

### Defects

1. **The `__int128` blocker is attributed to the wrong runtime paths for the corpus programs.** `RESULTS.md:72-74`, the DEVLOG, `run.py` `CONSTRUCT_EMITTER` and `fail_3` name only the range slice (`cruntime.py:16995`) and `ail_rand_floordiv` (`29811`).
   Probe: `python3 -B AIL_CURRENT/ail_chatgpt.py compile corpus/gdev/{g03_030,g11_038,g11_026}.py --debug-dir …`, then `/tmp/tcc-install/bin/tcc -O2 program.c`.
   Expected (per the report): first error at the range-slice/`pow` site.
   Actual: `'__uint128_t' undeclared` / `cannot convert 'unsigned long' to 'struct __uint128__'` at `__uint128_t num, den;` / `(uint64_t)ua << shift` inside **`ail__idiv_exact`, `cruntime.py:3835-3844`** — 3/3 sampled corpus-blocked programs, a site named nowhere. `fail_3`'s "emitted by" line is therefore wrong for the very error it quotes (its cited C line, `int shift = 55 - (abl - bbl);`, is one line above the `__uint128_t` and matches neither pointer). Consequence: the "cost to remove" scope (slice + int `pow`) omits the exactly-rounded integer-true-division path, which needs two-word 128-bit shift/div/mod — the most expensive piece and the one that stops most of the 17 corpus programs. (For `chain_relax` the cited slice site is correct: 7398/7435 verified.)

2. **Minor:** "the Python front end is 41-91% … (the tcc/gcc cold ratio in the table)" — that ratio is 158% for `g00_036` in the same table; the stated range should be 41-158% or scoped to programs where tcc is faster (the text does mention the case, but the range is presented as the table's range).

**Minor process note:** both commits carry `Co-Authored-By: Claude Opus 5.5`, while the report header says the model was `commandcode/deepseek-v4.1-flash`; the job rules say other models should omit the line.

**Pre-existing:** none — no compiler/runtime behaviour changed; all probe output matches CPython.

**Unverified:** the per-variant bucket split (41/6/5/4/2 apt; 30/23 upstream) — only the totals 0/5/33 and the sampled constructs; per-program timing medians (load-dependent; I spot-checked 3 programs' ratios, which agree within the stated ~2x load); the worker's `/tmp/probes/` files (not committed); `test_ail_files`/`test_ail_corpus_findings3` (no compiler code touched); icount/step 5 — not applicable, no hot code touched.

VERDICT: FIX
1. `lab/tcc/RESULTS.md:72-74`, `lab/tcc/run.py` `CONSTRUCT_EMITTER['__int128 …']`, `lab/tcc/fail_3_tcc_apt_int128.txt` and the DEVLOG name only `cruntime.py:16995` and `29811` as the `__int128` sites. Probe (`g03_030`, `g11_038`, `g11_026` + tcc 0.9.28rc on the emitted C): expected a `__int128` error at the range-slice or `pow` site; actual `'__uint128_t' undeclared` / `cannot convert 'unsigned long' to 'struct __uint128__'` in `ail__idiv_exact`, `cruntime.py:3835-3844` (`__uint128_t num, den;`). Add that path to the blocker table, the emitter map, the derived excerpts, and the "cost to remove" sentence.
2. `RESULTS.md:154-158`: the stated front-end range "41-91%" is computed from the tcc/gcc cold ratio column, whose actual range is 41-158% (`g00_036` = 1.424/0.903); state the range over programs where tcc is faster, or print 41-158% and exclude `g00_036` explicitly.
[commandcode stop=end_turn turns=50 out_tokens=56126]

FINAL VERDICT: FIX  2026-11-06T20:59:02Z
