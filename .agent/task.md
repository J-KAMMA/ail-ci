Lane: hardening

# hard1: binary hardening of AIL executables (PIE, NX, RELRO, stack protector, FORTIFY) against C and Rust (measurement only)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** hardening properties of AIL binaries, measured, out of 6, in `lab/hardening/RESULTS.md`. The 0.1
claim "safe binaries" covers bounds and overflow stops (other jobs), but nobody has checked what the linker and gcc flags
give an AIL executable. Today the number is unknown. The target is a table for 5 AIL programs, the same 5 written in C
and built with gcc's defaults, and Rust where `rustc` is installed, plus a priced proposal.

Base: `origin/integ`. Files you may create or edit, and no others:
- `tools/hardening_check.py` (new), `lab/hardening/*.py` and `lab/hardening/*.c` (new), `lab/hardening/RESULTS.md` (new)
- `AIL_CURRENT/test_ail_hardening.py` (new) and `AIL_CURRENT/tests.d/test_ail_hardening.txt` (new, one line:
  `test_ail_hardening`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit any compiler file: not `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
`ir/*`, `parallel.py`, `typedpar.py`, `ail_chatgpt.py`, `buildcache.py` or `cli.py`. Do not change any build flag the compiler uses; this job only measures.

## Sub-steps

1. **The checker (20 min).** Write `tools/hardening_check.py BINARY...`. It uses `readelf` only (no `checksec`
   download) and prints one JSON line per binary with six properties:
   - `pie`: ELF type `DYN` and `PIE` in `DT_FLAGS_1`;
   - `nx`: the `GNU_STACK` segment is not executable;
   - `relro`: `full` (a `GNU_RELRO` segment and `BIND_NOW`), `partial` or `none`;
   - `canary`: the dynamic symbol `__stack_chk_fail` is present;
   - `fortify`: the number of `__*_chk` symbols;
   - `stripped`: no `.symtab` section; plus the file size in bytes.
   Check it on `/bin/ls`. Commit, push, and open the PR against `integ`.
2. **Measure (25 min).** Write 5 small programs in `lab/hardening/` (a CSV sum, a word count, a recursive tree, a string
   builder, a `dict` counter), each as `.py` and as the same algorithm in `.c`. Build the `.py` files with AIL (default
   mode, and `--strict` where it builds) and the `.c` files with `gcc -O2`. Build `lab/compare/src/*/main.rs` with the
   flags in `lab/compare/run_task.py` if `rustc` is on the runner, else write `n/a`. Run the checker on all of them and
   write `RESULTS.md`: one row per binary, one column per property, and the gcc and readelf versions. Commit and push.
3. **Price a proposal (20 min).** For 2 of the AIL programs, rebuild the generated C (`--debug-dir DIR`, then
   `DIR/program.c`) by hand with the flags AIL uses plus `-fstack-protector-strong -D_FORTIFY_SOURCE=2
   -Wl,-z,relro,-z,now`. Copy the exact gcc command line AIL used from its verbose output or the build code; do not
   edit it. Record for each: the properties, the stripped size in bytes and the instruction count with `tools/icount.c`,
   before and after, and whether the output is unchanged. Write it under "Proposal" in `RESULTS.md`. Do not change the
   compiler. Commit and push.
4. **Test (10 min).** Write `AIL_CURRENT/test_ail_hardening.py`: it builds one AIL program and asserts only the
   properties that are true today (for example `nx`), so a later change cannot lose them silently. It skips when there is
   no C compiler or no `readelf`. Register it (Appendix A rule 6) and run it. Commit, push, and wait for CI.

## Done-check

- `RESULTS.md` has a row for each of the 5 AIL and 5 C binaries (and Rust or `n/a`), with all six properties.
- The proposal section gives bytes and instruction counts before and after for 2 programs.
- `python3 AIL_CURRENT/test_ail_hardening.py` passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop if `readelf` is missing on the runner; give the exact error. Stop if a hand rebuild changes a program's output;
record it. Stop when 80 minutes pass. Push what is done first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `tools/update_manifest.py --check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, tag, publish, or edit
   `.github/workflows`.
8. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `AIL_CURRENT/python/pkg-v12/pyfunc.py`,
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Other lanes own them. Do not edit
   `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task names, plus the
   manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly.
- Modules in `AIL_CURRENT/stdlib/*.py` are standard modules shipped as AIL source. `AIL_CURRENT/ail_modules.py`
  (`BUNDLED_DIR`, line ~85) searches them after the program's own directory and `AIL_PATH`. Examples:
  `AIL_CURRENT/stdlib/shlex.py` and its test `AIL_CURRENT/test_ail_std_shlex.py`.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.

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
