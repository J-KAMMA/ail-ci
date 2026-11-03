Lane: pyreach

**Finish pyreachs3 from its existing work; do not redo it.** The first run (branch `job-pyreachs3-11032313`) did the work, then ended ERROR (a review that gave no answer or hit a model limit), so it got no verdict.

Start by checking whether `origin/integ` already contains this work (a later job may have carried it): if `git diff origin/integ...origin/job-pyreachs3-11032313` adds nothing new, report NOCHANGE and stop.

Otherwise apply that branch's work: cherry-pick, in order, every commit after "export of staging:integ + task" except "agent worker report".

```
git fetch origin job-pyreachs3-11032313
git log --oneline origin/job-pyreachs3-11032313
```

Commits named "worker: uncommitted edits" or "fix: uncommitted edits" hold unfinished work: read them, then finish the job.

Then verify against the original task below: re-run its measurements and targeted tests, check the boundary cases, fix what is wrong, and report the numbers. Time budget: 60 minutes.

# pyreach s3: local kind inference for plain Python sources

Design: `pyreach-design.md` (appendix below) (F1).
Base: `origin/integ` after s2 merged.

**Number this moves:** in the strict list of `lab/compare/src/ticket_audit/main.py` the blockers "'s' is annotated
bytes in the source, but the caller also supplies int" (the generated regex helper), "a typed dict requires a str key"
(`CODES[cat]` in `fail`) and "'out' is appended both a str and a non-str value" disappear; in chain_relax the two
"concatenating a str with a number" blockers (`"sum " + fmt(total)`) disappear; in rail_transfer the five notes
"cannot tell the type of element 0 of this tuple" disappear. No task becomes typed by this step alone.

The hand rewrites in `the target shapes in the appendix below` show which
annotations made each blocker go away; the compiler must infer those annotations itself.

## Changes (`AIL_CURRENT/python/pkg-v12/pyfunc.py`; the param rule lives near `_as_name`, about line 5356)

1. **`with open(path, 'rb') as f: data = f.read()`** (also inside `try:`): `data` is bytes (and str for `'r'`/default
   mode). Then `data.split(b'\n')` is a list of bytes and its elements are bytes. Today `data` has no kind and each
   element defaults to int, which is what poisons the regex helpers.
2. **Unannotated helper parameters from mixed call sites**: `fail(1, 'header')`, `fail(ln, 'syntax')`, ... gives
   `n: int, cat: str` when every call site agrees per position; disagreeing sites keep the by-name refusal.
3. **Return kind of a helper that returns a `"%..." % v` string**, possibly after `s = s[1:]` reassignments
   (`fmt` in chain_relax, `money` in ticket_audit): str.
4. **`out = []` later only appended str values** (including `"..." % (...)` and `"a" + str_helper(x)`): list of str.
   This is `_mark_str_lists` (about 28468); the `%`-format with a tuple right side must count as str.
5. **`list(map(int, X.split()))`** and walking a list produced by `bytes.split()` (`for x in raw`, comprehension over
   it): list of int / elements bytes. Today rail_transfer gets "is a blist" and the tuple-element notes from
   `tupexpr.py` `ex_Tuple` (about 287).
6. **A name rebound in a loop body** (`sl = st_lines[s]` before the loop, `sl = st_lines[u]` inside it) must not
   produce the "possibly unbound" ternary `sl if _ail_set_sl or _ail_unbound_sl(...)` when both bindings precede every
   read on all paths.

Every inferred kind must still be checked at each use: a use that disagrees is a refusal by name, never a coercion.

## Tests

New module `AIL_CURRENT/test_ail_pyreach_infer.py` + `tests.d` file. Probes (default build and
`AIL_UNIFIED_FORCE=1`, compared with CPython): `open(..,'rb')` read then split and regex match; same with `'r'`; a
helper called with (int, str) at three sites; a helper called with int at one site and str at another (must stay
refused under `--strict`, general path matches CPython); `"%.9f" % v` helper with `s = s[1:]`; `out = []` with `%`
appends; `list(map(int, ...split()))` with a value beyond int64 (default build: loud OverflowError like the int64
policy; `--exact-int`: exact); loop-rebound name.

## Gate

Design gate. In addition: run the strict build of all ten lab `.py` sources before and after, and attach both blocker
lists to the PR; no blocker may appear that was not there before. `.ail` C byte-identical for all ten twins.

## Commit and push

Commit and push after each of changes 1-6 with its probes.

## Stop rule

Stop when 2 hours pass or when an inference would need to choose between two kinds (refuse instead). Do not add new
container kinds (s5) or bytes keys (s6).


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
`the appendix below<task>/main.py` (WSL). They are the target shapes: what the compiler must accept
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

