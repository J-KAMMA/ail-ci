**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
All probes and tests are in. Here is what I found.

**What the diff really does:** adds `AIL_CURRENT/stdlib/linecache.py` (CPython's `getline`/`getlines`/`checkcache`/`updatecache`/`clearcache` over `cache`, with freshness by re-reading the file and comparing it to a private `_snapshots` copy), ten lab programs + `RESULTS.md`, `test_ail_std_linecache` (+ `tests.d` entry) and the three manifest pins. No compiler or runtime file is touched; `program.c` for a program that does not import `linecache` is byte-identical to `/tmp/base` (verified on `pG_plain.py`).

**Defects (all caused by this change; `/tmp/base` simply refuses these programs, and commit `4af33bd` shows the first one was correct before the fix commit):**

1. `checkcache` keeps a stale entry when the file exists but can no longer be **decoded**. This is a regression introduced by `42daf72`: probe `pC_badutf8.py` matches CPython on `4af33bd`, diverges on HEAD. `_read_lines` returns `None` for a `UnicodeDecodeError` and the new code only drops when `os.path.isfile` is false.
   ```
   import linecache
   open("c.txt","w").write("one\ntwo\n")
   print(repr(linecache.getline("c.txt",1)))
   f=open("c.txt","wb"); f.write(b"\xff\xfe bad bytes here\n"); f.close()
   linecache.checkcache()
   print("kept", "c.txt" in linecache.cache)
   print(repr(linecache.getline("c.txt",1)))
   ```
   expected (`python3`): `'one\n'` / `kept False` / `''` · actual (both builds): `'one\n'` / `kept True` / `'one\n'`. It also contradicts the module docstring's own "a decode error gives the empty result".

2. Entries installed in the public `linecache.cache` dict with `mtime is None` are dropped. CPython's `checkcache` does `if mtime is None: continue` (the real "cache seeded by a loader" idiom); here a missing `_snapshots` key means "drop".
   ```
   open("d.txt","w").write("one\ntwo\n")
   linecache.cache["d.txt"] = (8, None, ["seed\n"], "d.txt")
   print(repr(linecache.getline("d.txt",1)))
   linecache.checkcache()
   print("kept", "d.txt" in linecache.cache); print(repr(linecache.getline("d.txt",1)))
   ```
   expected: `'seed\n'` / `kept True` / `'seed\n'` · actual: `'seed\n'` / `kept False` / `'one\n'`. Fixable with `if mtime is None: continue`. The docstring's claim "`None` inside a tuple is not built" is **false** (`pI_none.py` prints `None True`).

3. An entry *replaced* in `cache` after being filled is kept with its synthetic lines, because the snapshot is keyed by name only and still matches the file. `pE_seed_int.py`: expected `kept False` / `'one\n'`, actual `kept True` / `'synth\n'`. Same root cause as (2).

4. Minor/doc: `cache[fn][0]` is described as "the number of characters read", but it counts the `"\n"` appended to a file without a final newline: `pF_bounds.py` prints `4 6 0` where CPython prints `4 5 <st_mtime>`. (`mtime` differing is documented; the `size` wording is not accurate.)

**Report claims:** fix 1 (unreadable file keeps its entry) — **verified** (`pB_perm.py`, chmod 0, both builds: `kept True`, cached line returned). Fix 2 (caller mutation survives `checkcache`) — **verified** for the mutation path (`pA_mutate.py`: mutation + append, same list, entry length 4; `pJ_mutate_change.py`: mutation + real content change drops and re-reads; `pH_truncate.py`: truncate then `checkcache` drops). "Manifest regenerated, `--check` exits 0" — **verified**. "`test_ail_std_linecache` 2 tests OK" — **verified** (`par_check.py -j 2`: 103.6 s, ok). "`test_ail_safetynet` OK" — **verified** (185.9 s, ok). "`test_ail_files` / `test_ail_corpus_findings3` OK", the six named probe files, and the CI shards — **unverified** (not re-run / not present; report itself says shards were never exercised).

**Speed:** no compiler/runtime change and `program.c` is byte-identical for non-users; 0 of 510 `~/corpus/gdev` programs mention `linecache`, so instruction counts are unchanged by construction (no `icount` run).

**Pre-existing:** `/tmp/base` has no `linecache` module at all, so those programs are refused there; nothing pre-existing blocks.

VERDICT: FIX
1. `checkcache` keeps a stale entry after the cached file is rewritten to non-UTF-8 bytes: `pC_badutf8.py` expected `kept False` / `''`, actual `kept True` / `'one\n'` (regression vs `4af33bd`; contradicts the docstring).
2. `checkcache` drops entries seeded in `linecache.cache` with `mtime is None`: `pD_seed_none.py` expected `kept True` / `'seed\n'`, actual `kept False` / `'one\n'`; add `if mtime is None: continue`, and fix the false "None inside a tuple is not built" docstring claim (`pI_none.py` prints `None True`).
3. An entry replaced in `cache` after being filled keeps its synthetic lines: `pE_seed_int.py` expected `kept False` / `'one\n'`, actual `kept True` / `'synth\n'`.
4. Minor: `cache[fn][0]` counts the appended newline (`pF_bounds.py`: `4 6 0` vs CPython `4 5 <mtime>`), and the docstring calls it "characters read".
[commandcode stop=end_turn turns=23 out_tokens=24751]


--- ORIGINAL TASK ---
Lane: stdlinecache

# linecache1: `import linecache` in compiled programs, shipped as AIL source (`AIL_CURRENT/stdlib/linecache.py`)

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** programs in `lab/stdlib/linecache/` that build in the default mode and print what CPython prints,
with the same exit status. Today it is 0/10: `linecache.getline` is refused with `not in the subset: linecache.getline
(not yet published in NAMES_library.json)` (probe of 2026-11-05). The target is at least 8/10. Tools that print a line of
a file by number (error reporters, `grep -n` style tools) use it.

Base: `origin/integ`. Files you may create or edit, and no others:
- `AIL_CURRENT/stdlib/linecache.py` (new)
- `lab/stdlib/linecache/*.py` (10 new programs), `lab/stdlib/linecache/data/*` (new) and `lab/stdlib/linecache/RESULTS.md`
  (new)
- `AIL_CURRENT/test_ail_std_linecache.py` (new) and `AIL_CURRENT/tests.d/test_ail_std_linecache.txt` (new, one line:
  `test_ail_std_linecache`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit any compiler file: not `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
`ir/*`, `parallel.py`, `typedpar.py`, `ail_chatgpt.py`, `buildcache.py` or `cli.py`.

How it works: a module file in `AIL_CURRENT/stdlib/` is found by `import linecache` (Appendix B). Follow
`AIL_CURRENT/stdlib/getopt.py` and `AIL_CURRENT/test_ail_std_getopt.py` as models.

## Sub-steps

1. **Programs and baseline (15 min).** Write 10 programs in `lab/stdlib/linecache/` and their input files in `data/`. Each
   program finds its data file relative to `__file__` or through a fixed relative path that the test sets up. Cover:
   `getline` of the first, a middle and the last line; a line number of 0, a negative one and one past the end (all return
   `""`); a missing file (returns `""`); `getlines`; `clearcache`; `checkcache` after the file was rewritten by the program
   itself; a file with no final newline (CPython adds `"\n"` to the last line); a UTF-8 file with non-ASCII text.
   Build each with the default command and record the first refusal line in `RESULTS.md` under "Before". Commit, push, and
   open the PR against `integ`.
2. **The module (25 min).** Write `AIL_CURRENT/stdlib/linecache.py` from CPython 3.12's `Lib/linecache.py` (print it with
   `python3 -c "import linecache, inspect; print(inspect.getsource(linecache))"`). Keep `getline`, `getlines`,
   `clearcache`, `checkcache`, `updatecache` and the `cache` dict. CPython uses `os.stat` (not built today) and
   `tokenize.open`. Rewrite only those parts: for example, compare the file's content or size instead of `st_mtime`, and
   open with `encoding="utf-8"`. Write every behaviour difference in the module docstring. Drop `lazycache` and module
   globals loaders, which need a module loader; say so in the docstring. Commit and push.
3. **Make the programs pass (20 min).** Build all 10 again. Fix the module, never the programs, until at least 8 build and
   match. A refusal that needs a compiler file goes into `RESULTS.md` as a follow-up, with the exact text. Commit and push.
4. **Test (15 min).** Write `AIL_CURRENT/test_ail_std_linecache.py`: it builds every passing program and compares stdout
   and the exit status with `python3`, in the default build and with `AIL_UNIFIED_FORCE=1`. It skips when there is no C
   compiler. Register it (Appendix A rule 6) and run it. Fill `RESULTS.md` under "After". Commit, push, and wait for CI.

## Done-check

- `python3 AIL_CURRENT/test_ail_std_linecache.py` passes.
- At least 8 of the 10 programs build and match CPython in both builds.
- `RESULTS.md` has the before/after table.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

Stop and report if a bundled `linecache.py` is not picked up by `import linecache`; give the exact message. Also stop if
fewer than 5 programs can pass without editing a compiler file; name each blocking refusal. Stop on any output that
differs from CPython without a loud stop. Stop when 80 minutes pass. Push what is done first.

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
