# job job-rbobs2-11090836  started 2026-11-08T23:41:23Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Summary:

**Applied the obs2 change** (`eb8b28cf..job-obs2-op1109`, 18 files, +6,109/−26 excluding `.agent`, `corpus`, `MANIFEST.json`).
- 9 files were already at the target; 3 new lab JSONs added.
- 2 files conflicted (`docs/design/OBSERVED_TYPES.md`, `lab/wedge/observe_probe.py`); both `HEAD` copies were byte-identical to obs1's `1c1e8b2f`, so the resolved merges keep both sides and equal the target exactly.
- Post-commit check: 18/18 patched files match `FETCH_HEAD`; `update_manifest.py --check` exits 0 (no pin changes needed). `tools/diff_ids.py` does not exist on this tree.
- Test registration `tests.d/test_ail_observe.txt` already present and correct.

**Tests** (`-j 2`, on the committed tree content): `test_ail_cpython_hybrid`, `test_ail_observe`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 5 modules, 0 failed, 415 s.

**Probes** (`/tmp/probes/`), all matching CPython or refused by name:

| probe | path | result |
|---|---|---|
| hc_basic | cmp.sh g/d | refused by name: "add() called with too many positional arguments" |
| hc_widths | cmp.sh g/d | refused by name: "int64 constant out of range: 1180591620717411303424" |
| hc_index | cmp.sh g/d | g/d same stdout, exit 0 |
| hc_channels | cmp.sh g/d | g/d same stdout, exit 0 |
| hc_defaults | cmp.sh g/d | refused by name: "using function add as a first-class value" |
| hb_basic | `ail build --cpython` | same stdout+exit; accelerated add,flag,scale,greet; all `_ail_is_native` true |
| hb_widths | hybrid | same; add,mul native (int64 overflow via arg, list item, dict value, attribute) |
| hb_defaults | hybrid | same; add native (`__defaults__`/`__code__` replacement) |
| hb_index | hybrid | same; at,last,local,put,lookup,nested native (negative/empty/nested IndexError, KeyError) |
| hb_channels | hybrid | same; add1,pick native (aliasing, argument, list item, attribute, dict value) |

Commit `7754ef08` on `job-rbobs2-11090836` (9 files, +6,136/−26 including DEVLOG), no push.
[commandcode stop=end_turn turns=56 out_tokens=30888]

## review 0
[model commandcode/deepseek-v4.1-flash]
Review complete.

## What the change really does

`ail build --cpython` (an explicit, opt-in mode) now installs a C vectorcall entry on the *original* CPython function object (3.12+, via `PyFunction_SetVectorcall`) instead of wrapping it in a Python closure. Guards run in C; keywords, wrong arity, guard failure, int64 overflow and traps fall back to unaltered `_PyFunction_Vectorcall`. Supporting fixes: the trap flag gains external linkage (unblocks indexing units), uncaught runtime raises fall back instead of `_Exit(1)`, and the build imports each `.so` before `build.json` may claim native. Plus lab/docs data for the obs2 measurement.

## Fidelity (the actual re-apply task)

All **18/18** target files match `FETCH_HEAD` byte-for-byte; the two "conflicted" files resolve exactly to the target. Base tree = `work`, manifest `--check` exits 0, `tests.d/test_ail_observe.txt` present. `tools/diff_ids.py` genuinely does not exist on this tree (`git log --all` has no history; absent from base and from `FETCH_HEAD`) — skipping it was correct.

## Probes (14, /tmp/rprobes)

All matched CPython, with `native` lines excluded (hybrid-only). Covers defaults replacement (wrong-size/empty/`None`/non-int/big-int defaults, empty tuple), `__code__` swap, aliasing (direct/list/dict/class-attr/`partial`/`map`), overflow via argument/list item/dict value/attribute, `bool` vs `int` (`int` subclasses, `MyStr`, `bytes`, generator, tuple, `bytearray`, mixed list), negative/empty/nested indexing with `IndexError`/`KeyError`, `a[n][m]`, mutation-after-slice, file overwrite/truncate, 4-thread trap+overflow, recursion (refused by name), zero-arg and float-list units.

**Unused feature ⇒ unchanged C:** compiled a plain program and a typed non-hybrid program with `--debug-dir` on HEAD and `/tmp/base` — `program.c` (1.57 MB), `program_mix0.c`, `program_mix1.c` **identical**; identical stdout/exit, matching CPython.

## Tests

`-j 2` on HEAD: `test_ail_cpython_hybrid`, `test_ail_observe`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → **5 modules, 0 failed, 298 s**.

## Report claims

| claim | status |
|---|---|
| 18 files / +6,109/−26 | verified (18 target files; 9 changed + DEVLOG = 6,136/−26 incl. DEVLOG) |
| 9 files already at target | **false, it's 10** (off-by-one in the report's count; conclusion unaffected) |
| 2 files conflicted, both = target | verified |
| `update_manifest.py --check` = 0 | verified |
| `diff_ids.py` absent | verified |
| tests.d entry present | verified |
| 5 modules 0 failed | verified (I measured 298 s, report says 415 s — different load, not a defect) |
| probes all match/refused | verified semantics; my own probes cover more |
| "post-commit 18/18 match" | verified |

## Unverified / pre-existing

- **Speed (5):** `tools/icount.c` builds but `perf_event_open` is denied in this container, so instruction counts could not be measured. Wall clock on my speed probe: `add1` 155 ns vs 475 ns on base; `total(xs)` 513 ns vs 857 ns on base — direction consistent with the report's claim, but not the icount numbers.
- **Pre-existing (identical on base):** hybrid traceback line numbers point at the generated copy (`out/ok.py:122` vs `ok.py:2`); a module whose source dir differs from the output dir picks up the original via the preamble's hardcoded `sys.path.insert`; direct dual-`.so` loading of the same-named function raises `Fallback` on base too.

No defect attributable to the change.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=75 out_tokens=105105]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-09T01:46:24Z
