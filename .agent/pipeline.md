# job job-bigint-fix10-10261221  started 2026-10-26T03:21:52Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":523,"duration_api_ms":402,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":532,"duration_api_ms":413,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Worker report — `job-bigint-fix10-10261221`**

Commit `48bda16` on the branch, not pushed. Earlier fix10 commits remain.

**Changes**
- `pyboxed2.py`: clone C units now turn their checked `ail_die("integer overflow")` stops into a flag + `longjmp` to the int64 wrapper, so the call site runs the exact boxed body. The wrapper resets the flag and catches the jump.
- `_setup_mix` now checks the successful lowering attempt’s info for `io`, so functions that print/assert stay boxed. This fixed the `test_ail_fuzz70` regression.
- `test_ail_bugs7.py`: overflow clone expectations updated to `mixed=True` (fix10 restores the clone).
- Added `bigint_cases/mix_clone_overflow.py` and its regression test.

**Tests on final commit `48bda16`**
```
112 tests, OK (skipped=1), 808s
```
Modules: `mixed_bounds`, `flush_exit`, `bigint`, `tint`, `unified`, `bugs7`, `fuzz70`, `safetynet`, `files`, `corpus_findings3`. Skip was the Windows-target/no-zig case in `test_ail_files`.

**Probes** (`bash ~/tools/cmp.sh`, CPython vs general/default)
- Match on both builds: `p01`, `p02`, `p03`–`p10`, `p12`–`p16`.
- `p13` also checked with `AIL_IR=0/1`: exact `2**63`, `2**64`, caught `IndexError`; clone contains `longjmp` + `__mix_overflow`.
- `p14` also checked with `AIL_IR=0/1`: OK.
- `p12`: generated C byte-identical to pre-patch `fix10head`.
- `p11_mixedfloat`: default fails `integer overflow`, but fails identically on `/tmp/base` and `fix10head` — pre-existing, not introduced or claimed fixed.
- `p02`/`p10` failed on pre-patch `fix10head`; both match now.

**Other**
- `tools/update_manifest.py --check` → 0.
- No `DEVLOG`/`DIFFERENCES` files exist in this export.
- `test_ail_quirks`, `test_ail_debug_flush`, `test_ail_unbound` fail identically on pre-fix10 `/tmp/base`; left untouched as pre-existing.
- Working tree has only the job-generated untracked `.agent/pipeline.md`.
[cost $0.0000, opencode tokens {"total": 10799151, "input": 295218, "output": 23365, "reasoning": 47928, "cache.write": 0, "cache.read": 10432640}]
    tool time: bash 86.4 min
       1014s bash   cd AIL_CURRENT && timeout 3600 python3 -m unittest -q test_ail_mixed_bounds test_ail_flush_exit test_ail_bigin
        808s bash   cd AIL_CURRENT && timeout 3600 python3 -m unittest -q test_ail_mixed_bounds test_ail_flush_exit test_ail_bigin
        704s bash   date -u; cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_mixed_bounds test_ail_flus
        673s bash   date -u; cd AIL_CURRENT && timeout 2200 python3 ../tools/par_check.py -j 2 test_ail_mixed_bounds test_ail_flus
        395s bash   date -u; cd AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_debug_flush test_ail_fuzz7
        366s bash   cd /tmp/fix10head/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_fuzz70 test_ail_debu
        357s bash   cd /tmp/base/AIL_CURRENT && timeout 1800 python3 ../tools/par_check.py -j 2 test_ail_fuzz70 test_ail_debug_flu
        341s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_bigint 2>&1 | tail -40

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review started 05:05 UTC, ended 05:25 UTC.

**What the change really does:** For each int-returning mixed clone it rewrites every `ail_die("integer overflow")` in that translation unit into a flag + `longjmp` to the clone's int64 wrapper; the wrapper catches it with `setjmp` and returns 0 so the call site runs the boxed body. It also gates clone selection on the successful attempt's (mutated) `io` info. This matches the report, but the `longjmp` bypasses the clone's own frame cleanup.

**Probes:** 60+ in `/tmp/rprobes`; clone-producing shapes used the `risky(...)` + module-level `d` template. Both builds matched CPython on overflow via argument, list item, dict value, attribute, default/kw arg, bool return, neg/`//`/`%`/`<<`/`**`, int(str), float→int, repeated overflows, two clones, nested and mutually recursive clones, and print/assert functions (including tagged clones). No-feature program (`r10`) generated byte-identical `program.c` on HEAD and base.

**Defect (new fallback path):**

```python
# /tmp/rprobes/r59_depth_min.py
def risky(xs: list[int], i: int) -> int:
    return xs[i] + xs[i - 1]

def rec(n: int, xs: list[int]) -> int:
    if n <= 0:
        return xs[0] * xs[0]
    return rec(n - 1, xs) + 1

def main() -> None:
    d = {"k": [1, 2, 3]}
    print("start", d)
    print(risky([1, 2, 3], 1))
    xs = [4294967296]
    print(rec(3, xs))
    s = 0
    for i in range(1000):
        s = (s + rec(70, xs)) % 1000000007
    print(s)
    try:
        print(risky([1], 1))
    except IndexError as e:
        print("IndexError", str(e))

main()
```

