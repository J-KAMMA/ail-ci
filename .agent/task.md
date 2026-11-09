Lane: aicomp

# aicomp1: where AIL stands on AI compute today (measurement only)

Time budget: 180 minutes. Commit and push after each sub-step. Follow `.agent/` rules. No compiler change.

**Why (owner, 2026-11-09):** the top goal is eliminating the world's compute waste, and AI compute is the fastest
growing share of it. The owner wants AIL to be both the language AI writes and a language for AI compute. Before any
design, measure what the existing pieces deliver: typed arrays (`ail_array`, docs/design on integ), the CPU matmul,
the Vulkan GPU path (opt-in, exact by default), and the torch-like API if present. Report losses plainly.

**Workloads** (same algorithm and dtype in every column; float32 and float64 where supported):
1. matmul 256/1024/2048, 2. elementwise chain (a*b+c, relu) on 10M floats, 3. reduction (sum, softmax over rows),
4. a 2-layer MLP forward pass (batch 64, 784-512-10) with fixed weights, 5. a tiny transformer-block forward pass
(one attention head, seq 128, dim 64) if the AIL API can express it; otherwise record exactly what is missing.

**Columns:** AIL (CPU typed path; GPU via Vulkan if a device exists, else say "no GPU on runner"), NumPy (note its
BLAS), PyTorch CPU, plain C (naive loops, gcc -O2), and pure CPython for 1-3 at the smallest size only.
Check outputs: exact match where the design promises it, else max relative error, stated per row.

**Numbers** (`lab/aicomp/RESULTS.md`, `results.json`): median wall of 5, CPU seconds, peak RSS, multiple of the best
column, and for AIL what could not be written. End with a 5-line verdict: the 3 largest gaps and what each would
take (estimate, labelled as an estimate).

Files: `lab/aicomp/*` only.
**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with a `Co-Authored-By:` line naming the model you actually are (Claude: `Claude Opus 5.5 <noreply@anthropic.com>` or `Claude Sonnet 5.5 <noreply@anthropic.com>`; other models: omit the line).
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
