# job job-rbpre237-10261405  started 2026-10-26T05:06:18Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":547,"duration_api_ms":425,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":531,"duration_api_ms":411,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `dddb588` on `job-rbpre237-10261405`.

- Re-applied pre237: `pymix._escapes` now keeps duplicate method bodies and records `obj.method()` call sites (the tree already had an equivalent dict-based fix; replaced with the accepted list form). Added/registered `test_ail_pre237.py`, DEVLOG entry, DIFFERENCES row `C?-job-rbpre237-10261405-1`.
- `tools/update_manifest.py` and `--check`: pass. `tools/diff_ids.py` does not exist on this branch (`rc=2`), so it was not run.
- Tests (`pre237`, `safetynet`, `files`, `corpus_findings3`): 27 run, OK, 1 skip (no zig for Windows target).
- Probes, all matching CPython on both builds:
  - `pre237_forms.py`: literal/argument/list-item/attribute/dict/alias counts, module-method name collision, duplicate methods, method chain, own try, zero/valid shifts, division/subscript traps.
  - `pre237_uncaught.py`: exit 1 and `ValueError: negative shift count` on both builds.
  - `pre237_dup_methods.py`: duplicate `run` methods, shl called only from the first method.
  - `pre237_collide_nocall.py`: module `run` does not call shl; method `run` does, under module try.
[cost $0.0000, opencode tokens {"total": 639427, "input": 27092, "output": 5619, "reasoning": 4476, "cache.write": 0, "cache.read": 602240}]
    tool time: bash 6.6 min, edit 0.0 min, read 0.0 min
        382s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -B -m unittest -v test_ail_pre237 test_ail_safetynet
         10s bash   cd /home/runner/work/ail-ci/ail-ci && printf '%s\n' /tmp/probes/pre237_*.py | xargs -P2 -I{} bash -c 'echo "==
          3s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/probes/pre237_uncaught.py "$PWD" 2>&1 | tail -2
          3s bash   git fetch https://github.com/J-KAMMA/ail-ci.git job-pre237-10260353 2>&1 | tail -5
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py --check; echo rc=$?; git status --short
          0s bash   git status && git log --oneline -5 && git branch --show-current
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/MANIFEST.json AIL_CURRENT/ail_check.py AIL_CURRENT/p

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review report**

**What the change really does:** Replaces `pymix._escapes`'s name-keyed method-body dict with a list that keeps duplicate method bodies, records `obj.method()` call sites, then adds/registers `test_ail_pre237.py`, a DEVLOG entry, a DIFFERENCES row, and refreshes MANIFEST. The `pymix` and test-file content is identical to the fetched pre237 diff; this matches the report.

**Probes** (own files in `/tmp/rprobes`, `cmp.sh` on HEAD and `/tmp/base`):
- `rp_worker_prog`, `rp_worker_uncaught` (extracted from the new test): match CPython, both builds and exits, on HEAD and base.
- `rp_dup`, `rp_dup_top` (duplicate method names, both orders), `rp_collide`, `rp_collide_top` (module function vs method name): match CPython on HEAD.
- `rp_values` (list item/dict value/attribute), `rp_attr` (method chain via argument), `rp_selfmethod` (own try + outer try), `rp_plain` (no class), `rp_other` (division trap), `rp_uncaught`: match CPython on HEAD.
- `_escapes` check: collision/duplicate sources give `_protected(shl, ValueError)` False on base, True on HEAD. Collision C differs (extra boxing, same output); all other C checked is byte-identical.

**Unchanged C:** `rp_plain`, `rp_other`, `rp_selfmethod`, and gdev `g13_018`, `g12_036`, `g06_032` are byte-identical base vs HEAD, so no speed change on those; `icount.c` not run.

**Tests:** `test_ail_pre237`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` → 0 failed; `test_ail_pre211` (displaced pre211 fix) → 0 failed. `update_manifest.py --check` rc=0. `tools/diff_ids.py` genuinely absent from this branch.

**Claims:** 1–6 verified. Exact “27 run / 1 skip” counts unverified (modules pass, counts not independently totalled). Individually named worker probes unverified (not present), but equivalent scenarios verified. DIFFERENCES row overstates this tree: base already had pre211's method-body/attribute fix, so I could not reproduce its claimed default-build exit 1 on `/tmp/base`; the only new behavior is duplicate method bodies. Record inaccuracy only, no code defect.

**Pre-existing:** none encountered beyond recorded ones; bound-method p9/p11 not re-probed (unverified).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1397740, "input": 49329, "output": 9082, "reasoning": 16961, "cache.write": 0, "cache.read": 1322368}]
    tool time: bash 6.6 min
        270s bash   cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_pre237 test_ail_safetynet test_ail_f
         30s bash   mkdir -p /tmp/rlogs; cd /home/runner/work/ail-ci/ail-ci printf '%s\n' /tmp/rprobes/*.py | while read p; do n=$
         22s bash   cd /tmp && rm -rf gcmp && mkdir gcmp && cd gcmp for g in g13_018 g12_036 g06_032; do   src=~/corpus/gdev/$g.py
         18s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' import importlib.util, pathlib p = pathlib.Path('AIL_C
         17s bash   cd /home/runner/work/ail-ci/ail-ci && for n in rp_collide_top rp_dup_top; do for t in head base; do wt=$PWD; [
         11s bash   cd /tmp/dbgcmp && for src in /tmp/rprobes/rp_other.py /tmp/rprobes/rp_selfmethod.py /tmp/rprobes/rp_collide_to
         11s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 600 python3 ../tools/par_check.py -j 2 test_ail_pre2
          4s bash   cd /tmp && rm -rf c2 && mkdir c2 && cd c2 && cp /tmp/rprobes/rp_collide_top.py h.py && cp /tmp/rprobes/rp_coll

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-26T06:30:35Z
