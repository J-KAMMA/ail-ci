**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
**What the change does:** adds `tools/repro_check.py` (builds each corpus program twice in short/long paths with different TMPDIR/HOME/epoch and compares `program.c` + executable sha256), a results document `lab/repro/RESULTS.md`, and a 5-program ratchet test. No compiler file is touched (`git diff work..HEAD -- AIL_CURRENT` = test module + manifest pins only), so instruction counts cannot move.

**Tests (HEAD 1aaf886):** `test_ail_repro` OK 17.3 s, `test_ail_safetynet` OK 179.6 s, `update_manifest.py --check` rc 0.

**Probes**
| probe | result |
|---|---|
| `/tmp/rprobes/p_basic.py` (no `__file__`), `--debug-dir` HEAD vs base worktree | `program.c` sha256 identical; cmp.sh CPython/g/d 0, same stdout |
| `/tmp/rprobes/p_file.py` (`__file__`, dirname, basename) | CPython/g/d 0, same stdout (HEAD and base) |
| `/tmp/rprobes/p_slice.py` (slice a bytearray then mutate) | CPython/g/d 0, same stdout |
| `repro_check.py -j 1 --filter linecache` | 9 DIFF `absolute path` (line 27672/28533), 08 identical — matches the report |
| `repro_check.py -j 1 --filter examples/ffi/libc_text.py` (also libm_math, sqlite_count, zlib_check, ffi_quick/step1_sqrt) | **DIFF with `C differs: 0, only executable differs: 1`**, `.symtab` at +2164/+1468/+2520/+1828/+798 |

**Verified claims:** 9 linecache diffs with the named cause; 12 corpus programs read `__file__`; cited lines (`ail_modules.py` `dunder_node`, `ail_chatgpt.py:6035/6425`) exist; no compiler file in the diff; manifest check passes; both test modules pass.

**False claims**
- RESULTS: "only executable differs: 0" and "every program with identical C also has an identical executable … the binary adds no second source of difference". False: five `examples/ffi*` programs have identical `program.c` and different executables (symbols `ffi_put_7a7acd.cold` vs `ffi_put_093756.cold`; `readelf -sW` differs throughout). Cause: `AIL_CURRENT/ail_ffi_lower.py:519` puts `sha1(str(absolute path))[:6]` into FFI symbol names. This is exactly the class the task asked to explain, and it is absent from the class table with no follow-up hook.
- Headline "113 measured — 83 identical, 9 different, 21 not built" is not the corpus result: 354/467 remain unmeasured, and the tool's own completed run on this branch (`/tmp/repro_baseline.log`, 467 programs) reports 392 identical, 14 different (9 C, 5 ELF-only), 61 not built. The statement that the first run "stopped after 100" is contradicted by that artifact.
- Test docstring/RESULTS say the ratchet programs are "the ones the document lists as identical"; `heapq/closest_points.py`, `examples/tutorial_project/step1.py` and `examples/algos/rpn.py` are not listed in the measured tables (heapq is not a measured module).

**Pre-existing (compiler unchanged, not caused by this change):** the five FFI executable-only differences; the `tomllib` compile crashes seen under the tool's 1.5 GB/`-j 2` limits (they build fine at `-j 1`, so the tool cannot distinguish a traceback from a named refusal and reports both as "not built").

**Unverified:** the 20 shards (not pushed); instruction counts (not re-measured — no compiler file changed); `test_ail_files`/`test_ail_corpus_findings3` (not re-run, per instructions).

**Defects**
1. `lab/repro/RESULTS.md` reports 0 executable-only differences and states identical C always yields an identical executable. Actual (probe above): 5 such programs, `examples/ffi/libc_text.py` `C differs: 0, only executable differs: 1`, `.symtab` +2164; same for `libm_math.py`, `sqlite_count.py`, `zlib_check.py`, `ffi_quick/step1_sqrt.py`. Expected per the task: each listed with cause and a named hook; actual: missing and explicitly denied (cause is the path hash at `ail_ffi_lower.py:519`).
2. The corpus number the task asks for is not delivered: 113 of 467 measured, while the doc's own completed run shows 467 (392 identical / 14 different / 61 not built), so "82 identical before and after" is not the corpus count and the difference list is incomplete.