Expected (CPython, default build):
```
start {'k': [1, 2, 3]}
3
18446744073709551619
344073926
IndexError list index out of range
```
exit 0. Actual default build: prints the first three lines, then `recursion depth exceeded`, exit 1. General build matches. Generated `rec__typed__mix` does `++ail_depth` and decrements on each return; `ck_mul` inside the base case now calls `rec__typed__mix_overflow_hit()` → `longjmp`, so all abandoned recursive frames skip `ail_depth--`. After ~700 fallbacks the leaked depth exceeds `AIL_MAX_RECURSION_DEPTH` (50000). Fix: save/restore `ail_depth` (and run the clone's cleanup) across the wrapper `setjmp`.

**Pre-existing (not blocking):** `r08`/`r13` fail with `integer overflow` on both work `628d43c` and base `054c7d7` (unified path, no clone); `p11_mixedfloat` fails identically on work/base. Note `r59` passes on base `054c7d7` and already failed differently on work, so this is a remaining regression of the fix10 series, which this task was to finish.

**Claims:** diff/manifest/changed tests/new bigint case/io gating verified; required modules pass on HEAD (`test_ail_bigint` 259.6s, `test_ail_bugs7` 79.9s, `test_ail_safetynet` 96.9s, `test_ail_fuzz70` 16.1s), `update_manifest.py --check` = 0. `p12` byte-identical-to-fix10head and `p13` AIL_IR=0/1 and the full 112-test/808s figure were not independently reproduced. Working tree only has untracked `.agent/pipeline.md`.

VERDICT: FIX
1. Repeated overflow fallback in a recursive mixed clone leaks `ail_depth` because `longjmp` skips the clone's `ail_depth--`; probe `r59_depth_min.py` above must print the four CPython lines and exit 0, but on the default build it dies with `recursion depth exceeded` (exit 1) after the first three lines.
[cost $0.0000, opencode tokens {"total": 7026215, "input": 127573, "output": 23743, "reasoning": 37651, "cache.write": 0, "cache.read": 6837248}]
    tool time: bash 10.1 min
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && (python3 ../tools/par_check.py -j 2 test_ail_bigint test_ail
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && setsid nohup python3 ../tools/par_check.py -j 2 test_ail_big
         40s bash   date; cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/r31_two.py /tmp/rprobes/r32_bool.py /tmp/rprob
         32s bash   date; cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/r41_listmut.py /tmp/rprobes/r42_arith.py /tmp/
         29s bash   date; cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/r21_repeat.py /tmp/rprobes/r22_twoclones.py /t
         27s bash   date; cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/r*.py; do echo "===== $(basename $f)"; bash ~/
         19s bash   date; cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/r49_print.py /tmp/rprobes/r50_assert.py /tmp/r
         19s bash   date; for p in r31_two r34_list r35_parse r36_global r37_float r38_nested r39_attr r40_loop r32_bool; do rm -r

## worker report 1
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**Done — commit `facb692` on `job-bigint-fix10-10261221`.**

**Fix**
- `_mix_overflow_fallback` now saves/restores the clone unit's `ail_depth`, and releases abandoned cleanup frames while restoring `ail_cleanup_top`/`ail_exc_top`.
- State is emitted only for symbols the clone unit actually declares, so non-recursive clones still compile.
- Extended `bigint_cases/mix_clone_overflow.py` with the recursive repeated-fallback case.

**Probes**
- 23 probes matched CPython on both general and default builds.
- `r59_depth_min` (reviewer’s repro), `r60_depth_cleanup`, `r61_depth_mutual` all pass, including repeated 1000-iteration recursion.
- `r59`/`r60` also matched with `AIL_IR=0` and `AIL_IR=1`.
- Pre-existing, reproduced on base `054c7d7` too: `p11_mixedfloat`, the `r62` unified-path shape, and `mix_try_overflow`’s default-build compile failure.

**Tests on final commit**
- `test_ail_bigint`, `test_ail_bugs7`, `test_ail_fuzz70`, `test_ail_mixed_bounds`, `test_ail_flush_exit`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`
- **8 modules, 0 failed, 424s**
- `update_manifest.py --check` → **0**
[cost $0.0432, opencode tokens {"total": 4212259, "input": 104901, "output": 12643, "reasoning": 12667, "cache.write": 0, "cache.read": 4082048}]
    tool time: bash 10.9 min
        425s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_big
         76s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/probes/final_results.txt && for f in /tmp/probes/p01_overflow
         74s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/probes/final_results.txt && for f in /tmp/probes/p*.py /tmp/p
         11s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/mix_cleanup_list.py /tmp/probes/mix_cleanup_str.py 
          9s bash   cd /tmp && rm -rf irtest && mkdir irtest && cp /tmp/probes/r59_depth_min.py irtest/p.ail && cp /tmp/probes/r60
          9s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/p02_list.py /tmp/probes/r59_depth_min.py; do echo =
          9s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/probes/r59_depth_min.py /tmp/probes/r60_depth_cleanup.py; 
          7s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_bigint.DefaultBu

## review 1
[model opencode-go/deepseek-v4.1-flash]
**Review — `work..HEAD` (`48bda16`, `facb692`)**

**What it really does:** For every int/bool-returning mixed clone, rewrites the clone unit's `ail_die("integer overflow")` sites into a hit helper that restores the unit's `ail_depth`/`ail_cleanup_top`/`ail_exc_top` (releasing abandoned cleanup frames while still live, before `longjmp`) and jumps to the int64 wrapper, whose flag makes `_call_mix_guarded` rerun the boxed body; clone selection is also gated on the successful attempt's `io`. This matches the report.

**Previous defect:** fixed. `r59_depth_min` now prints all four CPython lines and exits 0 on both builds; on `work` (628d43c) it still dies `recursion depth exceeded`. 1000× `rec(70)` fallbacks pass.

**My probes `rv01`–`rv18` (both builds vs CPython):**
- Match: boundary ±2^63/2^64 (`rv02`), aliased lists (`rv03`), overflow under caller `try/finally` (`rv04`), bool return (`rv10`), empty/negative index (`rv11`), dict/attribute inputs (`rv16`), add/sub/neg/shift/pow/floor-div overflow (`rv15`, 4 clones actually took the longjmp path), string ops (`rv14` general), no-feature C unchanged (`rv13`/`rv17`: `program.c` byte-identical to `work`; only path fields in native_report).
- All worker probes `p01`–`p16` pass except `p11_mixedfloat` (pre-existing); direct `bigint_cases/mix_clone_overflow.py` matches CPython on both builds.
- `AIL_IR=0` and `AIL_IR=1` on `r59` both match.

**Pre-existing (identical on `work` and `054c7d7`, not blocking):**
- `rv01_cross`, `rv14_strops`: default build ends `integer overflow` (these shapes form no clone).
- `rv09`/`rv12` (try/except, try/finally clones): default link error `undefined reference to ail_tint_from_int64`; same for `mix_try_overflow`.
- `p11_mixedfloat`: default-build overflow failure, same on both bases.

**Tests (HEAD, `-j 2`):** `test_ail_bigint` 255s, `test_ail_bugs7` 83s, `test_ail_safetynet` 89s, `test_ail_files` 90s, `test_ail_corpus_findings3` 146s — 5 modules, 0 failed. `update_manifest.py --check` → 0.

**Speed:** `perf_event_open` denied, so wall clock. Hot non-overflowing clone: HEAD 0.10–0.11s vs `work` 0.09s (~10% for `setjmp`) but 0.44s on `054c7d7` (clone still ~4× faster). No large slowdown.

**Claims:** verified — state save/restore and cleanup release in generated C, per-unit state pruning (non-recursive `add` clone omits depth), extended bigint case, r59/r60/r61, IR=0/1 on r59, pre-existing p11/mix_try, manifest. Not re-run: `test_ail_fuzz70`, `test_ail_mixed_bounds`, `test_ail_flush_exit`, `r62`, IR on r60.

**Unverified:** the cleanup-release branch itself, because no reachable clone currently pushes cleanup frames (try-clones fail to link pre-existing); no probe could exercise it.

VERDICT: ACCEPT
[cost $0.0608, opencode tokens {"total": 4490105, "input": 101532, "output": 16664, "reasoning": 37573, "cache.write": 0, "cache.read": 4334336}]
    tool time: bash 8.2 min
        120s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && setsid nohup python3 ../tools/par_check.py -j 2 test_a
        120s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && setsid nohup python3 ../tools/par_check.py -j 2 test_a
         48s bash   date; cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/probes/p*.py; do out=$(timeout 400 bash ~/tools/cmp.sh
         25s bash   date; cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/rv*.py; do echo "##### $(basename $f)"; timeou
         19s bash   date; cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/probes/r60_depth_cleanup.py /tmp/probes/r61_depth_mutu
         16s bash   date; cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/rv09_tryoverflow.py /tmp/rprobes/rv10_bool.py 
         15s bash   date; cd /home/runner/work/ail-ci/ail-ci; for wt in /tmp/base /tmp/fix10head; do for f in /tmp/rprobes/rv09_tr
         10s bash   cat > /tmp/rprobes/rv18_index.py <<'EOF' def rec(n: int, xs: list[int]) -> int:     if n <= 0:         return 

FINAL VERDICT: ACCEPT  2026-10-26T06:02:22Z
