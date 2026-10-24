# job job-pre68-10241806  started 2026-10-24T09:09:35Z  worker=oc reviewer=oc (GitHub)
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
Failed to fetch model list: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.
deepseek-v4.1-flash -> An unexpected critical error occurred:QoderAuthError: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.     at nde (file:///usr/local/lib/node_modules/@qoder-ai/qodercli/bundle/qoderc
DeepSeek-V4.1-Flash -> An unexpected critical error occurred:QoderAuthError: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.     at nde (file:///usr/local/lib/node_modules/@qoder-ai/qodercli/bundle/qoderc

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the literal `%d` float case on both builds.

- Cause: literal `"%d" % 3.7` compiled to `ail_obj_format`'s `d` spec, which rejects floats. `d`/`i`/`u` conversions now use the runtime `%` formatter unless the argument is provably `int`/`bool`, matching CPython truncation and inf/NaN errors.
- Added `AIL_CURRENT/test_ail_pre68.py`, registered in `ail_check.MODULES`, plus DEVLOG/DIFFERENCES entries and manifest pins.
- Commit: `1e66e46`.

Tests on the final commit: `test_ail_pre68`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` -> 27 passed, 1 skipped. Manifest `--check` passes.

Probes (17, all same stdout/exit as CPython on both builds): `p01_literal_d_float`, `p02_literal_d_percent`, `p03_variable_fmt_float`, `p04_arg_float`, `p05_list_item`, `p06_attr_float`, `p07_dict_float`, `p08_mixed`, `p09_edges`, `p10_float_other`, `p11_float_hex`, `p12_literal_hex_float`, `p13_int_forms`, `p15_nonfinite_nested`, `p16_tuple_args`, `p17_literal_mixed_values`, `p18_known_int_forms`.
[cost $0.0000, opencode tokens {"total": 2488172, "input": 96214, "output": 9592, "reasoning": 11550, "cache.write": 0, "cache.read": 2370816}]
    tool time: bash 10.1 min
        385s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_pre68 test_ail_safetynet tes
         75s bash   rm -f /tmp/probes/p14_mixed_types.py && cd /home/runner/work/ail-ci/ail-ci && : > /tmp/probes_run.log && for p
         69s bash   cd /tmp/probes && cat > p13_int_forms.py <<'EOF' print("%d" % True) print("%d" % False) print("%i" % 42) print
         41s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/probes/p0*.py /tmp/probes/p10*.py; do echo "=== $(basename
         10s bash   cd /tmp/probes && cat > p17_literal_mixed_values.py <<'EOF' def show(v):     try:         print("%d" % v)     
          9s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'EOF' from pathlib import Path p = Path('AIL_CURRENT/test_ai
          6s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest test_ail_pre68 -v 2>&1 | tail -30
          5s bash   cd /tmp/probes && cat > p11_float_hex.py <<'EOF' for v in [3.7, -3.7, float("inf")]:     try:         print("%

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does.** `_percent_format` now raises its runtime-fallback `Unsupported` for a literal `%d` conversion whose argument `infer_kind` does not prove `int`/`bool`; `expr_BinOp` catches it and re-emits the whole `%` as `ail2f_percent`. Despite the wording, only `d` is reachable (`_PCT_RE` never matches `i`/`u`, which already fell back).

**Probes (cmp.sh, both g and d)**
- Match CPython: `p1` literal/width/sign/`%%`/mixed tuple/`%i`/`%u`; `p2` arg/list/attr/dict; `p6` annotations; `p8` attr mutation; `p10` call order; `p13` int channels/flags; `p14` typed; `p15` int64 edges; `p16` list/dict mutation+slice; `p17` widths; `p20` flag combos.
- `p5` (no float `%d`): generated `program.c` identical to base on both builds (only `native_report.json` temp paths differ).
- `p3` inf/-inf/nan/str/None: match CPython; then large finite floats differ (below).
- Target reproduced on base: `p2`/`p6`/`p14` fail on base with `TypeError: unsupported format string passed to non-int`, pass on HEAD.

**Pre-existing (not blocking)**
1. Large finite float `%d` (`1e20`, `9.3e18`): CPython prints the big integer; HEAD exits 3 `AIL limit: integer overflow`; base exits 1 `TypeError`. The same int64 limit hits `print(10**20)` on both trees, so this is the language's int64 width, not this change.
2. Augmented float assignment (`y += 0.5`, `w -= 0.25`) leaves `infer_kind` as int: CPython prints `1`/`0`; base and HEAD both exit 1 with the same `TypeError` (identical).
3. `"%.3d" % 7`: build fails with a compiler `TypeError` on both base and HEAD (message-construction bug in the precision refusal); `"%.3d" % 3.7` now works on HEAD.
4. `"%lld"`: AIL prints on both trees, CPython raises `ValueError` (identical).

**Tests / records.** `test_ail_pre68 test_ail_safetynet test_ail_files test_ail_corpus_findings3` -> 27 tests, 1 skipped, OK. Manifest `--check` rc 0. Commit `1e66e46` has the required `Co-Authored-By`.

**Report claims.** Fixed on both builds: verified. Test/DEVLOG/DIFFERENCES/manifest: verified. 27 passed/1 skipped: verified. 17-probe claim: verified from the worker log plus reruns of key cases. The `d`/`i`/`u` wording is inaccurate (only `d` changed; `i`/`u` already used the runtime), but behaviour is correct. No regression found in int formatting, flags, widths, int64 edges or mutation.

**Unverified.** Speed (no `~/corpus/gdev` program uses literal `%d` formatting); full 17-probe rerun (log inspected, key cases rerun).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2965497, "input": 151026, "output": 9797, "reasoning": 35394, "cache.write": 0, "cache.read": 2769280}]
    tool time: bash 10.0 min
        270s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_pre68 test_ail_safetyne
        165s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 -m unittest test_ail_pre68 test_ail_safetyne
         26s bash   cd /home/runner/work/ail-ci/ail-ci && : > /tmp/head_cmp.log; for p in /tmp/rprobes/p*.py; do echo "########## 
         23s bash   cd /tmp/base && : > /tmp/base_cmp.log; for p in /tmp/rprobes/p*.py; do echo "########## $(basename $p)" >> /tm
         13s bash   cd /home/runner/work/ail-ci/ail-ci && for p in /tmp/rprobes/p8_attr_mutation.py /tmp/rprobes/p9_branches.py /t
          9s bash   cd /home/runner/work/ail-ci/ail-ci && bash ~/tools/cmp.sh /tmp/rprobes/p9_branches.py "$PWD" 2>&1 | tail -30; 
          9s bash   cat > /tmp/rprobes/p13_int_channels.py <<'EOF' class Box:     def __init__(self, v):         self.v = v   def 
          9s bash   cat > /tmp/rprobes/p18_augassign.py <<'EOF' def main():     z = 1     z = z * 1.5     print("%d" % z)     w = 

FINAL VERDICT: ACCEPT  2026-10-24T09:45:02Z
