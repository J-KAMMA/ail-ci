# job job-unifrecb-11032052  started 2026-11-03T11:54:30Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Branch `job-unifrecb-11032052`, final commit `1860bcc` (cherry-picked `44b7505`, then verification/finish).

**Fix**
- Applied the branch’s guard, then extended recursion detection to follow loaded function-name mentions, so `g = f`, list-item, dict-value and attribute recursion no longer SIGSEGV.
- Raised the soft stack limit to 256 MiB (64 MiB was not enough for a list-item self-call).
- Default typed path untouched.

**Generated C**
- Unified 100,000-call probe: adds `ail2_depth`/`AIL2_MAX_RECURSION_DEPTH 50000`, guards `pfu_f` entry, decrements on every frame leave, and calls `ail2_raise_stack_limit()` in `main`. Diff is 80 lines.
- Default build: `program.c` byte-identical for all 10 `lab/compare/typed.py` tasks, including the two `--exact-int` tasks. Three hashes: berth_sim `5718c44a139cd83a…`, echo_pack `827e698df3b91e2e…`, tree_fold `98a47ce986a42f95…`.

**Instruction counts**
- Unavailable on this runner: `perf_event_open: Permission denied`, `perf_event_paranoid=4`, no valgrind, `sudo` denied. Used the byte-identical default `program.c` hashes instead.

**Probes** (both AIL builds unless noted)
- `p_deep100k`, `p_exact50000`, `p_mutual`, `p_method`, `p_funcvalue`, `p_boundary`, `p_argpaths`: exit 1, `recursion depth exceeded`; 49,999 succeeds, 50,001 raises. CPython differs only because its limit is ~1,000.
- `p_callee_alias`, `p_callee_list`, `p_callee_dict`, `p_callee_attr`: exit 1, no SIGSEGV (all used to segfault on unified).
- `p_callee_global`, `p_callee_param`: still SIGSEGV on **both** builds — pre-existing, unchanged by this job.

**Tests on final commit**
`test_ail_unified_recursion`, `test_ail_callable_values`, `test_ail_unified`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6 modules, 733s, 0 failed.

`test_ail_runtime_error_names` is not present in this tree, so there was no skipped case to un-skip.
[cost $0.0000, opencode tokens {"total": 5658887, "input": 117827, "output": 13285, "reasoning": 21983, "cache.write": 0, "cache.read": 5505792}]
    tool time: bash 24.1 min, edit 0.0 min
        735s bash   cd /home/runner/work/_temp/w2 && timeout 2600 python3 tools/par_check.py -j 2 test_ail_unified_recursion test_
        354s bash   cd /home/runner/work/_temp/w2 && timeout 1500 python3 tools/par_check.py -j 2 test_ail_unified_recursion test_
        103s bash   cat > /tmp/cmp_c2.sh <<'EOF' #!/bin/bash set -u tasks="berth_sim chain_relax echo_pack ledger_bin rail_transfe
         55s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/*.py; do echo "===== $(basename $p)"; timeout 300 bash ~
         53s bash   cat > /tmp/cmp_c.sh <<'EOF' #!/bin/bash set -u tasks="berth_sim chain_relax echo_pack ledger_bin rail_transfer
         41s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/p_deep100k.py /tmp/probes/p_boundary.py /tmp/probes/p_mu
         30s bash   cd /tmp/probes && cat > p_callee_list.py <<'EOF' def f(n):     if n <= 0:         return 0     fs = [f]     re
         20s bash   cd /home/runner/work/_temp/w2 && for p in /tmp/probes/*.py; do echo "===== $p"; timeout 600 bash ~/tools/cmp.s

## review 0 failed to run: (no final text) [cost $0.0000, opencode tokens {}]     tool time:  

## review 0
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0000, opencode tokens {}]
    tool time: 

FINAL VERDICT: ERROR  2026-11-03T13:00:52Z
