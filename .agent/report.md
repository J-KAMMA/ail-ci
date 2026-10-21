Done. Final report:

**Fix (C168).** `AIL_CURRENT/python/pkg-v12/pyboxed2.py`: added `_str_window_bounds()` (emits the optional start/end, tests each supplied bound's tag, passes `has_lo/has_hi = 0` for a `None`) and used it in `_m_find`, `_m_rfind`, `_m_rindex`, `_m_count` (str branch), `_m_index` (str branch only) and `_prefix_test`. List/tuple `_m_index` kept exactly as before, so no scope creep. Literal `None` already worked on the typed path; variable/argument/list/dict/attribute `None` now works on the general path too.

**Probes** (each `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`, both `g` and `d` builds, all `same stdout`, exit 0):
`p_basic` (literal), `p_var` (variable), `p_arg` (function args), `p_mixed` (None/int/-neg mixes), `p_types` (bool/int bounds), `p_sources` (attribute, list item, dict value), `p_tuple_prefix` (tuple prefixes + None), `p_errors` (float/str/list bounds → TypeError), `p_alias` (same var both bounds, call returns, nested).

**Tests on final commit `96393d6`:**
`par_check.py -j 2` → 7/7 ok: `test_ail_fuzz3n`, `test_ail_fuzz3`, `test_ail_str_find_alias`, `test_ail_str_rfind`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (205 s, 0 failed). Also `test_ail_corpus_findings` / `_findings2` ok. `tools/update_manifest.py --check` OK.

**Records:** no `DIFFERENCES.md`/`DEVLOG.md` existed in this export, so I created both at the repo root: C168 marked closed plus one open placeholder row for the pre-existing `list.index(None)` divergence I found; DEVLOG entry dated 2026-10-21.

**Caveat:** `test_ail_fuzz1` fails here because `tools/difffuzz.py` is missing from the export (`ModuleNotFoundError`); unrelated to this change. Not pushed, per rules.
[cost $0.0775, opencode tokens {"total": 7458455, "input": 230877, "output": 18803, "reasoning": 16711, "cache.write": 0, "cache.read": 7192064}]
