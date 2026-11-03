Lane: pyreach

# pyreach s5: dicts of containers and record lists

Design: `pyreach-design.md` (appendix below) (F3).
Base: `origin/integ` after s4 merged.

**Number this moves:** the strict list of `lab/compare/src/ticket_audit/main.py` keeps only bytes-key blockers
(s6); rail_transfer's `bysrc.setdefault(s, set()).add(d)` blocker is gone; ledger_bin's `acc[r[1]] = [r[2], r[3], True]`
and `a[2] = False` blockers are gone. No task becomes typed by this step alone.

## What to build

A dict whose values are containers, lowered to the slot form the dict-of-lists work (s1, `ail_syntax.py`
`lower_dict_of_lists`) already uses: key -> slot index dict plus one typed list per field/row.

1. **Dict of record lists**: every store is `d[k] = [e0, e1, ..., en]` with the same arity and a fixed kind per
   position (int, float, str, bool; set or list of int as a position too). Lower to parallel field lists indexed by
   slot. `r = d.get(k)` / `r = d[k]` then `r[i] op= v` must change the stored record (shared reference semantics); a
   bool position keeps printing `True`/`False`. `d.values()`/`d.items()` iteration and `for k, (a, b, s) in d.items()`
   unpack in insertion order. `d.get(k)` with one argument followed by `is None` needs Optional: keep the refusal
   until s8 unless the test is `k in d`.
2. **`d.setdefault(k, set()).add(v)` / `d.setdefault(k, [0, 0, 0])` / `d.get(k, [0, 0, 0])`**: slot form with a set or
   list row; `len(d[k])`, `v in d[k]`, iteration over `d[k]`.
3. Sites: `_explain_dict_of_containers` in `pyfunc.py` (about line 35036) is where the refusal is produced; the
   lowering itself belongs beside `lower_dict_of_lists` in `ail_syntax.py`. Any use not listed above leaves the source
   unchanged (old route).

`Counter` is not in this step (term_rank needs F4 and F7 first).

## Tests

New module `AIL_CURRENT/test_ail_pyreach_dictrows.py` + `tests.d` file. Probes vs CPython (default build and
`AIL_UNIFIED_FORCE=1`): record dict with update through a `get` alias and through `d[k][1] += x`; bool field printed;
`sum(a[1] for a in d.values() if a[2])`; `sorted(d.items(), key=lambda kv: (-kv[1][1], kv[0]))`; dict of sets via
`setdefault(..).add`, with duplicates; `setdefault(k, [0,0,0])` counters; balances beyond int64 from input (int64
default: loud OverflowError; `--exact-int`: exact or refused by name, never wrapped); an alias kept after `del d[k]`
(must be refused or match CPython).

## Gate

Design gate; `.ail` C byte-identical; `test_ail_pytyped_reach` and `test_ail_collections` still pass.

## Commit and push

Commit and push after 1 and after 2, each with its probes.

## Stop rule

Stop at 2 hours. If aliasing of a fetched row cannot be made exact, refuse `r = d.get(k)` aliases by name and land
the rest. Never copy a row where CPython shares it.


## Appendix (copied from the design session; the runner cannot read its files)

### pyreach-design.md

````
# Python sources on the typed path: blocker chains, features, order (pyreach)

Date: 2026-11-02. Base: `origin/integ` 4f1245b1. Earlier work: branch `job-rbpyreach1-11021550` (re-apply of the
accepted `pyreach1`, review verdict FIX, its review tail is inlined in the pyreach s1 task); its design note is
`docs/design/PY_TYPED_REACH.md` on that branch.

## Method

Each `lab/compare/src/<task>/main.py` was built with
`python3 -B AIL_CURRENT/ail_chatgpt.py compile <src> --strict --syntax python [--exact-int] -o out`
(`--exact-int` for chain_relax and rail_transfer, as `run_task.py` does), first on integ, then on the rbpyreach1
tree. The first blocker was then rewritten by hand in a scratch copy (same behaviour, typed-friendly shape) and the
build repeated, until the program built typed or the next blocker was clearly large. The hand rewrites are in
the hand-rewritten sources (inlined in the s3 and s8 appendices where needed). They are the target shapes: what the compiler must accept
from the original source. Typed scratch builds were run on every public and hidden case against `reference.py`, and
on the perf input under `tools/icount.c`, next to the `.ail` twin:

