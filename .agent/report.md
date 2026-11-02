# job job-arena1s1-11030038  started 2026-11-02T15:39:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented arena1 S1 and committed it as `42ee12f`.

**Changes**
- `_loop_local_release_points` now frees `list[int]` / `list[float]` / `list[str]` locals created fresh in `if`/`elif`/`else` or inner-loop bodies, with conservative escape checks (read after block, next-iteration read, lambda capture, attribute store, append to another container, return, break/continue).
- `_for_inner_impl` frees numeric-field iteration snapshots after the loop and both spines after a `str` field loop.
- Added `tools/rss_phases.py` and registered `test_ail_loop_block_release`.

**RSS, design input N=3M**
| measure | base | new |
|---|---:|---:|
| direct `/usr/bin/time -f %M`, median of 3 | 464.5 MiB | **430.8 MiB** |
| `rss_phases.py` sort phase, default | 463.4 | 430.8 |
| `rss_phases.py` cut/mirror peak, default | 467.9 | 445.8 |
| `rss_phases.py` peak, fixed mmap threshold | 419.3 | 374.4 |

Output on that input is byte-identical to C.

**Verification**
- Probes all matched CPython on default and `AIL_UNIFIED_FORCE=1`: `positive`, `fields3`, `neg2`, `s1_routes`, `s1_item_attr`, `fields`, `blocks`, `neg3`, `s1_empty`.
- Final commit: 31 tests passed, 1 skipped (no `zig` for Windows target) across `test_ail_loop_block_release`, `test_ail_last_use_free`, `test_ail_chunk_loop_release`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.
- `tools/update_manifest.py --check` passes. No new DIFFERENCES row: changed programs’ output is unchanged. Pre-existing untracked `.agent/pipeline.md` was not touched.
[cost $0.0000, opencode tokens {"total": 12804507, "input": 637777, "output": 34104, "reasoning": 51858, "cache.write": 0, "cache.read": 12080768}]
    tool time: bash 17.9 min, write 0.0 min
        521s bash   python3 -m unittest -v test_ail_loop_block_release test_ail_last_use_free test_ail_chunk_loop_release test_ail
        239s bash   python3 -m unittest test_ail_loop_block_release test_ail_last_use_free test_ail_chunk_loop_release test_ail_sa
         97s bash   python3 tools/rss_phases.py --n 3000000 /tmp/tf_ail /tmp/arena/tf_ail_base > /tmp/arena/rss_phases_final.txt 2
         35s bash   for f in /tmp/arena/ph_*.txt; do b=$( { /usr/bin/time -f "%M" /tmp/arena/tf_ail_base < $f > /dev/null; } 2>&1 
         25s bash   for p in positive fields3 neg2 s1_routes s1_item_attr fields blocks neg3; do echo "=== $p ==="; bash ~/tools/c
         19s bash   python3 - <<'PY' lines=open('/tmp/arena/in1m.txt','rb').read().split(b'\n') if lines[-1]==b'': lines=lines[:-1
         13s bash   mkdir -p /tmp/arena && python3 - <<'PY' import importlib.util, random spec=importlib.util.spec_from_file_locat
         11s bash   for b in /tmp/tf_ail /tmp/arena/tf_ail_base; do echo "$b"; for i in 1 2 3; do /usr/bin/time -f %M "$b" < /tmp/

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Reviewed commit `42ee12f` (`git diff work..HEAD`).

**What the change really does.** It generalises `_loop_local_release_points` from struct locals in a loop’s top-level body to LIST/FLIST/SLIST locals declared fresh in any `if`/`elif`/`else` or inner-loop block inside a loop, with new conservative escape guards; and it frees `_numeric_field_value`/`_slist_snapshot` temps after a `for x in o.f` loop. This matches the report’s description (the str-field loop is now emitted as two statements rather than one, but semantics are unchanged).

**Probes** (all in /tmp/rprobes, `cmp.sh`, default + `AIL_UNIFIED_FORCE=1`): `rev_subscript`, `rev_alias_after`, `rev_arg_keep`, `rev_routes`, `rev_item_routes`, `rev_posblocks`, `rev_copy_indep`, `rev_field_indep`, `rev_slist_alias`, `rev_flist_alias`, `rev_alias_escape_{i,f,s}`, `rev_ro_alias_{i,f}`, `rev_wr_alias_i`, `rev_alias_mid_{i,f}`, `rev_ret_alias`, `rev_ctor_alias`; plus existing `empties`, `nestedblock`, `typed_tail`, `arg_escape`, `nofeature`, `structs`, `typed_passthru`, `typed_alias`, `alias`, `forfield`. All outputs and exit codes matched CPython. Typed-path probes with early frees (`rev_alias_after`, `rev_copy_indep`, `nestedblock`, `empties`, `forfield`) were clean under ASan+UBSan. `nofeature.py`’s `program.c` is byte-identical to base.

**RSS** (`/usr/bin/time -f %M`, generated design input): 3M base median 474,540 KiB (474.5 MB) → head median 440,128 KiB (**440.1 MB**, ≤445); 1M base median 174,772 KiB (170.7 MiB) → head median 150,000 KiB (146.5 MiB, ≤162). Head output equals base on both inputs and equals the C program on the 3M input. Wall time 1.83–1.85 s → 1.83–1.87 s (neutral; `icount` unavailable, perf_event_open denied).

**Claims.** Change description, RSS direction/targets, byte-identical tree_fold output, test registration, manifest `--check`, and “no new DIFFERENCES row” verified. The new `test_ail_loop_block_release` plus `test_ail_safetynet` pass on HEAD. The exact “31 passed, 1 skipped across six modules,” the other compare tasks, all ASan/UBSan runs, corpus, and the 20 shards were not re-run.

**Pre-existing.** `for x in o.i/o.s` while the body appends to the same field iterates a snapshot on the default build (`rev_fieldmut`: CPython 19/`abz`, AIL 7/`ab`); identical on base, so not caused by this change.

**Unverified.** Other compare tasks’ RSS/wall, full sanitizer matrix, full suite/shards, and the worker’s exact test count.

VERDICT: ACCEPT
[cost $0.1080, opencode tokens {"total": 11006318, "input": 210653, "output": 19498, "reasoning": 54247, "cache.write": 0, "cache.read": 10721920}]
    tool time: bash 6.4 min, write 0.0 min
        179s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT; date; python3 ../tools/par_check.py -j 2 test_ail_loop_block_r
         14s bash   cd /home/runner/work/ail-ci/ail-ci; for p in rev_alias_escape_f rev_alias_escape_i rev_alias_escape_s; do rm -
         14s bash   cd /home/runner/work/ail-ci/ail-ci; for p in typed_tail forfield rev_routes; do rm -rf /tmp/rpsan_$p; mkdir -p
         13s bash   cd /home/runner/work/ail-ci/ail-ci; for p in rev_routes rev_item_routes rev_posblocks; do echo "=== $p"; bash 
         11s bash   file /tmp/rev_tf_head; cd /tmp; for b in rev_tf_base rev_tf_head; do echo "=== $b"; for i in 1 2 3; do /usr/bi
         10s bash   cd /home/runner/work/ail-ci/ail-ci; for p in rev_alias_escape_f rev_alias_escape_i rev_alias_escape_s; do echo
         10s bash   cd /home/runner/work/ail-ci/ail-ci; for p in rev_ro_alias_i rev_ro_alias_f rev_wr_alias_i; do echo "=== $p"; b
         10s bash   cd /home/runner/work/ail-ci/ail-ci; for p in typed_passthru typed_alias alias; do echo "=== $p"; bash ~/tools/

## full suite
test_ail_instruction_gap

## worker report (suite fix)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed `c9819a4`.

- Root cause: new escape guards (`break`/`continue`, append, attribute store) were applied to all loop locals, disabling existing struct-local early frees in `test_ail_instruction_gap`.
- Fix: restrict those guards to `list[int]`/`list[float]`/`list[str]` locals; struct refs keep existing release behavior.
- Refreshed manifest pin.
- Verified: `test_ail_instruction_gap` and `test_ail_loop_block_release` pass; related `test_ail_last_use_free` and `test_ail_chunk_loop_release` also pass.
[cost $0.0220, opencode tokens {"total": 952009, "input": 78849, "output": 3828, "reasoning": 8788, "cache.write": 0, "cache.read": 860544}]
    tool time: bash 0.5 min
         10s bash   python3 -m unittest -q test_ail_instruction_gap 2>&1 | tail -40
          9s bash   python3 -m unittest -q test_ail_loop_block_release 2>&1 | tail -60
          8s bash   python3 -m unittest -q test_ail_instruction_gap 2>&1 | tail -100
          1s bash   python3 -m unittest -q test_ail_last_use_free test_ail_chunk_loop_release 2>&1 | tail -30
          1s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo CHECK_EXIT:$? && git status
          0s bash   python3 tools/update_manifest.py --check 2>&1 | tail -40; echo EXIT:$?
          0s bash   grep -rn "_loop_local_release_points\|loop_local_points" --exclude-dir=.git . | head -20
          0s bash   git add AIL_CURRENT/python/pkg-v12/pyfunc.py AIL_CURRENT/manifest.d/45.txt && git commit -m "arena1 S1: keep s

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T19:03:57Z
