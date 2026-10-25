# bigint-fix03: "int operation the local proof cannot bound, but no tagged local (a call result not proven to fit int64)" (B, coverage)

`ir/driver.py` apply() (about line 205) raises this refusal for a function whose int result comes from a call the
bound proof cannot size (`bigcap._lp_reason` says "a call result not proven to fit int64") when the function has no
tagged local to hold it. Before `bigint` the same functions compiled on the typed path. Now the typed-only build
refuses and the default build drops the whole program to the general path.

Shapes seen (all return or accumulate an int that comes from a call):
- a user METHOD returning an int: `def read(b: Box) -> int: return b.get()`
- `dict.get(k, default)` with int values: `return d.get(w, 1)` (also module-level `LIM.get(w, 1)`)
- `list.pop()` / `heapq.heappop` returning an int: `return self.items.pop()` in a method, `heappop(h)` in a function
- the same call used as `t += keep(w)` where `keep` itself is the dict.get shape
- time/clock call results (`monotonic_ms()` differences, test_ail_monotonic)

## Modules
test_ail_collections (is_anagram, shares, main), test_ail_sets_general, test_ail_clock, test_ail_exc_str (case1, main),
test_ail_dunders (Stack__pop), test_ail_modconst (keep), test_ail_ir_s3c3 (heappop), test_ail_monotonic,
test_ail_rep5_idioms (bytes_keyed_locals), test_ail_source_check (2 tests: `ail check --syntax python --interface`
reports this refusal for `def read(box:Box)->int: return box.get()`), test_ail_stdlib_batch4, test_ail_typed_blockers,
test_ail_spec_fixes (part). Some of these also hit fix02 (int from text); run them after fix02 or tell the two apart by message.

## Reproducers (`AIL_NO_GENERAL=1`; the IR is on by default)
`y2.py`:
```
class B:
    def __init__(self, v: int):
        self.s = v
    def get(self) -> int:
        return self.s
def f(b: B) -> int:
    return b.get()
print(f(B(2)))
```
CPython `2`. AIL: `not in the subset: f() has an int operation the local proof cannot bound, but no tagged local (a call result not proven to fit int64)`.

`b8.py`:
```
def keep(d: dict[str, int], w: str) -> int:
    return d.get(w, 1)
def main() -> None:
    d: dict[str, int] = {"x": 3}
    print(keep(d, "x"))
main()
```
CPython `3`. AIL: same refusal in keep().

`me2.py`:
```
class Stack:
    def __init__(self):
        self.items: list[int] = []
    def push(self, v: int) -> None:
        self.items.append(v)
    def pop(self) -> int:
        return self.items.pop()
def main() -> None:
    s = Stack()
    s.push(4)
    print(s.pop())
main()
```
CPython `4`. AIL: refusal in Stack__pop().
Contrast (works): `def g(x:int)->int: return x+1` then `def f(x:int)->int: return g(x)`, and `return b.s` (a field).

## Category
B. Fix: when the proof cannot bound a call result, give the function a tagged local for it (the tagged-int lowering
already exists for locals) instead of raising; or treat these library/method call results as tagged-returning. Do not
fall back to int64 without a check.

## Fixed means
The three reproducers compile with `AIL_NO_GENERAL=1` and print what CPython prints, including a value above 2**63
stored in the dict/list/field (the result must be exact, not an overflow stop). The listed modules no longer show
this message.

run the listed modules and test_ail_bigint test_ail_tint test_ail_unified before committing.

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
