# err1 results: per-message fix rate

Question: when an AI receives one AIL compiler refusal or "built on the general path" note,
how often does its next program build on the typed path, keep CPython's output, and lose the
message? vibe1 (`lab/vibe/RESULTS.md`) reported 0.00 on 9 of the top 10 messages, but that run
counted "the next round built" (a fallback note never blocks a build), so it could not tell an
actionable message from a dead end. This job measures the fix itself.

## 1. Collection

Message builders:

| source | what it emits |
|---|---|
| `AIL_CURRENT/python/pkg-v12/pyc.py:1182` | the `note: <file>:<line>:<col>: built on the general path (about 20x slower) because <reason>; run with --strict to see why` template |
| `AIL_CURRENT/python/pkg-v12/pyfunc.py:13594` | `yield: this language has no generators` |
| `AIL_CURRENT/python/pkg-v12/pyfunc.py:28112` | `while-else is unsupported` |
| `AIL_CURRENT/python/pkg-v12/pyfunc.py:39205` | the `dict of containers` rewrite |
| `AIL_CURRENT/python/pkg-v12/tupexpr.py:287` | `cannot tell the type of element N of this tuple` |
| `AIL_CURRENT/ail_chatgpt.py:5478` | `_FALLBACK_NOTE` / `_fallback_notes` (positioning and `--strict` hint) |

What actually fired:

- 8 vibe programs that built (`lab/vibe/programs/*/ail-0.py`) and the 8 records in
  `lab/vibe/results.json` with compiler rows (11 AIL attempts, 12 message occurrences).
- 100 programs from the gdev corpus (`corpus/gdev/g*.py`), compiled with
  `compile --syntax python` (`lab/err/compile_runs.json`, 108 runs).
