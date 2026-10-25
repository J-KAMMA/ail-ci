# job job-pre190-10252047  started 2026-10-25T11:48:00Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":497,"duration_api_ms":371,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":507,"duration_api_ms":384,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `367e389` on `job-pre190-10252047`.

**Cause:** on the current candidate (`afa63a4`) another accepted job's generic int-constant folder in `pyfunc.py` had its own 4096-bit cap, refusing `0 * (1 << 5000)`, `0 ** (1 << 5000)`, `1 ** (1 << 5000)`, `(-1) ** (1 << 5000)` and `(1 << 5000) >> 5000` before the pre190 reductions ran. On a temporary merge, 3 of 4 tests failed.

**Fix:** make that folder share the pre190 2**20-bit cap (`_CONST_INT_BITS = _MAXSPLIT_BITS`), plus a regression check that the caps agree. No pre190 compiler logic was removed.

**Verification**
- Merged tree with `afa63a4`: `test_ail_pre190` 5/5 pass (was 3 failures); `test_ail_pre160` passes.
- Clean `afa63a4` already fails `test_ail_pre121` 2 tests (different refusal text) — unrelated pre-existing integration breakage, unchanged by this fix.
- Required tests on final tree: `test_ail_pre190`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failures.
- Probes `/tmp/probes/p190_*` (25 files): 23 match CPython on both builds; 2 oversized maxsplit probes (`p190_split_refuse1/2`) are refused by name as expected. Same results on the fixed merged tree; before the fix, probes at/above 4096 bits were refused on the merge.
- `update_manifest.py --check` exits 0.

Not run: full suite (per rules).
[cost $0.0000, opencode tokens {"total": 4307147, "input": 122353, "output": 9744, "reasoning": 36170, "cache.write": 0, "cache.read": 4138880}]
    tool time: bash 24.0 min
        532s bash   cd AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_ail_ir_s4c1 test_ail_pre190 > /tmp/shar
        350s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre
         93s bash   mkdir -p /tmp/probes && cd /tmp/probes && python3 - <<'PY' exprs = {  'p190_0_mul_4000':'print(0 * (1 << 4000)
         89s bash   cd /home/runner/work/ail-ci/ail-ci && : > /tmp/probes_branch.log && for f in /tmp/probes/p190_*.py; do echo "=
         60s bash   cd /tmp && : > /tmp/probes_merged.log && for f in /tmp/probes/p190_*.py; do echo "=== $(basename $f)" >> /tmp/
         60s bash   cd /tmp/merged/AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=incompatible-pointer-types' PYTHONUTF8=
         54s bash   cp /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/test_ail_pre190.py /tmp/merged/AIL_CURRENT/test_ail_pre190.py; 
         52s bash   cd AIL_CURRENT && python3 -m unittest -q test_ail_pre190 2>&1 | tail -60

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `367e389` (`git diff work..HEAD`)**

**What it really does:** Sets the integration generic int-constant folder's cap to the pre190 maxsplit cap (`_CONST_INT_BITS = _MAXSPLIT_BITS`, i.e. 2**20 bits) by appending one line to `pyfunc.py`; adds an invariant test plus DEVLOG/DIFFERENCES/MANIFEST updates. Matches the report.

**Probes** (`/tmp/rprobes`, `cmp.sh`, general + default builds):
- shift boundaries 4095/4096/4097/5000/1048574/1048575: match CPython on HEAD and merged.
- reductions via argument/list/attribute/dict/maxsplit: match both.
- 1,000,000-bit reduction: matches; >2**20-bit constants: named refusal both.
- non-int zero/power cases, errors, negative/parity cases: match both.
- non-feature program: generated `program.c` byte-identical HEAD-vs-`work` and merged-vs-`afa63a4`.

**Integration check:** on a simulated merge (`/tmp/merged` = `afa63a4` + branch, corrected to the commit's line), `test_ail_pre190` passes 5/5 with the fix; without the appended assignment 3 behavioural tests plus the new invariant test fail. Worker's 25 probes on merged: 23 match CPython, 2 named maxsplit refusals.

**Tests on HEAD** (`par_check.py -j 2`): `test_ail_pre190`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failures. `test_ail_pre160` OK on HEAD and merged. `update_manifest.py --check` exits 0. `test_ail_pre121` on clean `afa63a4` has the reported 2 pre-existing failures.

**Claims:** all report claims verified; none false.

**Pre-existing (not caused by this commit):** `0 ** (1 << 2000000)` and similar >2**20-bit special-exponent folds are refused on `afa63a4` and remain refused on merged, while the branch folds them; named refusal, so non-blocking. Also the branch's runtime `integer overflow` for `(1 << 1048576) >> 1048576` versus the integration tree's named refusal.

**Unverified:** full suite (not run per rules); runtime icount not applicable (compile-time-only change).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 2221334, "input": 79154, "output": 7744, "reasoning": 31396, "cache.write": 0, "cache.read": 2103040}]
    tool time: bash 8.6 min
        210s bash   date; cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_pre190 test_ail_safetynet tes
         60s bash   date; cd /tmp && : > /tmp/workerprobes_merged.log; for f in /tmp/probes/p190_*.py; do printf '%s: ' "$(basenam
         33s bash   cd AIL_CURRENT && time python3 -m unittest -q test_ail_pre190 2>&1 | tail -20
         32s bash   cd /tmp/merged/AIL_CURRENT && cp python/pkg-v12/pyfunc.py /tmp/pyfunc_merged_fixed.py && python3 - <<'PY' p='p
         32s bash   cd /tmp/merged/AIL_CURRENT && python3 - <<'PY' p='python/pkg-v12/pyfunc.py' s=open(p).read() assert s.endswith
         32s bash   date; cd /tmp/merged/AIL_CURRENT && time python3 -m unittest -q test_ail_pre190 2>&1 | tail -30
         19s bash   date; cd /tmp && : > /tmp/rprobes_head.log; for f in /tmp/rprobes/*.py; do echo "=== $(basename $f)" >> /tmp/r
         19s bash   date; cd /tmp/baseaf/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_pre121 2>&1 | tail -25

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T13:46:50Z
