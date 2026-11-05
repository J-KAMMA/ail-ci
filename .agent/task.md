**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
```
Review — limits1 (work..HEAD = 8f1e68c, 3aacf23)

What the change does (one line): adds docs/LIMITATIONS.md (15 sections), lab/limits/ (15 probe .py + expected.json), AIL_CURRENT/test_ail_limits.py + tests.d entry and the two manifest shards; no compiler, runtime, or stdlib file is touched.

Diff scope: only the files the task allows (verified with git diff --name-only work..HEAD); update_manifest.py --check rc 0. A plain program's --debug-dir program.c is byte-identical between work and HEAD (sha 7ab3b627…), so programs that don't use the feature get unchanged C.

Probes run (all with --debug-dir/default build; base = /tmp/base2 at work)
All 15 lab/limits probes reproduce expected.json exactly: 01 rc2 literal message, 02 stdout+OverflowError rc1, 03–13 refused with the recorded text, 14/15 general-path note + correct stdout. CPython oracles in expected.json verified.
Additional probes: D_mul (runtime * overflow → same message), Q_stdin_int (int() from stdin → "integer overflow in int()"), S2_round_var (runtime round → "…in round()"), T_floordiv, U_abs, M/N (negative literal and 2**64 refused rc2), F_keys view refused with the analogous message, G_view_return (stale view: CPython [('a',1),('b',2)] vs AIL [('a',1)], exit 0 — matches the page's "Silent differences" repro), H_view_arg (builds, same stdout), A_getcwd (builds — os built list is accurate), C_subprocess/C2, J2/J4/J5/J6, K_pool_map (no note, --strict rc 0), L_cache_deco (accepted), X_rebound_deco (builds on general path), Y_tmp_workaround.

Report claims: entry 2 CPython output verified; entry 9 full "did you mean 'eval'?" line verified; entry 10 stdout empty/stderr usage/exit 2 verified; entry 12 verified; entry 14 (plain Thread → note; map → typed, strict rc 0) verified; k_view_return repro verified; 15 probes as recorded verified; tests verified; manifest verified. Unverified: the 15-probe AIL_UNIFIED_FORCE=1 claim (ran cmp.sh only on J2/G/C), the "20x slower" figures, test_ail_files/test_ail_corpus_findings3 (not re-run, not required of the reviewer), the 20 shards (worker says not run).

Tests on HEAD: par_check.py -j 2 test_ail_limits test_ail_safetynet → 2 modules, 0 failed (16s / 262s).

Defects (page statements that are false — the task asked for accurate "what to do instead"):
1. Entry 15's workaround does not work in the shape the page (and the message) gives. Probe /tmp/rprobes/J2.py:
   import json
   data: dict[str, int] = json.loads('{"a": 1}')
   print(data["a"])
   Expected per page: typed path (no note). Actual: builds on the general path —
   note: p.py:2:1: built on the general path (about 20x slower) because json.loads(s): the type of the result is not declared here; write the type down: `data: dict[str, int] = json.loads(s)` …
   Only an annotation inside a function is honoured (J5_func builds with no note); module-level annotation (J2) and split annotation (J6) fall back. The page's advice as written is wrong at module level.
2. Entry 11 says "`subprocess` is built on the general path". Probe /tmp/rprobes/C_subprocess.py (`r = subprocess.run(["true"]); print(r.returncode)`) builds with no general-path note, and --strict also succeeds; --debug-dir program.c contains the fork/execve implementation (line 7243). Expected per page: general-path note; actual: typed build, no note. The sentence (and its "keep the call where the typed path can leave to the general build" advice) is false.
3. Entry 3 says "This check covers the direct assignment form only" and that views reaching a name are the only gap. The quoted message itself says "name, field, item or container", and probes are refused for those stores: /tmp/rprobes/O_attr_view.py (`b.v = d.items()`) and /tmp/rprobes/P_dict_item_view.py (`m = {"k": d.items()}`) both exit build rc 3 with the same "a dict view kept in a name, field, item or container" line; I_view_item (list container) too. Expected per page: builds on the general path; actual: refused.

Pre-existing: the dict-view stale-snapshot result (G) exists on the base too (compiler untouched); it is disclosed in the page as the stop rule requires, so it does not block acceptance. The entry-15 note wording and the entry-3 scope wording originate in the compiler, but the page repeats/extends them as its own advice.

Not checked: 20 shards, the full 15-probe forced-general run, timings; no hot code is touched, so no icount run.

VERDICT: FIX
1. docs/LIMITATIONS.md entry 15: the advised module-level annotation still builds on the general path. Probe J2.py above: expected no "built on the general path" note; actual note present. Say the annotation must be inside a function (J5_func) or give a working form.
2. docs/LIMITATIONS.md entry 11: "subprocess is built on the general path" is false. Probe C_subprocess.py above: expected the general-path note; actual typed build, no note, --strict rc 0, C contains fork/execve.
3. docs/LIMITATIONS.md entry 3: "This check covers the direct assignment form only" is false. Probes O_attr_view.py (`b.v = d.items()`) and P_dict_item_view.py (`m = {"k": d.items()}`): expected build on the general path; actual build rc 3 with "a dict view kept in a name, field, item or container".
```
[commandcode stop=end_turn turns=34 out_tokens=26933]


