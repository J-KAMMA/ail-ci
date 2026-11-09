# CONTINUATION (2026-11-10): the previous run of this job ended with FINAL VERDICT: ERROR, most likely the
# runner time limit. Your branch already holds the earlier commits: read git log and the DEVLOG first, do NOT
# redo finished sub-steps, finish the remaining ones, commit and push after each. Keep the run under 4 hours;
# if a full measurement cannot fit, cut seeds/sizes and say so in the report.

Lane: fc-reach
Needs: fclist1

# fcdict1: a dict whose values are lists, sets or dicts stays on the typed path, with CPython's sharing of the value object

Time budget: 60 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** pyproof typed count. The bucket "a dict of containers (lists, sets or dicts as values)" is the
only blocker of 3 programs:
- `lab/compare/src/ledger_bin/main.py` (general; `acc[r[1]] = [r[2], r[3], True]`, line 116)
- `lab/compare/src/ticket_audit/main.py` (general; `events[ev] = [vc, cents, set()]`, line 101)
- `lab/pyperf/run.py --help` (refused; `info['wall_cpython'] = [round(...)...]`)

Target: typed +2 (ledger_bin and ticket_audit), and `lab/pyperf/run.py` no longer refused (general or typed).

`pyreachs5` ("dicts of containers and record lists") and `pyreachs6` already worked on these two programs. Start by
finding what they built and why the programs still fall back: read their commits on `integ`
(`git log --oneline origin/integ | grep -E 'pyreachs(5|6)'`) and the `--strict` list of each program.

Base: `origin/integ` after `fclist1` is integrated. Files you may create or edit, and no others:
- `AIL_CURRENT/python/pkg-v12/pyfunc.py` (search `as a dict of containers`), `optlib.py`, `unified.py`
- `lab/reach/fcdict1/*.py` (probes, new) and `lab/reach/fcdict1.md` (new)
- `AIL_CURRENT/test_ail_fcdict1.py` (new) and `AIL_CURRENT/tests.d/test_ail_fcdict1.txt` (new, one line)
- the manifest files that `tools/update_manifest.py` writes

## What CPython does, and what to build

`v = d[k]` binds the same list object that the dict holds, so `v[0] = v[1]` changes `d[k]` too (the reproducer
`lab/pyproof/repro/a-dict-of-containers-lists-sets-or-dicts-as-values.py`). A value list that mixes kinds by
position (`[vc, cents, set()]`, `[r[2], r[3], True]`) is a record: element 0 is always int, element 2 always a set.
Build:
- dict values held as shared references to containers (RC), so a name bound from `d[k]` writes through;
- a fixed-position record kind for value lists whose length and per-position kinds are the same at every store,
  read and write by constant index only (`a[2] = False` keeps position 2 bool);
- `d.setdefault(k, [0, 0, 0])` and `d.get(k)` on such dicts.
Anything else (a value list indexed by a variable while its positions differ in kind, a list that grows) keeps the
fallback. Printing a record value must print CPython's list text (`[3, 450, True]`).

## Sub-steps

1. **Baseline and probes (15 min).** Run `python3 lab/pyproof/report.py -j 2 --only <path>` for the three programs on
   `origin/integ` and record "Before" in `lab/reach/fcdict1.md` with each program's `--strict` blocker list. Drop
   programs already typed; NOCHANGE and stop if none is left. Write at least 12 probes: the reproducer; `v = d[k]`
   then `v.append(...)`; a set value with `.add`; a dict-of-dict counter; `setdefault` with a record; printing a
   record value and the whole dict; `del d[k]` while a name still holds the value; a record whose int position
   receives a value beyond int64 (must stop loudly or match). Commit, push, open the PR.
2. **Build it (30 min).** Implement in `pyfunc.py`, reusing pyreachs5's record-list code where it exists. Run the
   probes in both builds after each change. Commit and push.
3. **Test and numbers (15 min).** `AIL_CURRENT/test_ail_fcdict1.py` builds every probe and the three programs and
   compares with `python3` in both builds. Register it. Rerun the three rows and the programs typed at the base;
   record "After". Check that ledger_bin and ticket_audit still pass every case of `lab/compare/tasks/<task>` with
   the lab's own checker. Commit, push, wait for CI.

## Done-check

- ledger_bin and ticket_audit typed and matching (typed +2), and `lab/pyperf/run.py --help` built and matching.
- No program typed at the base lost; all compare-lab cases of the two tasks match `reference.py`.
- `python3 AIL_CURRENT/test_ail_fcdict1.py` passes; the 20 shards pass; only the files above changed.

## Stop rule

Stop at once, push, and report on any wrong output in either build. Stop if the change needs a file not listed;
name it. Stop when 60 minutes pass. Push what is done first.

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
8. Lane `fc-reach` owns `AIL_CURRENT/python/pkg-v12/pyfunc.py`, `optlib.py` and `unified.py` for this job; edit them
   only as this task says. Never edit `AIL_CURRENT/ail_chatgpt.py`, `AIL_CURRENT/ail_syntax.py`, `pyc.py`,
   `buildcache.py`, `pyboxed2.py`, or `packaging/ail_lang/cli.py`. Do not edit `DEVLOG.md`: put notes in the files this
   task names.

## Appendix B: repository facts

- Build: `python3 -B AIL_CURRENT/ail_chatgpt.py compile SRC -o OUT [--strict] [--debug-dir DIR]`. `DIR/program.c` is
  the generated C. `--strict` means the typed path or a refusal. `-o` must not exist yet. A fallback to the general
  path prints `note: ... built on the general path ...` on stderr.
- AIL is Python syntax plus optional annotations. Ints are int64, and overflow stops loudly; exact ints are explicit.
- pyproof: `python3 lab/pyproof/report.py -j 2 --only PATH` reruns one row; a full run is about 12 minutes at `-j 2`.
  Classification: typed (no fallback note), general, refused, wrong (output differs from CPython 3.12).
- CPython 3.12 is the oracle: compare stdout and the exit status, and stderr where a task says so.

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
