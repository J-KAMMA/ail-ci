# job job-pre168-10250413  started 2026-10-24T19:15:56Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":329,"duration_api_ms":202,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":332,"duration_api_ms":204,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `fedfaa6` on `job-pre168-10250413`.

- Reproduced the first difference: default build emitted `ail_list_push(ail_list)` for `list(itertools.permutations(...))`.
- Fix: typed lowering now refuses `list(...)` over tuple-yielding itertools streams by name; default falls back to the general path. Added `test_ail_pre168.py` and registered it.
- Tests on HEAD: `test_ail_pre168` 5 tests/20.9 s pass; `test_ail_safetynet` 5/120.9 s pass. Also `test_ail_files` 18 (1 skip)/128 s and `test_ail_corpus_findings3` 2/203 s pass on the same code.
- Probes: 23 `perm*` plus 4 `pre168_*` programs all match CPython on both builds; typed-only build refuses with rc=3 and the named message. Manifest `--check` rc=0; worktree clean except untracked `.agent/pipeline.md`.
- Remaining known/unfixed: float/str/None `r` and negative `r` differences; also discovered `list(product([1,2]))` yields `[1, 2]` instead of CPython’s `[(1,), (2,)]` (separate pre-existing issue).
[cost $0.0000, opencode tokens {"total": 4793377, "input": 108592, "output": 12731, "reasoning": 16310, "cache.write": 0, "cache.read": 4655744}]
    tool time: bash 14.3 min
        204s bash   python3 -m unittest AIL_CURRENT.test_ail_corpus_findings3 2>&1 | tail -20
        142s bash   python3 -m unittest AIL_CURRENT.test_ail_pre168 2>&1 | tail -8 && python3 -m unittest AIL_CURRENT.test_ail_saf
        129s bash   python3 -m unittest AIL_CURRENT.test_ail_files 2>&1 | tail -20
        121s bash   python3 -m unittest AIL_CURRENT.test_ail_safetynet 2>&1 | tail -20
         93s bash   for p in perm1 perm2 perm3 permA permB permC permD permE permF permG permH permI permJ permK permL permM permN
         21s bash   python3 -m unittest AIL_CURRENT.test_ail_pre168 -v 2>&1 | tail -30
         19s bash   cat > /tmp/probes/pre168_literal.py <<'EOF' import itertools   def main() -> None:     out = list(itertools.pe
         16s bash   cat > /tmp/probes/permA.py <<'EOF' from itertools import permutations   def main() -> None:     out = list(per

## review 0
[model opencode/deepseek-v4.1-flash-free]
- **Change**: `itlib.Streams.hoist` now refuses `list(<itertools stream>)` at compile time when the stream is not scalar (tuple-yielding), so the default build falls back to the general path; plus a new test module, manifest, DEVLOG and DIFFERENCES rows.

**Probes** (all via `bash ~/tools/cmp.sh`, g=general, d=default):

| probe | content | result |
|---|---|---|
| p1_types | permutations int/float/str/bool/tuple, r=0,1,2,5, empty | g/d match CPython |
| p2_sources | r from arg/list item/attribute/dict, return `list(...)`, negative r | g/d match except negative r (pre-existing) |
| p3_other | combinations, CWR, product 2 pools/repeat, pairwise, zip_longest, pool mutation | g/d match |
| p4_scalar/p4b | list over chain/islice/accumulate/repeat/chain.from_iterable | g/d match; scalar list use not over-refused |
| p4c | `sorted(permutations(...))` | default bad C; identical on base (pre-existing) |
| p5_untouched | plain lists/zip/chain/generator | `--debug-dir` `program.c` byte-identical to base |
| p6 | `list(product([1,2]))` | default `[1,2]` vs CPython `[(1,), (2,)]`; identical on base (pre-existing) |
| p7/p9/p10/p11 | zip(count), combinations, product 2 pools, pairwise | HEAD g/d match; base default failed with `ail_list_push(ail_list)` |
| p13 | result into function arg, attribute, dict value, list append | g/d match; typed path refuses rc=3 by name |

Typed-only check: rc=3 with `list(itertools.permutations(...)) ... typed path`; default prints the fallback note and matches CPython.

**Pre-existing / not caused**: negative `r` (`[]` + exit 0 vs CPython `ValueError`; base general identical, base default did not build); `sorted(itertools.permutations(...))` default bad C (identical on base); `list(product([1,2]))`/`repeat=1` (identical on base; `/tmp/probes/pre168_prod1.py` shows it); float/str/None `r` (not probed; worker says unfixed); arity-1 wrappers such as `islice(permutations(...))` are not covered by the refusal (pre-existing).

**Claims**: first difference reproduced — verified; fix/refusal/fallback — verified; test added and registered — verified; `test_ail_pre168` (21.7 s) and `test_ail_safetynet` (122 s) pass — verified; manifest `--check` rc=0, trailer present, clean except untracked `.agent/pipeline.md` — verified; four `pre168_*` probes match — verified; `test_ail_files`/`test_ail_corpus_findings3` and gdev counts — unverified (not re-run; change is compile-time only and p5 C is identical); the referenced `test_ail_pre137` does not exist.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1816738, "input": 64371, "output": 7449, "reasoning": 20374, "cache.write": 0, "cache.read": 1724544}]
    tool time: bash 4.6 min
        124s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre168 test_ail_safetynet 2>&1 | tail -30
         27s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p1_types p2_sources p3_other p4_scalar p5_untouched; do echo "===
         21s bash   cat > /tmp/rprobes/p7_zip.py <<'EOF' import itertools   def main() -> None:     print(list(zip(itertools.count
         19s bash   date; cd /home/runner/work/ail-ci/ail-ci; for p in pre168_literal pre168_return pre168_sources pre168_types; d
         16s bash   for n in comb prod2 pairwise ziplong; do :; done cat > /tmp/rprobes/p9_comb.py <<'EOF' import itertools   def 
         10s bash   cd /home/runner/work/ail-ci/ail-ci; for p in p2_sources p4_scalar; do echo "===== $p BASE ====="; bash ~/tools
          9s bash   cd /home/runner/work/ail-ci/ail-ci; echo "== p4b HEAD =="; bash ~/tools/cmp.sh /tmp/rprobes/p4b_no_sorted.py $
          9s bash   cd /tmp; rm -rf tt; mkdir tt; for p in p12_ziplong p11_pairwise p9_comb; do cp /tmp/rprobes/$p.py tt/$p.py; do

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T20:55:54Z
