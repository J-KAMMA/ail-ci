# job job-rbpre171-10251803  started 2026-10-25T09:09:54Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
MODEL
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":393,"duration_api_ms":264,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":407,"duration_api_ms":276,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Applied `pre171` on top of the current tree.

- Commit: `590b06a` — 7 files: `pymix.py` indirect-call detection, `cruntime.py` worker `ail_par_trap_value`, `pyfront.py` shift guards already present, new `test_ail_pre171.py`, `ail_check.py`, DEVLOG, DIFFERENCES, MANIFEST.
- `tools/diff_ids.py` does not exist in this repository or the fetched job branch; `tools/update_manifest.py` ran and `--check` exits 0.
- Tests on final commit: `test_ail_pre171` 5 ok, `test_ail_safetynet` 5 ok, `test_ail_files` 18 ok (1 skipped: no zig for Windows target), `test_ail_corpus_findings3` 2 ok, `test_ail_pre109` 5 ok.
- Probes (all `/tmp/probes`, `cmp.sh` both builds, all match CPython): `p1_indirect_shift`, `p2_indirect_alias`, `p3_indirect_raise`, `p4_uncaught` (exit 1, `ValueError: negative shift count`), `p5_boundaries` (counts −2/−1/0/1/63/64/100 via args, list, attr, dict, augmented), `p6_valid_indirect` (valid shifts). Parallel shifts at 1 and 4 threads covered by `test_ail_pre171`.
- Untracked `.agent/pipeline.md` left untouched.
[cost $0.0000, opencode tokens {"total": 1469863, "input": 51000, "output": 8732, "reasoning": 4051, "cache.write": 0, "cache.read": 1406080}]
    tool time: bash 13.2 min, edit 0.0 min
        216s bash   python3 -m unittest -v test_ail_corpus_findings3 2>&1 | tail -40
        131s bash   python3 -m unittest -v test_ail_files 2>&1 | tail -50
        130s bash   python3 -m unittest -v test_ail_safetynet 2>&1 | tail -40
        125s bash   python3 -m unittest test_ail_safetynet 2>&1 | tail -6
         49s bash   python3 -m unittest test_ail_corpus_findings3 2>&1 | tail -6
         35s bash   for p in /tmp/probes/p*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" "$PWD"; done 2>&1 | tee /tmp/probes/log
         27s bash   python3 -m unittest -v test_ail_pre171 2>&1 | tail -30
         26s bash   python3 -m unittest test_ail_pre171 2>&1 | tail -6; python3 tools/update_manifest.py --check; echo manifest_rc

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review report — pre171 re-apply (HEAD `590b06a`)

**What the diff really does:** adds an AST pass in `pymix._indirect_names` that treats trap-capable functions loaded as values / called inside lambdas / reached through such callers as protected, so they are refused from typed mixed mode; adds `ail_par_trap_value` so an adopted exception on a parallel worker records code+message and the join re-raises it on the caller. `pyfront` shift guards and the `pymix` shift-trap detection were already present in this tree and are unchanged by the commit.

**Claims checked**
- 7 changed files, commit `590b06a`, message trailer: verified.
- `pymix` indirect detection, `cruntime` worker trap, new `test_ail_pre171.py`: verified. Generated C for a parallel program contains the hook (`dbg_par/program.c:196,389,457,605`).
- `pyfront.py` shift guards already present: verified (no pyfront hunk in `git diff work..HEAD`; current guards carry `negative shift count`).
- `tools/diff_ids.py` absent from `c140486`, `FETCH_HEAD`, `work`, `HEAD`: verified.
- `update_manifest.py --check`: rc 0.
- Tests on HEAD: `test_ail_pre171`, `test_ail_safetynet` (par_check -j 2, 127s) and `test_ail_pre109` (18s) all pass, 0 failed.
- Unverified: worker’s counts for `test_ail_files` and `test_ail_corpus_findings3` (not rerun, per reviewer policy).
- Minor report inaccuracy: the “7 files” list includes `pyfront.py`, which the commit does not change.

**Probes** (own, `/tmp/rprobes`, both builds unless noted)
- `r1_callback`, `r2_attr_ret`, `r3_aug_raise`, `r4_direct_unused`, `r6_apply`: callback/list/attr/dict/return/alias/augmented shift, valid and negative: all match CPython.
- `r5_lambda`: lambda-held helpers; HEAD matches CPython, base default build exits 1 — the fix is real.
- `r7b`/`r8`/`r12`/`r13` (AIL `parallel for`, threads 1 and 4): caught, uncaught, message reuse and valid runs all correct; `r12` message does not bleed between a shift, `int("zz")`, and another shift.
- `r10_par_int`: named compile-time refusal (str constant in parallel body) — acceptable.
- Worker’s `p1`–`p6`: re-ran, all match (including uncaught exit 1).
- C unchanged for a non-feature program: `program.c` byte-identical HEAD vs base (only `native_report.json` build paths differ).
- Speed: all 24 `/home/runner/corpus/gdev` programs containing indirect name loads have identical `pymix.analyze` candidates/rejections on HEAD vs base, so no instruction-count change; icount not run.

**Pre-existing (identical on base, not blocking)**
1. `r9_genexp`: `gen = (shl(1,-1) for _ in range(1))` consumed under `try`. Expected `caught ValueError 'negative shift count' ...` then `valid [4, 8]`; HEAD and base print nothing, exit 1 (`ValueError: negative shift count`). Deferred generator call sites are not marked indirect.
2. `r11_method`: `C.run` calls `shl(1,-1)`, `c.run()` is inside `try`. Expected `caught ValueError ...` then `valid 8`; HEAD and base default build print nothing, exit 1 (general build matches). Attribute call sites are not tracked in `call_sites`.

**Minor observation:** the new `ail_raise_value_adopt(...)` line in `ail_par_go_wide` is redundant with the later `ail_raise_msg(code,msg)` re-raise already added on this base (same `exception_new`/adopt call, so no behaviour change; the latter is now dead for `msg[0] && code`).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 3830905, "input": 101823, "output": 12995, "reasoning": 36343, "cache.write": 0, "cache.read": 3679744}]
    tool time: bash 4.5 min
        129s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_pre171.py test_ail
         26s bash   date; cd /tmp/probes && for p in p*.py; do echo "=== $p"; bash ~/tools/cmp.sh "$p" /home/runner/work/ail-ci/ai
         19s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 900 python3 tools/par_check.py -j 2 test_ail_pre109.py 2>&1 | ta
         11s bash   cd /tmp/rprobes && for p in r1_callback r2_attr_ret; do echo "######## $p BASE"; bash ~/tools/cmp.sh $p.py /tm
         11s bash   cd /tmp/rprobes && for p in r5_lambda r6_apply; do echo "######## $p BASE"; bash ~/tools/cmp.sh $p.py /tmp/bas
         11s bash   cd /tmp/rprobes && for p in r5_lambda r6_apply; do echo "######## $p HEAD"; bash ~/tools/cmp.sh $p.py /home/ru
         10s bash   cd /tmp/rprobes && for p in r1_callback r2_attr_ret; do echo "######## $p"; bash ~/tools/cmp.sh $p.py /home/ru
          8s bash   cd /tmp/rprobes && for p in r3_aug_raise r4_direct_unused; do echo "######## $p HEAD"; bash ~/tools/cmp.sh $p.

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T10:46:56Z
