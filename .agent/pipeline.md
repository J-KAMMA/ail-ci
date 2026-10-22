# job job-fuzz21-10230420  started 2026-10-22T19:21:00Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report**

- **Found/fixed:** first silent stdout difference was in unpack error text on the general path (`p10_errors`): messages omitted counts and used `"'int' object is not iterable"`. `pyboxed2.py` now emits CPython’s `too many values… (expected N)`, `not enough… (expected N, got M)`, starred `(expected at least N, got M)`, and `cannot unpack non-iterable X object`.
- **Tests:** added `AIL_CURRENT/test_ail_fuzz21.py`, registered it in `ail_check.MODULES`, updated manifest pins.
- **Final test run (commit `65cb573`):** `test_ail_fuzz21`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 modules passed in 244s.
- **Probes:** 22 programs in `/tmp/probes/`. 21 match CPython on both builds (2/2). `p08_huge` differs only for giant integer literals (`10**50` → `integer overflow` on both builds, not unpacking); its range/starred unpack lines match.
- **Records:** `DEVLOG.md` and `docs/spec/DIFFERENCES.md` added (neither existed in this export); manifest `--check` passes.
- Not verified: the v1 general path (`AIL_GENERAL=v1`); probes exercised the default/forced-general builds.
[cost $0.0000, opencode tokens {"total": 6411828, "input": 133412, "output": 15431, "reasoning": 15945, "cache.write": 0, "cache.read": 6247040}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `65cb573 fuzz21: CPython unpack error text on the general path`**

Change inspected: `pyboxed2.py` adds `ail2_unpack_*` helpers and uses CPython's counts/non-iterable wording on the general path; new `test_ail_fuzz21.py`; manifest/DEVLOG/DIFFERENCES updated.

**Probes** (25 written in `/tmp/rprobes`, both g/d builds compared to CPython; base checked):
- Match on both builds: basic/swap/nested/star (`p01`), too-few and too-many over tuple/list/str/range/iter/map/gen/dict/set (`p02`,`p03`), starred errors (`p05`), for-loop unpack (`p06`), generator raising mid-unpack (`p08`), values via arg/list/attr/dict (`p09`), aliasing (`p10`), nested unpack (`p11`), ranges incl. negative/huge (`p12`), BMP str/bytes (`p17`), nested star (`p18`), user `__iter__` iterators (`p19`), star over str/bytes/range/dict/set (`p20`), non-unpack C (`p21`), duplicate targets/assign-expr/bytes (`p13`,`p16`,`p18` worker probes), typed args (`p22`).
- Named compile-time refusals (acceptable): non-BMP literal (`p13`), starred comprehension target (`p23b`).
- Worker's 22 probes re-run: 21 SAME, only `p08_huge` DIFF (huge int literal) — matches report.
- Non-unpack `--debug-dir` `program.c` is byte-identical to base (only temp paths in `native_report.json` differ).

**Pre-existing (identical on base, do not block):**
- Comprehension for-clause unpack is done by indexing: `[a for a,b in ["a"]]` gives `IndexError` instead of `ValueError not enough...`; `iter([1,2])` element gives `TypeError ... not subscriptable` instead of `[1]` (`p23c`).
- Old-style `__getitem__` iterables fail to unpack (`p04`,`p07`). The new wording now says "cannot unpack non-iterable GetItem", a mislabel, but the failure predates the change.
- Non-BMP string literal refused; >64-bit integer traps with `integer overflow` (already recorded in DIFFERENCES).

**Tests/records:** `test_ail_fuzz21 test_ail_safetynet test_ail_files test_ail_corpus_findings3` → 4/4, 244 s, 0 failed. `update_manifest.py --check` exit 0.

**Speed:** `icount` unavailable (`perf_event_open: Permission denied`, paranoid=4). Fallback timing on a tight 2M-iteration generic-unpack loop: base 0.27 s vs HEAD 0.28 s (~4%), no large slowdown.

**Claims:** all verified except "v1 general path not verified" — accurate; `AIL_GENERAL=v1` is legacy and not exercised by `cmp.sh`/tests. No defect caused by this change.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2366263, "input": 63221, "output": 11387, "reasoning": 18247, "cache.write": 0, "cache.read": 2273408}]

FINAL VERDICT: ACCEPT  2026-10-22T19:59:06Z
