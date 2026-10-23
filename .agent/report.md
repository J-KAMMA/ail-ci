# job job-perf3b-10240813  started 2026-10-23T23:13:50Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Kept the change; it exceeds the keep threshold. `rangecheck.py` now ignores type-annotation subtrees when deciding whether a zero-argument method can be analysed in place, so the existing method-field bounds proof fires for annotated `read_*` accessors.

- Before: AIL 47.3 ms vs C 10.0 ms, `ail/c = 4.728 [4.701, 4.824] slower`
- After: AIL 40.8 ms vs C 9.8 ms, `ail/c = 4.145 [4.119, 4.170] slower`; `ail/base = 0.866 [0.863, 0.871] faster` (13.4% less AIL time, ranges disjoint)
- Output matched the oracle in every timed run and boundary control.
- Probes all matched CPython on both builds: `cursor_fields.py`, `bcursor_fields.py`, `method_side_effects.py`, `range_guards.py`.
- Tests passed: `test_ail_range_checks`, `test_ail_binary_cursor_cli`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`; manifest `--check` passes.

Commits: `12f2492` (change + tests), `fed1c2c` (final benchmark result/DEVLOG).
[cost $0.0368, opencode tokens {"total": 1957763, "input": 125597, "output": 5749, "reasoning": 15089, "cache.write": 0, "cache.read": 1811328}]
    tool time: bash 8.5 min, edit 0.0 min, write 0.0 min
        338s bash   python3 ../tools/par_check.py -j 2 test_ail_range_checks test_ail_safetynet test_ail_files test_ail_corpus_fin
         74s bash   for p in /tmp/probes/*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$PWD" | grep -E "exit|same stdout|DIF
         57s bash   for p in /tmp/probes/*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$PWD"; done 2>&1 | tee /tmp/probes_ru
         27s bash   python3 bench/compare.py --app binary_cursor_records --base 4ffe276 2>&1 | tail -25
         15s bash   python3 ../tools/par_check.py -j 2 test_ail_range_checks test_ail_binary_cursor_cli 2>&1 | tail -10
          0s bash   git show --stat 4ffe276 && git show 4ffe276 --format=full | head -80
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo check_exit=$?; git status -
          0s bash   git status && git log --oneline -10 && pwd && ls

## review 0
[model opencode-go/deepseek-v4.1-flash]
Review (23:37–23:49)

**Change**: `rangecheck.py` skips function/argument annotation subtrees in `inline_candidate`; annotated zero-arg guard methods (`remaining()`) are now analysed in place, so byte checks in `read_*` are elided. Test/DEVLOG/manifest updated.

**Probes** (`bash ~/tools/cmp.sh`, general + default builds, HEAD; base where noted):
- `annot_guard.py`: annotated `remaining`/`has`/`read_u8`/`read_u32`, empty/short/exact boundaries, negative via alias, values through arg/list item/attribute/dict — same stdout, exit 0.
- `annot_noninline.py`: annotated methods with store/loop/try/call, positions `-1..len+1` — same stdout; both CPython and AIL exit 1 on the probe's own uncaught IndexError.
- `annot_bounds.py`: one-sided guards, negative indices, field mutation between calls, empty — same stdout.
- `annot_plain.py` and gdev `g00_000.py`: `--debug-dir` `program.c` byte-identical between `/tmp/base` (4ffe276) and HEAD.
- `annot_types.py`: float/bool/int annotations and guarded read — same on HEAD and base.

**Tests on HEAD (`-j 2`)**: `test_ail_range_checks`, `test_ail_binary_cursor_cli`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all ok. Manifest `--check` ok; `git diff --check` clean.

**Speed**: independent rerun in a `/tmp` worktree, `bench/compare.py --app binary_cursor_records --rounds 6 --base 4ffe276`: AIL 40.8 ms vs base 47.3 ms, `ail/base = 0.867 [0.861, 0.868]`; `ail/c = 4.088 [4.021, 4.207]` vs before `4.728 [4.701, 4.824]`. Ranges disjoint, 13.3% less AIL time, above the 3% threshold; matches committed results.

**Claims**: all verified, none false. No new correctness or C-output difference observed.

**Pre-existing**: none observed (the nonzero exit in `annot_noninline.py` is the probe's own uncaught IndexError, identical under CPython and AIL).

**Unverified**: gdev instruction counts (`perf_event_open` denied on this runner); wider suite not run, per instructions.

VERDICT: ACCEPT
[cost $0.0383, opencode tokens {"total": 2132410, "input": 93990, "output": 7313, "reasoning": 22915, "cache.write": 0, "cache.read": 2008192}]
    tool time: bash 7.2 min
        201s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_files te
        121s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_range_ch
         40s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/*.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p"
         26s bash   cat > /tmp/rprobes/annot_types.py <<'EOF' class Cursor:     def __init__(self, a: int, data: bytes):         s
         18s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/rc-head HEAD 2>&1 | tail -2 && cd /tmp/rc-head && 
         18s bash   cd /tmp/rc-head && date && python3 bench/compare.py --app binary_cursor_records --rounds 6 --cpu 1 --base 4ffe
          5s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/cdiff && mkdir -p /tmp/cdiff && for src in /tmp/rprobes/anno
          0s bash   git worktree add /tmp/base work 2>&1 | tail -3; ls /tmp/probes 2>/dev/null; echo ---; ls /tmp/probes_run* 2>/d

FINAL VERDICT: ACCEPT  2026-10-23T23:49:50Z
