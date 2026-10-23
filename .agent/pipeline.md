# job job-pre20-10240301  started 2026-10-23T18:01:44Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done and committed as `04900f0` (no push).

**Change**
- Literal non-BMP `chr()` is now refused at build time by name: `chr() of the non-BMP code point U+1F600 ...`.
- Runtime non-BMP values now stop with `AIL limit: chr_non_bmp` instead of an internal error.
- Typed/default path is unchanged and still matches CPython.
- Added `AIL_CURRENT/test_ail_pre20.py` (3 tests), registered it in `ail_check.py`, updated `DIFFERENCES.md`, both `DEVLOG.md`s, and `MANIFEST.json`.

**Tests**
- `python3 tools/par_check.py -j 2 test_ail_pre20 test_ail_safetynet test_ail_files test_ail_corpus_findings3`
- 4 modules in 312s, 0 failed (pre20 11.1s, safetynet 118.8s, files 123.7s, corpus3 193.0s).
- `python3 tools/update_manifest.py --check` passes.

**Probes**
- `pre20_literal.py`: g+d build refused by name (U+1F600).
- `pre20_literal_typed.py`: g refused by name; d matches CPython.
- `pre20_arg.py`, `pre20_list.py`, `pre20_attr.py`, `pre20_dict.py`: g exit 3 `AIL limit: chr_non_bmp`; d matches CPython.
- `pre20_bmp.py`, `pre20_types.py`: g+d match CPython.

`.agent/pipeline.md` remains untracked and uncommitted.
[cost $0.0000, opencode tokens {"total": 3802408, "input": 348934, "output": 15270, "reasoning": 28540, "cache.write": 0, "cache.read": 3409664}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `04900f0` (`git diff work..HEAD`).

**Probes** (`/tmp/rprobes`, HEAD vs `/tmp/base` via `cmp.sh`)
- `p_lit`, `p_lit_first` (U+10000), `p_lit_max` (U+10FFFF): literal non-BMP is refused by name on HEAD (g and untyped d); base gave the internal error, exit 1 on both. Fixed by the permitted compile-time refusal.
- `p_lit_var`: typed `main` — g refuses by name, d matches CPython; base g internal error, d matches.
- `p_bound` (0, 65, D7FF, E000, FFFD, FFFF), `p_lit_bmp` (literal U+FFFF), `p_neg` (-1, 0x110000, -0x1F600), `p_bool`: g+d match CPython.
- `p_expr`, `p_dyn`, `p_list`, `p_attr`, `p_dict` (non-BMP through variable/argument/list/attribute/dict): HEAD g exits 3 with `AIL limit: chr_non_bmp`, d matches; base g exits 1 with the internal error, d matches — pre-existing, now declared.
- `p_dead` (uncalled function): HEAD g refuses syntactically; base built and matched. This is the task's allowed "refuse the construct" option, not reachability-gated.
- Non-feature `p_plain`: typed default `program.c` identical base vs HEAD; general differs only in the embedded `ail_bi_chr` body, as intended.

**Tests / records**
- `test_ail_pre20` 10.8s and `test_ail_safetynet` 116.6s: 0 failed.
- `python3 tools/update_manifest.py --check` passes; the new test is registered and in `MANIFEST.json`; both DEVLOGs have the dated entry; commit trailer is present.

**Report claims**
- Verified: literal refusal, runtime named limit, typed/default path matching, tests, manifest, records.
- Unverified: the worker's `test_ail_files` / `test_ail_corpus_findings3` numbers were not re-run, per the reviewer scope.
- Speed: no hot-path change; no icount needed.

**Pre-existing**
- Dynamic non-BMP `chr()` still differs from CPython on the general path; this was already a difference on the base (internal error) and is now a declared named limit.
- Changing the shared runtime body necessarily changes the embedded C of every general-path program; no generated code outside that helper changed.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1036075, "input": 41683, "output": 5281, "reasoning": 15415, "cache.write": 0, "cache.read": 973696}]

FINAL VERDICT: ACCEPT  2026-10-23T18:23:41Z
