# job job-fuzz27-10230628  started 2026-10-22T21:29:38Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Final report

- **Defect found (silent, general path):** after `set.pop()`, `symmetric_difference_update` / `intersection_update` / `^=` / `&=` replaced the entries but kept the old pop cursor `fin`. Next `pop()` skipped the first remaining element, then could walk past the live entries.
  - Pre-fix probe p16: CPython `1,2,1 False True`; general path `1,3,1 True False`. Typed path was correct.
  - Fix: `ail_setx_swap_bodies` now swaps `fin` with the body (`cruntime.py:15250`).

- **Probes (final commit, both builds match CPython):**
  - p16 cursor after `symmetric_difference_update`/`intersection_update`
  - p17 `^=`, `&=`, empty result, empty other, repeated pops
  - p18 set through an attribute
  - p19 set through a list item
  - p20 set through a dict value
  - p21 set through a function argument
  - p01–p10 broader 10-program set sweep: clean except p08 (both raise unhashable TypeError) and p09 (`10**30`: both builds error `integer overflow`, not silent)
  - p12/p22 show the documented insertion-order `pop()` difference (DIFFERENCES A2), not the defect.

- **Tests on final commit `92a0da7`:** `test_ail_fuzz27`, `test_ail_sets_general`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 5 modules, 0 failed. `update_manifest.py --check` passes.

- **Records:** no `DIFFERENCES.md` or `DEVLOG.md` exists anywhere in this export, so no rows/entry could be added.
[cost $0.0000, opencode tokens {"total": 4360229, "input": 94261, "output": 14177, "reasoning": 15631, "cache.write": 0, "cache.read": 4236160}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
# Review — `92a0da7`

**Change:** one-line swap of the `fin` pop cursor in `ail_setx_swap_bodies` (`cruntime.py:15250`), plus `test_ail_fuzz27` and manifest/shards entries. All three swap callers use a fresh temporary whose `fin` is 0, so the swap resets the cursor consistently with the replaced body.

**Probes** (`/tmp/rprobes`, `cmp.sh`, both HEAD builds unless noted):
- `r01` basic pop → `symmetric_difference_update(set())`: base general prints `1/3/1 True False`; CPython/HEAD `1/2/1 False True`. Defect and fix confirmed.
- `r02` `^=`, `&=`, `intersection_update`; `r03` set via attribute, list item, dict value, function argument; `r04` empty set/result, repeated pops, KeyError; `r10` pop/discard/add/difference_update/clear: HEAD matches CPython on both builds.
- `r14` set comprehension/frozenset equality; `r15` `^= s`, `&= frozenset`, `^=` frozenset; `r08` frozenset hash/equality with set; `r09` issubset/isdisjoint/ordering: match.
- `r06` unhashable `remove`, `r07` caught unhashable `add`/`symmetric_difference_update`: both raise/catch the same TypeError.
- `r11` repeated swaps: base general segfaults (the old cursor bug); HEAD runs and matches the typed path.
- `r12` self-aliasing swaps: base general prints `<object>`; HEAD matches typed path. `r05`/`r11`/`r12` still differ from CPython only by the documented insertion-order `pop` (pre-existing; typed base shows the same).
- `r16` `10**30`: both builds exit 1 with `integer overflow`; identical on base (not silent).

**Non-feature C:** plain `print(1+2)` compiled with `--debug-dir`; `program.c` is byte-identical base vs HEAD (only temp paths in `native_report.json` differ).

**Tests:** `par_check.py -j 2 test_ail_fuzz27 test_ail_safetynet` → 0 failed; `update_manifest.py --check` → rc 0. Copying `test_ail_fuzz27` onto the base tree fails all 4 tests, so it is a genuine regression test.

**Claims:** defect/fix, typed path correct, test run, manifest, and absence of DIFFERENCES/DEVLOG files verified. Exact p-number probes not rerun (equivalent probes used). “DIFFERENCES A2” is a false label: no such file exists; the insertion-order difference is documented in `AIL_REFERENCE_MORE.md:561-562`. Speed unverified: `perf_event_open` denied on this runner; the touched helper is O(1) and not on a hot path.

**Pre-existing (non-blocking):** insertion-order `pop` differences (`r05`, `r11`, `r12`) and `10**30` overflow refusal (`r16`).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1028973, "input": 37839, "output": 6855, "reasoning": 9175, "cache.write": 0, "cache.read": 975104}]

FINAL VERDICT: ACCEPT  2026-10-22T21:50:04Z