VERDICT: FIX
[commandcode stop=end_turn turns=41 out_tokens=39371]


--- ORIGINAL TASK ---
Lane: ff-supply

# ffrepro1: reproducible builds: the same source gives a byte-identical executable across directories and times

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** programs whose executable is byte-identical when built twice: once in `/tmp/a/x` and once in
`/tmp/b/longer/path/x`, with a different `TMPDIR`, a different `HOME`-free environment, and `SOURCE_DATE_EPOCH`
set to two different values. Corpus: the 10 compare-lab `.py` sources, `lab/stdlib/*/*.py` and `examples/`
(about 80 programs). Today unknown. Target: every program identical, or each difference explained in `RESULTS.md`
with the follow-up job that removes it.

Base: `origin/integ`. Files you may create or edit, and no others:
- `tools/repro_check.py` (new: builds each program in both setups, compares sha256 of the executable and of
  `program.c`, and on a difference prints the first differing C line or the ELF section that differs)
- `lab/repro/RESULTS.md` (new), `AIL_CURRENT/test_ail_repro.py` (new: 5 programs), `tests.d` entry
- `AIL_CURRENT/python/pkg-v12/cruntime.py`, `filert.py`, `AIL_CURRENT/ir/emit_c.py`: only to remove a source of
  difference (an absolute path, a temporary name, a set or dict iterated in hash order), with byte-identical C for
  programs that had no difference

Known suspects to check: `__FILE__` and absolute include paths in the C (fix with `-ffile-prefix-map` only if the
flag is set in a file this task may edit; otherwise record the hook needed in `ail_chatgpt.py`), temporary
directory names in symbols, build-id notes, `buildcache.py` timestamps.

## Sub-steps

1. **Checker and baseline (20 min).** Run the whole corpus; classify differences by cause. Commit, push, open the PR.
2. **Fixes (25 min).** Remove the causes that live in files this task may edit. Prove each fix keeps instruction
   counts of the 10 compare-lab tasks identical.
3. **Test (15 min).** `test_ail_repro.py` builds 5 programs twice and compares hashes.

## Done-check

- The count of identical programs before and after is in `RESULTS.md`; every remaining difference has a cause and a
  named hook; the test passes; icount identical on 10/10; the 20 shards pass.

## Stop rule

Stop if a fix changes any program's output or icount. Stop when 60 minutes pass. Push first.

## Appendix A: standing rules (from agent-brief-rules.md)

1. No regressions: a program that built and matched CPython before must still do so in the default build. A loud
   stop is allowed only where the value cannot be computed. Never silent wrong output: stop and report the moment
   any program prints something CPython does not.
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
   `pyc.py`, `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`, unless this task names the file and
   the one minimal hook it may add there (owner decision 3 of 2026-11-06: only when no other running job edits that
   file). Do not edit `DEVLOG.md` either: put your notes in the files this task names. Edit only the files this task
   names, plus the manifest files that `tools/update_manifest.py` writes.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly. Release builds use
  gcc -O2.
- Library policy: a small spec library is written in AIL (`AIL_CURRENT/stdlib/*.py`, found by `ail_modules.py`
  `BUNDLED_DIR`); TLS, signatures and SQLite go through proven native libraries.
- Runtime-backed modules follow `AIL_CURRENT/python/pkg-v12/proclib.py` (stage G8, subprocess): a tree-to-tree pass
  plus a C core header (`ailproc_core.h`), wired by two lines in `filelib.py` (`PRIMS.update(...)` near line 66 and
  `rewrite_tree(...)` near line 152). A program that does not import the module must produce byte-identical C.
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.
- Speed claims: instruction counts with `tools/icount.c`, output unchanged.

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
