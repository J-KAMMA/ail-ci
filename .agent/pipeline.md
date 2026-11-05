# job job-linecache1-11052339  started 2026-11-05T14:39:43Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Fixed and committed (`474eb58`). Final verification:

**Defects fixed** (all reproduced first via `~/tools/cmp.sh` in both builds):
1. `checkcache` kept a stale entry after the file became non-UTF-8 — `_read_lines` now returns status 2 on a decode error (the typed runtime raises `UnicodeDecodeError`, the general path its parent `ValueError`), and `checkcache` drops the entry. `pC_badutf8.py`: now `kept False` / `''`, matches CPython.
2. Seeded `mtime is None` entries were dropped — added `if mtime is None: continue`. `pD_seed_none.py`: now `kept True` / `'seed\n'`.
3. A tuple replaced in `cache` after filling kept synthetic lines — `_snapshots` now stores `(entry, copy_of_lines)` and compares both. `pE_seed_int.py`: now `kept False` / `'one\n'`.
4. `size` counted the appended newline — now summed before appending. `pF_bounds.py`: now `4 18`, matching CPython. Docstring's false "`None` inside a tuple is not built" claim corrected in both the module and `RESULTS.md`.

**Probes (both default and `AIL_UNIFIED_FORCE=1`, all same stdout/exit as CPython):** `pA_mutate`, `pB_perm`, `pC_badutf8`, `pD_seed_none`, `pE_seed_int`, `pF_bounds`, `pI_none`, `pJ_mutate_change`, `pH_truncate` — 9/9.

**Tests:** `test_ail_std_linecache` 2 OK (133.7 s); `test_ail_safetynet` 5 OK (130.7 s) — the earlier failure under `ulimit -v 1500000` was an OOM in `S4_generators_gc`, and it passes with no cap; `test_ail_files` 18 OK (1 skip); `test_ail_corpus_findings3` 2 OK.

**Manifest:** `tools/update_manifest.py` updated only `manifest.d/a9.txt`; `--check` exits 0.

Files changed: `AIL_CURRENT/stdlib/linecache.py`, `lab/stdlib/linecache/RESULTS.md`, `AIL_CURRENT/manifest.d/a9.txt`.
[commandcode stop=end_turn turns=37 out_tokens=25962]

## review 0
[model commandcode/deepseek-v4.1-flash]
All four review defects are fixed and my boundary probes agree with CPython. Here is the report.

## What the diff really does
Reworks `AIL_CURRENT/stdlib/linecache.py`'s freshness check: `_read_lines` now returns `(status, lines, size)` (0 unopenable, 1 ok, 2 decode error), `size` is summed before the synthetic `"\n"` is appended, `checkcache` skips `mtime is None` and lazy entries, drops on status 2, and `_snapshots` stores `(entry, copy_of_lines)` so a replaced cache entry is detected. Plus `RESULTS.md` wording and the `stdlib/linecache.py` manifest pin. No compiler/runtime file touched.

## Review 1 defects
1. **Bad UTF-8 keeps stale entry** — fixed. `p1_badutf8`: CPython `'one\n'` / `kept False` / `''`; both builds now identical (was `kept True` / `'one\n'`).
2. **Seeded `mtime is None` dropped** — fixed. `p2_seed_none`: `'seed\n'` / `kept True` / `'seed\n'` in both builds; `p5_none` prints `None True`.
3. **Replaced entry keeps synthetic lines** — fixed. `p3_seed_int`: `kept False` / `'one\n'` in both builds.
4. **`size` counted appended newline** — fixed. `p4_bounds` on `"abc"`: `3 4 'abc\n'` and `True True True` in both builds (CPython `st_size`=3).

## My probes (all HEAD, both general and default builds, same stdout/exit as CPython)
- `p6_empty` empty→content + `checkcache`; `p7_alias` mutation via dict value and a slice alias, line 4 appended; `p8_perm` chmod 0 keeps entry; `p9_multi` `checkcache()` over two entries drops only the changed one; `p13_uncached_bad` invalid UTF-8 never cached, then fixed; `p14_sources` filename via argument/list item/attribute/dict value; `p15_int64` `±2**63-1` line numbers; `p16_lazy` lazy tuple, seeded `None` on a missing file, and `clearcache`.
- Non-user program `p10_plain`: `--debug-dir` `program.c` byte-identical to `/tmp/base` (`IDENTICAL`).

## Tests / manifest
`par_check.py -j 2 test_ail_std_linecache test_ail_safetynet` → 2 modules, 0 failed (142.9 s / 138.2 s). `update_manifest.py --check` exits 0. `git diff --stat work..HEAD` touches only the three allowed files.

## Claims
- Fixes 1–4, docstring correction, 9/9 probes, tests, manifest — **verified** (mutation probes covered by `p7`/`p9`).
- `test_ail_files` 18 OK, `test_ail_corpus_findings3` 2 OK — **unverified** (not re-run per review scope).

## Pre-existing
- `p11_bom`: UTF-8 BOM retained (`'\ufeffabc\n'` vs CPython `'abc\n'`); byte-identical divergence on `/tmp/base`, so not caused by this change.

## Speed
Not run: no compiler/runtime change; only the imported `linecache` module differs, and 0 corpus/gdev programs import it.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=24 out_tokens=20274]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T16:25:17Z
