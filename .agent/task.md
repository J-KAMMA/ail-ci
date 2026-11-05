Lane: codegen

**Owner decisions (2026-11-03):** stripped binary growth up to +1% is allowed only on a task whose instructions drop by at least 1%; on every other task the binary must not grow. The recursion-depth limit keeps its current counting (limit 50,000) and the same firing point; do not change how depth is counted.

# bce s4: whole-program field facts (parallel list groups, non-negative int fields) — producer only

Repository `https://github.com/J-KAMMA/ail-ci`, branch from `origin/integ` **after bce-s1 merged** (needs
`lab/beatc/bce_census.py`, `bce_enabled()`, `test_ail_bce.py`; if missing, stop). Time budget: **80 minutes**.
Commit and push after each sub-step (a)–(d); open the PR after (a). Do not touch `.github/workflows`. Follow
Appendix A.

**Number this moves:** none directly; the generated C of every compare-lab task must stay byte-identical (the
facts are only computed and dumped). s5 and s6 consume them (tally_lang −7.8%, ledger_bin −8% icount measured).

## What to compute

One pass over **every function of the program** before any function is lowered, on the typed Python AST that
`pyfunc` compiles (both `.ail` and `--syntax python` sources arrive there; check that `ail_syntax` lowers `.ail`
to it and say so in the PR). Put it next to the whole-program call graph in `pyfunc.py` `to_c` (where recursive
functions are found), keep the result per program like `ir/driver.py` keeps `SUMMARIES` (identity of
`ctx.funcs`), and hand it to the passes through `ir/driver.py` `facts_for()` as `facts['fields']`.

1. **Parallel groups.** A set G of list fields of one struct type (`p.n_op`, `p.n_a`, `p.n_b`), or of list locals
   of one function, is a group when:
   - every construction gives all members the same length: struct constructor arguments that are all the empty
     literal `[]` (or all `[e] * n` with the same SSA-equal `n`); locals: all initialised to `[]` in the same
     block before any use;
   - every length change of a member is inside a **group block**: a run of consecutive statements, one per
     member, each the same change on the same object (`o.a.append(x); o.b.append(y); …`, or all `.pop()`, or all
     `.clear()`), where the arguments are names or constants (cannot raise, cannot call user code), and nothing
     else is between them;
   - every other use of a member is: index read `o.a[i]`, index store `o.a[i] = v` / `o.a[i] op= v`, `len(o.a)`,
     `for x in o.a`, `x in o.a`, `o.a.sort()`, or a read-only builtin (`sum`, `min`, `max`, `sorted`, `str`). Any
     other use invalidates the whole group: passing the list to a function, binding it to a name, storing it in a
     container or field, returning it, `del`, slice store, `insert`, `extend`, `pop(i)`, `remove`, closure or
     lambda capture, `global`.
   - **grow-only** flag: every group block is an `append` block.
   - The tally struct (Appendix C) must give `{n_op, n_a, n_b}` and `{val, has}` grow-only, and
     `{s_kind, s_line, s_e, s_var, s_a, s_b, s_j}` (index stores into `s_j` are allowed).
2. **Non-negative int fields.** For each struct int field, the union of every stored value (constructor
   argument, `o.f = e`, `o.f += e`, `o.f -= e`) over a fixed point: `o.f += c` with `c >= 0` keeps the bound; a
   stored value from a call uses that function's result range when the pass can bound it from its `return`
   statements (else unknown); any unbounded store makes the field unknown. Report `lo >= 0` fields. ledger's
   `Rd.pos` (constructor `6`, `r.pos += 1`, `r.pos += x` with `x` the result of `readvar`, which only returns
   `0` or a sum of non-negative shifted bytes) must come out `>= 0`; if the result range of `readvar` is beyond
   this step, report it.
3. **Whole program only.** Compute nothing (empty facts) for `--separate`, `--object`, `--module`, library builds
   (`--lib`, `compile-library`, `compile-module`), programs with `@extern` functions taking a struct or list,
   programs that import user modules, and any function compiled on the general/boxed path or the CPython hybrid
   that touches the struct type. Any AST construct the pass does not recognise invalidates the facts it could
   affect. `bce_enabled()` false → empty facts.

## Sub-steps

(a) The pass + `facts['fields']` plumbing (`{'groups': [{'struct': name or None, 'fn': name or None,
    'members': [...], 'grow_only': bool}], 'nonneg': [(struct, field)]}`).
