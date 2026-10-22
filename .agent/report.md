Implemented and committed on `job-fuzz15-10220831` as `6f1b3c4`.

**Fixed cause (1):** `re.split(..., maxsplit<0)` and `re.sub` / `re.subn` with `count<0` treated a negative limit as unlimited. CPython does zero splits / zero replacements. Updated all four loops in `relib.py` (split, literal replacement, template replacement, callable replacement), covering str, bytes, compiled patterns, positional and keyword limits.

**Probes (each run with `cmp.sh` on both builds):**
- `r13`, `r15`, `r23`, `r33`, `r39`, `r40`, `r43`, `r44`: negative/zero/positive boundaries, via argument, list item, dict value, attribute, lambda, bytes, compiled pattern — all `g same stdout`, `d same stdout` after the fix.
- Random area programs: `fre301`–`fre310` (generated `re` patterns/operations), `jsonr01`–`jsonr10` (generated nested JSON documents/options), `j25`/`j27`/`j28`/`j29` (float formatting, int-key sorting, all BMP code points) — all matched CPython on both builds.
- 40+ additional directed `json`/`re` probes were run; only the declared limits below differed.

**Remaining differences found (not fixed):**
- `json.loads` of surrogate pairs/escaped surrogates (`j09`, `j18`): runtime `ValueError`; non-BMP support is a declared 16-bit-string limit.
- `json.loads` integers beyond int64 (`j11`): runtime integer overflow vs CPython arbitrary precision.
- Non-BMP `chr()` on the forced general path (`j26`): internal error; default build matches.
- `re.IGNORECASE` with a non-ASCII subject (`r41`): runtime `ValueError`; Unicode case table unavailable.
- Forms refused by name: findall with several groups, split with groups, non-literal replacement templates, non-literal patterns.

**Tests:** added `AIL_CURRENT/test_ail_fuzz15.py`, registered in `ail_check.py`, refreshed `MANIFEST.json` and `ci_shards.json`. Final commit run: `test_ail_fuzz15`, `test_ail_re`, `test_ail_json_fast`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 0 failed. `update_manifest.py --check` and `ci_shards.py --check` pass; worktree clean.

This export contains no `DIFFERENCES.md` or `DEVLOG.md` in the git tree, so the required record rows/entry could not be added without fabricating new files.
[cost $0.1041, opencode tokens {"total": 8287012, "input": 360664, "output": 24862, "reasoning": 19118, "cache.write": 0, "cache.read": 7882368}]
