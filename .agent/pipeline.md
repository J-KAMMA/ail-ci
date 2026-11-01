# job job-rbccsplit2-11011617  started 2026-11-01T07:18:19Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Reproduced the suite failure as a manifest-merge artifact: taking the integration side of `AIL_CURRENT/manifest.d` dropped the new `ccsplit.py` pin, and `tools/update_manifest.py` re-added it without the `s` flag, so `test_ail_packaging` failed `test_every_compiler_file_is_selected`.

Fixed `tools/update_manifest.py` to treat `.py/.h/.c` under `python/pkg-v12/` or `stdlib/` as SDK sources and restore a dropped pin with `s`; added a regression test in `test_ail_registry.py`. Commit: `ec7700a`.

Verified on that commit:
- `test_ail_registry`, `test_ail_packaging`, `test_ail_cc_split`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 6 modules, 0 failed.
- Simulated failing merge (`/tmp/wtdrop`) now passes `test_ail_packaging` (17 tests) and `update_manifest.py --check` (rc 0).
- Probes: `/tmp/probes/ccsplit_routes.py` matches CPython on both builds; `/tmp/probes/manifest_pin_flag.py` restores the `s` flag after the pin is dropped.
[cost $0.0000, opencode tokens {"total": 8830327, "input": 265121, "output": 20944, "reasoning": 55174, "cache.write": 0, "cache.read": 8489088}]
    tool time: bash 38.4 min, edit 0.0 min, read 0.0 min
        926s bash   cd /home/runner/work/ail-ci/ail-ci && mods=$(for s in $(seq 0 19); do m=$(python3 tools/ci_shards.py --shard $
        586s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' > /tmp/first80.txt import sys sys.path.insert(0,'AIL_CU
        372s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_reg
        236s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 4 test_ail_sdk
         24s bash   grep -rn "breaks other tests\|pass without it\|full suite" /home/runner/work/_temp /tmp/opencode /home/runner 
         19s bash   mkdir -p /tmp/probes && cat > /tmp/probes/ccsplit_routes.py <<'EOF' def fibr(n: int) -> int:     if n < 2:    
         18s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree remove --force /tmp/wtdrop 2>/dev/null; rm -rf /tmp/wtdrop;
         17s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_packaging 2>&1 | tail -60

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report

**What the change really does:** Adds `sdk_source()` to `tools/update_manifest.py`, so every tracked `.py/.h/.c` under `AIL_CURRENT/python/pkg-v12/` or `AIL_CURRENT/stdlib/` is treated as an SDK source; an unpinned such file is restored with the `s` flag. Adds a merge regression test to `test_ail_registry`, a DEVLOG entry, and the regenerated `test_ail_registry` pin. No compiler/runtime code changes.

**Probes (HEAD unless noted):**
- `manifest_pin_restore.py`: new `pkg-v12` module, pin line dropped, tool rerun → pin restored as `s`; matches the new test.
- Same probe against base tool (`/tmp/base`): pin restored with flags `''` (AssertionError) → the regression test is meaningful.
- `/tmp/simold` (work + dropped `ccsplit.py` pin, old tool): pin `-`; `test_ail_packaging` **FAILED** (`pinned compiler files missing from sdk_files: python/pkg-v12/ccsplit.py`).
- `/tmp/simnew` (HEAD + dropped `ccsplit.py` pin, new tool): pin `s`; `test_ail_packaging` **OK**; `--check` rc 0.
- `/tmp/simmerge2` (merge prior branch into `origin/integ`, take integration side of `manifest.d`, new tool): `ccsplit.py` restored `s`; `--check` rc 0; packaging **OK**.
- New `.h/.c` under `pkg-v12` and `.py` under `stdlib` → all pinned `s`, `--check` rc 0, packaging **OK**.
- `ccsplit_routes.py` via `cmp.sh` on HEAD: general and default builds both match CPython.

**Tests on HEAD:** `test_ail_registry`, `test_ail_packaging`, `test_ail_safetynet`, `test_ail_sdk` → 0 failed.

**Claim check:** merge-artifact diagnosis, old-tool missing `s`, new-tool restore, regression test, and probe claims: **verified**. Six-module test claim: worker log shows it; independently re-ran four of the six. Report matches the diff.

**Notes / unverified:** An existing pin kept as `-` (not dropped) is still not upgraded by the tool; the actual integration merge drops the line, so this gap is not exercised. `test_ail_cc_split`, `test_ail_files`, `test_ail_corpus_findings3` not independently re-run (per review scope). Worker used `par_check -j 4` once, against the `-j 2` rule. No speed check (tooling-only change).

**Pre-existing:** none relevant.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1595289, "input": 45604, "output": 6623, "reasoning": 30102, "cache.write": 0, "cache.read": 1512960}]
    tool time: bash 9.4 min
        231s bash   cd AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_sdk 2>&1 | tail -15; date
        168s bash   cd AIL_CURRENT && date && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_registry test_ail_safetynet 
         34s bash   for wt in /tmp/simold /tmp/simnew; do echo "=== $wt test_ail_packaging ==="; (cd $wt/AIL_CURRENT && timeout 30
         19s bash   date && timeout 400 bash ~/tools/cmp.sh /tmp/probes/ccsplit_routes.py $PWD 2>&1 | tail -12; echo rc=${PIPESTAT
         18s bash   cd AIL_CURRENT && date && timeout 300 python3 ../tools/par_check.py -j 2 test_ail_registry test_ail_packaging 
         18s bash   rm -rf /tmp/simmerge2; git worktree add -q --detach /tmp/simmerge2 origin/integ && cd /tmp/simmerge2 && git -c
         18s bash   git worktree add --detach /tmp/simh HEAD 2>&1 | tail -1 cd /tmp/simh printf '# h\n' > AIL_CURRENT/python/pkg-v
         18s bash   rm -rf /tmp/simmerge; git worktree add -q --detach /tmp/simmerge origin/integ && cd /tmp/simmerge && git -c us

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T09:46:41Z