| task | typed from (scratch) .py | cases | icount .py-typed / .ail |
|---|---|---|---|
| echo_pack | rbpyreach1 tree, source unchanged | 57/57 | 2.82x |
| berth_sim | yes | 26/26 | 1.25x |
| ledger_bin | yes | 55/55 | 1.49x |
| ticket_audit | yes | 91/91 | 2.70x |
| rail_transfer | yes, with `INF = 1 << 62` | 23/24: `hidden/big_numbers` overflows int64 in the packed heap key `(nk << 22) \| a` | 1.08x |
| chain_relax | yes, but only with a 31-bit LCG (output changed, not checked) | - | - |
| term_rank, tree_fold, scar_life, tally_lang | no (chain stops at a large feature) | - | - |

Today the `.py` builds run on the general path, 50-200x slower than the best language.

## Per-task blocker chains

Feature tags refer to the table below. "[integ]" = first reasons on integ; "(F0)" = removed by the rbpyreach1 work.

- **echo_pack**: [integ] `unpack` returns bytes or None (F0: unannotated return kinds, owned-bytes helpers,
  dict of lists `idx`, bytearray as bytes view) -> **typed**.
- **berth_sim**: stepped slice `data[pos:pos+6*S:6]` x6 (F5) -> `del data/keys/order` (F5) -> `wait = [None, [], [], []]`
  None slot (F2) -> `heappush(free[cls[b]], b)`, `heappop(bw)` on a subscript / alias of an inner list (F5) ->
  `best = None` narrowed through `best is None or w2[0] < best` (F2) -> **typed**.
- **ticket_audit**: [integ] generated regex helper `s: bytes` but caller supplies int, entry "cannot return checked
  bytes" (F0 + F1: `data = f.read()` inside `with open(.., 'rb')` has no kind, so every split element is int) ->
  `fail(n, cat)` param kinds from mixed call sites, `money()` str return, `out = []` list of str (F1) ->
  `code, name, cap = parts[1:]` x5 (F5) -> `events[ev] = [vc, cents, set()]`, `per.setdefault(vc, [0, 0, 0])` (F3)
  -> `cents` bytes in one branch, int in another (F5 kind split) -> bytes as dict / set keys (F4) -> **typed**.
- **ledger_bin**: loop-body `def rv()` with `nonlocal pos` and `raise` (F6) -> `acc[id] = [name, bal, True]` record
  lists, `a[2] = False` (F3) -> `parse` returns `None, kind, 0` or `(strict, recs), None, 0`; records are tuples of
  arity 1-4 whose field 2 is str in one variant, int in another (F2, F10) -> tuple-return element kinds (`[]`,
  `e.kind` of a user exception) (F1) -> `.decode("ascii")` (F5) -> **typed** (scratch used parallel lists).
- **rail_transfer**: `INF = 1 << 200` with `--exact-int` (F8) -> `bysrc.setdefault(s, set()).add(d)`, `res[(s, d)] = None`
  (F3, F2) -> `list(map(int, read().split()))` / walking a bytes-split list (F1) -> `sl` rebound inside the loop
  ("possibly unbound" plumbing, F1) -> `st_lines = [None] * N` rows, `ids.get(ku)` one-argument (F2) -> builds typed
  with `INF = 1 << 62`, **but** `hidden/big_numbers` needs a > int64 packed key (F8). Stop: needs wide ints.
- **chain_relax**: `parse` returns None or int (F2) -> `18446744073709551615` literal and the `& ((1 << 64) - 1)` LCG
  (F8, u64) -> `fmt()` str return (F1) -> typed with a 31-bit LCG only. Stop: needs exact masked u64.