### target shape: ticket_audit/main.py (hand rewrite that builds typed; for reference only, do not commit it)

````python
import sys
import re

R_VEN = re.compile(rb'[A-Z]{3}')
R_NAME = re.compile(rb'[\x20-\x7b\x7d-\x7e]{1,40}')
R_CAP = re.compile(rb'[0-9]{1,6}')
R_EVT = re.compile(rb'[0-9]{6}')
R_DATE = re.compile(rb'([0-9]{4})-([0-9]{2})-([0-9]{2})')
R_TIME = re.compile(rb'([0-9]{2}):([0-9]{2})')
R_PRICE = re.compile(rb'([0-9]{1,4})\.([0-9]{2})')
R_SEAT = re.compile(rb'[A-Z]([0-9]{1,3})')
R_BUYER = re.compile(rb'[a-z][a-z0-9]{3,11}')
R_COUNT = re.compile(rb'[0-9]{1,9}')
R_CENTS = re.compile(rb'[0-9]{1,12}')

CODES = {'header': 2, 'syntax': 3, 'value': 4, 'reference': 5,
         'duplicate': 6, 'capacity': 7, 'summary': 8}


def fail(n: int, cat: str):
    sys.stdout.write("line %d: %s\n" % (n, cat))
    sys.stdout.flush()
    sys.exit(CODES[cat])


