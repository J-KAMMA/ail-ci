# job job-fuzz84-10231555  started 2026-10-23T06:56:33Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed `80f136d`.

**Bug fixed**
- `str.split`/`rsplit` silently ignored a keyword already supplied positionally:
  - `"a,b".split(",", sep="-")` → printed `['a', 'b']`
  - `"a,b,c".split(",", 1, maxsplit=2)`
  - `"a,b".rsplit(",", sep="-")`
- `splitlines` ignored a second `keepends`:
  - `"a\nb".splitlines(True, keepends=False)` → used `True`
- All now fail at compile time with a named refusal; valid keyword forms still match CPython.

**Verification**
- `p80a`–`p80d`: duplicate keyword probes refuse by name on both builds.
- `p61`, `p81`, `p82`: valid `sep=`/`maxsplit=`/`keepends=` forms, including values via arguments, list items, attributes, dict values, empty and negative limits — same stdout on both builds.
- Other text probes (`p64`–`p69`, `p71`, `p72`, `p75`–`p78`) matched CPython.
- Pre-existing, not fixed: non-ASCII `title`/`capitalize`/`swapcase`/`casefold` still hit general-path `AIL limit` errors.

**Tests on final commit**
- `test_ail_fuzz84`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: **4/4 pass**, 240s.
- `update_manifest.py --check`: passes.
- Added `test_ail_fuzz84.py`, root `DEVLOG.md`/`DIFFERENCES.md` (absent in this export), and registered the module.
[cost $0.0000, opencode tokens {"total": 13222979, "input": 577269, "output": 37774, "reasoning": 43072, "cache.write": 0, "cache.read": 12564864}]

## review 0 failed to run: (no final text) [cost $0.0000, opencode tokens {"total": 220758, "input": 50018, "output": 1983, "reasoning": 3509, "cache.write": 0, "cache.read": 165248}] (cut off after 60 minutes) 

## review 0
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {}]
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-23T10:03:48Z
