# job job-fuzz22-10230420  started 2026-10-22T19:21:51Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed `04840c3`.

- Boxed path now uses full-Unicode `title`/`capitalize`/`swapcase`/`casefold`, fixing `AIL limit: str_title_nonascii` / `str_lower_nonascii`.
- Added and registered `AIL_CURRENT/test_ail_fuzz22.py` covering every BMP code point plus multi-character rules.
- Passed `test_ail_fuzz22`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, plus `test_ail_gcstress`, `test_ail_fuzz3`, `test_ail_fuzz3n`; all probes now match CPython.
- Non-BMP remains unsupported by the 16-bit general runtime (pre-existing). No `DIFFERENCES.md`/`DEVLOG.md` exists in this export, so no records were added; not pushed.
[cost $0.0000, opencode tokens {"total": 11503160, "input": 323389, "output": 31820, "reasoning": 41007, "cache.write": 0, "cache.read": 11106944}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
Reviewed `work..HEAD` (`04840c3`, 5 files). Correctness probes all matched CPython or were named refusals identical on base.

**Probes** (`/tmp/rprobes`, both `g`/`d` builds unless noted)
- `p1` containers/args/attrs/list/dict values, mixed BMP → match.
- `p3`, `p4` (12k random curated), `p10` (15k random cased+combining) sequences: sigma/titlecase/combining/punctuation → match.
- `p5` empty, chained/aliased strings, 10k `ß` expansions, empty output → match.
- `p7` Cherokee `casefold`≠`lower`, `ẞ`, `İ`, `ΐ`, etc. → head matches; base dies `AIL limit: str_lower_nonascii` (the fixed defect).
- `p9`, `p15` all-BMP predicates (`isdigit/isdecimal/isnumeric/isalpha/isalnum/isspace/isidentifier/istitle`) → match.
- `p6`, `p14` `.title()` on int/list → same `AttributeError`/exit as base.
- `p11` embedded NUL/newline → match.
- `p2`/`p8`/`p12` non-BMP literal, `chr(non-BMP)`, `chr(surrogate)` → named refusals/errors identical to base (pre-existing).
- `nofeature.py`, `loweronly.py` with `--debug-dir`: generated `program.c` byte-identical to base.

**Tests on HEAD**: `test_ail_fuzz22` 18.9s, `test_ail_safetynet` 119.2s, `test_ail_files` 127.4s, `test_ail_corpus_findings3` 199.7s, `test_ail_gcstress`/`test_ail_fuzz3`/`test_ail_fuzz3n` 57s — all pass. `tools/update_manifest.py --check` passes.

**Report claims**: full-Unicode boxed case methods — verified; test added/registered and covers all BMP + multi-char — verified; all named test modules pass — verified; non-BMP pre-existing unsupported — verified; no DIFFERENCES/DEVLOG in export — true.

**Speed**: `tools/icount.c` cannot run here (`perf_event_open` EPERM, `perf_event_paranoid=4`). Relevant gdev programs (`g20_030`, `g25_040`) show no change over 200 runs. A synthetic 300k-iteration ASCII `.title()` loop is ~20–30x slower on the general path (0.01s → 0.38s user); correctness-only fallback, not hot in the corpus, but an ASCII fast path would recover it. Compile of a title program: 3.07s → 3.95s, binary 121,536 → 191,968 bytes.

**Pre-existing**: non-BMP literal/`chr`/surrogate refusals (same on base); base non-ASCII case-method limits are what this change fixes.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 5434563, "input": 105192, "output": 14635, "reasoning": 37040, "cache.write": 0, "cache.read": 5277696}]

FINAL VERDICT: ACCEPT  2026-10-22T20:43:40Z