- A long tail: most messages occur once. The 15 selected are the 9 reproducible messages vibe1's
  model actually saw (its #1 is retired, see below), plus the 6 highest-frequency messages that
  only the gdev corpus produced (three at 3 occurrences, three at 2).

| # | message (short) | vibe1 | gdev | total |
|---|---|---|---|---|
| 01 | `sys.stdin.buffer.readline` used as a value | 1 | 0 | 1 |
| 02 | `_ail_l1l` bound from popping rows of 1 and 5 fields | 1 | 0 | 1 |
| 03 | comparing a str with a number | 1 | 0 | 1 |
| 04 | `d.get(k)` with one argument | 1 | 1 | 2 |
| 05 | dict of containers | 1 | 0 | 1 |
| 06 | class list comprehensions | 1 | 1 | 2 |
| 07 | mixes bools and numbers | 1 | 0 | 1 |
| 08 | returns bytes on one path and a number on another | 1 | 0 | 1 |
| 09 | while-else | 1 | 0 | 1 |
| 10 | nested annotation (list of dicts) | 0 | 3 | 3 |
| 11 | dunder method `Fraction.__float__` | 0 | 3 | 3 |
| 12 | format spec on a Decimal | 0 | 2 | 2 |
| 13 | yield / no generators | 0 | 2 | 2 |
| 14 | tuple used where a single value is needed | 0 | 2 | 2 |
| 15 | `'arr'` is a list parameter, which is read-only | 0 | 2 | 2 |

vibe1's #1 message (`cannot tell the type of element 0 of this tuple`, 3 occurrences) is not in
the table: on the current compiler it can no longer be triggered from a small user program. It
came from tuple displays in the standard-library prelude, positioned past the end of the user's
file; `AIL_CURRENT/test_ail_pre133.py` records that fix (`cannot tell ...` must not appear). It
is included in the design as message AIL0116 but has no fix-rate row.

Each trigger is in `lab/err/triggers/`; `manifest.json` gives its input file and the substring
that identifies the message. Every trigger was recompiled and the message, the build result and
the CPython output were checked before measuring.

## 2. Fix rate

Harness: `lab/err/measure.py`. Same model path as vibe1 (`cmd -p --model
deepseek-v4.1-flash --effort low`, one turn, no tools); the prompt is the previous file plus
the compiler message and nothing else. 5 independent replies per trigger. A reply is **fixed**
when it builds, its exit status and stdout match CPython, and the trigger's message is gone;
**still blocked** when it builds and the message remains (or the build is refused); **worse**
when it builds and the output differs, or no code came back.

| # | message (short) | fixed | still blocked | worse | rate |
|---|---|---|---|---|---|
| 01 | `sys.stdin.buffer.readline` as a value | 5 | 0 | 0 | 1.00 |
| 02 | `_ail_l1l` rows of 1 and 5 fields | 1 | 4 | 0 | 0.20 |
| 03 | str compared with a number | 5 | 0 | 0 | 1.00 |
| 04 | `d.get(k)` one argument | 5 | 0 | 0 | 1.00 |
| 05 | dict of containers | 4 | 1 | 0 | 0.80 |
| 06 | class list comprehension | 5 | 0 | 0 | 1.00 |
| 07 | mixes bools and numbers | 0 | 0 | 5 | 0.00 |
| 08 | bytes/number return | 4 | 0 | 1 | 0.80 |
| 09 | while-else | 5 | 0 | 0 | 1.00 |
| 10 | nested annotation | 5 | 0 | 0 | 1.00 |
| 11 | `Fraction.__float__` | 0 | 5 | 0 | 0.00 |
| 12 | Decimal format spec | 5 | 0 | 0 | 1.00 |
| 13 | yield | 5 | 0 | 0 | 1.00 |
| 14 | tuple where a single value is needed | 2 | 1 | 2 | 0.40 |
| 15 | list parameter read-only | 5 | 0 | 0 | 1.00 |
| | **total** | **56** | **11** | **8** | **0.75** |

Raw per-reply records: `lab/err/fixrate_original.json`.

### Why the low-rate messages fail

| class | messages | evidence |
|---|---|---|
| names an internal symbol the user never wrote | 02 | the message is about `_ail_l1l`; the four "still blocked" replies changed surrounding code but could not tell which user value had two widths. `--strict` also says only "split the statement into simple named steps". |
| the suggested fix changes observable output | 07 | the note says "make every operand a bool (or `int(...)` every operand)"; all five replies followed it and printed `0` where CPython prints `False`, so all five are `worse`. No local edit both removes the note and keeps the output; the value must move to a class field. |
| the location is in the standard library, not the user's file | 11, 12 | `from fractions import Fraction` alone emits the note at line 235 of a 3-line file; `Decimal` formatting points at line 1687 of a 4-line file. Five of five replies touched the Fraction/Decimal call, and the note stayed because the prelude line is what refuses. |
| the fix is structural, not a local edit | 14, 05 | 14: the tuple comprehension has to become a named annotated list plus a loop; two replies kept the comprehension and changed the return type, so the output differed. 05: one reply grew the dict one more level instead of replacing it with a class. |
| the rewrite is a one-line, checkable substitution | 01, 03, 04, 06, 09, 10, 12, 13, 15 | 5/5 fixed. These already say what to write (most have a `write instead:` clause). |
| correct but the model chose another valid path | 08 | one reply returned `str` on both paths instead of `bytes`; it builds and loses the note but prints a different type. |

## 3. Rewritten messages

`lab/err/messages_rewritten.json` holds the 15 messages in the agent format described in
`docs/design/AGENT_ERRORS.md`: location, a one-sentence cause in the user's own names, and a
concrete replacement built from the trigger's code. The same harness was re-run on that text
(the compiler itself is unchanged; the reply is still compiled with the real compiler and the
original message substring is still the check).

| # | message | old rate | new rate | change |
|---|---|---|---|---|
| 01 | stdin buffer | 1.00 | 0.80 | -0.20 |
| 02 | `_ail_l1l` | 0.20 | 0.00 | -0.20 |
| 03 | str/number | 1.00 | 1.00 | 0 |
| 04 | dict.get | 1.00 | 1.00 | 0 |
| 05 | dict of containers | 0.80 | 1.00 | +0.20 |
| 06 | class comprehension | 1.00 | 1.00 | 0 |
| 07 | bool/number mix | 0.00 | 1.00 | +1.00 |
| 08 | bytes/number return | 0.80 | 1.00 | +0.20 |
| 09 | while-else | 1.00 | 1.00 | 0 |
| 10 | nested annotation | 1.00 | 1.00 | 0 |
| 11 | Fraction dunder | 0.00 | 1.00 | +1.00 |
| 12 | Decimal format | 1.00 | 1.00 | 0 |
| 13 | yield | 1.00 | 1.00 | 0 |
| 14 | tuple/single value | 0.40 | 1.00 | +0.60 |
| 15 | list parameter | 1.00 | 1.00 | 0 |
| | **total** | **0.75** | **0.92** | **+0.17** |

The rewrite moves three dead ends and two near misses: 07, 11 and 14 go from 0.00/0.00/0.40 to
1.00, and 05/08 lose their one failure each. 01 loses one reply: that reply introduced a new
`sys.stdin.buffer` use and the build refused it (a model error, not a wording one). 02 stays at
zero: its cause is a compiler-internal temporary, so text alone cannot tell the user which
value to change; step 2 of the design changes the emitter.

Raw per-reply records: `lab/err/fixrate_rewritten.json`. The four messages whose text changed
after review (02, 06, 10, 14) were re-measured on the final text: 06/10/14 stay at 5/5 and 02
stays at 0/5, so the totals above are unchanged.

## 4. Self-check probes

Each published `Replace`/`With` block was applied literally to its trigger (the `Replace` text
is matched byte for byte, indentation included) to produce `/tmp/probes/NN.py`. These were
compiled with `AIL_CURRENT/ail_chatgpt.py compile --syntax python`, run, and compared with
CPython on the trigger's input. `message_gone` is the trigger's original message substring in
stderr. Each file was also run through `bash ~/tools/cmp.sh /tmp/probes/NN.py $PWD`: all 15
matched CPython on both the general (`AIL_UNIFIED_FORCE=1`) and default builds (`g same stdout`
/ `d same stdout`), and every `Replace` string occurred exactly once in its trigger.

| probe | build | message gone | output = CPython |
|---|---|---|---|
| 01 | ok | yes | yes |
| 02 | ok | no | yes |
| 03 | ok | yes | yes |
| 04 | ok | yes | yes |
| 05 | ok | yes | yes |
| 06 | ok | yes | yes |
| 07 | ok | yes | yes |
| 08 | ok | yes | yes |
| 09 | ok | yes | yes |
| 10 | ok | yes | yes |
| 11 | ok | yes | yes |
| 12 | ok | yes | yes |
| 13 | ok | yes | yes |
| 14 | ok | yes | yes |
| 15 | ok | yes | yes |

14 of the 15 literal edits lose their message. 02 is the only one that does not: the refused
construct is a compiler-internal temporary, so the local list edit keeps the output correct but
the note survives; it is reported as such, not as a working fix. 11's edit replaces the
`fractions` import along with the call, so the prelude note is never emitted.

## 5. Limits

- One model (`deepseek-v4.1-flash`), one run, 5 replies per message. This is a rate, not a
  ranking; sampling noise on 5 replies is about ±0.2.
- The prompt gives the previous file and one message; vibe1 gave the task spec too, so these
  rates are not comparable to vibe1's 0.00 column.
- 02 stays at zero after the rewrite (1/5 original, 0/5 rewritten): its cause is a
  compiler-internal temporary, so text alone cannot tell the user which value to change; step
  2 of the design changes the emitter. 11 is not a wording dead end: 0/5 original, 5/5
  rewritten, because the new text points at the user's 3-line file instead of line 235 of the
  prelude.

## 6. Re-measure after the emitter fix (err3, step 2)

Step 2 changes what the compiler prints for two messages, so the same harness was re-run on
the text the compiler now emits (not the err1 rewritten text):

- **02** -- the row-arity note names the user's variable and every heap it was popped from,
  at the user's first pop site (`...:78:13`), with no `_ail_l1l`.
- **11** -- the `Fraction.__float__` note points at line 3 of the 3-line program and adds
  `(this note comes from the standard library's fractions module)`; the prelude line 235 is gone.

`python3 lab/err/measure.py --messages <current messages> --only 02_poprow_arity,11_fraction_dunder
--jobs 2`, 5 replies each, same model path as section 2.

| # | message | old rate | step-2 rate |
|---|---|---|---|
| 02 | row arity (`_ail_l1l` -> user names) | 0.20 | **1.00** (5/5) |
| 11 | `Fraction.__float__` position | 0.00 | 0.00 (0/5) |

02 clears its target (>= 0.60): every reply named the two heaps and rebuilt, keeping CPython's
output.  11 still reads as a dunder the user must supply; five replies kept `from fractions
import Fraction`, which prints the note by itself, so the position alone does not tell the model
to remove the import.  The 1.00 in section 3 came from the rewritten message that also carries
the `Replace:`/`With:` block; the human note does not carry it (the `--json` `fix` for AIL0111
does, and applying it removes the note).

Raw records: `lab/err/fixrate_err3.json`.

Follow-up (`job-err3-11081940`): the note now selects the user's call that is actually refused.
A later call on a value that is not the prelude type (`print(float(3))`, `f"{1.5:.1f}"`) is no
longer chosen, and a reason that names only a prelude helper (`_dec_cmp_parts`) is mapped too.
These changes move only the `file:line:col` of the notes; the message text and the rates above
are unchanged, so the model run was not repeated.
