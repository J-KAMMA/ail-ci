# job job-ffpkg1-11081617  started 2026-11-08T07:25:26Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the three review defects by replacing the ad-hoc comparator with a faithful PEP 440 parser/specifier matcher.

- `AIL_CURRENT/ail_pkg.py`: PEP 440 version parsing/comparison, zero-padding, wildcards (`==1.0.*`), parenthesised specifiers, prerelease exclusion, and correct stable classification of local versions (`1.0.0+1abc`).
- `AIL_CURRENT/test_ail_pkg.py`: added regression tests for the three defects.
- Updated `manifest.d/21.txt`; `update_manifest.py --check` rc=0.

Probes: review probes `probe_a`–`probe_e` all pass (gamma/delta/paren accepted; `>1.0` and `>=2.0` vs rc refused; local-only version selected). Differential vs `packaging` matched except the intentional empty-spec case.

Tests on final commit `94cc32c`: `test_ail_pkg`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4/4 ok.
[cost $0.0000, opencode tokens {"total": 1859718, "input": 84373, "output": 9084, "reasoning": 15989, "cache.write": 0, "cache.read": 1750272}]
    tool time: bash 10.4 min, edit 0.0 min, read 0.0 min
        351s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 1500 python3 tools/par_check.py -j 2 test_ail
        254s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 1500 python3 tools/par_check.py -j 2 test_ail
          8s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 600 python3 tools/par_check.py -j 2 test_ail_
          7s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 300 python3 tools/par_check.py -j 2 test_ail_
          1s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/probe_review.py <<'PY' import json, os, subprocess, sys, temp
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 /tmp/probe_pep.py && ulimit -v 1500000; timeout 300 python3 tool
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git show --stat HEAD && git diff HEAD~1..HEAD --stat && git diff HEAD~1.

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report — job ffpkg1

**What the diff really does.** Commit `94cc32c` replaces `ail_pkg.py`'s ad-hoc version/specifier matcher with a self-contained PEP 440 parser (`_parse_version`/`_cmpkey`), a specifier matcher (`_accepts_python` + wildcards, `~=`, `===`, parenthesised clauses, prerelease gating), fixes `_is_stable` to parse rather than regex-match, and adds three regression test methods. No compiler/runtime file is touched (only `ail_pkg.py`, `test_ail_pkg.py`, `manifest.d/21.txt`), so generated C is unchanged.

**Probes** (`/tmp/rprobes/`, `file://` fake index):
- zero-padding: `alpha` locked `1.0.0`, `gamma` requires `alpha==1.0` -> accepted, `sync` synced 2. **fixed**
- local-only `1.0.0+1abc` -> `add loc` selects it. **fixed**
- `alpha 2.0.0rc1` + `beta requires alpha>=2.0` -> `add beta` refused by name; `sync` of a tampered lock refuses too. **fixed**
- `alpha 1.0.0` + `beta requires alpha>1.0` -> refused by name. **fixed**
- `alpha (>=1.0)` and `alpha==1.0.*` -> accepted. **fixed**
- direct differentials: version ordering 0/455 mismatches, `_is_stable` 0 mismatches, valid-specifier acceptance matches `packaging` except empty-spec (never called unguarded) and exotic `~=v1.0`/`===` raw-vs-normalized edges; invalid specifiers are loudly refused.

**Claims.**
- PEP 440 parse/compare, zero-padding, wildcard, paren, prerelease, local-stable — **verified**.
- Regression tests for the three defects — **verified**.
- “probe_a–probe_e all pass” — **verified** by equivalent end-to-end recreations (originals not on disk).
- “differential matched except intentional empty-spec” — **mostly verified**; a wider matrix also shows obscure `~=v1.0` (loud refusal) and `===` v-prefix raw-equality differences. Not reachable via the named defects or normal metadata; no silent wrong result on normal versions.
- `manifest.d/21.txt` updated, `update_manifest.py --check` rc=0 — **verified**.
- Tests on HEAD `test_ail_pkg`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` with `-j 2` — **4/4 ok** (352s), **verified**. Only the permitted files changed.

**Pre-existing:** none identified. **Unverified:** full PyPI census / `test_ail_packaging` (outside this fix), and the exact original probe files (recreated).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1026304, "input": 59128, "output": 9852, "reasoning": 11916, "cache.write": 0, "cache.read": 945408}]
    tool time: bash 6.0 min
        353s bash   date; cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 900 python3 tools/par_check.py -j 2 tes
          2s bash   cat > /tmp/rprobes/probe_all.py <<'PY' import sys, tempfile sys.path.insert(0,"/tmp/rprobes") from harness2 im
          1s bash   git worktree add /tmp/base work 2>&1 | tail -3; ls /tmp/base/AIL_CURRENT/ail_pkg.py
          0s bash   cat > /tmp/rprobes/diff_spec2.py <<'PY' import sys, itertools sys.path.insert(0, "/home/runner/work/ail-ci/ail
          0s bash   cat > /tmp/rprobes/diff_spec3.py <<'PY' import sys, itertools sys.path.insert(0, "/home/runner/work/ail-ci/ail
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo "rc=$?"; git status --sho
          0s bash   cat > /tmp/rprobes/probe_synclock.py <<'PY' import sys,tempfile sys.path.insert(0,"/tmp/rprobes") from harness
          0s bash   cat > /tmp/rprobes/probe_synclock.py <<'PY' import sys,tempfile,json sys.path.insert(0,"/tmp/rprobes") from ha

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T09:06:07Z