--- ORIGINAL TASK ---
Lane: limits

# limits1: `docs/LIMITATIONS.md`, the 0.1 limitations page, every entry backed by a probe that a test re-runs

Time budget: 80 minutes. Commit and push after each sub-step. Follow `C:\Users\bluec\ail-work\agent-brief-rules.md`
(no regressions, CI first, memory cap).

**Number this moves:** limitations listed for 0.1 users, each with a probe program whose behaviour a test checks. Today
there is no limitations page, so a user finds the refusals one by one. The target is 15 entries and 15 probes, all
checked by the test.

Base: `origin/integ`. Files you may create or edit, and no others:
- `docs/LIMITATIONS.md` (new)
- `lab/limits/NN_<name>.py` (15 new probes) and `lab/limits/expected.json` (new)
- `AIL_CURRENT/test_ail_limits.py` (new) and `AIL_CURRENT/tests.d/test_ail_limits.txt` (new, one line: `test_ail_limits`)
- the manifest files that `tools/update_manifest.py` writes

Do not edit `DIFFERENCES.md`, `docs/PORTING.md`, `README.md` or any other existing doc. Link to `docs/PORTING.md` for the
rewrites instead of copying them. Do not edit any compiler file: not `pyfunc.py`, `pyc.py`, `cruntime.py`, `pyboxed2.py`, `unified.py`, `optlib.py`,
`ir/*`, `parallel.py`, `typedpar.py`, `ail_chatgpt.py`, `buildcache.py` or `cli.py`.

## Sub-steps

1. **Pick and probe (30 min).** Read `DIFFERENCES.md` (open entries), the "Blocker buckets" of `lab/stdcensus/RESULTS.md`
   and `docs/PORTING.md`. Pick the 15 limitations a user of small CLI tools meets first. Candidates: int64 by default
   (overflow stops; `--exact-int`), dict views kept in a name are snapshots, `with` around `yield`, non-BMP string
   literals, decorators other than `@staticmethod` and `lru_cache`, multiple inheritance, a module used as a value,
   `argparse` refused, `os.*` functions that are not built, threads only on the general path, `eval`/`exec`, the
   stdlib census (3/197 modules), compile time, `.py` sources that fall back to the general path (about 20x slower).
   For each, write a probe of 3-15 lines in `lab/limits/`, build it in the default mode, and record in `expected.json`
   either the first refusal line (with the file name and line numbers removed) or "builds, prints X, CPython prints Y".
   Commit, push, and open the PR against `integ`.
2. **The page (25 min).** Write `docs/LIMITATIONS.md`: one short section per entry, with what fails, the exact message,
   what to do instead (or "no workaround yet"), and the probe path. Group them under "Language", "Standard library",
   "Speed and build". Commit and push.
3. **Test (20 min).** Write `AIL_CURRENT/test_ail_limits.py`: it builds every probe and checks the recorded text is still
   in the output. When a limitation is lifted, the test fails with "limitation lifted: update docs/LIMITATIONS.md and
   lab/limits/expected.json". It also checks that each section names an existing probe. It skips when there is no C
   compiler. Register it (Appendix A rule 6) and run it. Commit, push, and wait for CI.

## Done-check

- `docs/LIMITATIONS.md` has 15 entries, and `lab/limits/` has 15 probes.
- `python3 AIL_CURRENT/test_ail_limits.py` passes.
- The 20 shards pass.
- `git diff --stat origin/integ` shows only the files listed above.

## Stop rule

If a probe shows output that differs from CPython with no error at all (a silent wrong result), do not list it as a
limitation: record it under "Silent differences found" at the end of the page with its repro, commit, push, and report
it. Stop when 80 minutes pass. Push what is done first.

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
