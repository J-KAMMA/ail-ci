# job job-pre18-10240245  started 2026-10-23T17:48:00Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first recorded pre-existing difference (`format('x', ' z')`: `Sign not allowed...` vs CPython's `Space not allowed...`).

- Commit `7d1620b` on `job-pre18-10240245`.
- `safetyrt.py`: distinguish a space sign from `+`/`-`.
- `pyboxed2.py`: route str specs carrying any sign to `safetyrt.FMT`; the core formatter silently ignored them.
- Added and registered `test_ail_pre18.py`; added DEVLOG entry; updated manifest.

Verification on the final commit:
- `test_ail_pre18`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 4 modules, 0 failed (302s).
- `update_manifest.py --check`: rc 0.
- Probes, both `g` and `d` builds identical to CPython: `pre18_direct` (recorded case), `pre18_direct2`, `pre18_literal`, `pre18_full` (sign spellings, widths, empty/non-ASCII, argument/list/attribute/dict sources, numeric types), `pre18_strformat` (str.format path).
- `ci_shards.py --check` still reports unassigned `test_ail_fuzz20`, `test_ail_fuzz22` (pre-existing) and the new `test_ail_pre18`; the workflow runs unassigned modules by name, as noted in the task.
[cost $0.0000, opencode tokens {"total": 5588921, "input": 130830, "output": 11094, "reasoning": 19413, "cache.write": 0, "cache.read": 5427584}]

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `7d1620b`**

Diff: `safetyrt.py` now names the space-sign ValueError; `pyboxed2.py` routes statically-str specs carrying a sign to `safetyrt.FMT`; new `test_ail_pre18.py`, manifest/`ail_check` registration, DEVLOG.

**Probes (HEAD, g+d vs CPython)**
- `rp_signs`: space/`+`/`-`, widths, fills (`+<5`, `-<5`, ` <5`), empty/non-ASCII, arg/list/attr/dict sources — matches except pre-existing invalid-spec wording.
- `rp_fstring2`: literal/nested/computed specs, numeric values — matches.
- `rp_strformat`: `str.format` literal and computed specs — matches (base had `Sign` for space).
- `rp_numeric`: int/bool/float sign flags, aliases/containers — matches.
- `rp_conv`: `!s`/`!r` conversions mostly match; remaining mismatches are base-identical.
- `rp_unrelated` and `rp_nosign`: `--debug-dir` `program.c` byte-identical to `/tmp/base`; HEAD-vs-base diffs in sign probes are only the intended `Space` vs `Sign` corrections.

**Pre-existing (identical on base, non-blocking)**
- Invalid-spec message lacks the `'<spec>' for object of type 'str'` suffix (`" +5"`, `"0+5"`, `"  .2s"`).
- `z` flag on str: `format('x','z')` gives `'x'`; `format('x','z#')` gives the alternate-form error.
- `f"{42!s:+5}"` / `f"{42!r:+5}"` return `'42   '` instead of `Sign not allowed`.
- Other recorded fuzz66 diffs remain: `format(1e300,'#')` -> `1e+300`; `10**30` integer overflow.

**Tests / checks**
- `test_ail_pre18`, `test_ail_safetynet`: 2 modules, 0 failed. `test_ail_files`, `test_ail_corpus_findings3`: 0 failed.
- `test_ail_pre18` fails on `/tmp/base`, so it does exercise the fix.
- `update_manifest.py --check` rc 0; `ci_shards.py --check` shows only the reported unassigned modules.
- All five worker-listed probes re-run: same stdout as CPython on both builds.
- Speed: `perf_event_open` denied (verified), so instruction counts unavailable; non-format C is unchanged.

All report claims verified, except “routes str specs carrying any sign” is true only for statically-str values; `!s`-converted non-str values still take the core path (pre-existing, base-identical).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2445834, "input": 66099, "output": 11286, "reasoning": 20161, "cache.write": 0, "cache.read": 2348288}]

FINAL VERDICT: ACCEPT  2026-10-23T18:14:36Z
