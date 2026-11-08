# job job-fbnarrow3-11081820  started 2026-11-08T09:23:49Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed. The narrowing runtime registers itself at import time (`narrowint.py` bottom `register()`), which reads `AIL_NARROW_INT`; that variable was missing from `ail_server.IMPORT_ENV`, so the compile server did not key/freeze it. Added `AIL_NARROW_INT` to `IMPORT_ENV` and refreshed `manifest.d/19.txt`.

Commit: `94c67be`

Tests on final commit (`tools/par_check.py -j 2`, 0 failed):
- test_ail_server 189.8s
- test_ail_narrow_int 29.1s
- test_ail_safetynet 131.8s
- test_ail_files 99.2s
- test_ail_corpus_findings3 228.8s

`python3 tools/update_manifest.py --check`: rc 0.

Probes (`bash ~/tools/cmp.sh`, default + general, all match CPython; plus `AIL_NARROW_INT=0/1` on both builds, all match):
- `p1_bounds.py` — int32/int64 boundaries, negative indexes, pop/clear
- `p2_field.py` — class field append/read/widen, argument and attribute values
- `p3_sources.py` — values via list item, dict value and attribute
- `p4_alias.py` — same list passed twice, alias mutation
- `p5_empty_negative.py` — empty list, IndexError paths, negative read/write

Server identity verified distinct for `AIL_NARROW_INT` unset / `0` / `1` (`6347a95a…`, `a553e32a…`, `2e46558f…`).
[cost $0.0000, opencode tokens {"total": 1703280, "input": 59626, "output": 6605, "reasoning": 10681, "cache.write": 0, "cache.read": 1626368}]
    tool time: bash 11.0 min, edit 0.0 min
        420s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_server test_ail_na
        187s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_server 2>&1 | tail -80
         33s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p*.py; do d=$(mktemp -d /tmp/nrpXXXX); cp "$p" "$d/
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p*.py; do echo "=== $p"; timeout 300 bash ~/tools/c
          2s bash   cd AIL_CURRENT && timeout 400 python3 -m unittest -q test_ail_server.Process.test_import_time_environment_read
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   pwd && ls -la && git status && git branch --show-current && git log --oneline -10
          0s bash   git log --oneline --all --decorate | head -40; echo ---; git rev-list --count HEAD; echo ---; git show --stat 

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Change (one line):** Adds `AIL_NARROW_INT` to `ail_server.IMPORT_ENV` so the compile server is keyed on it, plus the matching `manifest.d/19.txt` hash and a DEVLOG entry. No compiler/runtime logic changes.

**Probes** (`/tmp/rprobes/`, run with `bash ~/tools/cmp.sh`, general + default, against HEAD):
- `p1_narrow.py` (int32/int64 bounds, list/dict/field/argument flow): matches CPython with unset, `=0`, `=1`.
- `p2_plain.py` (feature unused; strings, bytearray, classes): matches CPython.
- `p3_slice.py` (list/bytearray copy then source mutation): matches CPython; values stay snapshot-correct.
- `p4_bounds.py` (narrow-shaped int list): matches CPython with unset and `=1`.

**Server-keying probe** (custom compile pairs, fresh `AIL_SERVER_DIR`):
- HEAD, `=1` then unset: 2 sockets, first C has `ilist`, second does not; both run correctly.
- HEAD, unset then `=1`: 2 sockets, correct C in both directions.
- Base (`/tmp/base`), `=1` then unset: **1 socket**, second (default) C still contains `ilist` — reproduces the bug the change fixes.
- Non-feature C unchanged: default-build `program.c` for `p2_plain`, `p3_slice`, `p4_bounds` is byte-identical between HEAD and base.
- `ail_server.identity()` distinct for unset/`0`/`1`: `6347a95a…`, `a553e32a…`, `2e46558f…` (matches report exactly).

**Tests on HEAD:** `test_ail_server` ok 188.3s, `test_ail_safetynet` ok 132.5s, `test_ail_narrow_int` ok 27.5s; `tools/update_manifest.py --check` rc 0. The failing assertion on base is precisely `test_import_time_environment_reads_are_all_keyed: ['AIL_NARROW_INT']`, and it passes on HEAD.

**Report claims:**
- Import-time `register()` reads `AIL_NARROW_INT`: verified.
- Variable was missing from `IMPORT_ENV` and not keyed: verified.
- Add to `IMPORT_ENV`, refresh manifest, commit `94c67be`: verified.
- Test timings: verified for the three modules I re-ran; `test_ail_files` and `test_ail_corpus_findings3` unverified (not re-run, per scope).
- Mechanism phrase "emitting narrowed C without the runtime": not reproduced. With unset then `=1` on base the same server was reused yet the runtime was added per request by `prepare()`; the real observed defect is only default C being polluted when the template was imported with `AIL_NARROW_INT=1`. The fix is still correct; the report overstates this direction.

**Pre-existing:** none found (all cmp probes match on both HEAD and base).

Not checked: `test_ail_files`, `test_ail_corpus_findings3`, instruction-count speed (change is one string in the server identity, not a hot path).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 647734, "input": 49313, "output": 5990, "reasoning": 7471, "cache.write": 0, "cache.read": 584960}]
    tool time: bash 5.6 min
        120s bash   cd /home/runner/work/ail-ci/ail-ci && nohup python3 tools/par_check.py -j 2 test_ail_server test_ail_safetynet
        120s bash   cd /home/runner/work/ail-ci/ail-ci && setsid python3 tools/par_check.py -j 2 test_ail_server test_ail_safetyne
         31s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p1_narrow p3_slice p4_bounds; do echo "=== $p unset"; env -u AI
         29s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 600 python3 tools/par_check.py -j 1 test_ail_narrow_int 2>&1 | t
         14s bash   cd /home/runner/work/ail-ci/ail-ci && echo "=== p2 plain unset"; env -u AIL_NARROW_INT timeout 300 bash ~/tool
          4s bash   cd /home/runner/work/ail-ci/ail-ci for p in p2_plain p3_slice p4_bounds; do   for wt in head base; do     root
          3s bash   cd /home/runner/work/ail-ci/ail-ci run_pair () {   wt=$1; tag=$2; rm -rf /tmp/sv_$tag /tmp/d_${tag}_1 /tmp/d_$
          3s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/ds1 /tmp/ds2 /tmp/srvA && mkdir -p /tmp/srvA && AIL_SERVER_D

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T11:02:09Z