(b) Dump: `AIL_BCE_FACTS=path` writes the facts as JSON at the end of the build.
(c) Unit probes (append to `test_ail_bce.py`; they read the dump, no C change): the tally struct (positive);
    each invalidating use above (one probe each: group must disappear); a raising argument between two appends
    inside a `try` (`o.a.append(1); o.b.append(int(s))` — invalid); two constructions with unequal literals
    (`P([1], [])` — invalid); a local parallel group built in one loop (ledger's `ops/xs/ys/zs` shape) and the same
    with one extra `xs.append` (invalid); non-negative field broken by `r.pos = -1` on one path, by `r.pos -= 1`,
    by `r.pos = int(text)` with a text value beyond int64 (rule 2); the same group written in Python syntax
    (`class P:` with `self.a.append(x); self.b.append(y)` in a method) — positive if that program reaches the
    typed path, otherwise just no crash.
(d) Done check, DEVLOG entry, PR.

## Done check

- `python3 lab/beatc/bce_census.py check --base /tmp/base --out /tmp/check.json`: every task/syntax `same C`,
  exit 0.
- `AIL_BCE_FACTS=/tmp/f.json` builds of tally_lang and ledger_bin show the groups/fields listed above.
- Compile time (`tools/compile_phases.py`, median of 5) of tally_lang, ticket_audit and tree_fold within 3% of
  base (the pass is one AST walk per function plus a small fixed point).
- `tools/par_check.py -j 2 test_ail_bce test_ail_ir_s3 test_ail_modules test_ail_strict`; all 20 shards green.

## Stop rule

Stop and report if: any generated C changes; the pass needs type information that `pyfunc` does not have
before lowering (say which); compile time grows more than 3% on any task; or 80 minutes pass. Do not use the
facts in any pass in this step.

## Appendix A: standing rules (owner-approved 2026-10-30)

1. **No regressions.** A program that built and matched CPython before must still do so after, in the default
   build. A loud stop only where the value cannot be computed. When a fast path cannot handle a case, keep the
   old route.
2. **Big values.** Wherever ints come from text, fields or arithmetic, probe values beyond int64 too. Run every
   probe in the default build AND with `AIL_UNIFIED_FORCE=1` and compare both with CPython.
3. **CI before you report.** Push early, open the PR against `integ` of `J-KAMMA/ail-ci`, wait for all 20
   `shard` checks (`gh pr checks <n> -R J-KAMMA/ail-ci`, at most once every 10 minutes). Report only when all
   pass, or say exactly which fail and why.
4. **Stack at most 2 deep.** Branch from integ or from one unmerged PR, never from a stacked PR.
5. **Memory.** Wrap heavy runs in `ulimit -v 1500000`; `tools/par_check.py` at `-j 2` at most; leave no
   background jobs running.
6. Batch `gh` queries; never poll in a tight loop.
7. **Registration.** New test module: add `AIL_CURRENT/tests.d/<module>.txt` containing the module name, `git
   add` it, run `python3 tools/update_manifest.py`, then `python3 tools/update_manifest.py --check`.
8. **Never** read or print credentials, run a broad `pkill`, merge PRs, change repository settings, cancel runs,
   or edit `.github/workflows`. **No compare-lab number may get worse.**

## Appendix B: measuring on a GitHub runner

`perf_event_open` is denied on runners: `sudo apt-get install -y valgrind`; `lab/beatc/bce_census.py` then uses
callgrind (`--icount auto`). Base tree: `git worktree add /tmp/base origin/integ`.

## Appendix C: the shapes the facts must cover (from `lab/compare/src`)

```
# tally_lang/main.ail
struct Prog { n_op: list[int]; n_a: list[int]; n_b: list[int];
    s_kind: list[int]; s_line: list[int]; s_e: list[int]; s_var: list[int];
    s_a: list[int]; s_b: list[int]; s_j: list[int]; outroots: list[int];
    vars: dict[str, int]; val: list[int]; has: list[bool]; bs: list[int]; }
fn node(p: Prog, op: int, a: int, b: int) -> int {
    p.n_op.append(op); p.n_a.append(a); p.n_b.append(b); return len(p.n_op) - 1; }
...  p.val.append(0); p.has.append(false);                          # line 180-181
...  p.s_kind.append(kind); p.s_line.append(line); p.s_e.append(-1); p.s_var.append(-1);
     p.s_a.append(0); p.s_b.append(0); p.s_j.append(-1);            # line 197-198
...  p.s_j[t] = s4;                                                  # index stores only
let p = Prog([], [], [], [], [], [], [], [], [], [], [], {}, [], [], []);
# ledger_bin/main.ail
struct Rd { data: bytes; pos: int; err: int; }
let r = Rd(data, 6, 0);   r.pos += 1;   if n - r.pos < x { r.err = 1; } else { r.pos += x; }
```

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
