Lane: codegen

**Finish relrterr from its existing work. Do not redo it.** The first run (branch `job-relrterr-11030727`) finished the implementation. Its review then timed out, so it got no verdict. Start by cherry-picking that branch's work commit ("job relrterr: name uncaught runtime errors and report their source line"):

```
git fetch origin job-relrterr-11030727
git log --oneline origin/job-relrterr-11030727
git cherry-pick <that commit>
```

Then verify it against the original task below.

**Owner decision (2026-11-02): the default build carries the exception name and the source line number in runtime errors.** The first run measured the binary growth at +4,336 to +20,632 bytes across the 10 compare tasks. That is expected, because of the per-statement site string.
- Check whether the site strings can be shared or deduplicated, for example one string per source line rather than per statement, or a line-number table. Do it only if it is simple and changes no output.
- Report the instruction count before and after on the 10 compare tasks. Use tools/icount.c, or report that it cannot run.
- Known, out of scope: `AIL_UNIFIED_FORCE=1` recursion segfaults (an existing bug). Leave its test skipped, with a comment.

Updating test expectations for the new message text is allowed for exactly this change. List each one.

Time budget: 80 minutes.


# rel-rterr: uncaught runtime errors name the Python exception, like CPython's last traceback line

**Release blocker 5.** A beginner's typed program that indexes past the end prints `list index out of range`
with no exception name and no line. CPython prints `IndexError: list index out of range`. User `raise`
statements already print `ValueError: bad n`; the runtime's own traps do not.

**Number this changes:** of the five probes below, the stderr last line starts with CPython's exception name
in 0/5 cases today; after this task 5/5. Instruction counts of the ten `lab/compare` tasks unchanged (failure
path only); each binary grows by at most 512 bytes.

## Standing rules (inlined)

1. No regressions: every program that built and matched CPython before must still do so (stdout and exit code).
2. Probe in the default build AND with `AIL_UNIFIED_FORCE=1`.
3. Push early, PR against `integ`, wait for all 20 `shard` checks (poll at most every 10 minutes).
4. Branch from `origin/integ`. Never merge, change settings or cancel runs.
5. New test module: add `AIL_CURRENT/tests.d/<module>.txt`, then `python3 tools/update_manifest.py` and
   `--check`.
6. `ulimit -v 1500000` for heavy local runs; `par_check -j 2` at most.

## Evidence (installed `ail`, integ 4928269c, 2026-11-02)

```
oob.py:  def main(): xs: list[int] = [1, 2, 3]; i: int = 5; print(xs[i])
$ ail run oob.py           -> stderr "list index out of range", exit 1
ke.py:   d: dict[str, int] = {"a": 1}; k: str = "b"; print(d[k])   (inside def main)
$ ail run ke.py            -> stderr "key error", exit 1                  CPython: KeyError: 'b'
dz.py:   n = 0; print(10 // n)
$ ail run dz.py            -> "integer division by zero"                  CPython: ZeroDivisionError: integer division or modulo by zero
rec.py:  def f(n: int) -> int: return f(n + 1);  print(f(0))
$ ail run rec.py           -> "recursion depth exceeded"                  CPython: RecursionError: maximum recursion depth exceeded
pop.py:  xs: list[int] = []; print(xs.pop())   (inside def main)
$ ail run pop.py           -> "pop from empty list"                       CPython: IndexError: pop from empty list
rv.py:   raise ValueError("bad n")
$ ail run rv.py            -> "ValueError: bad n"   (already right; keep)
$ ail build --debug oob.py -o oobd && ./oobd
list index out of range
  raised near /tmp/.../oob.py:4                                             (--debug already adds the line)

With AIL_UNIFIED_FORCE=1 the unified runtime already prints the names:
$ AIL_UNIFIED_FORCE=1 ail run oob.py   -> "IndexError: list index out of range"
$ AIL_UNIFIED_FORCE=1 ail run ke.py    -> "KeyError: 'b'"
$ AIL_UNIFIED_FORCE=1 ail run dz.py    -> "ZeroDivisionError: integer division or modulo by zero"
$ AIL_UNIFIED_FORCE=1 ail run rec.py   -> no message, exit 139 (segfault; separate bug, do NOT fix here:
                                          leave the unified recursion probe out of the test, mention it in the PR)
```
So only the default (typed) runtime needs the change; the unified output is the target text.

