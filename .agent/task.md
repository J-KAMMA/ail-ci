You continue on the current branch, where your earlier work is committed. **Fix only these findings from the last review, nothing else:**

## review 1
## Review findings

**Defect 1 — typed `groupby` look-ahead cache is stale for keys over mutable elements (new regression)**

Probe `/tmp/rprobes/gb_cache_regress_len.py`:

```python
import itertools

def run() -> None:
    rows: list[list[int]] = [[1], [1], [2], [2, 2]]
    for k, grp in itertools.groupby(rows, key=lambda v: len(v)):
        if k == 1:
            rows[3].append(9)
        print(k, len(list(grp)))

run()
```

- CPython, general path and **base default build**: `1 3` / `3 1`
- **HEAD default build** (`--strict` also succeeds, so this is the typed path): `1 3` / `2 1`

`pure_key` calls `len(v)` “pure”, but `v` is a mutable list. The new cache stores the look-ahead key before the loop body mutates `rows[3]`; CPython computes that key while consuming the previous group, after the mutation. The base build’s second key call happened after the mutation and matched. `key=len` regresses identically (`/tmp/rprobes/gb_keylen_regress.py`). The report’s claim that accepted keys “cannot read mutable state” is false.

**Defect 2 — typed `accumulate` initial guard misses one-argument `round()`**

Probe `/tmp/rprobes/acc_round_arg.py`:

```python
import itertools

def f(xs: list[float], y: float) -> None:
    print(list(itertools.accumulate(xs, initial=round(y))))

f([1.5, 2.5], 2.5)
```

- CPython and general path: `[2, 3.5, 6.0]`
- **HEAD default build** (typed, `--strict` succeeds): `[2.0, 3.5, 6.0]`

`_expr_kind` treats `round(x)` as the type of `x` (float), but one-argument `round` returns an `int`. The same-type check therefore accepts and the typed accumulator coerces `2` to `2.0`. This is also wrong in the base, but the new “mismatched initial is refused” fix does not cover it and it is not listed in `DIFFERENCES.md`.

**Other observed (pre-existing, not introduced):** `/tmp/rprobes/gb_keyexc.py` prints `key 2` before `ZeroDivisionError` in CPython but not on either base or HEAD default; typed groupby computes the look-ahead key before yielding the group. Not listed in the report.

## Claim check

- Groupby stale bound-method key now matches (`1 / -5 / -1`): **verified** via `test_ail_fuzz8` and rerun.
- Typed accumulate refuses mismatched initials / general path preserves tags `[False, 1, 3, 6]`, `[0, 1.5, 4.0]`, `[False]`: **partly false** — the listed cases pass, but one-arg `round` escapes the guard (Defect 2).
- Sort key exception leaves the list unchanged: **verified** (`/tmp/rprobes/sort_exc1.py`).
- “14 probes all matching on both builds”: **unverified/false** — two counterexamples above.
- `2**70` overflow: **verified** (both builds exit 1, no silent wrong answer).
- 10/10 tests pass with `-j 2`: **verified** (567 s).
- Manifest `--check` exits 0 and worktree clean: **verified**.
- New DIFFERENCES rows `C?-fuzz8-9/10`: **verified present**.

## Other checks

- No-feature program: generated `program.c` byte-identical to base under `--debug-dir`.
- Speed: `g17_038` 280300 vs 280304 instructions, `g00_022` 225193 vs 225193; no slowdown.

Probe both builds with `bash ~/tools/cmp.sh`, add each fixed case to the tests, then commit. If a finding cannot be fixed safely, refuse the construct by name at compile time instead of leaving a silent wrong answer.

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

**Where you run:** a GitHub Actions runner (4 cores). Commit your work on the current branch; do not push.
