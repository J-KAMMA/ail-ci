**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
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


--- ORIGINAL TASK ---
Lane: frontend

**Front-end cache: skip the Python lowering when nothing changed (owner approved 2026-11-02).** tccdev1 (docs/design/TCC_DEV.md) measured the front end at 1.2–4.2 s of a 2.03 s median cold build. A C compiler swap cannot reach Rust's 0.4–0.5 s. This task caches the front-end result and measures what that wins.

**Step 1, price it first (the speed-claims rule).** For the 10 lab/compare tasks, measure the warm rebuild in three cases:
- (a) nothing changed;
- (b) one function body edited;
- (c) one imported module edited.

Split the time into front end, C compile and link, and give the median and spread of 5 runs. State the Amdahl bound for each case before you build anything. A whole-program cache only helps case (a). Say how much of (b) and (c) a per-module cache would reach.

**Step 2, implement as opt-in.** Add `AIL_FE_CACHE=1` (and `--fe-cache`). It stores the emitted C, keyed by a hash of:
- the source and every imported AIL or Python module it reads;
- all flags and every environment variable that affects the output (`AIL_*`, `--exact-int`, `AIL_FE_JOBS` and the others; list them);
- the compiler itself, meaning the hash of the package files, so any compiler change invalidates the cache;
- the Python version.

If any input cannot be hashed for sure, fall back to a full build. Never risk a stale hit. The cache lives under `$XDG_CACHE_HOME/ail/fe` (default `~/.cache/ail/fe`) with a size cap, default 200 MB, that evicts the least recently used entries. Writes are atomic: write to a temp file, then rename. If the cache is per module, the same rules apply to each module key.

**Step 3, prove the output is identical (the optimization-adoption rule).**
- On all 10 tasks and the lab/corpus programs, the C emitted on a cache hit must be byte-identical to a fresh build.
- Add tests:
  - editing the source, an import, a flag, an env var or a compiler file each forces a miss;
  - a corrupt or truncated cache entry falls back to a full build;
  - two concurrent builds do not corrupt the cache.

**Step 4, measure.** Measure cold, hit and miss times, with the resident server on and off. Also report the disk used per entry and the RSS. Add the results to docs/design/TCC_DEV.md, or write docs/design/FE_CACHE.md. Include:
- the bound against the measured gain;
- how close the hit path gets to 0.5 s;
- a recommendation on whether to turn it on by default. Leave that decision to the owner.

Time budget (the first attempt ran out the 5.5 h runner limit with nothing committed):
- Commit and push after each step.
- Do Step 2 and Step 3 before the full measurement. In Step 1 measure only 3 tasks (`berth_sim`, `rail_transfer`, `tally_lang`) with 3 runs each.
- Keep all measuring under 60 minutes. Measure the rest of the 10 tasks only if there is time left, and say which were skipped.

Rules:
- Default behaviour does not change: the cache is off unless enabled.
- Do not change any test expectation.
- New package files need the right manifest flag (manifs1 automation, `s` for pkg-v12 files).
- Commit the scripts under lab/fecache/.

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Register a new test module: if `AIL_CURRENT/tests.d/` exists, add `AIL_CURRENT/tests.d/<module>.txt` containing the module
    name and do NOT edit the tuple in `ail_check.py`; otherwise append it to the `MODULES` tuple.
  - `git add` new files, run `python3 tools/update_manifest.py`, then `--check`. Do not hand-edit `MANIFEST.json` or `manifest.d/`.
- **Required tests:** the targeted modules for what you touch, plus test_ail_safetynet, test_ail_files and test_ail_corpus_findings3. Run them on your final commit, not an earlier one.
- **Mandatory self-check before you report.** A reviewer will repeat it, and past reports were wrong about half the time.
  1. Write probe programs in /tmp/probes/ for every behaviour you changed. Cover the boundaries your implementation implies, not only the example: types, widths, empty, negative, aliasing, values reaching the code through an argument, a list item, an attribute and a dict value, and both builds.
  2. Run each probe with `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`.
  3. Every probe must match CPython or be refused by name.
  4. List the probes and their results in the report.
- **Never claim something works unless a probe or test you ran shows it.** If you did not verify something, say so.
- **Tokens:** use grep -n, narrow reads, and `tail` on long logs.
- **Budget:** stop at the budget note, leaving a committed, consistent state.
- **Report:** keep it brief, with numbers.
- Test data: email addresses only on example.com / example.org (the public export audit rejects any other domain).

**Work in few steps** (each step costs model time):
- Write all probe programs first, then run them together with one command, for example a loop over `bash ~/tools/cmp.sh`, instead of one command per program.
- Search only inside the repository (`grep -rn ... AIL_CURRENT tools`), never across `/home` or `/tmp`.
- Read a file once, using a range that is large enough, instead of many small reads.
- Do not re-run a test that already passed unless you changed code since.

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
