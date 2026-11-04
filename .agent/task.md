**Finish this job: the reviewer judged it FIX.** You work on the job's branch, so your earlier commits are here. Below is the last review, then the original task.

1. Check every defect the review names against the current code. A defect may already be fixed by the last commit: confirm that with the probe the review gives, and do not redo it.
2. Fix every defect that remains. If a feature cannot be made exact, turn it into a named compile-time refusal; never leave a crash or a silent difference.
3. Re-run the probes, the job's own test module and test_ail_safetynet, and run `python3 tools/update_manifest.py`. Commit.

--- LAST REVIEW ---
## review 1
[model commandcode/deepseek-v4.1-flash]
# Review: lsp1b (hover / read-only dirs / message remap)

**What the change does:** in `packaging/ail_lang/lsp.py` it adds full-sync `didChange`, a conservative `type_hover` (signature / annotation / all-literal-one-kind, else null), a read-only fallback that probes the buffer in a `mkdtemp` dir with `path.parent` on `AIL_PATH`, and path/base-name remapping of diagnostic messages; plus tests, docs and DEVLOG. That matches the DEVLOG. The worker's own report is truncated ("Mostly passing; three failures are my probe's own indexing…") and contains no probe list or numbers, so I treated the DEVLOG as the claim set.

**Probes** (`/tmp/rprobes/`, run on HEAD and on `/tmp/base` = `work`):
- `rev_hover.py` (44 direct `type_hover` cases): 5 review names → null; `b"a b".split()`, `range(3)` → null; strings/comments/attribute/keyword-label → null; int/float/str/bytes/bool/None → correct; same-type reassignment → type; mixed/alias/argument/list-item/dict-value/attribute/`for`-target/augassign/tuple-unpack/`-1` → null; annotation and signature correct; global/nonlocal/class/comprehension/lambda scoping correct; UTF-16 positions correct (`raw char` pos → null, `unit` pos → `int`). No wrong type found.
- `rev_server.py` (real server): writable + read-only `didOpen` publish clean messages (`helper.py`, no `.ail-lsp-`), no temp leftovers; read-only new and existing files both publish; `didChange` full and range (including after an astral char) work and leave the file untouched; imported-module diagnostics publish on the import's own URI. `R5` (read-only `module_path` import) fails **identically on base and HEAD** — `ail check -I lib` ignores `-I`, so pre-existing.
- `cmp.sh` on `p_sanity.py`, `p_imports.py`, `p_slice.py`: both builds match CPython, exit 0. `--debug-dir` generated `program.c` identical base vs HEAD (1,171,220 bytes). Diff touches no compiler/runtime file, so no speed impact (icount not applicable).

**Tests on HEAD:** `test_ail_lsp` passed (65.9 s). `test_ail_safetynet` failed `S4_generators_gc` under `-j 2`; standalone that case matches CPython exactly on HEAD **and** on base — a concurrency flake, not caused by the change. `tools/update_manifest.py --check` clean. `test_ail_files`/`test_ail_corpus_findings3` and the 20 shards were not run (Unverified).

**Defect (caused by the change):**
1. **A read-only project loses `strict`, so an Error becomes a Warning.** The fallback hand-checks a probe file in `mkdtemp`, so `project.find(probe.parent)` cannot see the project's `ail.toml`; `found_strict` becomes False. Base checked the on-disk file and found the project.
   Probe (`/tmp/rprobes/rev_server.py` R3): directory at `0555` containing `ail.toml` (`entry = "blocker.py"`, `strict = true`) and, on disk, `blocker.py` = `def find(d: dict[int, int], k: int) -> int | None: …`; `didOpen` of that file.
   Expected (base, and `docs/LSP.md`): severity **1** (Error), message `int | None: only a class type can be None here …`.
   Actual HEAD: severity **2**, `runs on the slow general path because int | None: …`.
   (For a *new* file in a read-only dir this was already broken on base; the regression is the existing-file/`didChange` case.)

**Minor, non-blocking:** `_annotation`'s docstring says "exactly as the source writes it", but it is `ast.unparse`: `x: dict [ int , int ]` hovers as `dict[int, int]`. `-1`, `x, y = 1, 2` and `x = 1 if c else 2` show no type (conservative; the rule arguably expects `int`).