- **term_rank**: [integ] module constants from calls `STOP = set(b"..".split())`, `UP = bytes.maketrans(..)` and the
  mutable module dict `cache = {}` (F7) -> `heapq.nsmallest` (F5) -> entry/regex-helper kinds (F0, F1: `docs = [[]]`
  rows have no element kind) -> `bytes.translate`, `bytes.isdigit` (F4) -> `Counter` (F3) -> bytes in `set`, dict keys,
  `list[list[bytes]]`, `b"doc %d:" % i` (F4). Stop: F4 is needed as a whole (tokens hold `\x80-\xff`, so a utf-8
  decode is not an exact workaround).
- **tree_fold**: `NODE.match(s, pos)` and `match = NODE.match` (F5) -> `reversed()` (F5) -> `.decode('latin-1')` (F5)
  -> `kids` holds `()` and `[]` (F1) -> `find_first` returns `None, par` or `v, par` (F2) -> `ops` tuples
  `(str, None|int|str)` (F2, F10) -> one stack holds str and int, `it.__class__ is str` (F10) -> then: empty-list
  element kinds, tuple rows with str fields ("a row holds int64 or float fields only"), tuple returns of lists,
  bound-method alias `pop = st.pop`, `extend` of a list-valued expression (F1, F10). Stop: F10 is large.
- **scar_life**: [integ] loop-body `def count4` (F0 lifts it) -> regex-helper param kind, `parse_rule` returns None or
  a list (F2), `out` list kind, nested-def local `r` clashes with `main`'s `r` (F6 bug), `int(x, 2)` on bytes,
  tuple-unpack from a call (F5) -> the board is one N-bit int (N up to 4096*4096), shifted by W and N-W (F8).
  Stop: needs a typed big-int / bitset.
- **tally_lang**: `exec(compile(src, ...))` of generated Python with `locals()`-style use. Stop: out of scope for the
  typed path (CPython-hybrid territory, job cpyhyb1). Behind it: heterogeneous recursive AST tuples, classes.

## Feature table

Corpus = 905 Python programs in `lab/census/programs/{gdev,dev}` and `lab/corpus/programs` (regex/AST grep, programs
containing the pattern; an upper bound on what the feature unblocks, since a program usually has other blockers too).

