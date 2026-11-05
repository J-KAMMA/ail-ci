# job job-relnotice1_rr1-11060525  started 2026-11-05T20:27:34Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Committed as `e1723061` on `job-relnotice1_rr1-11060525` (not pushed).

**What caused it:** my branch was an export of an older `staging:integ`; today's integ had since added `AIL_CURRENT/stdlib/linecache.py` and `struct.py`. Merged onto today's integ, the notices inventory and its test predated them, so `test_ail_third_party_notices.test_every_file_is_listed` failed with exactly those two paths. The other five listed modules pass; I reproduced the failure first in a worktree of today's integ with my change applied (1 failure), then fixed it.

**Fix:** `linecache.py`'s docstring now names `stdlib/LICENSE-PSF.txt` (it is a reduction of CPython's `Lib/linecache.py`); `struct.py` gets an AIL-owned row under `MIT OR Apache-2.0` (AIL's own implementation, behaviour follows CPython). Inventory counts 13/3/67 → 14/4/69. Also merged today's integ (conflicts only in DEVLOG, DIFFERENCES, one `manifest.d` shard; pins refreshed, `--check` rc=0). No compiler/runtime code changed. DEVLOG entry and DIFFERENCES row `C?-job-relnotice1_rr1-11060525-1` added.

**Tests on the final commit** (`par_check.py -j 2`): test_ail_obj_refs, test_ail_packaging, test_ail_safetynet, test_ail_third_party_notices (7), test_ail_unified, test_ail_virtual_dispatch, test_ail_files, test_ail_corpus_findings3 — 8/8 modules, 0 failed.

**Probes** (`bash ~/tools/cmp.sh ... $PWD`):
- `p1_linecache.py` — getline/getlines/checkcache, in-range/0/negative-index (empty)/missing/empty file/no-final-newline: same stdout on general and default builds.
- `p2_struct.py` — calcsize/pack/unpack/Struct plus range and short-buffer error texts: same stdout on both builds.
- `p3_notices_inventory.py` — 20 rows, 69 files, missing=[], no_notice=[], absent_license=[].

Caveat: this checkout cannot reproduce the failure without merging today's integ (the branch base lacks `linecache.py`/`struct.py`), so I verified the fix on a reconstructed integ+change tree (identical tree hash as the final commit) and on the final commit itself.
[commandcode stop=end_turn turns=77 out_tokens=51183]

## review 0
[model commandcode/deepseek-v4.1-flash]
## Review report

**What the change really does.** Relative to today's integ (`8c2c99c1`), the whole delta is: merge integ into the branch, add two rows to `THIRD_PARTY_NOTICES.md` (`linecache.py` as CPython/PSF, `struct.py` as AIL-owned `MIT OR Apache-2.0`), update counts 13/3/67 → 14/4/69, add one attribution line to `linecache.py`'s docstring, refresh `manifest.d` pins, add a DEVLOG entry and DIFFERENCES row. No compiler or runtime change. This matches the report.

**Claims checked**
- Premise verified: `work` stdlib lacks `linecache.py`/`struct.py`; integ has both, so exactly those two were unlisted.
- Docstring now names `LICENSE-PSF.txt`; struct row is AIL-owned — verified by reading both files (struct.py is a 521-line AIL implementation, not CPython's wrapper).
- Counts verified: 69 files under stdlib+third_party; 14 CPython-derived (10 modules + 4 tomllib), 4 AIL-owned, 1 PSF license, 50 typeshed.
- `tools/update_manifest.py --check` rc=0.
- `git diff 8c2c99c1 HEAD -- AIL_CURRENT/python` is empty (only `packaging/ail_wheel_backend.py`, already part of the branch's prior wheel-PSF fix).

**Tests on HEAD** (`par_check.py -j 2`): obj_refs, packaging, safetynet, third_party_notices (7/7 incl. wheel tests), unified, virtual_dispatch, files, corpus_findings3 — 8/8 modules, 0 failed.

**Probes** (`bash ~/tools/cmp.sh`, both general and default builds; all same stdout/exit as CPython 3.12):
- `p1_linecache.py` — getline/getlines/checkcache, in/out-of-range, 0, negative, missing file, no final newline, rewrite then checkcache.
- `p2_struct.py` — calcsize (<i, <3h, >qQ, b), signed/unsigned pack, unpack, repeat, `s`, out-of-range and short-buffer errors, `Struct`.
- `p3_plain.py` — no-feature program; `--debug-dir` `program.c` and `program_mix0.c` are byte-identical between HEAD and integ (only temp paths in `native_report.json` differ).

**Pre-existing:** none observed. Speed is unaffected (compiler tree identical to integ; no icount needed).

**Unverified:** the "not pushed" claim and the exact conflict list during the merge.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=17 out_tokens=15030]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T22:47:01Z
