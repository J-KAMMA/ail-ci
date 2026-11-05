# job job-imghdr1-11060325  started 2026-11-05T18:26:56Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Summary:

**Commit** `9a500d3` on `job-imghdr1-11060325` (not pushed, per runner instructions).

**Results**
- Before: 0/10 built (all refused; first line `imghdr.what (not yet published in NAMES_library.json)`, program 10 `imghdr.tests used as a plain value`).
- After: **10/10 build and match CPython** in the default build and with `AIL_UNIFIED_FORCE=1` (stdout + exit 0). All take the general path (`what` returns `str` or falls off the end; no `Optional[str]`).
- `python3 AIL_CURRENT/test_ail_std_imghdr.py`: 2 tests, OK (223s).

**Module** `AIL_CURRENT/stdlib/imghdr.py`: CPython 3.12 source, same `what`, `test_*` order and return strings. Forced rewrites documented in the docstring: drop `PathLike` (accept `str`), drop `warnings._deprecated` (no DeprecationWarning; stdout/exit unchanged), drop `test()`/`testall()` (refused `KeyboardInterrupt`/`os.path`), and `ord(b'P')` → `b'P'[0]` (compiler `ord()` fails on bytes).

**Self-check probes** (`bash ~/tools/cmp.sh`, both builds; all same stdout, exit 0):
- `p_types.py` — h via argument, list item, dict value, attribute; empty/31/32/33 bytes.
- `p_boundary.py` — jpeg h[6:10], gif h[:6], netpbm len>=3, webp h[8:12], empty prefix.
- `p_file.py` — path, `f.read(32)`, file object + tell/seek.
- `p_order.py` — len 13 and test order.

**Required tests**
- `test_ail_files.py`: OK (18 tests, 1 skipped).
- `test_ail_corpus_findings3.py`: OK.
- `test_ail_safetynet.py`: OK without `ulimit` (5 tests). Under `ulimit -v 1500000` it failed only `S4_generators_gc` with truncated output — the cap killed the program, unrelated to this change.

`tools/update_manifest.py --check` passes; diff from the base commit contains only the named files plus the manifest shards.
[commandcode stop=end_turn turns=55 out_tokens=29621]

## review 0
[model commandcode/deepseek-v4.1-flash]
**What the change does:** adds `AIL_CURRENT/stdlib/imghdr.py` (CPython 3.12's module minus `PathLike`, the deprecation warning, `test()/testall()`, and `ord(b'P')`→`b'P'[0]`), 10 lab programs, a test module, its `tests.d` registration, and manifest rows. Matches the report; no compiler/runtime files touched.

**Probes** (all in `/tmp/rprobes/`, `bash ~/tools/cmp.sh … $PWD`, both builds vs CPython):

| probe | result |
|---|---|
| p1_index — bytes indexing/`in`, netpbm 2nd/3rd-byte boundaries, 8/11/12-byte slices | same stdout, exit 0 |
| p2_inputs — h via argument, list item, dict value, attribute, `from imghdr import what`, bytearray | same stdout, exit 0 |
| p3_file — empty file, file at offset 4 + tell/seek restore, missing path | same stdout, exit 1 |
| p4_state — replace `imghdr.tests`, append, call `tests[0]` directly | same stdout, exit 0 |
| p5_nofeature — no imghdr use | `--debug-dir` program.c identical to `/tmp/base`; exit 3 same |
| p6b_kw — `what(file=None, h=…)` | same stdout, exit 0 |
| p7_noneboth — `what(None, None)` | exit 1 both |
| p8_filesize — 32/33-byte files, repeat read | same stdout, exit 0 |
| p9_path — `pathlib.Path` to `what` | named compile refusal, as documented |
| p2b_strh / p6_kw | exit 1 both / named refusal (CPython TypeError) — no silent wrong output |

**Tests:** `par_check.py -j 2 test_ail_std_imghdr test_ail_safetynet` → `test_ail_std_imghdr` OK (297s); `test_ail_safetynet` failed only `S4_generators_gc` under `ulimit -v 1500000` (truncated output). Re-run without the cap: 5 tests, OK — environmental, as the worker stated. `update_manifest.py --check` rc=0.

**Report claims:** all verified (10/10 both builds, 0/10 before — confirmed on 01 and the census row, module rewrites, 2 tests OK, general-path build note). `test_ail_files`/`test_ail_corpus_findings3` claims: unverified (out of scope). No speed check needed — non-users' C is byte-identical and no hot code changed.

**Pre-existing:** none observed.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=28 out_tokens=15557]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T20:22:07Z
