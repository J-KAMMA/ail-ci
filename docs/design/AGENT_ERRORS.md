# Agent-actionable compiler errors (err1 design)

Status: design only; the compiler is unchanged. Data: `lab/err/RESULTS.md`,
`lab/err/fixrate_original.json`.

## The defect, in numbers

15 messages that fired on the vibe programs and the gdev corpus were put to the same model
vibe1 used, one message plus the previous file, 5 replies each. 56/75 replies fixed the program
(builds, output matches CPython, message gone). The 19 failures are concentrated in four
messages:

| message | rate | what goes wrong |
|---|---|---|
| `_ail_l1l` is bound from popping rows of 1 fields ... | 0.20 | names a compiler temporary; the user has no `_ail_l1l` |
| mixes bools and numbers | 0.00 | "make every operand a bool (or `int(...)`)" changes `False` to `0`; all 5 replies printed the wrong output |
| dunder method `Fraction.__float__` | 0.00 | points at line 235 of a 3-line file (the `fractions` prelude) |
| tuple used where a single value is needed | 0.40 | "unpack it or read `r[0]`" does not describe the structural change (a comprehension → a named annotated list) |

The other 11 messages are actionable already: they carry a `write instead:` clause or a
one-line substitution, and 53/55 replies fixed them. So the rewrite does not need to invent a
new voice for every message; it needs one schema, applied to the four dead ends and then to
the rest for consistency.

## Format

Every diagnostic is three things: **where**, **why in the user's names**, and **the edit**.

```
<file>:<line>:<col>: <CODE>: <one sentence: what the user wrote, why it is refused>
Replace:
<the exact source text, copied from the user's file, one or more whole lines>
With:
<the replacement text; it must compile and keep the program's output>
```

Rules for the emitter:

1. `file:line:col` is a position in a file the user wrote. A refusal that comes from a prelude
   or a compiler temporary points at the user's call site and says so (`this note comes from
   the standard library's fractions module`).
2. The cause names only identifiers that occur in the user's source or the standard-library
   name they called. `_ail_l1l`, mangled locals and internal row names never appear.
3. `Replace` / `With` is a literal edit. `Replace` is copied byte for byte from the user's
   file, including the replaced line's leading spaces, and `With` starts at the same column;
   an agent concatenates `With` where `Replace` was. When the fix also touches another line
   (the caller of a changed signature, a second heap operation), `Replace` spans every
   changed line so the pair stays one literal edit. `With` must build on the typed path and
   keep the program's output. If no local edit can do both, the message says which structure
   must change and shows the smallest working shape (a class, a named list, a flag).
4. A fallback note keeps `note:` and adds `this did not block the build; the program still
   runs, about 20x slower`. A refusal uses `error:`.
5. One code per family, stable across releases (`AIL0101` … `AIL0116`).

Machine form, `--json`:

```json
{"code":"AIL0107","severity":"note","file":"main.py","line":1,"col":1,
 "cause":"this dict literal puts an int and a bool in one dict; an AIL dict has one value type, and writing 0/1 would change what prints",
 "message":"main.py:1:1: AIL0107: ...",
 "fix":{"replace_range":[1,1],"with":"class Node:\n    def __init__(self, kind: str, line: int, has_else: bool) -> None:\n        ..."}}
```

`replace_range` is 1-based, inclusive (`[first_line, last_line]`); `with` replaces those whole
lines. An agent can apply it with no parsing. `message` is exactly the human text, so a CLI
prints the same bytes it sends.

## The 15 rewrites

Full text (with the complete `Replace`/`With` blocks) is `lab/err/messages_rewritten.json`;
the table shows the cause and the edit it asks for. Every block was applied literally to its
trigger (same indentation, no re-typing): all 15 build, print CPython's output on both the
default and the general build, and 14 of 15 lose the message (02 does not; see the last
section).

