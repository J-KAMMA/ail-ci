# job job-fecache1-11021435  started 2026-11-02T05:38:51Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Continue if you have next steps, or stop and ask for clarification if you are unsure how to proceed.
[cost $0.0000, opencode tokens {"total": 13096885, "input": 1204401, "output": 39353, "reasoning": 52427, "cache.write": 0, "cache.read": 11800704}]
    tool time: bash 63.1 min, edit 0.0 min, write 0.0 min
       1117s bash   cd /home/runner/work/_temp/w2 && python3 lab/fecache/verify.py --corpus --out lab/fecache/verify-corpus.json 2
       1091s bash   cd /home/runner/work/_temp/w2 && python3 lab/fecache/verify.py --corpus --out lab/fecache/verify-corpus.json 2
        305s bash   cd /home/runner/work/_temp/w2 && python3 lab/fecache/measure.py --phase step4 --runs 3 --out lab/fecache/step4
        272s bash   cd /home/runner/work/_temp/w2 && python3 lab/fecache/measure.py --phase step4 --runs 3 --cc-cache --out lab/fe
        243s bash   cd /home/runner/work/_temp/w2 && python3 lab/fecache/measure.py --phase step4 --runs 3 --out lab/fecache/step4
        229s bash   cd /home/runner/work/_temp/w2 && python3 lab/fecache/measure.py --phase step4 --runs 3 --cc-cache --out lab/fe
        146s bash   cd /home/runner/work/_temp/w2 && python3 lab/fecache/measure.py --phase step1 --runs 3 --out lab/fecache/step1
         89s bash   cd /home/runner/work/_temp/w2 && python3 lab/fecache/measure.py --phase step1 --runs 3 --out lab/fecache/step1
(cut off after 100 minutes)

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
## Review: front-end cache (`job-fecache1-11021435`)

**What the change really does.** Adds an opt-in `AIL_FE_CACHE=1` / `--fe-cache` cache in `python/pkg-v12/fecache.py`: on a miss `pyc.build_cached` runs the normal build and captures the emitted C (single unit, all `_split_build` units, or mixed-mode units + link order); on a hit it recompiles the stored C with the stored flags and links. Key = source text + `strict`/`force_general` + `buildcache.sources_hash(python/pkg-v12)` + `sys.version`/`sys.platform` + `buildcache.build_env()`. LRU under `$XDG_CACHE_HOME/ail/fe/c`, 200 MB default, atomic replace. Default path is unchanged: `build_cached` calls `build` when the cache is off. Tests, lab scripts and `docs/design/FE_CACHE.md` are added.

**Probes** (all in `/tmp/rprobes`, run with `AIL_FE_CACHE=1`, fresh cache, recording wrapper compiler, against `/tmp/base` = `work`):
- `p_big`, `p_mix` (exact int / boxed), `p_dict`, `p_args`, `p_boxed` (class/try/f-string), `p_mixed2` (2-unit mixed clone, kept 2 `.c` files) — miss and hit stdout match CPython; hit C byte-identical to miss (`p_mixed2` per-file hashes equal).
- `p_io` — hit binary re-reads/truncates `data.txt` correctly; no value is frozen.
- `p_file` — `__file__` is embedded in the merged source, so compiling the same text from two paths misses and prints each path correctly (no stale path hit).
- `p_split2` with `AIL_CC_SPLIT=4 AIL_CC_SPLIT_MIN=1` — `ccsplit` still refused to split (reason 11), so the multi-unit split capture stayed unexercised.
- No-feature check: emitted C for `p_big, p_mix, p_split, p_dict, p_args, p_mixed, p_mixed2, p_boxed, p_split2` with `AIL_NO_CACHE=1` is identical to the `work` build.

**Defects**

1. **Manifest was not regenerated, so the prescribed test runner cannot start.** `cd AIL_CURRENT && python3 ../tools/update_manifest.py --check` prints `unpinned python/pkg-v12/fecache.py`, `unpinned test_ail_fe_cache.py`, `unpinned tests.d/test_ail_fe_cache.txt`, `stale ail_chatgpt.py`, `stale python/pkg-v12/buildcache.py`, `stale python/pkg-v12/pyc.py` (exit 1). Expected: clean. Actual: fails. Consequence: `python3 ../tools/par_check.py -j 2 test_ail_fe_cache test_ail_safetynet` aborts with `ValueError: hash mismatch: ail_chatgpt.py`; expected the modules to run. The base worktree passes this check, so it is introduced here.
2. **Missing DEVLOG entry.** The rule requires a new top entry dated 2026-11-02; `DEVLOG.md` still starts with `## 2026-11-01 -- prog5 ...`.
3. **Documented key is wrong for the cache's own variables.** `docs/design/FE_CACHE.md` says the cache's own `AIL_FE_CACHE*` variables are excluded; only the exact `AIL_FE_CACHE=` is filtered in `fecache.build_env()`. Probe `/tmp/rprobes/p_same.py`: build once with `AIL_FE_CACHE_LOG=one.log`, then same source with `AIL_FE_CACHE_LOG=two.log`; expected `hit` (own variable has no effect on output), actual two separate `miss` keys. Same for `AIL_FE_CACHE_DIR`/`AIL_FE_CACHE_MAX_MB`. Not a wrong-output bug, but the claim is false and uselessly fragments the cache.

**Claims / tests.** The worker report is effectively empty (runner cut off), so it makes no checkable claims. The doc's 3-task/3-run scope and the `verify-*.json` summaries (10/10 compare, 213/229 corpus hit with identical C, 16 refusals) agree with the committed JSON; I did not re-run the timings. `test_ail_fe_cache` passes standalone (13 tests); `test_ail_safetynet` passes standalone (5 tests), but neither can be run via `par_check` because of defect 1.

**Pre-existing.** None found: the base no-cache C matched on every probe.

**Unverified.** Step 1/4 timing numbers, the `AIL_CC_SPLIT` multi-unit capture (could not make `ccsplit` split), and `test_ail_files` / `test_ail_corpus_findings3`.

VERDICT: FIX
[cost $0.0883, opencode tokens {"total": 3746959, "input": 348822, "output": 11484, "reasoning": 31773, "cache.write": 0, "cache.read": 3354880}]
    tool time: bash 4.2 min
        171s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 1400 python3 -m unittest test_ail_safetynet 2>&1 | tail -
         20s bash   cd /tmp/rprobes && FLAGS=--exact-int bash run.sh p_mixed.py p_boxed.py 2>&1 | tail -55
         20s bash   cd /tmp/rprobes && sed -i 's#--syntax python -o#--syntax python $FLAGS -o#g' run.sh && sed -i 's#^wt=#FLAGS=${
         12s bash   cd AIL_CURRENT && timeout 1500 python3 -m unittest -v test_ail_fe_cache 2>&1 | tail -60
          7s bash   cd /tmp/rprobes && cat > p_mixed2.py <<'EOF' def risky(xs: list[int], i: int) -> int:     return xs[i]  def ma
          5s bash   cd /tmp/rprobes && cat > run.sh <<'EOF' #!/bin/bash wt=/home/runner/work/_temp/w2 base=/tmp/base for p in "$@"
          3s bash   cd /tmp/rprobes && rm -f split2.log && AIL_CC_SPLIT=4 AIL_CC_SPLIT_MIN=1 AIL_CC_SPLIT_LOG=/tmp/rprobes/split2.
          3s bash   cd /tmp/rprobes && cat > p_split2.py <<'EOF' def f0(n: int) -> int:     s = 0     for i in range(n):         s

## fix round skipped: only 11 minutes left

FINAL VERDICT: FIX  2026-11-02T10:21:53Z