| F | Feature | Tasks it blocks | Corpus programs | Semantics risk (where typed could differ from CPython) | Size |
|---|---|---|---|---|---|
| F0 | rbpyreach1 re-land + its 2 review defects | echo_pack (done), part of ticket_audit, term_rank, scar_life | - | dict-of-lists: `[]` sentinel vs `None` (kept to truth tests only); the two regressions (recursion, non-statement `setdefault`) | S |
| F1 | Local kind inference: `with open(..,'rb')` read, empty containers from later appends, helper params from mixed call sites, `%`-format str returns, `list(map(int, x.split()))`, tuple-return element kinds, exception attribute kinds, rebound loop names | ticket_audit, chain_relax, rail_transfer, ledger_bin, tree_fold, term_rank | most programs with `x = []` (not countable by grep) | Low: wrong inference is a compile refusal or a C type error, not a silent diff, if every inferred kind is checked at each use | M |
| F2 | None beyond scalar locals: Optional returns of unannotated helpers, narrowing through `x is None or ..`, None list slots / `[None] * n` rows, one-argument `dict.get`, None in tuple returns | chain_relax, berth_sim, rail_transfer, ledger_bin, tree_fold, scar_life | `is None` 98, `return None` 41, `= None`/`[None]` 53, `get(k)` 14 | **High**: `print`/`str`/`==` of None, None vs 0 / `[]`, TypeError on use of None (exit 1). Needs owner Q1 | L |
| F3 | Dict/set of containers and record lists: `d[k] = [a, b, True]`, `setdefault(k, set())`, `setdefault(k, [0,0,0])`, `Counter` | ledger_bin, ticket_audit, rail_transfer, term_rank | `Counter` 47, `setdefault(..container)` 17, `x[k] = [..]` <=205 | Medium: aliasing (`a = d.get(k); a[1] += 5` must change the stored row: sharing semantics of 2026-10-15), bool vs int elements (`True` prints `True`), insertion order | L |
| F4 | Owned bytes as dict/set keys, list elements, parameters; bytes methods `translate`/`maketrans`/`isdigit`/`lower`; `bytes % args` | ticket_audit, term_rank | 14 read stdin bytes (corpus is str-heavy; binary/protocol programs need it most) | Low: bytes are immutable; store an owned copy, hash by content | M |
| F5 | Shape lowerings: stepped slices, `del name`, `reversed()`, tuple-unpack from a slice / call, heapq on a subscript or alias, `nsmallest`/`nlargest`, `decode('ascii'/'latin-1')`, `re` `match(s, pos)` and method aliases, local name reused with another kind in a disjoint range | berth_sim, ticket_audit, ledger_bin, tree_fold, term_rank, scar_life | step slice 44, `reversed` 14, `del` 4, nsmallest 2, decode 1 | Low: each is exact if CPython's edge rules are copied (slice.indices clamping, negative step, `ValueError` on unpack length, `UnicodeDecodeError` on non-ASCII) | M (S each) |
| F6 | Closures: loop-body `def` with `nonlocal`/`raise`; nested-def local names clashing with the enclosing function | ledger_bin, scar_life | nested def 27, in a loop 0, `nonlocal` 3 | Medium: late binding, a fresh function per iteration (identity only visible via `is`) | M |
| F7 | Module-level computed constants (`set(b"..".split())`, `bytes.maketrans`) and module mutable dicts used as caches | term_rank | 22 module `NAME = call(..)` | Medium: import-time evaluation order and side effects; one shared dict across functions | M |
| F8 | Exact wide ints on the typed path: masked u64 (`& (2**64-1)`), compare-only big sentinels, > 64-bit packed keys, big-int bitboards | chain_relax, rail_transfer, scar_life | 4 | **High**: any wrap is a silent diff; needs proofs or owner Q2 | L-XL |
| F10 | Tuples/rows with str, bytes or list fields; variant-arity tuples; multi-value returns of containers; mixed str/int stacks | tree_fold, ledger_bin, tally_lang | not greppable | Medium: tuple identity/printing, per-variant field kinds | L-XL |
| F9 | `exec`/`compile` of generated code | tally_lang | 0 | n/a: out of scope for the typed path | - |

## Build order (most tasks typed earliest)

1. **s1 F0** re-land rbpyreach1 with its two fixes -> echo_pack typed (1 task).
2. **s2 F5a** stepped slices, `del`, `reversed()`, heapq on subscript/alias, `nsmallest` -> berth_sim reduces to its
   two None blockers.
3. **s3 F1** inference pack -> ticket_audit and chain_relax lose their inference blockers.
4. **s4 F5b** unpack from slice/call, kind split of reused names, `decode('ascii'/'latin-1')`.
5. **s5 F3** dict/set of containers and record lists.
6. **s6 F4** owned bytes keys/elements -> ticket_audit typed (2 tasks).
7. **s7 F2a** (needs Q1) None list slots and `is None or` narrowing -> berth_sim typed (3 tasks).
8. **s8 F2b** (needs Q1) Optional returns of unannotated helpers, one-argument `dict.get`, `[None] * n` rows, None in
   tuple returns -> chain_relax and rail_transfer are left with F8 only.

Phase 2, to be split after s8 lands and the next strict lists are re-measured: F8 masked u64 (chain_relax typed, 4
tasks), F6 + F10 variant tuples (ledger_bin), F7 + rest of F4 + `Counter` (term_rank), F10 (tree_fold), F8 wide
ints (rail_transfer, scar_life; Q2), F9 (tally_lang; Q3). Steps s2-s6 need no owner decision and can run while Q1 is
open. Core compiler work runs as one sequential line (memory `split-core-fixes`): one step at a time, each on
integ after the previous one merged (stack at most 2).