## Where

`AIL_CURRENT/python/pkg-v12/cruntime.py` (the C runtime is Python string text):
- `static int ail_exc_kind_of(const char *w)` (about line 538) already maps these messages to
  `AIL_EXC_VALUE / _ZERODIV / _INDEX / _KEY / _RUNTIME / _UNICODE_DECODE`.
- `static void ail_die(const char *w)` (about line 563) prints the uncaught trap:
  `fflush(stdout); fputs(w, stderr); AIL_DBG_UNCAUGHT(); fputc(10, stderr); _Exit(1);`
- A second runtime (the general/object path) has `ail_die` / `ail_die_bare` near line 11056; its `ail_die`
  prints `AIL internal error: ` + w. Look at which one the probes hit before touching it.
- Careful: `_PARALLEL_DIE_EDITS` (about line 30160) and similar tuples patch the runtime text by exact string
  match (`'static void ail_die(const char *w) {\n'`). Do not change the lines they match; insert new code after
  them.

## Changes

1. Add `static const char *ail_exc_pyname(const char *w)` next to `ail_exc_kind_of`: returns "IndexError",
   "KeyError", "ZeroDivisionError", "ValueError", "RuntimeError", "UnicodeDecodeError" by
   `ail_exc_kind_of(w)`, plus "RecursionError" for "recursion depth exceeded" and "MemoryError" for "out of
   memory"; NULL otherwise (and NULL when `w` already starts with an exception name followed by `: `).
2. In the uncaught path of `ail_die`, print `name: ` before `w` when the name is not NULL. Nothing else
   changes: same exit status (1), same stdout flush, `--debug`'s "raised near" line unchanged.
3. Only if 1-2 are green and time is left: in a build without `--debug`, append one line
   `  (build with --debug to see the line)` after the message. Skip this step if more than 10 existing test
   assertions would need new text; say so in the PR body (the owner decides whether the default build should
   carry line numbers).

## Tests

New module `AIL_CURRENT/test_ail_runtime_error_names.py` (+ `tests.d/test_ail_runtime_error_names.txt`): the
five probes above plus `rv.py`; for each, build with the default build and with `AIL_UNIFIED_FORCE=1` (except
the recursion probe under unified, see above), assert
exit code 1, stdout equal to CPython's, and that the last stderr line (ignoring a `  raised near` line) equals
CPython's last stderr line for IndexError / ZeroDivisionError / RecursionError / pop, and starts with `KeyError`
for the dict probe (CPython also prints the key; AIL need not). Also one `try: ... except IndexError:` probe to
prove catching is unchanged.

Existing tests that compare stderr to the bare old text: `grep -rn '"key error"\|list index out of range\|
integer division by zero\|recursion depth exceeded' AIL_CURRENT/test_*.py`. Update an assertion only when it
checks the uncaught stderr text; count them in the PR body.

## Gate

- `python3 tools/par_check.py -j 2 test_ail_runtime_error_names test_ail_exception_context
  test_ail_exception_values_core test_ail_overflow_error test_ail_finally test_ail_reraise test_ail_parallel_for
  test_ail_debug test_ail_debug_lines test_ail_fuzz_findings` all pass.
- `python3 tools/codegen_diff.py --pins`: the only diff is the ail_die change; then update pins with
  `python3 tools/fix_codegen_pins.py` if they hash the runtime.
- Instruction count of each `lab/compare/src/*/main.ail` perf input unchanged (`tools/icount.c`), binary size
  growth <= 512 bytes; put the 10 before/after sizes in the PR body.
- `python3 tools/update_manifest.py --check`; PR against `integ`, all 20 shards green.

## Commit and push

Commit and push after each sub-step: (a) test module (failing probes marked `expectedFailure`), (b) changes 1-2
with updated assertions, (c) pins and manifest, (d) change 3 if done. Open the PR after (a).

## Stop rule

Stop and report if: any change would alter stdout or exit status of any program; the parallel-die patch tuples
stop matching; more than 25 existing assertions need new text; instruction counts move on any lab/compare task;
or 80 minutes pass.

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
