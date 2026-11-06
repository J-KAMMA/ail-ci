# job job-bces5-11061041  started 2026-11-06T01:41:33Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model commandcode/deepseek-v4.1-flash]
Done. Here's the summary.

## What I found and fixed

**Review defect 1 (blocking) — fixed, verified.** The working tree already carried a `mutators` fact; the decisive probe now passes:

```
tally_lang/ail  base 19,585,727,453 → head 17,526,407,763 Ir   ratio 0.89486  (≤0.93)
                stripped 71,896 → 67,800 bytes, same output
```

The fix: `fieldfacts.compute` now emits `{'mutators': {fn: [group ids a call can grow]}}`, built from the same accepted `append`/`pop`/`clear` runs that validate a group, transitively over the call graph. `groupcse.changes_length` uses it for struct groups, so `pe1` in `parse_line` (which only appends `n_op/n_a/n_b`) no longer blocks the statement group's rewrites (restoring 5, not 3), while a call that can reach an append still blocks a negative-index crossing.

I hardened it beyond the prior WIP: user-defined methods and struct constructors are treated as able to change every group, and callback-capable builtins (`map`, `filter`, `sorted`/`min`/`max`/`sum` with a key, etc.) are no longer in the safe list.

## Verification

- Probes (default + `AIL_UNIFIED_FORCE=1`), all match CPython: `/tmp/probes/{cross_no_grow,cross_grow,cross_pop,cross_two_obj,cross_grow_transitive}.py`, `/tmp/probes2/{method_named_update,ctor_mutates_arg,keyed_sorted_between}.py`.
- `test_ail_bce` pass; `test_ail_safetynet` pass; `test_ail_files`, `test_ail_corpus_findings3` pass. (An initial safetynet failure was my own `ulimit -v 1500000`: the generator pool needs address space; the program exits 1 with `AIL internal error: generator: no stack` under the limit and matches CPython without it.)
- `python3 tools/update_manifest.py` + `--check` clean.
- Full census: tally 0.89486; echo_pack 1.06419, term_rank 1.03117, ticket_audit 1.01180. I proved these three are **not** caused by bces5: their C is byte-identical at the branch export base `4b5e417` and `7612779`, and the same ratios already measure at `7612779`; the export base itself diverges from `origin/integ` (`/tmp/base`) in those functions. `9e8faaf`/my commit leave echo_pack and ticket_audit unchanged and term_rank 0.17% lower. Recorded in DEVLOG.

Two commits on `job-bces5-11061041` (`e04851a`, `e6f29f7`); nothing pushed, no background jobs, temp worktrees removed.
[commandcode stop=end_turn turns=130 out_tokens=79746]

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: bces5 fix — `mutators` fact

**What the diff really does:** adds a whole-program `mutators` fact (per top-level function, the struct groups a call may grow, transitive over the call graph; unknown/method/constructor calls mark all struct groups) and makes `groupcse.changes_length` use it for struct groups, so a call that cannot reach an append no longer blocks a cross-rewrite. Plus an `.ail` test, DEVLOG, manifest. Matches the report.

**Defect 1 (tally below 7%) — fixed, verified.**
`bce_census.py check --base /tmp/base --icount callgrind --tasks tally_lang`: base 19,585,726,577 → head 17,526,406,887 Ir, ratio **0.89486**, same output, stripped 71,896 → 67,800. Exit 0.

**Correctness probes** (`/tmp/rprobes/*.py`, default + `AIL_UNIFIED_FORCE=1`): safe non-mutating call with `i=-3..2`; growth via `insert`; growth via `+=`; growth through an argument alias; read/store with negative index across a safe call; a no-feature list program. All match CPython, no crashes. `AIL_BCE=0` C is byte-identical to the base. Note: `.py` probes (`--syntax python`) use dynamic objects and do **not** engage `groupcse`; the feature is exercised by the added `.ail` `group_call_growth` test (`cross_call` stays `ck`, `cross_peek` becomes `nck`), which passes.

**Tests:** `test_ail_bce`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (`-j 2`, 0 failed). `update_manifest.py --check` clean.

**No-task-worse check vs the branch's real base `4b5e417`:** `echo_pack`, `ticket_audit`, `ledger_bin`, `tree_fold` C byte-identical; `term_rank` ratio 0.9983, same output. So the >1 ratios vs `/tmp/base` (`echo_pack 1.064`, `term_rank 1.031`, `ticket_audit 1.012`) come from `/tmp/base` being newer integ, not this change.

**Claims:** tally fix verified; `mutators` construction/transitivity and conservative treatment of method/constructor/callback calls verified in the diff; probe/test/manifest claims verified. Direct "5 not 3 rewrites in `parse_line`" not independently counted (ratio confirms the effect).

**Pre-existing:** the `/tmp/base` vs `4b5e417` divergence that makes three tasks exceed ratio 1.0; not caused by bces5.
**Unverified:** direct rewrite-count in `parse_line`, gdev icounts, full 10-task census and all shards.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2584220, "input": 92819, "output": 7615, "reasoning": 26442, "cache.write": 0, "cache.read": 2457344}]
    tool time: bash 13.3 min
        279s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 lab/beatc/bce_census.py check --base /tmp/exportbase --ico
        148s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test_ail_c
        143s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 lab/beatc/bce_census.py check --base /tmp/base --icount ca
        142s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_bce test_ail_saf
         58s bash   date; cd /home/runner/work/ail-ci/ail-ci && python3 lab/beatc/bce_census.py check --base /tmp/exportbase --ico
         16s bash   cd /home/runner/work/ail-ci/ail-ci && for p in r1_safe_neg r2_insert_grow r3_augassign_grow r4_alias_arg_grow 
          5s bash   cd /tmp/cchk for p in r1_safe_neg r6_no_feature; do   cp /tmp/rprobes/$p.py src.py   for tag in base head head
          2s bash   cd /tmp/cchk for p in /tmp/probes/cross_no_grow.py /tmp/probes/cross_grow.py /tmp/probes2/method_named_update.

## full suite skipped: only 78 minutes left (the integration gate runs it)

FINAL VERDICT: ACCEPT  2026-11-06T05:23:19Z