| # | code | old (current compiler) | new (agent format) |
|---|---|---|---|
| 01 | AIL0101 | `sys.stdin.buffer.readline` … "used as a value is not" (no edit) | **Cause:** `sys.stdin.buffer.readline` is saved in `read`; only a direct call is supported. **Replace** `read = sys.stdin.buffer.readline` / `print(read().decode().strip())` **with** `print(sys.stdin.readline().strip())`. |
| 02 | AIL0102 | `'_ail_l1l' is bound from popping rows of 1 fields in one place and 5 in another` (internal name) | **Cause:** `b = heapq.heappop(fh)` takes one field from `free1/2/3`, `entry = heapq.heappop(wait1)` takes a 5-field row from `wait1/2/3`; the compiler reuses one temporary. **Replace** `b = heapq.heappop(fh)` (at its 16-space indent) **with** `fh.sort()` / `b = fh.pop(0)`. |
| 03 | AIL0103 | "comparing a str with a number … write instead: compare like with like …" | **Cause:** `s` is a str and `1` is a number; `s == 1` is always False. **Replace** `if s == 1:` **with** `if s == "1":`. |
| 04 | AIL0104 | "`d.get(k)` with one argument gives None … give the default" | **Cause:** `d.get(k)` gives None for a missing key and there is no None for an int. **Replace** `v = d.get(k)` **with** `v = d.get(k, -1)`. |
| 05 | AIL0105 | "`accounts[rid] = [name, initial, True]` uses `accounts` as a dict of containers …" (then repeats the bool/number note) | **Cause:** `accounts` is a dict whose values are lists; a typed dict holds int/float/str/bytes. **Replace** the assignment **with** a `class Account` and `accounts: dict[int, Account] = {}` / `accounts[rid] = Account(name, initial, True)`. |
| 06 | AIL0106 | "class list comprehensions are unsupported" (no edit) | **Cause:** `[P(x) for x in xs]` builds class instances; only number/str/bytes comprehensions are built. **Replace** `return [P(x) for x in xs]` **with** `out: list[P] = []` / `for x in xs: out.append(P(x))` / `return out`. |
| 07 | AIL0107 | "mixes bools and numbers … make every operand a bool (or `int(...)` every operand)" | **Cause:** the dict has an int (`'line': 3`) and a bool (`'has_else': False`); writing `0`/`1` would print `0` instead of `False`. **Replace** the dict **with** a `class Node` and `Node('when', 3, False)`. |
| 08 | AIL0108 | "make_term returns bytes on one path and a number on another" (no edit) | **Cause:** one function has one return type; this path returns the number `0`. **Replace** `return 0` **with** `return b"0"`. |
| 09 | AIL0109 | "while-else is unsupported. write instead: a flag …" | **Cause:** the loop has no `break`, so the `else` body always runs. **Replace** `while i < 3: … else: print("done", i)` **with** the loop followed by `print("done", i)` (and, with a `break`, a `done` flag). |
| 10 | AIL0110 | "a nested annotation (a list of lists) is not a records parameter; one level of rows is recognised, not two" | **Cause:** `list[dict[str, str]]` is two levels; the typed path takes `list[SomeClass]`. **Replace** the function **and its call site** (lines 1–7) **with** `class Row` + `def sizes(records: list[Row]) -> list[int]:` + `print(sizes([Row("1", ""), Row("2", "3")]))`. |
| 11 | AIL0111 | "dunder method `Fraction.__float__`; only `__init__` is supported …" at `:235:5` of a 3-line file | **Cause:** `float(x)` needs `Fraction.__float__`; importing `fractions` prints this note, and the old position was line 235 of the prelude. **Replace** the import and `print(float(x))` **with** `print(1 / 2)`. |
| 12 | AIL0112 | "a format spec on a Decimal in an f-string (`__format__` is not built)" at `:1687:1` of a 4-line file | **Cause:** format specs apply to int/float/str, not `Decimal`; the old position was line 1687 of the `decimal` prelude. **Replace** `print(f"{d:.2f}")` **with** `print(f"{float(d):.2f}")`. |
| 13 | AIL0113 | "yield: this language has no generators. write instead: build a list with `out.append(x)` and `return out`" | **Cause:** `yield` makes a generator; none are built. **Replace** `def gen(...): for i in range(n): yield i` **with** `def gen(n: int) -> list[int]:` / `out: list[int] = []` / `for i in range(n): out.append(i)` / `return out`. |
| 14 | AIL0114 | "a tuple used where a single value is needed. write instead: unpack it into names (`a, b = r`) or read one field (`r[0]`)" | **Cause:** the comprehension builds a list of 2-field tuples in one expression; the list must be named and appended to. **Replace** `return [(m, pow(base, -1, m)) for m in moduli]` **with** `out: list[tuple[int, int]] = []` / `for m in moduli: out.append((m, pow(base, -1, m)))` / `return out`. |
| 15 | AIL0115 | "'arr' is a list parameter, which is read-only; to change it in a helper, keep the list in a class field … or build and return a new list" | **Cause:** `arr` is a `list[int]` parameter, so `arr[0] = 1` cannot change the caller's list. **Replace** `def fill(...) -> None: arr[0] = 1` / `fill(xs)` **with** `def fill(arr: list[int]) -> list[int]:` / build `out`, set `out[0] = 1`, `return out` / `xs = fill(xs)`. |
| 16* | AIL0116 | "cannot tell the type of element 0 of this tuple … give it a name with an annotation" (positioned past the user's file) | **Cause:** the tuple element is an empty list or an unknown value; name its type. **Replace** `t = ([], n)` **with** `xs: list[int] = []` / `t = (xs, n)`. Kept for the retired vibe1 #1 message; no fix-rate row (not reproducible from a user program on the current compiler). |

## Re-measured fix rate

The 15 rewritten messages were fed to the same model, 5 replies each, with the same harness.
The compiler is unchanged, so a reply is still checked against the real message and CPython.

| # | message | old rate | new rate |
|---|---|---|---|
| 01 | stdin buffer | 1.00 | 0.80 |
| 02 | `_ail_l1l` | 0.20 | 0.00 |
| 03 | str/number | 1.00 | 1.00 |
| 04 | dict.get | 1.00 | 1.00 |
| 05 | dict of containers | 0.80 | 1.00 |
| 06 | class comprehension | 1.00 | 1.00 |
| 07 | bool/number mix | 0.00 | 1.00 |
| 08 | bytes/number return | 0.80 | 1.00 |
| 09 | while-else | 1.00 | 1.00 |
| 10 | nested annotation | 1.00 | 1.00 |
| 11 | Fraction dunder | 0.00 | 1.00 |
| 12 | Decimal format | 1.00 | 1.00 |
| 13 | yield | 1.00 | 1.00 |
| 14 | tuple/single value | 0.40 | 1.00 |
| 15 | list parameter | 1.00 | 1.00 |
| | **total** | **0.75** | **0.92** |

Raw records: `lab/err/fixrate_rewritten.json`. The three lowest-rate messages -- 07, 11 and 14
-- move from 0.00/0.00/0.40 to 1.00 because the cause now names
the user's call site (11) or the structure that must change (07, 14); 12 was already 1.00 and
does not move. The one regression, 01, is a reply that
introduced a new `sys.stdin.buffer` use and was refused (a model error). 02 stays at zero: its
cause is a compiler-internal temporary, so no wording can tell the user which value to change;
steps 1–2 below are required.

## Implementation split (each step ≤ 2 h, ready to queue)

Every step lists the files, the test, and the number it moves. "Rate" is the per-message fix
rate from this job's harness.

**Step 1 — `--json` diagnostic schema (2 h).**
Files: `AIL_CURRENT/ail_chatgpt.py` (`_fallback_notes`, add `--json` to the compile parser),
`AIL_CURRENT/python/pkg-v12/pyc.py:1182` (return structured fields: code, file, line, col,
cause, replace_range, with).
Test: new `AIL_CURRENT/test_ail_agent_errors.py` — compile one program per message family with
`--json`, assert the object parses, `fix.with` compiles, and applying `replace_range` removes
the message. Moves: machine-readable coverage 0 → 15/15 messages; no fix-rate change yet.

**Step 2 — the compiler-side dead end (2 h).**
Files: `AIL_CURRENT/python/pkg-v12/pyfunc.py` (the heapq/heap row capture; replace `_ail_l1l`
in the cause with the user's names and point at the two pop sites),
`AIL_CURRENT/ail_chatgpt.py` (`_fallback_notes`: when the refusing line is in a prelude, map
the position to the user's call site, so the already-measured 11 rewrite is what the compiler
prints).
Test: extend `test_ail_pre133.py` and `test_ail_agent_errors.py`; the 02 trigger must either
lose the message or point at the user's line, and the 11 trigger must point at the user's line
rather than the prelude.
Moves: 02 0.20 → ≥0.60 (target; re-run `lab/err/measure.py`), and prints the 11 rewrite
(0.00 → 1.00 on wording alone) instead of the prelude position.

**Step 3 — apply the format to the other 13 messages (2 h).**
Files: `AIL_CURRENT/python/pkg-v12/pyfunc.py` (`Yield`, `while-else`, `dict of containers`,
tuple refusals), `pyc.py` (the fallback template), `AIL_CURRENT/python/pkg-v12/strictmode.py`
(classification text).
Test: `test_ail_agent_errors.py` asserts every message has a location in the user's file, no
`_ail_` identifier, and a `With:` block that builds.
Moves: total 0.75 → ≥0.90 on the 15-message set.

**Step 4 — emit an applicable `replace_range` (2 h).**
Files: `AIL_CURRENT/ail_source_edit.py` (line range from the source map),
`AIL_CURRENT/ail_chatgpt.py` (attach it to the JSON object and to `edit`).
Test: `test_ail_agent_errors.py` applies each `fix` with `ail_source_edit`, recompiles, and
asserts the message is gone and the output is unchanged; both builds.
Moves: agent-applicable fixes 0 → 15/15.

**Step 5 — re-measure on the vibe programs and gdev (2 h).**
Files: `lab/err/measure.py` (add `--json` mode: feed the object, apply it, rebuild),
`lab/err/RESULTS.md` (new row).
Test: the harness itself; run the 15 triggers, 5 replies.
Moves: reports the realised rate after steps 1–4; target ≥0.90 overall and ≥0.60 on 02/11.

**Step 6 — guard (1 h).**
Files: `AIL_CURRENT/test_ail_agent_errors.py` (add to `tests.d/`).
Test: run `test_ail_agent_errors`, `test_ail_safetynet`, `test_ail_files`,
`test_ail_corpus_findings3`.
Moves: prevents a regression to `_ail_` names or prelude positions; no rate change.

## What this design deliberately does not do

- It does not change a message that already works (01, 03, 04, 06, 09, 10, 12, 13, 15 keep
  their meaning; they gain the location/code/edit fields).
- It does not promise that a local edit exists for every note. 02 is the one compiler-side
  dead end: the note comes from a compiler temporary the user cannot see, so no wording can
  name the value; the typed path must learn the construct (a separate compiler job). 11 is
  fixed by wording alone (0.00 → 1.00): the rewritten note points at the user's call site
  instead of line 235 of the `fractions` prelude.
- It does not tune wording for the model. Every rewrite is checked by recompiling the reply
  and comparing CPython output.
