Lane: fnvfix

# fnvfix1: make the two pyproof "wrong" programs pass under the int64 default (examples and docs only)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** pyproof (`lab/pyproof/RESULTS.md`) reports `wrong 2`. The target is wrong 0, reached without
changing the compiler.

Both programs stop loudly with `OverflowError` because their values exceed int64. That is the designed default (owner
decision 2026-10-31: int64 by default, overflow stops loudly, big ints only where explicit). So the compiler is right,
and the programs and docs must be fixed:
- `examples/crate/fnvhash/main.py`: a 64-bit FNV hash in plain Python whose intermediate products exceed int64.
- `lab/compare/src/scar_life/main.py`: calls `int("1"*64, 2)`.

Base: `origin/integ`. You may edit only these files: those two programs, their READMEs or tests, `lab/pyproof/run.py` (or
however pyproof chooses build flags), `lab/pyproof/RESULTS.md`, and the docs page that describes `--exact-int`.

## Steps

1. **Find the intended way (15 min).** Read how AIL expresses explicit big or wrapping ints today: the `--exact-int`
   flag, any per-function or per-file marker, and any u64 or wrapping type used by `examples/crate`. Find how compare-lab
   builds scar_life: if it already passes a flag, pyproof must use the same flag for that program, and that is the
   whole fix for scar_life. Record what you found.
2. **Fix (40 min).** For each program, choose one, in this order:
   - (a) pyproof uses the program's declared build flags; read them from the program's README or task config.
   - (b) the program uses the explicit big-int or wrapping facility, keeping its output identical to CPython.
   - (c) a one-line comment at the top of the program, saying which flag it needs and why, and pyproof honours it.
   Never change the program's output, and never weaken pyproof's check.
3. **Verify (25 min).** Rerun pyproof on these two programs, plus the full pyproof run if it fits in the time. The
   result must be wrong 0, with typed, general and refused counts unchanged otherwise. Then run
   `python3 -m compileall -q -j 0 AIL_CURRENT tools`. Update RESULTS.md.

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