## Correctness gate (every feature, every step)

1. **CPython-identical**: for every lab task the step touches, `python3 lab/compare/run_task.py --task <t>
   --langs ail,ail-py,python --icount perf --out /tmp/r-<t>.json` reports all public and hidden cases and the perf input
   correct for `ail-py`, and `ail-py path: typed` once the step claims it. Plus the step's own probes (edge cases
   below), each run with the default build and with `AIL_UNIFIED_FORCE=1`, compared byte for byte (stdout and exit
   code) with `python3`. Probe ints beyond int64 wherever ints come from text or arithmetic.
2. **No regressions**: a probe that built and matched CPython on the base must still do so (rules 1). Run the touched
   modules with `tools/par_check.py -j 2`, then the CI shards.
3. **`.ail` C byte-identical**: for all ten `lab/compare/src/*/main.ail`, the generated C on the step's head equals the
   base's (`compile --debug-dir` on both trees, `cmp` the program `.c`; or `tools/codegen_diff.py --base origin/integ
   --source "$(cat main.ail)"`). Also `tools/codegen_diff.py --pins`. Any difference fails the step.
4. **Speed**: when a task becomes typed, its `.py` icount on the perf input is within the step's stated bound of the
   `.ail` twin (the bounds below are 10% over the hand rewrites' measured ratios).

## Stop rules

- A step that cannot meet the gate in its time box (2 hours of a cheap coding model) stops, pushes what is green, and
  reports the failing case; it does not widen its scope.
- A feature that would need a semantics choice not settled by the owner (Q1-Q3) stops at a by-name refusal: the
  program keeps the old route (general path, or a strict refusal under `--strict`).
- Any silent difference from CPython found in a probe stops the step: refuse the shape by name instead.
- Any change of a `.ail` C byte or of a codegen pin stops the step until explained and removed.
- If a step makes any previously typed program fall back to general, or any program slower in icount, it stops.
- Stop the whole line after s8 and re-measure before splitting phase 2.

## Owner questions (not decided here)

**Q1. None beyond scalar locals.** Today scalar Optional locals/params/returns are a present flag plus a value
(`optlib.py`). Tasks need None list slots, `[None] * n` rows, one-argument `dict.get`, Optional returns of
unannotated helpers, None inside tuple returns. Options:
- A. Extend the tagged form exactly: a present flag per value and per element (rows: an absent-row bit). Every use
  CPython would reject (`heappush(None, ..)`, `None + 1`) raises the same exception type and exits 1; `print`,
  `str`, `repr`, `==` give CPython's answers. Costs one flag per element.
- B. Lower None to a sentinel (-1, `[]`, `b""`) only where a proof shows the program never observes the difference;
  otherwise refuse. Faster, narrower, proof code per pattern.
- C. Status quo: refuse every None outside scalar locals (berth_sim, chain_relax, rail_transfer stay general).
Recommendation: **A** (exact, general; B can be added later as an optimisation on top of A where a proof exists).

**Q2. Ints wider than int64 on the typed path** (chain_relax masked u64, rail_transfer's 1<<200 sentinel and >64-bit
packed heap keys, scar_life's N-bit board). Options:
- A. Status quo: programs that may need wide ints stay on the general path (`--exact-int`).
- B. Exact typed u64 only where a proof shows every result is masked with `& (2**64 - 1)` (or `% 2**64`) before any
  other use, plus compare-only big constants; no wrap is ever visible.
- C. B plus an int128 kind for proven-bounded intermediates (rail_transfer's packed key).
- D. A typed big-int/bitset kind (scar_life).
Recommendation: **B** now (chain_relax; exact by proof), C/D only after measuring how many census programs need them
(grep found 4 of 905).

**Q3. tally_lang (`exec` of generated code).** Options: A. stays general / CPython-hybrid (job cpyhyb1);
B. lower `exec` of code built from a closed template set (very large, low reuse). Recommendation: **A**.

````

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
