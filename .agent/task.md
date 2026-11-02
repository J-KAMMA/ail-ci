Lane: frontend

# rel-diag: beginner mistakes get `file:line:col:` and a hint, never a raw C compiler error

**Release blocker 6.** Three of the most common beginner mistakes are reported without a location and with
wording that blames AIL ("not in the subset") for the user's own bug, and a method without `self` leaks a gcc
error from the generated C.

**Number this changes:** of the 5 probes A-E below, 0 print a `file:line:col:` prefix today (and D exits 4 with
a gcc error); after this task 5/5 carry `NAME.py:LINE:COL:` with the right line, probe D exits 3 with a named
message, and probe B ends with `did you mean 'greet'?`. Exit codes of A, B, C, E stay as they are (3, 3, 3, 2);
control F keeps its location.

## Standing rules (inlined)

1. No regressions: a program that built and matched CPython before must still do so; do not turn any
   currently-built program into a refusal.
2. Check every probe on the default build and with `AIL_UNIFIED_FORCE=1`.
3. Push early, PR against `integ`, wait for all 20 `shard` checks (poll at most every 10 minutes).
4. Branch from `origin/integ`. Never merge, change settings or cancel runs.
5. New test module: add `AIL_CURRENT/tests.d/<module>.txt`, then `python3 tools/update_manifest.py`, `--check`.
6. `ulimit -v 1500000` for heavy local runs; `par_check -j 2` at most.

## Evidence (installed `ail run`, integ 4928269c, 2026-11-02)

| probe | source | AIL stderr today | rc | CPython |
|---|---|---|---|---|
| A | `x = 1` / `print(y)` | `not in the subset: name 'y' is not defined` | 3 | `NameError: name 'y' is not defined` (line 2) |
| B | `def greet(n: str) -> None:` / `    print(n)` / blank / `greet2('a')` | `not in the subset: the name 'greet2' is not a known function/class/builtin` | 3 | `NameError: name 'greet2' is not defined. Did you mean: 'greet'?` (line 4) |
| C | `def add(a: int, b: int) -> int:` / `    return a + b` / blank / `print(add(1))` | `not in the subset: add() called without a required argument b` | 3 | `TypeError: add() missing 1 required positional argument: 'b'` (line 4) |
| D | `class C:` / `    def hi() -> None:` / `        print('hi')` / blank / `C().hi()` | `the C compiler rejected this (general path):` / `/tmp/ailc-*/program.c:11999:10: error: too many arguments to function 'pm_C_hi'` | 4 | `TypeError: C.hi() takes 0 positional arguments but 1 was given` (line 5) |
| E | `def f() -> None:` / `print(1)` / blank / `f()` | `AIL source /tmp/.../e04.py: expected an indented block after function definition on line 1 (e04.py, line 2)` | 2 | `IndentationError: expected an indented block after function definition on line 1` |
| F (control) | `xs: list[int] = [1, 2]` / `def main() -> None:` / `    print(cnt)` / blank / `main()` | `pF.py:3:5: not in the subset: 'cnt' is read before it is assigned (the general path could not build this program either); general path: name 'cnt' is not defined` | 3 | `NameError` at line 3 |