def money(c: int) -> str:
    return "%d.%02d" % (c // 100, c % 100)


def noleadzero(b):
    return not (len(b) > 1 and b[0:1] == b'0')


def main():
    if len(sys.argv) != 2:
        sys.exit(1)
    try:
        with open(sys.argv[1], 'rb') as f:
            data: bytes = f.read()
    except Exception:
        sys.exit(1)
    lines = data.split(b'\n')
    if lines and lines[-1] == b'':
        lines.pop()
    if not lines or lines[0] != b'TKT/1':
        fail(1, 'header')

    venues: dict[str, int] = {}
    ev_vc: dict[str, str] = {}
    ev_price: dict[str, int] = {}
    ev_n: dict[str, int] = {}
    sold: set[str] = set()
    nrec = 0
    nS = nR = 0
    sold_total = 0
    revenue = 0
    n = len(lines)
    for i in range(1, n):
        ln = i + 1
        parts = lines[i].split(b'|')
        t = parts[0]
        nf = len(parts) - 1
        if t == b'V' and nf == 3:
            code = parts[1]
            name = parts[2]
            cap = parts[3]
            if not (R_VEN.fullmatch(code) and R_NAME.fullmatch(name)
                    and name[0] != 0x20 and name[-1] != 0x20
                    and R_CAP.fullmatch(cap)):
                fail(ln, 'syntax')
            if not noleadzero(cap) or not (1 <= int(cap) <= 100000):
                fail(ln, 'value')
            ks = code.decode()
            if ks in venues:
                fail(ln, 'duplicate')
            venues[ks] = int(cap)

            nrec += 1
        elif t == b'E' and nf == 5:
            ev = parts[1]
            vc = parts[2]
            date = parts[3]
            tm = parts[4]
            price = parts[5]
            md = R_DATE.fullmatch(date)
            mt = R_TIME.fullmatch(tm)
            mp = R_PRICE.fullmatch(price)
            if not (R_EVT.fullmatch(ev) and R_VEN.fullmatch(vc) and md and mt and mp):
                fail(ln, 'syntax')
            d = [x - 48 for x in ev]
            bad = (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 != 0
            y, mo, da = int(md.group(1)), int(md.group(2)), int(md.group(3))
            if not (2000 <= y <= 2099 and 1 <= mo <= 12):
                bad = True
            else:
                dim = [31, 29 if y % 4 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][mo - 1]
                if not (1 <= da <= dim):
                    bad = True
            if int(mt.group(1)) > 23 or int(mt.group(2)) > 59:
                bad = True
            if not noleadzero(mp.group(1)):
                bad = True
            cents = int(mp.group(1)) * 100 + int(mp.group(2))
            if cents % 5 != 0:
                bad = True
            if bad:
                fail(ln, 'value')
            if vc.decode() not in venues:
                fail(ln, 'reference')
            if ev.decode() in ev_vc:
                fail(ln, 'duplicate')
            ev_vc[ev.decode()] = vc.decode()
            ev_price[ev.decode()] = cents
            ev_n[ev.decode()] = 0
            nrec += 1
        elif t == b'S' and nf == 3:
            ev = parts[1]
            seat = parts[2]
            buyer = parts[3]
            ms = R_SEAT.fullmatch(seat)
            if not (R_EVT.fullmatch(ev) and ms and R_BUYER.fullmatch(buyer)):
                fail(ln, 'syntax')
            d = [x - 48 for x in ev]
            if (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 != 0:
                fail(ln, 'value')
            sn = ms.group(1)
            if sn[0:1] == b'0':
                fail(ln, 'value')
            if ev.decode() not in ev_vc:
                fail(ln, 'reference')
            key = ev + b'|' + seat
            if key.decode() in sold:
                fail(ln, 'duplicate')
            if ev_n[ev.decode()] >= venues[ev_vc[ev.decode()]]:
                fail(ln, 'capacity')
            sold.add(key.decode())
            ev_n[ev.decode()] += 1
            sold_total += 1
            revenue += ev_price[ev.decode()]
            nS += 1
            nrec += 1
        elif t == b'R' and nf == 2:
            ev = parts[1]
            seat = parts[2]
            ms = R_SEAT.fullmatch(seat)
            if not (R_EVT.fullmatch(ev) and ms):
                fail(ln, 'syntax')
            d = [x - 48 for x in ev]
            if (3 * d[0] + d[1] + 3 * d[2] + d[3] + 3 * d[4] + d[5]) % 10 != 0:
                fail(ln, 'value')
            if ms.group(1)[0:1] == b'0':
                fail(ln, 'value')
            key = ev + b'|' + seat
            if ev.decode() not in ev_vc or key.decode() not in sold:
                fail(ln, 'reference')
            sold.discard(key.decode())
            ev_n[ev.decode()] -= 1
            sold_total -= 1
            revenue -= ev_price[ev.decode()]
            nR += 1
            nrec += 1
        elif t == b'END' and nf == 2:
            cnt = parts[1]
            centb = parts[2]
            if not (R_COUNT.fullmatch(cnt) and R_CENTS.fullmatch(centb)):
                fail(ln, 'syntax')
            if not noleadzero(cnt) or not noleadzero(centb):
                fail(ln, 'value')
            if int(cnt) != nrec or int(centb) != revenue:
                fail(ln, 'summary')
            if i + 1 < n:
                fail(ln + 1, 'summary')
            out: list[str] = []
            out.append("venues %d events %d sold %d refunds %d" % (len(venues), len(ev_vc), nS, nR))
            out.append("revenue " + money(revenue))
            pe: dict[str, int] = {}
            pt: dict[str, int] = {}
            pr: dict[str, int] = {}
            for evk in ev_vc:
                vk = ev_vc[evk]
                pe[vk] = pe.get(vk, 0) + 1
                pt[vk] = pt.get(vk, 0) + ev_n[evk]
                pr[vk] = pr.get(vk, 0) + ev_n[evk] * ev_price[evk]
            for vk in sorted(venues):
                out.append("%s events=%d tickets=%d revenue=%s" % (vk, pe.get(vk, 0), pt.get(vk, 0), money(pr.get(vk, 0))))
            top = sorted(ev_vc, key=lambda k: (-ev_n[k], k))[:3]
            for evk in top:
                out.append("top %s %d" % (evk, ev_n[evk]))
            sys.stdout.write("\n".join(out) + "\n")
            return
        else:
            fail(ln, 'syntax')
    fail(n + 1, 'summary')


main()

````

### target shape: chain_relax/main.py (hand rewrite that builds typed; for reference only, do not commit it)

````python
import sys
from math import sqrt


def parse(s, lo, hi):
    if not s or not all('0' <= ch <= '9' for ch in s):
        return -1
    v = int(s)
    if v < lo or v > hi:
        return -1
    return v


def fmt(v: float) -> str:

    s = "%.9f" % v
    if s.startswith("-") and not any(ch in "123456789" for ch in s):
        s = s[1:]
    return s


def main():
    a = sys.argv[1:]
    if len(a) != 3:
        return 1
    n = parse(a[0], 1, 10000000)
    t = parse(a[1], 0, 1000000)
    seed = parse(a[2], 0, 4000000000)
    if n < 0 or t < 0 or seed < 0:
        return 1
    M = (1 << 31) - 1
    x = seed
    h = [0.0] * n
    for i in range(n):
        x = (x * 1103515245 + 12345) & M
        h[i] = float(((x >> 33) % 2001) - 1000) / 64.0
    for s in range(1, t + 1):
        if s & 1:
            for i in range(n - 1):
                c = h[i]
                d = (h[i - 1] + h[i + 1]) - (c + c)
                h[i] = c + 0.375 * (d / (1.0 + sqrt(d * d + 0.0625)))
            i = n - 1
            c = h[i]
            d = (h[i - 1] + h[0]) - (c + c)
            h[i] = c + 0.375 * (d / (1.0 + sqrt(d * d + 0.0625)))
        else:
            i = n - 1
            c = h[i]
            d = (h[i - 1] + h[0]) - (c + c)
            h[i] = c + 0.375 * (d / (1.0 + sqrt(d * d + 0.0625)))
            for i in range(n - 2, -1, -1):
                c = h[i]
                d = (h[i - 1] + h[i + 1]) - (c + c)
                h[i] = c + 0.375 * (d / (1.0 + sqrt(d * d + 0.0625)))
    total = 0.0
    energy = 0.0
    for i in range(n):
        total = total + h[i]
        tt = h[(i + 1) % n] - h[i]
        energy = energy + tt * tt
    out = [
        "sum " + fmt(total),
        "energy " + fmt(energy),
        "min " + fmt(min(h)),
        "max " + fmt(max(h)),
        "first " + fmt(h[0]),
        "middle " + fmt(h[n // 2]),
        "last " + fmt(h[n - 1]),
    ]
    sys.stdout.write("\n".join(out) + "\n")
    return 0


sys.exit(main())

````

### target shape: rail_transfer/main.py (hand rewrite that builds typed; for reference only, do not commit it)

````python
import sys
from heapq import heappush, heappop


def main():
    raw = sys.stdin.buffer.read().split()
    data = [0] * len(raw)
    for i in range(len(raw)):
        data[i] = int(raw[i])
    N = int(data[0]); M = int(data[1]); Q = int(data[2])
    X = data[3:3 + N]
    p = 3 + N
    SH = 24
    MASK = (1 << SH) - 1
    NB = 22
    NMASK = (1 << NB) - 1
    ids = {}
    node_station = [0] * N  # index by node id; extended for line nodes
    st_lines = [[] for _ in range(N)]
    adj = [[] for _ in range(N)]
    nid = N
    for i in range(M):
        u = data[p]; v = data[p + 1]; L = data[p + 2]; t = data[p + 3]
        p += 4
        ku = u * 100000 + L
        a = ids.get(ku, -1)
        if a < 0:
            a = nid; nid += 1
            ids[ku] = a
            node_station.append(u)
            adj.append([])
            st_lines[u].append(a)
        if u == v:
            continue
        kv = v * 100000 + L
        b = ids.get(kv, -1)
        if b < 0:
            b = nid; nid += 1
            ids[kv] = b
            node_station.append(v)
            adj.append([])
            st_lines[v].append(b)
        ts = t << SH
        adj[a].append((ts << NB) | b)
        adj[b].append((ts << NB) | a)

    # group queries by source
    qs = []
    sidx: dict[int, int] = {}
    srcs: list[int] = []
    dl: list[list[int]] = []
    seen: set[int] = set()
    for i in range(Q):
        s = data[p]; d = data[p + 1]; p += 2
        qs.append((s, d))
        if s != d:
            if s not in sidx:
                sidx[s] = len(srcs)
                srcs.append(s)
                dl.append([])
            if s * N + d not in seen:
                seen.add(s * N + d)
                dl[sidx[s]].append(d)
    res: dict[int, int] = {}
    INF = 1 << 62
    for si in range(len(srcs)):
        s = srcs[si]
        dests = dl[si]
        sl = st_lines[s]
        if not sl:
            for d in dests:
                res[s * N + d] = -1
            continue
        dist = [INF] * nid
        remaining = len(dests)
        heap = []
        for a in sl:
            dist[a] = 1
            heap.append((1 << NB) | a)
        heap.sort()
        while heap and remaining:
            it = heappop(heap)
            u = it & NMASK
            k = it >> NB
            if dist[u] != k:
                continue
            if u < N:
                if s * N + u in seen and s * N + u not in res:
                    res[s * N + u] = k
                    remaining -= 1
                sl2 = st_lines[u]
                if sl2:

                    nk = k + (X[u] << SH) + 1
                    for a in sl2:
                        if nk < dist[a]:
                            dist[a] = nk
                            heappush(heap, (nk << NB) | a)
            else:
                w = node_station[u]
                if k < dist[w]:
                    dist[w] = k
                    heappush(heap, (k << NB) | w)
                for e in adj[u]:
                    nk = k + (e >> NB)
                    w = e & NMASK
                    if nk < dist[w]:
                        dist[w] = nk
                        heappush(heap, (nk << NB) | w)
        for d in dests:
            if s * N + d not in res:
                res[s * N + d] = -1
    out = []
    for s, d in qs:
        if s == d:
            out.append("0 0")
        else:
            k = res[s * N + d]
            if k < 0:
                out.append("none")
            else:
                out.append("%d %d" % (k >> SH, k & MASK))
    sys.stdout.write("\n".join(out) + ("\n" if out else ""))


main()

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
