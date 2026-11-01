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
