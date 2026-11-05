# job job-relcheck1-11051335  started 2026-11-05T04:36:51Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed as `e1795f6`.

- Check 1: `_` now accepted as a PEP 440 pre-release separator; `0.1.0_rc1`, `_dev1`, `_a1` all FAIL with the development-version reason.
- Check 9: tag existence and commit peeling are separate; a tag on a tree now FAILs (`does not peel to a commit`) instead of passing as absent.
- Added two fixture tests for both regressions.

Verification:
- Probes: underscore pre-releases FAIL 1; `0.1.0`, `0.1.0+local` PASS 1; tag-on-tree FAIL 9; tag-on-main PASS 9; tag-on-old FAIL 9.
- `test_ail_release_check`: 14/14 OK.
- `test_ail_files`: 18 tests OK (1 skipped).
- `test_ail_corpus_findings3`: 2/2 OK.
- `test_ail_safetynet`: 5/5 OK uncapped; under the 1.5 GB cap `S4_generators_gc` fails as previously reported (pre-existing, no compiler/runtime changes).
- `update_manifest.py` ran; `--check` returns 0.
[cost $0.0000, opencode tokens {"total": 636212, "input": 45219, "output": 4147, "reasoning": 3422, "cache.write": 0, "cache.read": 583424}]
    tool time: bash 11.3 min, edit 0.0 min
        227s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 550 python3 AIL_CURRENT/test_ail_corpus_findi
        203s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 550 python3 AIL_CURRENT/test_ail_safetynet.py 2>&1 | tail -8; ec
        133s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 550 python3 AIL_CURRENT/test_ail_safetynet.py
        110s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 550 python3 AIL_CURRENT/test_ail_files.py 2>&
          2s bash   cd /home/runner/work/ail-ci/ail-ci && python3 AIL_CURRENT/test_ail_release_check.py -v 2>&1 | tail -25
          1s bash   mkdir -p /tmp/rprobes && cat > /tmp/rprobes/probe_release.py <<'PY' import os, subprocess, sys, tempfile, shut
          1s bash   cd /home/runner/work/ail-ci/ail-ci && git show --stat HEAD && git log --oneline -8 origin/integ..HEAD
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py; echo "manifest=$?"; python3 tools/upda

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: relcheck1 fix (e1795f6)

**What the diff really does.** `tools/release_check.py` adds `_` to the pre-release separator class in check 1, and check 9 now tests tag existence before peeling, reporting `does not peel to a commit` as FAIL instead of "no tag". Two fixture tests and the manifest hash are added. Matches the report; only the three allowed files change.

**Runs**
- `test_ail_release_check`: 14/14 OK.
- `par_check -j 2 test_ail_files test_ail_corpus_findings3`: both ok.
- `test_ail_safetynet`: uncapped 5/5 OK; under the 1.5 GB cap `S4_generators_gc` fails (unchanged from base).
- `update_manifest.py --check`: 0; `git diff --check`: clean; script runs on HEAD with exit 1 and correct summary.

**Probes** (fixture repos in `/tmp/rprobes`, `--remote ''`)
- Check 1 HEAD vs base: `_rc1`, `_dev1`, `_a1`, `_b2`, `_rc`, `_alpha1`, `1!0.1.0_rc1` FAIL on HEAD, PASS on base; `0.1.0`, `0.1.0+local`, `0.1.0_rc1+local` (local stripped), `_post1`, `.post1`, `_1`, `_local`, `1!2.0_3` unchanged.
- Check 9 HEAD vs base: annotated/lightweight tag on tree or blob now FAIL (`does not peel to a commit`), base PASS; absent, on-main, on-old, nested tag, and local-version tags behave identically on both.
- No compiler/runtime files touched, so C output probes and instruction counts are not applicable.

**Claims**: all verified except exact per-test counts in `test_ail_files` (module passes; skipped count not recounted) and the `18 tests` figure. `0.1.0_rc1`/`_dev1`/`_a1`, tag-on-tree, tag-on-main/old, 14/14, safetynet uncapped/capped, and manifest check all match.

**Pre-existing** (identical on base, not blocking): `0.1.0_preview1` and `0.1.0_c1` (PEP 440 spellings of rc) still PASS check 1; `S4_generators_gc` fails under the 1.5 GB cap.

**Unverified**: exact test counts within the `test_ail_files` run; `--online`.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 448768, "input": 41701, "output": 4624, "reasoning": 9611, "cache.write": 0, "cache.read": 392832}]
    tool time: bash 9.5 min
        223s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && ulimit -v 1500000; timeout 900 python3 ../tools/par_
        204s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 600 python3 test_ail_safetynet.py 2>&1 | tai
        127s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && ulimit -v 1500000; timeout 600 python3 ../tools/par_
          4s bash   cd /tmp/rprobes && sed -i "s/def first(row): return row.split()\[2\] if row else '?'/def first(row): return ro
          4s bash   cat > /tmp/rprobes/probe_release.py <<'PY' import os, subprocess, sys, tempfile, shutil from pathlib import Pa
          2s bash   cat > /tmp/rprobes/probe_extra.py <<'PY' import subprocess,sys,tempfile,shutil from pathlib import Path HEAD=P
          2s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 300 python3 test_ail_release_check.py -v 2>&1 | tail
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add -f /tmp/base work >/dev/null 2>&1; ls /tmp/base/tools/r

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-05T06:13:52Z
