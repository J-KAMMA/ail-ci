# bigint-fix06: other forms of "int operation the local proof cannot bound, but no tagged local" (B, coverage)

Same refusal as fix03 (`ir/driver.py` apply(), "...cannot bound, but no tagged local (<reason>)") but with a different
`<reason>` from `bigcap._lp_reason`. Do fix03 first (call results); this task is the remaining reasons. Each one used to
compile on the typed path and now makes the typed-only build refuse (default build: general path).

## Forms (reason in brackets)
1. `Counter[str]` / `defaultdict(int)` item update `d[k] += n` [reported as "call result not proven"]
2. a module-level int variable used in an expression at module level: `x = 0` then `print(1 // x)` [an operand not proven int]
3. an int formatted in a method such as `__str__`: `"%d.%02d" % (self.c // 100, self.c % 100)` [an operand not proven int]
4. `int(<float>)` and `int(<bool field>)`, `t.n = int(3.7)`, `int(t.todo)`, `t.done + 1` with bool fields [a call of int()]
5. the INT64_MIN idiom `-9223372036854775807 - 1` (constant folding is exact in CPython; the proof calls it beyond int64)
   [an int operation beyond int64]; the merge-only test_ail_fuzz74 builds a list of int edge values with it.

## Modules
test_ail_collections (annotated, ctr_alias, reprs), test_ail_boolfield (field_literal), test_ail_dunders (Money____str__),
test_ail_exc_str (t_intfloat), test_ail_stdlib_batch1 (main), test_ail_typed_blockers (1 test), test_ail_ir_s3c3
(escape/pop_empty, with fix03), and the merge-tree-only modules test_ail_fuzz74 (item 5), test_ail_debug_flush
(mixed_div, typed_big: a module-level `x = 0; print(1 // x)` gives the general-path message "integer division or modulo
by zero" instead of the typed "raised near" site line; item 2) and test_ail_debug_lines (same). The merge-only modules run
only in /home/bluec/code/ail-wt/bigint-merge (Ubuntu-24.04); the reproducers below show each cause on `bigint` itself.

## Reproducers (`AIL_NO_GENERAL=1`)
k1.py: `from collections import Counter` / `def main() -> int:` / `a: Counter[str] = Counter()` / `a["x"] += 1` / `print(a["x"])` / `return 0` / `main()`
 CPython `1`; AIL refuses main(). `defaultdict(int)` with `b["y"] += 2` the same. (deque.append / d[0] is fine.)
op1.py: `x = 0` newline `print(1 // x)`: CPython raises ZeroDivisionError; AIL refuses `main()` (module code).
op3.py:
```
class Money:
    def __init__(self, c: int):
        self.c = c
    def __str__(self) -> str:
        return "%d.%02d" % (self.c // 100, self.c % 100)
def main():
    print(Money(12345))
main()
```
CPython `123.45`; AIL refuses `Money____str__()`.
e3.py: `t.n = int(3.7)` in a method-less class with an int field: CPython `3`; AIL refuses `main()` (a call of int()).
e2.py: `x = -9223372036854775807 - 1` / `print(x)`: CPython `-9223372036854775808`; AIL refuses.
(`int(f)` of a plain float local, `x == 9007199254740992.0` comparisons already work.)

## Category
B. Fix the compiler (give these ints tagged locals / exact folding), keep the tests.

## Fixed means
Each reproducer compiles with `AIL_NO_GENERAL=1` and prints the CPython output (op1: the ZeroDivisionError trap with
the same message and exit status as the typed path printed before bigint: `integer division by zero` + `raised near` line under --debug).
The listed modules no longer show the refusal.

run the listed modules and test_ail_bigint test_ail_tint test_ail_unified before committing.
(For the merge-only modules: re-run them in the merge tree after the integrator merges.)

**Rules for every job.**
- **Load:** you are one of up to five agents on a 16 GB PC. Keep local parallelism at 2 (`-j 2`) and never run the whole suite; the full suite runs on CI after merge.
- **Commits:** commit with explicit `git add` on your branch. Messages end with `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Forbidden:** push, stash, rebase, reset, and deletion outside /tmp.
- **Records:**
  - New DIFFERENCES rows use placeholder ids `C?-<your branch>-N`.
  - Add a DEVLOG entry at the top with today's date.
  - Run `python3 tools/update_manifest.py`, then `--check`.
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