F already has the location (the undefined name is inside a function); A is the same mistake at module level
and loses it. F must keep its location; improving its wording ("never assigned" rather than "read before it
is assigned") is optional.

Good examples to copy the format from (these already work):
```
e03.py:1:16: expected ':'
e20.py:1:1: import of 'numpy' is not available: it is not part of the standard library ...
  write instead: drop the import and write what you need by hand with plain lists, dicts and loops
```

## Where

- Raise sites without a location, `AIL_CURRENT/python/pkg-v12/pyboxed2.py` (the general path):
  `raise Unsupported("name '%s' is not defined" % node.id)` (about lines 5765 and 5806),
  `raise Unsupported('%s() called without a required argument %s' ...)` (about line 7393),
  `raise Unsupported("the name '%s' is not a known function/class/builtin" % name)` (about line 8168).
  The same argument message also exists in `pyboxed.py` (about line 1919).
- How a location is attached elsewhere: `error.source_line = node.lineno; error.source_column =
  node.col_offset` (many places in `AIL_CURRENT/ail_chatgpt.py`, e.g. around lines 335 and 1370). Find where
  the driver turns `source_line` into the `path:line:col:` prefix and make these errors carry it.
- Probe D: the general path emits methods as `pm_<Class>_<method>` (`pyboxed2.py` about line 4190). Before
  emitting a method call, compare the number of arguments passed (including the bound `self`) with the method's
  parameters; on a mismatch raise `Unsupported` with the location and CPython's wording
  (`C.hi() takes 0 positional arguments but 1 was given`). Also check the typed path refuses it the same way.
- Probe E: the message is built from Python's `SyntaxError`/`IndentationError` (`.lineno`, `.offset`); the
  `AIL source <path>: ` prefix is added in `AIL_CURRENT/ail_chatgpt.py` (search `'AIL source '`, about line
  5732). Format it as `NAME.py:LINE:COL: <msg>` like probe `e03` does.

## Changes

1. A, C, F: attach the node's line and column at the four raise sites (or once, in the general path's statement
   visitor, for any `Unsupported` that has no `source_line` yet: that also covers other messages).
2. B: when the unknown name has a close match among the module's functions, classes, globals and builtins
   (`difflib.get_close_matches(name, candidates, n=1, cutoff=0.8)`), append `; did you mean 'greet'?`.
3. D: the arity check above.
4. E: the `file:line:col:` format.
5. Optional, only with time left: `ail build --strict` prints a truncated line
   `   construct:     print() given a dict[str` for `counts: dict[str, int] = {...}; print(counts)`; the value
   is cut at the first comma somewhere before `AIL_CURRENT/ail_chatgpt.py` line ~5578 prints
   `blocker['construct']`. Make it the whole construct text.

Keep the words "not in the subset" (other tools grep for them); only add the location and the hint.

## Tests

New module `AIL_CURRENT/test_ail_beginner_errors.py` (+ `tests.d/test_ail_beginner_errors.txt`): write each
probe to a temp file `pN.py`, compile with `AIL_CURRENT/ail_chatgpt.py compile pN.py -o pN`, assert the exit
code (A, B, C, D, F: 3; E: 2), that stderr's first line starts with `pN.py:LINE:` with the CPython line, and
for B that it contains `did you mean 'greet'?`. Run the same with `AIL_UNIFIED_FORCE=1`. Add one control: a
correct program using a method with `self` still builds and prints what CPython prints.
Existing modules that assert these messages: `grep -rln "is not defined\|not a known function\|called without
a required argument" AIL_CURRENT/test_*.py`; adapt an assertion only where it compares the whole line.

## Gate

- `python3 tools/par_check.py -j 2 test_ail_beginner_errors test_ail_refusal_messages test_ail_refusal_hints
  test_ail_strict test_ail_fallback_note test_ail_python_syntax test_ail_quickstart_docs test_ail_tutorial
  test_ail_lsp test_ail_dunders test_ail_virtual_dispatch` all pass.
- Generated C of the ten `lab/compare/src/*/main.ail` byte-identical to integ (messages only; no codegen change).
- `python3 tools/update_manifest.py --check`; PR against `integ`, all 20 shards green.

## Commit and push

Commit and push after each sub-step: (a) the test module with failing probes marked `expectedFailure`,
(b) change 1, (c) change 2, (d) change 3, (e) change 4, (f) change 5 if done, (g) manifest. Open the PR after (a).

## Stop rule

Stop and report if: any currently-built program becomes a refusal; any lab/compare C changes; probe D needs
more than one arity check site; more than 15 existing assertions need new text; or 80 minutes pass (finish the
current sub-step, push, report what is left).

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