**Pre-existing:** R5 `module_path` import (`ail check` ignores `-I`); `S4_generators_gc` flake under parallel load.

**Unverified:** the 20 shards, `test_ail_files`, `test_ail_corpus_findings3`; the VS Code/Neovim snippets in `docs/LSP.md`.

VERDICT: FIX
1. Read-only directories drop the project's `strict` setting: with `ail.toml` `strict = true` and a typed-path blocker in a `0555` directory, `didOpen` of the on-disk file publishes severity 2 (`runs on the slow general path because int | None…`) where base and the docs give severity 1 (`int | None: only a class type can be None here …`). Cause: `Diagnoser.diagnose` runs `project.find` on the `mkdtemp` probe's parent instead of the opened file's parent.
[commandcode stop=end_turn turns=41 out_tokens=53013]


--- ORIGINAL TASK ---
Lane: lsp

**Finish lsp1b from its existing work; do not redo it.** The run on branch `job-lsp1b-11040505` did the work, then ended ERROR because the pipeline's review step crashed (a bug in the job runner, now fixed; not your work's fault), so it got no verdict.

Start by checking whether `origin/integ` already contains this work: if `git diff origin/integ...origin/job-lsp1b-11040505` adds nothing new, report NOCHANGE and stop.

Otherwise apply that branch's work: cherry-pick, in order, every commit after "export of staging:integ + task" except "agent worker report".

```
git fetch origin job-lsp1b-11040505
git log --oneline origin/job-lsp1b-11040505
```

Commits named "worker: uncommitted edits" or "fix: uncommitted edits" hold unfinished work: read them, then finish the job.

Then verify against the original task below: re-run its measurements and targeted tests, check the boundary cases, fix what is wrong, and report the numbers. Time budget: 60 minutes.

xisting work, and fix the three defects its review found.** The first run (branch
`job-lsp1-11031803`) did the work. Its review returned FIX. The fix run then hit a model usage limit, and no verdict
followed.

Start on a branch from `origin/integ`:

```
git fetch origin job-lsp1-11031803
git cherry-pick 6954063d 2cd724c2
git checkout origin/integ -- AIL_CURRENT/ail_chatgpt.py AIL_CURRENT/python/pkg-v12/pyfunc.py \
    AIL_CURRENT/AIL_REFERENCE_MORE.md AIL_CURRENT/LANGUAGE_QUICKSTART_JA.md
git commit -m "lsp: keep compiler and reference files as on integ"
```

Other lanes edit those four files, so this job must not change them. Removing them also removes `ail check --types`,
which the branch's hover code calls (`compiler_types`, about line 258 of `packaging/ail_lang/lsp.py`;
`_compiler_hover`, about line 608). Delete that code path.

# lsp1b: a correct hover, read-only directories, clean messages

Time budget: 80 minutes. Commit and push after each sub-step.

**Number this moves:** on the review probe below, wrong hover types go from 5 to 0. A read-only project directory
publishes diagnostics (today it publishes nothing). Temp-file names in diagnostic messages go from 1 to 0.

Base: `origin/integ`.

## The review's defects (from `job-lsp1-11031803`, review 0)

1. **Hover reports wrong types.** For the probe below, `ail check` is clean, and CPython prints
   `float bool float float float`. Hover gave `int` for all five names. It also gave `list[str]` for
   `b"a b".split()` and `list[int]` for `range(3)`, showed types for names inside strings and comments, and used the
   last assignment in the scope.
   ```python
   def main() -> None:
       a = 1 / 2
       b = not 1
       c = abs(-3.5)
       d = sum([1.5, 2.5])
       n = round(1.234, 2)
       print(a, b, c, d, n)
   main()
   ```
2. **Read-only directories lose all diagnostics.** With the directory at mode `0555`, a `didOpen` with a syntax-error
   buffer publishes nothing. Cause: `Server.analyse` (about line 730) always calls
   `tempfile.mkstemp(dir=path.parent)` (about line 742).
