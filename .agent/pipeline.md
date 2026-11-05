# job job-relcheck1-11051133  started 2026-11-05T02:36:43Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented the release-0.1 preflight.

- `tools/release_check.py`: 11 checks, aligned PASS/FAIL/INFO/SKIP output, summary, `--json`, `--repo`, `--branch`, `--remote`, `--online`, `--build`; read-only via `git show`.
- `AIL_CURRENT/test_ail_release_check.py`: 8 tests over a temp git fixture; registered in `tests.d`; manifest updated and `--check` clean.
- `lab/release/PREFLIGHT.md`: today’s full output and the fix for each FAIL.

Verification: new tests 8/8 pass; `test_ail_files` 18/18, `test_ail_corpus_findings3` 2/2, `test_ail_safetynet` 5/5. Under the 1.5 GB cap only `S4_generators_gc` fails with `generator: no stack`; it passes uncapped, and no compiler files were changed. Commits: `b8a302c`, `4d49acf`. Not pushed.
[cost $0.0000, opencode tokens {"total": 2259313, "input": 94328, "output": 12686, "reasoning": 19947, "cache.write": 0, "cache.read": 2132352}]
    tool time: bash 12.9 min, edit 0.0 min, write 0.0 min
        498s bash   ulimit -v 1500000 for t in test_ail_files test_ail_corpus_findings3 test_ail_safetynet; do   echo "== $t =="  
        191s bash   python3 AIL_CURRENT/test_ail_safetynet.py >/tmp/test_ail_safetynet_nocap.out 2>&1; echo "exit=$?"; tail -4 /tm
         68s bash   python3 /tmp/run_s4_detail.py 2>&1 | tail -20
          4s bash   cat >/tmp/run_s4.py <<'PY' import sys, tempfile sys.path.insert(0, '/home/runner/work/_temp/w2/AIL_CURRENT') i
          4s bash   cat >/tmp/run_s4_detail.py <<'PY' import sys, tempfile, subprocess from pathlib import Path sys.path.insert(0,
          3s bash   ulimit -v 1500000; python3 tools/release_check.py --branch HEAD --build | tail -6; echo "exit=${PIPESTATUS[0]}
          2s bash   git add lab/release/PREFLIGHT.md git commit -q -m "Record the release-0.1 preflight report  Co-Authored-By: Cl
          1s bash   python3 AIL_CURRENT/test_ail_release_check.py -v; echo "exit=$?"

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: relcheck1

**What the diff really does.** Adds a read-only `tools/release_check.py` (11 checks, PASS/FAIL/INFO/SKIP, summary, `--json`, `--repo`, `--branch`, `--remote`, `--online`, `--build`), an 8-test fixture suite under `AIL_CURRENT`, its `tests.d` registration plus two manifest rows, and `lab/release/PREFLIGHT.md`. No compiler, runtime, or `.github` files are touched, so generated C cannot change. This matches the worker report.

**Verification run (HEAD 4d49acf)**
- `AIL_CURRENT/test_ail_release_check.py`: 8/8 pass, 0.8 s.
- `python3 ../tools/par_check.py -j 2 test_ail_release_check test_ail_safetynet`: release check ok; safetynet fails only `S4_generators_gc` under the 1.5 GB cap. Uncapped: 5/5 OK (188 s). Pre-existing/environmental: no compiler files changed and the same test file is in `work`.
- `tools/update_manifest.py --check`: exit 0. `tools/ci_shards.py --check`: exit 0 (new module is spread dynamically; not a defect).
- `release_check.py --branch origin/integ` output matches `lab/release/PREFLIGHT.md` exactly; check 1 reason is exactly `0.1.0.dev0 is a development version`.
- `release_check.py --branch HEAD --build`: check 11 PASS, `built ailc-0.1.0.dev0-py3-none-any.whl`.
- `git diff --name-only work..HEAD`: only the six allowed files.

**Probes** (fixture repos under `/tmp/rprobes`, all with `--remote ''` where the fixture has no `origin`):
- `light`: lightweight tag `v0.1.0` on main → PASS (control).
- `diffempty`: empty status + both table layouts → `4 open or empty rows` (correct).
- `annot`, `devheading`, `vheading`, `localver`: defects below.

**Defects**

1. **Check 9 rejects an annotated release tag that points at main.** Probe `/tmp/rprobes/annot` (final version 0.1.0, `git tag -a v0.1.0 -m release` on main), command `python3 tools/release_check.py --repo /tmp/rprobes/annot --branch main --remote ''`. Expected `PASS 9 tag ... tag v0.1.0 points at main`; actual `FAIL 9 tag ... tag v0.1.0 points at fef5c5236701, not main`, exit 1. Cause: `git rev-parse refs/tags/v0.1.0` returns the tag object, not its commit; it needs `^{commit}`. A signed/annotated tag is a normal release tag.

2. **Check 2 mishandles the version in a heading.** Two probes:
   - `/tmp/rprobes/devheading` (version 0.1.0, heading `## 0.1.0.dev0`): expected FAIL (no heading for final 0.1.0), actual `PASS 2 changelog ... CHANGELOG.md has a heading for 0.1.0`, exit 0. The `\b` after the version matches before `.dev0`.
   - `/tmp/rprobes/vheading` (version 0.1.0, heading `## v0.1.0`): expected PASS, actual `FAIL 2 changelog ... CHANGELOG.md has no heading for 0.1.0`, exit 1. The `\b` before the version does not match after `v`.
   So check 2 can both pass a pre-release heading and reject a valid `v`-prefixed heading.

3. **Check 1 rejects a final release with a local version label.** Probe `/tmp/rprobes/localver`, `__version__ = "0.1.0+local"`: expected PASS (a final release; `+local` is a local label, not a pre-release), actual `FAIL 1 version 0.1.0+local is a development version`, exit 1. The unanchored `(?:a|b|rc|dev)` matches letters inside the label (also `+ubuntu`).

**Observation, not counted as a defect.** Check 7 reports 15 open rows, but `HEAD:DIFFERENCES.md` has 17 rows containing an `open` cell. The two missed rows (`C?-job-prog30-11021835-1`, `C?-job-pre128-10242352-2`) put `open` in the third column with prose in the declared status column, so this is arguably malformed data rather than a parser bug; the FAIL/PASS decision is unchanged.

**Pre-existing.** `S4_generators_gc` fails only under the 1.5 GB cap; it passes uncapped on HEAD and no compiler/runtime file changed, so it is not caused by this change.

**Unverified.** `test_ail_files` / `test_ail_corpus_findings3` claims (not rerun per instructions); check 10 `--online` (no network/`gh` probe).

Claims in the worker report are otherwise verified; the diff does what the report says, but check 9's annotated-tag false FAIL is a wrong release-gate result.

VERDICT: FIX

1. Check 9 must compare the tag's peeled commit (`v<version>^{commit}`) with main; annotated tags on main currently FAIL. Probe `/tmp/rprobes/annot`.
2. Check 2's heading match must not accept `## 0.1.0.dev0` for version `0.1.0` and must accept `## v0.1.0`. Probes `/tmp/rprobes/devheading`, `/tmp/rprobes/vheading`.
3. Check 1 must not treat letters inside a local label (`0.1.0+local`) as a pre-release marker. Probe `/tmp/rprobes/localver`.
[cost $0.0000, opencode tokens {"total": 1815823, "input": 195734, "output": 7009, "reasoning": 31000, "cache.write": 0, "cache.read": 1582080}]
    tool time: bash 5.4 min, read 0.0 min
        188s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT; timeout 420 python3 test_ail_safetynet.py 2>&1 | tail -8; ech
        128s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && ulimit -v 1500000; python3 ../tools/par_check.py -j 2 test_
          3s bash   date; cd /home/runner/work/_temp/w2; ulimit -v 1500000; timeout 300 python3 tools/release_check.py --branch HE
          1s bash   date; cd /home/runner/work/_temp/w2; python3 AIL_CURRENT/test_ail_release_check.py -v 2>&1 | tail -15; echo "e
          0s bash   mkdir -p /tmp/rprobes && cat > /tmp/rprobes/fixture.py <<'PY' import os, subprocess, sys, shutil from pathlib 
          0s bash   cd /home/runner/work/_temp/w2; git diff --name-only work..HEAD; echo "=== tests.d ==="; cat AIL_CURRENT/tests.
          0s bash   cd /home/runner/work/_temp/w2; git rev-parse origin/integ; git rev-parse HEAD; echo "=== manifest check real e
          0s bash   cd /home/runner/work/_temp/w2; echo "=== ANNOTATED TAG, remote='' ==="; python3 tools/release_check.py --repo 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all three review defects and committed on `job-relcheck1-11051133`.

**Changes**
- Check 9: peel annotated tags with `refs/tags/v<version>^{commit}` before comparing to main.
- Check 2: exact version boundaries; rejects `## 0.1.0.dev0`, accepts `## v0.1.0` and `## [0.1.0]`.
- Check 1: strips the `+local` label before looking for pre-release markers.
- Added 4 regression tests (12 total), updated the manifest.

**Probes (fixture repos)**
- `annot`: PASS 9 `tag v0.1.0 points at main`; advanced main still FAIL 9.
- `devheading`: FAIL 2 `no heading for 0.1.0`.
- `vheading`: PASS 2.
- `localver` / `ubuntulocal`: PASS 1 as final releases.
- `light`: PASS 9 (control).

**Tests on final commit**
- `test_ail_release_check`: 12/12 pass.
- `test_ail_files`: ok; `test_ail_corpus_findings3`: ok.
- `test_ail_safetynet`: 5/5 pass uncapped; `S4_generators_gc` still fails only under the 1.5 GB cap (pre-existing/environmental).
- `update_manifest.py --check` and `ci_shards.py --check`: exit 0.
- `release_check.py --branch origin/integ` still matches `lab/release/PREFLIGHT.md` exactly.

Commits: `fc6df48`, `6ef6c97`. Diff vs `origin/integ` is only the six allowed files. Not pushed.
[cost $0.0000, opencode tokens {"total": 717373, "input": 30205, "output": 4838, "reasoning": 6874, "cache.write": 0, "cache.read": 675456}]
    tool time: bash 30.5 min
        625s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && ulimit -v 1500000; timeout 880 python3 ../tools/par_check.py -j 2
        502s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && ulimit -v 1500000; timeout 880 python3 ../tools/par_check.py -j 2
        358s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 600 python3 test_ail_safetynet.py 2>&1 | tail -8; echo "e
        334s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 500 python3 test_ail_safetynet.py 2>&1 | tail -12; echo "
          4s bash   cd /home/runner/work/_temp/w2 && python3 - <<'PY' from pathlib import Path p = Path('tools/release_check.py') 
          2s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py && python3 tools/update_manifest.py --check;
          1s bash   cd /home/runner/work/_temp/w2 && timeout 300 python3 AIL_CURRENT/test_ail_release_check.py -v 2>&1 | tail -25;
          1s bash   mkdir -p /tmp/rprobes && cat > /tmp/rprobes/make.py <<'PY' import os, subprocess, sys, shutil from pathlib imp

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: relcheck1 fix

**What the diff really does.** The two commits only change `tools/release_check.py`: check 9 peels `refs/tags/v<version>^{commit}`, check 1 splits off `+local` and anchors pre-release markers, check 2 replaces the `\b` boundary with exact lookarounds; four fixture tests and one manifest line are added. This matches the report.

**Runs**
- `test_ail_release_check`: 12/12 pass.
- `par_check -j 2 test_ail_release_check test_ail_safetynet`: release check ok; safetynet `S4_generators_gc` fails under the 1.5 GB cap, uncapped 5/5 passes -> pre-existing, no compiler/runtime files changed.
- `update_manifest.py --check` 0; `ci_shards.py --check` 0 (module unassigned but spread by `--shard`; not a defect).
- `release_check.py --branch origin/integ` matches `lab/release/PREFLIGHT.md` exactly; `--branch HEAD --build` PASS 11.
- No C probes needed: the diff is only the six allowed non-compiler files.

**Probes** (fixture repos in `/tmp/rprobes`, `--branch main --remote ''`)
- Claimed fixes verified: annotated tag on main PASS 9, annotated tag on old commit FAIL 9; `## 0.1.0.dev0` FAIL 2, `## v0.1.0` PASS 2, `## [0.1.0]` PASS 2; `0.1.0+local`/`0.1.0+ubuntu` PASS 1, `0.1.0.dev0+local` FAIL 1.
- Defect: `0.1.0_rc1` (also `_dev1`, `_a1`) -> check 1 `PASS ... is a final release`; expected FAIL. PEP 440 accepts `_` separators; old `b8a302c` FAILed these, so the new boundary regex `(?:^|[.\-]|(?<=\d))` regressed it.
- Defect: `v0.1.0` tagged on a tree object -> check 9 `PASS ... no tag v0.1.0 yet`; expected FAIL (a tag exists and does not point at main). Old `b8a302c` FAILed; `^{commit}` failure is treated as absence.

**Claims**: all report claims verified except `test_ail_files`/`test_ail_corpus_findings3` (not rerun) and `--online` (not run).

**Pre-existing**: uppercase `0.1.0.RC1` passes check 1 on both old and new; `S4` under the cap; the check 7 15-vs-17 open-cell observation is unchanged.

**Unverified**: `--online`; `test_ail_files`; `test_ail_corpus_findings3`.

VERDICT: FIX
1. Check 1 misses underscore-separated PEP 440 pre-release markers. Probe: fixture with `__version__ = "0.1.0_rc1"`. Expected `FAIL 1 ... development version`; actual `PASS 1 ... final release` (same for `0.1.0_dev1`, `0.1.0_a1`). Allow `_` before `dev|a|b|rc`.
2. Check 9 treats a tag that does not peel to a commit as absent. Probe: `git tag -a v0.1.0 -m rel <tree>` in a fixture. Expected `FAIL 9 ... not main`; actual `PASS 9 ... no tag v0.1.0 yet`. Check for the tag first, then compare its peeled commit; FAIL when peeling fails.
[cost $0.0000, opencode tokens {"total": 1106849, "input": 87904, "output": 5795, "reasoning": 25758, "cache.write": 0, "cache.read": 987392}]
    tool time: bash 9.9 min
        312s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 500 python3 test_ail_safetynet.py 2>&1 | tail -8; echo "e
        254s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && ulimit -v 1500000; timeout 700 python3 ../tools/par_check.p
         15s bash   mkdir -p /tmp/rprobes && cat > /tmp/rprobes/probe_release.py <<'PY' import os, subprocess, sys, tempfile, shut
          6s bash   date; cd /home/runner/work/_temp/w2 && ulimit -v 1500000; timeout 300 python3 tools/release_check.py --branch 
          4s bash   cd /home/runner/work/_temp/w2 && python3 AIL_CURRENT/test_ail_release_check.py -v 2>&1 | tail -22; echo "exit=
          3s bash   cd /home/runner/work/_temp/w2 && git show b8a302c:tools/release_check.py > /tmp/rprobes/old_release_check.py &
          1s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check; echo manifest=$?; python3 tools/ci_
          0s bash   cd /home/runner/work/_temp/w2 && timeout 120 python3 tools/release_check.py --branch origin/integ > /tmp/rprob

FINAL VERDICT: FIX  2026-11-05T03:52:27Z
