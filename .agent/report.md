# job job-fuzz89-10231611  started 2026-10-23T07:12:44Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `9210005`.

**Defect:** whitespace `bytes`/`bytearray` `split`/`rsplit` with a reached `maxsplit` dropped the outer whitespace from the remainder (`b" a ".split(None, 0)` → `[b"a"]` instead of `[b"a "]`). Fixed both directions in `AIL_CURRENT/python/pkg-v12/safetyrt.py`; typed-path loops already had CPython's rule.

**Records:** created `DEVLOG.md` and `DIFFERENCES.md` (they were absent), row `C?-job-fuzz89-10231611-1`. Manifest updated and `--check` passes.

**Probes** (all same on both builds and CPython, after fix): p1_slice, p2_startswith, p3_replace, p4_count, p5_split, p6_compare, p7_concat, p8_nesting, p9_ba, p10_bounds, p11_ws_forms, p12_ba_ws — 12/12. The only difference seen was the p5 whitespace-split remainder; no others.

**Tests on final commit:** `test_ail_fuzz89`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (245s).
[cost $0.0000, opencode tokens {"total": 4429194, "input": 296570, "output": 12364, "reasoning": 10564, "cache.write": 0, "cache.read": 4109696}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `9210005` (fuzz89: bytes whitespace split at maxsplit)**

**Diff:** only `safetyrt.py`'s `ail2b_split_ws` changes (plus test, manifest, records). The fix stops trimming the outer whitespace off the remainder once `maxsplit` is reached, for both `split` and `rsplit`. That matches CPython and the typed-path `ail_bytes_split`/`ail_blist_split` logic.

**Probes (in `/tmp/rprobes`, both builds, compared against CPython):**
- `p1b_ws_all` — empty/space-only/leading/trailing/mixed WS, `\x00`/`\xff`, maxsplit `-5..2**62`: same on HEAD; base is wrong at `maxsplit 0/1` (e.g. `b"a  b  "` → `[b'a  b']` vs CPython `[b'a  b  ']`).
- `p2_ws_ba` — bytearray split/rsplit, mutation after split: same on HEAD; base wrong.
- `p3_ws_delivery` — maxsplit via argument, list, attribute, dict: same.
- `p4_ws_forms` — default/None/`sep=`/keyword forms: same.
- `p5_ws_alias` — aliases, list/tuple/dict items, slices: same.
- `p6_shapes` / `p7_extra` — slicing, startswith/endswith, replace/count, compare, concat, nesting, bytearray ops: same.
- `p8_exhaustive` — all strings over `{a, space, tab}` length ≤4 × maxsplit `-1..4`, both split directions: same on both builds.
- `p1` huge literal (`2**63-1`, `-2**63`) fails with `integer overflow` on HEAD **and** base: pre-existing, recorded below.

**Tests on HEAD:** `test_ail_fuzz89`, `test_ail_safetynet` — 2 modules, 0 failed (117s). The other two modules claimed by the worker were not rerun, per the reviewer budget.

**Claims:** commit `9210005` verified; defect and both-direction fix verified; typed-path already-correct claim verified (typed split program builds without fallback on base and matches; typed `rsplit` is refused/falls back); records + manifest `--check` verified. The worker's “12/12 probes, no other difference” is unverified as their probe files are absent, but my probes found no other difference.

**Speed:** `tools/icount.c` cannot run here (`perf_event_open: Permission denied`). No gdev program uses bytes split, and a non-bytes program's generated `program.c` is byte-identical to base, so no hot-code impact.

**Pre-existing:** the `integer overflow` compile refusal for out-of-range literal maxsplit occurs identically on base.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2437932, "input": 74357, "output": 10014, "reasoning": 15769, "cache.write": 0, "cache.read": 2337792}]

FINAL VERDICT: ACCEPT  2026-10-23T07:46:27Z