3. **Buffer diagnostics leak the temp file name.** Opening `helper.py` with a syntax-error buffer gives the message
   `AIL source /tmp/.../.ail-lsp-XXXX.py: invalid syntax (.ail-lsp-XXXX.py, line 2)`. `_remap_problems` (about line
   192) remaps the path field but not the message text.

## Sub-steps

1. **Apply (15 min).** Apply as above, delete the `compiler_types` path, and run `test_ail_lsp`. Commit, push, open
   the PR.
2. **Hover shows a type only when it is certain (20 min).** A wrong type is worse than no type. Hover returns:
   - for a function name: its signature as written (`_signature`);
   - for a parameter or a name with an annotation: the annotation text;
   - for a name where every assignment in its scope is a literal of one type (int, float, str, bytes, bool or None):
     that type;
   - for anything else: `null`. This includes every name in the probe above, `b"a b".split()` and `range(3)`, and
     any position inside a string or a comment.

   Add tests for each rule and for the probe: all five names give `null`. Commit, push.
3. **Read-only directories (20 min).** In `Server.analyse`, if `tempfile.mkstemp(dir=path.parent)` raises `OSError`,
   write the buffer to a file in a new `tempfile.mkdtemp()` instead, and put `path.parent` first on the `AIL_PATH`
   environment variable of the check. `AIL_PATH` is the module search path in `AIL_CURRENT/ail_modules.py` (line 283);
   it mirrors `PYTHONPATH`, so imports still resolve. Remove the temp dir afterwards.
   Add a test with a `0555` directory. Skip it when `os.geteuid() == 0`, because root ignores the mode. Commit, push.
4. **Messages (10 min).** In `_remap_problems`, replace every occurrence of the temp file's full path, and of its base
   name, in the message text with the opened file's path or base name. Add a test with the import case from defect 3.
   Commit, push.
5. **Docs and final run (10 min).** In `docs/LSP.md`, remove any claim of inferred-type hover and state the three
   rules. Run `test_ail_lsp` and `test_ail_safetynet`, then `tools/update_manifest.py --check`. Commit, push.

## Done-check

- `git diff origin/integ --stat` shows only `packaging/ail_lang/lsp.py`, `AIL_CURRENT/test_ail_lsp.py`,
  `docs/LSP.md`, `DEVLOG.md` and manifest files.
- `test_ail_lsp` and `test_ail_safetynet` pass.
- The probe gives 0 wrong hovers.
- All 20 shards pass.

## Stop rule

Stop if any of these happens. Then push what is green and report.

- A fix would need a change to a compiler file (`AIL_CURRENT/*.py` other than the test, or `python/pkg-v12/`).
- Any generated C changes.
- 80 minutes pass.

## Appendix A: standing rules

1. No regressions: a program that built and matched CPython before must still do so in the default build.
2. Probe ints beyond int64 wherever ints come from text or arithmetic; run probes in the default build and with
   `AIL_UNIFIED_FORCE=1`, compare both with `python3`.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most
   once every 10 minutes). Report only when all pass, or say which fail and why.
4. Branch from `integ` (or one unmerged PR at most).
5. Memory: wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py -j 2` at most; leave no background jobs.
6. New test module: `AIL_CURRENT/tests.d/<module>.txt` if the directory exists, else `ail_check.py` MODULES; `git add`,
   `tools/update_manifest.py`, then `--check`.
7. Never print credentials, run a broad pkill, merge PRs, change repository settings, cancel runs, or edit
   `.github/workflows`.

## Appendix B: repository facts

- `ail lsp` lives in `packaging/ail_lang/lsp.py`. On integ, it has the `Diagnoser` class (line 56), `to_lsp`,
  `hover_for` and `Server` (line 204). The branch adds `apply_change`, `type_hover` (about line 642), `_scope_types`,
  `_value_type` and `_signature`.
- Diagnostics come from the same front end as `ail build`: `ail check` (`_source_check` in `ail_chatgpt.py`). Keep
  it that way.
- Tests: `AIL_CURRENT/test_ail_lsp.py` (registered in `AIL_CURRENT/tests.d/`). It runs scripted JSON-RPC sessions.
- To run the server by hand: `PYTHONPATH=$PWD/packaging AIL_SDK_DIR=$PWD/AIL_CURRENT python3 -m ail_lang.cli lsp`.

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
