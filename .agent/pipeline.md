# job job-fuzz51-10231205  started 2026-10-23T03:06:36Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Found and fixed a silent wrong answer: `bytes`/`bytearray` `ljust`, `rjust`, and `center` with an explicit `None` fillchar padded with spaces instead of raising CPython's `TypeError`.

- Cause/fix: `None` was the omitted-fill sentinel in `prelude_bytes.py:312`; replaced with a private sentinel, with matching signatures in `safetyrt.py:2115`.
- Regression: `AIL_CURRENT/test_ail_fuzz51.py`; probes `p91`–`p93` now match CPython on both builds.
- Tests: fuzz51, safetynet, files, corpus_findings3 (4/4), plus 4 targeted bytes/API modules (4/4); manifest check passes.
- Commit: `70cadf7`.
- Pre-existing, not silent: `bytes.strip(None)`/`lstrip`/`rstrip` are refused by name, and wrong-type fillchar messages differ.
[cost $0.0000, opencode tokens {"total": 32639626, "input": 985125, "output": 83426, "reasoning": 103299, "cache.write": 0, "cache.read": 31467776}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**Change:** Bytes/bytearray `ljust`/`rjust`/`center` used `None` as the omitted-fillchar sentinel, so explicit `None` silently padded with spaces. The worker substituted a private sentinel in `prelude_bytes.py:312` and updated the generated signatures in `safetyrt.py:2115`.

**Probes (`/tmp/rprobes`):**
- `p1` — bytes/bytearray padding with omitted, explicit `None`, and valid fillchars; widths `-100,-1,0,1,3,4,5,6,1000`; values via argument, list item, attribute, dict value, nested call. Base: silent padding for all `None` cases. HEAD: same stdout as CPython on both builds, including exact TypeError messages. Fix confirmed.
- `p2` — wrong fillchar types and other bytes methods. Only `wrong_int`/`wrong_str` messages differ (`a bytes-like object is required` vs `...must be a byte string of length 1`); identical on base, so pre-existing. `wrong_len`, `wrong_empt`, zfill, expandtabs match.
- `p4` — `bytes.strip(None)`/`lstrip`/`rstrip`: refused by name on both HEAD and base; pre-existing.
- `p6`, `p8` — the requested str area: replace with empty old (counts `-2,0,2,9`), strip-all chars, center even/odd/negative widths, zfill signs (`-`,`+`,`--`,`-+`,`+-`), expandtabs `0`/negative/large, unicode fillchars, multi-char fill errors. All match CPython on both builds.
- `p7` — keyword fillchar: CPython rejects keyword args for bytes methods; AIL accepts them. Same on base, pre-existing. Explicit `None` keyword is now a TypeError instead of silent padding.
- `p5` — non-feature program (no bytes padding): `program.c` byte-identical between base and HEAD; only `native_report.json` temp paths differ.

**Tests:** `test_ail_fuzz51`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`4 modules, 0 failed`). `tools/update_manifest.py --check` exits 0.

**Report claims:** sentinel/fix, commit `70cadf7`, test results, manifest — verified. “p91–p93 match” — covered by `p1` (verified). “4 targeted bytes/API modules” — unverified (not named). Pre-existing differences — verified.

**Speed:** no `~/corpus/gdev` program uses bytes/bytearray padding, so the changed helper is not on any hot corpus path; no icount regression run needed.

**Pre-existing:** wrong-type fillchar messages, `strip(None)` refusal by name, and keyword-argument acceptance on bytes methods. None caused by this change.

**Minor note:** the new `DIFFERENCES.md` row describes a now-fixed silent difference rather than a remaining deliberate difference; documentation-only.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 939979, "input": 39053, "output": 7992, "reasoning": 9350, "cache.write": 0, "cache.read": 883584}]

FINAL VERDICT: ACCEPT  2026-10-23T04:30:50Z
