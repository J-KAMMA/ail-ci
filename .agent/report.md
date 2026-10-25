# job job-pre211-10252259  started 2026-10-25T14:02:49Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":352,"duration_api_ms":221,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":354,"duration_api_ms":228,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Report**

- `r9_genexp`: already refused by name on both builds (`a generator expression used as a value`); no change.
- `r11_method`: reproduced on the default build only. `AIL_NO_MIX=1` made it match, locating the cause in pymix. Fixed `_escapes` to include class-method bodies and attribute call sites, so the method → helper chain reaches the boxed `try` and `shl` is no longer selected for a typed clone.
- Commit `bc4efd4` on `job-pre211-10252259`; added `test_ail_pre211.py`; DEVLOG/DIFFERENCES updated; `update_manifest.py` and `--check` exit 0.

**Tests on final commit:** pre211 (2), pre109 (5), safetynet (5), files (18, 1 skipped), corpus_findings3 (2) — all pass. Mixed-mode related: mixed_bounds (2), flush_exit (10), bugs7 (9) — all passed.

**Probes (both builds):**
- `r11_method`, `r11_forms`, `r11_chain`, `r11_traps`: same stdout as CPython, exit 0.
- `r11_uncaught`: same stdout/exit 1 and `ValueError: negative shift count`.
- `r9_genexp`: refused by name on both builds.

No push performed.
[cost $0.0000, opencode tokens {"total": 1812959, "input": 67792, "output": 10609, "reasoning": 14878, "cache.write": 0, "cache.read": 1719680}]
    tool time: bash 9.7 min
        276s bash   cd AIL_CURRENT && printf '%s\n' test_ail_pre211.py test_ail_pre109.py test_ail_safetynet.py test_ail_files.py 
        122s bash   cd AIL_CURRENT && printf '%s\n' test_ail_mixed_bounds.py test_ail_flush_exit.py test_ail_bugs7.py | xargs -P 2
        109s bash   cd AIL_CURRENT && printf '%s\n' test_ail_pre211.py test_ail_pre109.py test_ail_safetynet.py test_ail_files.py 
         19s bash   for p in r11_method r11_forms r11_chain r11_uncaught r11_traps r9_genexp; do echo "===== $p"; bash ~/tools/cmp
         14s bash   for p in /tmp/probes/r11_forms.py /tmp/probes/r11_chain.py /tmp/probes/r11_uncaught.py /tmp/probes/r11_alias.p
         10s bash   mkdir -p /tmp/probes && cat > /tmp/probes/r9_genexp.py <<'EOF' def shl(a, b):     return a << b  def consume(g
          6s bash   cat > AIL_CURRENT/test_ail_pre211.py <<'PY' """pre211: a module function called from a class method under a bo
          6s bash   cat > /tmp/probes/r11_forms.py <<'EOF' def shl(a, b):     return a << b  def shr(a, b):     return a >> b  cla

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change really does.** Only compile-time `pymix._escapes` changed: it now records class-method bodies and `obj.method()` attribute call sites in the call graph, so a module function called from a method under an enclosing `try` is detected as exception-capable and kept boxed. No runtime/C change; no benchmark edits.

**Probes** (`bash ~/tools/cmp.sh`, HEAD vs `/tmp/base`, both builds vs CPython):

| probe | HEAD | base | meaning |
|---|---|---|---|
| p1_method | g+d match | d fails (exit 1) | target r11 fixed |
| p2_forms (arg/list/attr/dict/alias/zero/large/right/literal) | g+d match | d fails | fixed |
| p3_chain (method→method→helper; try inside method) | match | match | ok |
| p8_localtry (try inside method) | g+d match | d fails | fixed |
| p6_uncaught (no try) | match, exit 1 | match, exit 1 | ok |
| p7_static/classmethod/instance | g+d match | match | ok |
| p10_nofeature | match | match, C unchanged | ok |
| p13_genexp | refused by name `a generator expression used as a value` | same | report claim verified |

**Pre-existing (identical on base, non-blocking):**
- `p4_collide`: method name collides with a module function (`def run` + `class C: def run`). Default build exits 1, no `caught ValueError 'negative shift count'` / `valid 8`; general build matches. Same on base.
- `p5_dupname`: two classes define the same method name, one calling `shl`. Default build misses the handler; same on base.
- `p9_methodalias`, `p11_classval`: bound method stored as value / in list gives `AttributeError: 'C' object has no attribute 'run'` on both builds and both trees (unsupported method values, unrelated).

**Unchanged C:** `p10_nofeature`, `p12_classonly`, `p6_uncaught`, and gdev `g13_018`, `g12_036`, `g06_032` produced byte-identical `--debug-dir/program.c` on base vs HEAD; no runtime instruction-count impact expected.

**Tests:** `test_ail_pre211.py` and `test_ail_safetynet.py` pass on HEAD (2 modules, 0 failed). `update_manifest.py --check` exits 0. Commit `bc4efd4`, DEVLOG/DIFFERENCES additions match the diff.

**Claims:** r11 default-only + `AIL_NO_MIX=1` matches, r9 refused on both builds, and the fix location are verified. Worker's `pre109`, `files`, `corpus_findings3`, `mixed_bounds`, `flush_exit`, `bugs7` results were not re-run (review scope) — unverified.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 642711, "input": 33731, "output": 5126, "reasoning": 11982, "cache.write": 0, "cache.read": 591872}]
    tool time: bash 3.9 min
        103s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && python3 ../tools/par_check.py -j 2 test_ail_pre211.p
         52s bash   cd /tmp/rprobes && for p in p1_method p4_collide p5_dupname p9_methodalias p11_classval p2_forms p3_chain p6_u
         38s bash   cd /tmp/rprobes && for p in p1_method p2_forms p3_chain p4_collide p5_dupname p6_uncaught p7_static p8_localtr
         24s bash   set -e for f in g13_018 g12_036 g06_032; do   for t in h b; do     d=/tmp/gd_$t; rm -rf $d; mkdir -p $d; cp ~/
          7s bash   set -e for p in p10_nofeature p12_classonly p6_uncaught; do   for t in h b; do     d=/tmp/cmp_$t; rm -rf $d; m
          6s bash   cd /tmp/rprobes && cat > p13_genexp.py <<'EOF' def shl(a, b):     return a << b gen = (shl(1, -1) for _ in ran
          2s bash   d=$(mktemp -d /tmp/nomixXXXX); cp /tmp/rprobes/p1_method.py $d/p.py; cd $d; AIL_NO_MIX=1 AIL_NO_CACHE=1 AIL_QU
          1s bash   cd /tmp && rm -rf dbgtest && mkdir dbgtest && cp /tmp/rprobes/p10_nofeature.py dbgtest/p.py && cd dbgtest && A

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T15:35:59Z
