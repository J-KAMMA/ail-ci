# job job-fuzz33-10230814  started 2026-10-22T23:15:50Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Found and fixed a real silent wrong answer.

## What was wrong
`str.split`/`rsplit`/`splitlines` silently ignored a keyword when the same parameter was already supplied positionally. CPython raises `TypeError`; AIL printed a normal result:

- `"a,b".split(",", sep="-")` → AIL `['a', 'b']`, CPython `TypeError: argument for split() given by name ('sep') and position (1)`
- `"a,b,c".split(",", 1, maxsplit=2)` → same class of difference
- `"a\nb".splitlines(True, keepends=False)` → AIL `['a\n', 'b']`, CPython `TypeError: splitlines() takes at most 1 argument (2 given)`

Root cause: `_sep_maxsplit` merged keywords into free positional slots and dropped colliding ones; `_m_splitlines` preferred the positional and ignored `keepends`.

## Fix (commit `4ec24bdd`)
`AIL_CURRENT/python/pkg-v12/pyboxed2.py`: refuse a keyword whose positional slot is already filled, by name at compile time (same treatment `expandtabs`'s `tabsize` already had). Valid keyword forms are untouched. Added `AIL_CURRENT/test_ail_fuzz33.py` and registered it in `ail_check.MODULES`; refreshed `MANIFEST.json` (`--check` exits 0).

## Probes
~65 probes under `/tmp/probes/`, all on both builds (`g`, `d`):
- split/rsplit/partition/rpartition/splitlines/join over empties, unicode, NUL/control chars, maxsplit bounds, aliasing, slices, views, typed/untyped, iterables, mutation, threshold sizes (>15 separators, >96 bytes, 32/33 whitespace pieces), non-ASCII fuzz, keyword forms: **matched CPython**.
- `p61b` (`split`/`rsplit` duplicate `sep`/`maxsplit`) and `p61c` (`splitlines(True, keepends=...)`): **silent diff found** → now named refusals.
- `p62` starred split args, `p61d` extra `join` arg: named refusals (acceptable). `p63` positional + keyword `maxsplit`: matches CPython.
- `lab/fuzz` seeds 0–119: 0 DIFF.

## Tests on final commit
`test_ail_fuzz33`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → **0 failed** (159s). Also ran `test_ail_spec_fixes`, `test_ail_fuzz3`, `test_ail_fuzz3n`, `test_ail_fuzz_findings` → 0 failed.

## Notes
- No other differences found; only named refusals (non-BMP literal, int64-min literal, `**kwargs`, starred calls, unexpected/extra args).
- `DEVLOG`/`DIFFERENCES` files do not exist anywhere in this export (`git ls-files` has none), so no rows could be added.
- Working tree clean except the pipeline-managed `.agent/pipeline.md`.
[cost $0.0000, opencode tokens {"total": 19842851, "input": 571947, "output": 39229, "reasoning": 70459, "cache.write": 0, "cache.read": 19161216}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

Change: `4ec24bd` — compile-time refusal when `split`/`rsplit`/`splitlines` get a keyword already filled by a positional. 4 files, no runtime code.

### Probes (HEAD, both `g` and `d`; base where relevant)

| probe | content | result |
|---|---|---|
| p1 | all valid kw forms: `sep=`, `maxsplit=`, both orders, `split(None,1)`, `split(maxsplit=-1/0)`, `splitlines(keepends=...)` | matches CPython |
| p2 | duplicate `sep`/`maxsplit`/`keepends` in `split`/`rsplit`/`splitlines` | HEAD: named refusal; `/tmp/base`: silent wrong output (the reported defect) |
| p3 | same forms reached via function arg, list item, attribute, dict value | matches CPython |
| p4 | empty separator, multi-char separator, maxsplit 0, empty string, `\r\n`/`\r` splitlines | matches CPython (empty sep → ValueError) |
| p5 | `join` non-str → TypeError, `partition`/`rpartition` missing sep, negative/huge maxsplit | matches CPython |
| p6 | no changed feature | generated `program.c` identical HEAD vs base |
| p7 | starred call forms `split(*[], sep=...)`, etc. | refused identically on base and HEAD → pre-existing |
| p8 | `join` extra positional | named refusal |

Generated C for p1 (valid keyword forms) is byte-identical between HEAD and base, so no codegen/speed change. Change is compile-time only; no hot-path impact.

### Tests
- `test_ail_fuzz33`, `test_ail_safetynet`: **0 failed** (78 s).
- `python3 tools/update_manifest.py --check`: exit 0.
- `git diff --check`: clean.

### Claims
- Silent duplicate-keyword bug: **verified** (p2 base vs CPython).
- Refusals for all three methods: **verified** (p2, tests).
- Valid keyword forms unchanged: **verified** (p1 both builds, identical C).
- Test module added/registered + manifest: **verified**.
- DEVLOG/DIFFERENCES absent from export: **verified** (`git ls-files`, `find`).
- `test_ail_files`/`test_ail_corpus_findings3` re-run: **unverified** (not rerun per review budget).
- `lab/fuzz` seeds 0–119: **unverified** (not rerun).

### Pre-existing
- Starred-call forms refused on both base and HEAD, identical — not caused by this change.
- No other difference seen in the probed area.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 540727, "input": 61437, "output": 5035, "reasoning": 8591, "cache.write": 0, "cache.read": 465664}]

FINAL VERDICT: ACCEPT  2026-10-23T00:04:12Z
