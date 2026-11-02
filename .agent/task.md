Lane: codegen

# rel-evalorder: a hoisted `xs.count(...)` / `xs.index(...)` must not run before an earlier operand

**Release blocker 2 (silent wrong output).** AIL promises CPython's output or a named refusal. Today, on the
default build, a list `.count()` / `.index()` call is moved in front of its statement and runs before operands
that Python evaluates first. When an earlier operand raises, AIL has already run the call's side effects.

**Number this changes:** the four probes below go from DIFF to SAME on the default build and with
`AIL_UNIFIED_FORCE=1` (0/4 -> 4/4 in each mode); `count_noexc` stays SAME and stays typed
(`ail check` / `compile --strict` exit 0).

## Standing rules (inlined; GitHub runners cannot read the owner's files)

1. No regressions: a program that built and matched CPython before must still do so, on the default build.
   When the fast path cannot handle a case, keep the old route (return the node unchanged).
2. Run every probe in the default build AND with `AIL_UNIFIED_FORCE=1`; compare stdout and exit code with
   CPython 3.12.
3. Push early, open the PR against `integ`, wait for all 20 `shard` checks; report only when they pass, or say
   exactly which fail and why. Poll `gh pr checks` at most once every 10 minutes.
4. Branch from `origin/integ`. Never merge, never change repository settings, never cancel runs.
5. Register a new test module by adding `AIL_CURRENT/tests.d/<module>.txt` (one line, the module name); then
   `python3 tools/update_manifest.py` and `python3 tools/update_manifest.py --check`.
6. Heavy local runs under `ulimit -v 1500000`; `tools/par_check.py -j 2` at most.

## Evidence (reproduced on integ 4928269c, 2026-11-02)

Template (only the line marked `STMT` changes):

```python
def f(a: int) -> int:
    print("side")
    return a


def main() -> None:
    xs: list[int] = [1, 2]
    i: int = 5
    try:
        STMT
    except IndexError:
        print("caught")


main()
```

| probe | STMT | CPython stdout | AIL default stdout |
|---|---|---|---|
| eo_count | `print(xs[i], xs.count(f(2)))` | `caught` | `side` `caught` |
| eo_count_cmp | `print(xs[i] > 3, xs.count(f(2)))` | `caught` | `side` `caught` |
| eo_index | `print(xs[i], xs.index(f(1)))` | `caught` | `side` `caught` |
| eo_assign | `y = (xs[i], xs.count(f(2)))` | `caught` | `side` `caught` |
| count_noexc (control) | `print(xs.count(f(2)), xs[0])` | `side` `1 1` | same (keep it) |

Both exit 0. These already match: `print(xs[i], f(2))`, `print(xs[i], len(g()))`, `print(xs[i] + f(2))`,
`ys = [xs[i], f(2)]`, `print(xs[i], sum(g()))`, `print(f'{xs[i]} {f(1)}')`.

A fifth probe that is also wrong under `AIL_UNIFIED_FORCE=1`:

```python
def f(a: int) -> int:
    print("side")
    return a


def main() -> None:
    xs: list[int] = [1, 2]
    w: int = 1
    try:
        print(1, xs[4611686018427387904 * w] > 3, xs.count(f(2)))
    except IndexError:
        print("caught")


main()
```
CPython: `caught`; AIL default and unified: `side` `caught`. (Reduced from fuzz-lab seed 2075907166:
`python3 lab/fuzz/gen.py 2075907166 -o prog.py`.)

The generated C shows the cause: `int64_t ir2 = f(2LL);` and the whole count loop run before
`ail_ir_list_get(ir12, ir13)` (the `xs[i]` read).

## Where

`AIL_CURRENT/python/pkg-v12/pyfunc.py`, class `_ListLowering`:
- `index_or_count(self, node, prelude)` (about line 35078) builds `$v = __V ...` into `prelude` with no check.
- Its siblings already guard this: `expression()` (about line 34567) keeps `self.evaluated` = the operands of the
  current statement that Python evaluates earlier, `self.eval_start[-1]` marks where the current operand began;
  `heapq_reads_before(...)` and `list_source_changed_before(source, self.evaluated[:start])` use them.

## Changes

1. In `index_or_count`, compute `earlier = self.evaluated[:start]` with
   `start = self.eval_start[-1] if self.eval_start else len(self.evaluated)` (same as the `list()` lowering).
   Add a helper `quiet(node)` that is True only for nodes that cannot raise and have no side effects:
   `ast.Name`, `ast.Constant`, and `ast.Attribute` chains over a Name (no Subscript, no Call, no BinOp).
   Hoist only when either
   - every node in `earlier` is quiet, or
   - the call is `.count` with a quiet argument and a quiet receiver, and
     `not self.list_source_changed_before(receiver, earlier)` (count cannot raise, so only mutation matters).
   Otherwise `return node` unchanged (the old route; it may build on the general path, which is correct).
   `.index` can raise ValueError, so it needs the first condition.
2. Check the other hoisting helpers reached from `expression_inner` (`concat`, the `list(...)` lowering,
   sorted/heapq helpers) with the same template: replace `STMT` by `print(xs[i], <helper call with f(...)
   inside>)`. Fix any that print `side` the same way. If more than two more helpers need it, fix none of them,
   list them in the PR body and stop after step 1.
3. If probe 5 is still wrong under `AIL_UNIFIED_FORCE=1` after step 1, find whether the unified lowering hoists
   on its own; fix it only if the change is local (one function, under 20 lines); otherwise list it in the PR
   body as open.

## Tests

New module `AIL_CURRENT/test_ail_eval_order.py`, registered with `AIL_CURRENT/tests.d/test_ail_eval_order.txt`.
For each probe above (and any found in step 2): build with the default build and with `AIL_UNIFIED_FORCE=1`,
run, and assert stdout and exit code equal CPython's (`sys.executable` on the same file). Assert `count_noexc`
still passes `compile --strict` (typed). Follow the pattern of an existing CPython-comparison module such as
`AIL_CURRENT/test_ail_fuzz_findings.py`.

## Gate

- `python3 tools/par_check.py -j 2 test_ail_eval_order test_ail_list_ops test_ail_local_count_repeat
  test_ail_scalar_list_mutations test_ail_heapq_bisect test_ail_fuzz_findings test_ail_silent5 test_ail_silent6
  test_ail_python_syntax` all pass.
- Generated C of all ten `lab/compare/src/*/main.ail` and `lab/compare/src/*/main.py` byte-identical to integ
  (`python3 AIL_CURRENT/ail_chatgpt.py compile <src> -o /tmp/x --debug-dir <dir>` on both trees, `cmp` the
  `program.c`). If one differs, it must be only because it had this exact pattern; say which in the PR body.
- `python3 tools/update_manifest.py --check`.
- PR against `integ`, all 20 shards green.

## Commit and push

Commit and push after each sub-step: (a) the test module with the probes (expected to fail; mark them
`expectedFailure` until (b)), (b) change 1, (c) change 2 if any, (d) change 3 if any, (e) manifest. Open the PR
after (a).

## Stop rule

Stop and report if: change 1 makes any `lab/compare` C differ for a program without the pattern; more than
two other helpers need the guard; the unified fix is not local; any listed module fails for a reason unrelated
to this change; or 80 minutes pass. Do not add features, do not change refusal messages.

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
