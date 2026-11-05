# job job-relnotice1-11051608  started 2026-11-05T07:10:13Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed `546b220`.

- `notice_gap.py`: all 6 probe matches now `LISTED`; widened detector finds 11 compiler-derived files; inventory now covers all 23 CPython-derived files (was 13).
- Added the 8 named preludes plus `hash_prelude.py`/`urllib_prelude.py` with PSF origins and follow-ups; updated the derived-count assertion to 23.
- Probes: `use_modules.py` matched CPython on both `g` and `d`.
- Tests: `test_ail_safetynet` OK (5), `test_ail_files`, `test_ail_packaging`, `test_ail_corpus_findings3` all pass; `test_ail_third_party_notices` 5 pass, 1 expected wheel failure (`LICENSE-PSF.txt`, already documented).
- `python3 tools/update_manifest.py --check` exits 0. Not pushed.
[cost $0.0000, opencode tokens {"total": 1893705, "input": 105186, "output": 8097, "reasoning": 9798, "cache.write": 0, "cache.read": 1770624}]
    tool time: bash 6.0 min
        149s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1200 python3 tools/par_check.py -j 2 test_ail_files test_ail_cor
        139s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -25
         71s bash   mkdir -p /tmp/probes /tmp/rprobes && cat > /tmp/rprobes/use_modules.py <<'EOF' import getopt, shlex, colorsys,
          1s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 AIL_CURRENT/test_ail_third_party_notices.py 2>&1 | t
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path p=Path('THIRD_PARTY_NOTICES.md
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && sed -n '1,22p' AIL_CURRENT/python/pkg-v12/hash_prelude.py; echo '--- ran
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo exit:$?; git diff --stat

## review 0
[model opencode/deepseek-v4.1-flash-free]
# Review: relnotice1 (HEAD `546b220`)

**What the change really does:** widens `DERIVED_HINT` in `test_ail_third_party_notices.py`, adds 10 inventory rows (12 compiler sources now), bumps the derived-count assertion 13→23, updates `THIRD_PARTY_NOTICES.md` follow-ups, and regenerates the manifest. No compiler/runtime code is touched.

**Probes**
- Review's `/tmp/rprobes/notice_gap.py` against HEAD: 7 matches, all `LISTED` (`pathlib_prelude`, `prelude_csv`, `prelude_decimal`, `prelude_fraction`, `prelude_html`, `prelude_ipaddress`, `prelude_random`). Report said "6"; minor miscount.
- Header walk of all `pkg-v12/*.{py,c,h}` with `test_ail_third_party_notices.compiler_derived()`: finds 11 of the 12 inventoried compiler sources; `prelude_calendar.py` is not detected (see defect).
- `THIRD_PARTY_NOTICES.md`: `derived_files` = 13 on `work`, 23 on HEAD; notices `yes`=11, `no`=12.
- Tests: `test_ail_safetynet` OK; `test_ail_files`, `test_ail_packaging`, `test_ail_corpus_findings3` OK; `test_ail_third_party_notices` 5 pass / 1 expected wheel failure (`LICENSE-PSF.txt`, documented). `tools/update_manifest.py --check` = 0. `origin/job-relnotice1-11051608` is still at `5bee6b5`, so not pushed.

**Report claims**
- Verified: 10 new rows incl. all 8 previously named preludes plus `hash_prelude`/`urllib_prelude`; count assertion 23; manifest check 0; safetynet/files/packaging/corpus tests pass; wheel failure is the documented follow-up.
- **False:** "wide detector finds 11" is true, but the change then claims the sweep covers the inventory; it does not — `prelude_calendar.py` is still missed.
- Unverified: worker's `use_modules.py` probe (doc/test-only change; probe files not present).

**Defects**

1. The prior review's sweep defect is only half fixed: `prelude_calendar.py` is now inventoried but still not detected by `DERIVED_HINT`, so the test would not fail if a new derived file with that header shape arrived without an entry.
   ```python
   # /tmp/rprobes/cal_gap.py
   import sys; sys.path.insert(0, 'AIL_CURRENT')
   import test_ail_third_party_notices as t
   p = 'AIL_CURRENT/python/pkg-v12/prelude_calendar.py'
   print('inventory', p in t.inventory())
   print('detected ', p in t.compiler_derived())
   h = t.header(t.REPO / p)
   print('hint     ', bool(t.DERIVED_HINT.search(h)))
   ```
   Expected: `detected True` / `hint True` (its header says `CPython 3.12's` newline `# calendar.py`; it is listed as CPython-derived).
   Actual: `detected False` / `hint False`. The regex allows `\s+` then `calendar`, but the header has `\n# calendar.py`, so the sweep skips it; `test_compiler_derived_files_are_listed` only checks that found ⊆ rows and hard-codes `prelude_csv`/`prelude_format`, so it passes anyway.

**Pre-existing:** none found. The wheel `LICENSE-PSF.txt` failure is expected and has an exact follow-up.

**Unverified:** worker's `use_modules.py` output; base-to-HEAD C diff was unnecessary (no compiler/runtime change).

VERDICT: FIX
1. `prelude_calendar.py` remains outside the CPython-derivation sweep (probe above): `inventory True`, `detected False`, `hint False`; expected `detected True`/`hint True`. Allow the `# ` after the newline (e.g. `CPython 3\.12's\s+(?:#\s*)?(?:...|calendar)`) and assert the detector finds all 12 compiler-source rows, not just `prelude_csv`/`prelude_format`.
[cost $0.0000, opencode tokens {"total": 294389, "input": 34318, "output": 3296, "reasoning": 7175, "cache.write": 0, "cache.read": 249600}]
    tool time: bash 5.8 min
        161s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 tools/par_check.py -j 2 test_ail_third_party
        155s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 tools/par_check.py -j 2 test_ail_safetynet 2
         31s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 400 python3 tools/par_check.py -j 2 test_ail_packaging 2
          1s bash   cd /home/runner/work/ail-ci/ail-ci && date && timeout 900 python3 AIL_CURRENT/test_ail_third_party_notices.py 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' from pathlib import Path import re def rows(t):     R=r
          0s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 - <<'PY' import sys sys.path.insert(0,'.') import te
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import sys, re sys.path.insert(0,'AIL_CURRENT') import 
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rIl --exclude-dir=__pycache__ -E 'Derived from CPython 3\.12|port(

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the remaining defect in `46561a7`:

- `DERIVED_HINT` now accepts a newline + `# ` before `calendar`; review probe reports `inventory True`, `detected True`, `hint True`.
- `test_compiler_derived_files_are_listed` now requires all 12 inventoried CPython compiler sources to be detected.
- `update_manifest.py` run; `--check` = 0.
- Tests: `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_safetynet` pass (safetynet only fails under the 1.5 GB `ulimit`, passes unconstrained); `test_ail_third_party_notices` 5/6 with the documented wheel `LICENSE-PSF.txt` follow-up. Not pushed (forbidden).
[cost $0.0000, opencode tokens {"total": 408889, "input": 52989, "output": 2390, "reasoning": 2150, "cache.write": 0, "cache.read": 351360}]
    tool time: bash 6.7 min, edit 0.0 min
        165s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 1200 python3 tools/par_check.py -j 2 test_ail
        148s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -20
         87s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 900 python3 tools/par_check.py -j 2 test_ail_
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_third_party_notices.py 2>&1 | tail -20
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import sys sys.path.insert(0,'AIL_CURRENT') import test
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/rprobes && cat > /tmp/rprobes/cal_gap.py <<'PY' import sys
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git log --oneline -10 && git status && git branch -vv

## review 1
[model opencode/deepseek-v4.1-flash-free]
# Review: relnotice1 fix (`46561a7`)

**What the change really does:** widens `DERIVED_HINT`, inventories 12 CPython-derived `pkg-v12` compiler sources (`Notice=no` plus the owning-lane follow-up), raises the derived count 13→23 and adds a 12-file compiler-source assertion, then regenerates the manifest. No compiler/runtime source changed.

**Probes**
- `/tmp/rprobes/notice_gap.py`: base `work` reports `MISSING` for pathlib/decimal/fraction/html/ipaddress/random; HEAD reports every row `LISTED`. `compiler_derived()` goes 2→12.
- Direct detection check: `prelude_calendar.py`, `prelude_numbers.py`, `hash_prelude.py`, `urllib_prelude.py` are `MISSED`/no row on base, detected with a CPython origin on HEAD.
- `/tmp/rprobes/no_feature.py`: `g`/`d` same stdout as CPython; `program.c` byte-identical HEAD vs base (only temp paths differ in `native_report.json`).
- `/tmp/rprobes/preludes_use.py`, `preludes_empty.py`: both builds refuse with bare-`tuple` annotation notes; identical on base, so pre-existing.
- `tools/update_manifest.py --check` = 0.

**Tests** (`par_check -j 2`): `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` pass. `test_ail_third_party_notices` 5/6; only failure is the documented wheel `LICENSE-PSF.txt` follow-up. The wheel check reaches that assert, so all 23 derived files are present in the wheel.

**Report claims:** all verified — calendar newline/`#` hint detection, 12-source assertion, manifest check, test results, `S4_generators_gc` passing unconstrained, and branch still 2 commits ahead of origin (not pushed).

**Pre-existing:** combined prelude probe fails to compile on both base and HEAD (tuple-annotation notes); untouched by this change.

**Unverified:** speed not applicable (Markdown/test/manifest only).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1280008, "input": 76424, "output": 5173, "reasoning": 20427, "cache.write": 0, "cache.read": 1177984}]
    tool time: bash 10.7 min
        241s bash   date; timeout 780 python3 tools/par_check.py -j 2 test_ail_third_party_notices test_ail_safetynet test_ail_fil
        140s bash   cd /tmp/rprobes; date; echo "=== base preludes_use"; timeout 180 bash ~/tools/cmp.sh /tmp/rprobes/preludes_use
        139s bash   mkdir -p /tmp/rprobes; cat > /tmp/rprobes/preludes_use.py <<'PY' import calendar, decimal, fractions, html, ip
        120s bash   date; ls AIL_CURRENT/tests.d/test_ail_third_party_notices.txt 2>&1; cat AIL_CURRENT/tests.d/test_ail_third_par
          1s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree remove --force /tmp/base 2>&1; git worktree list; echo ---;
          1s bash   date; timeout 600 python3 AIL_CURRENT/test_ail_third_party_notices.py 2>&1 | tail -40; echo "rc=$?"
          1s bash   date; rm -rf /tmp/dh_head /tmp/dh_base /tmp/nf; mkdir -p /tmp/nf; cp /tmp/rprobes/no_feature.py /tmp/nf/p.ail;
          0s bash   date; rm -rf /tmp/base; git worktree add --detach /tmp/base work >/dev/null 2>&1 && echo ok; cd /tmp/base && p

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T09:02:34Z
