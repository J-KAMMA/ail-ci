# Python sources and the typed path (lab/compare)

Date: 2026-11-01. Branch: `job-pyreach1-11011012`.

## Method

For each of the ten `lab/compare/src/<task>/main.py` programs:

    python3 AIL_CURRENT/ail_chatgpt.py compile lab/compare/src/<task>/main.py \
        --syntax python --strict -o /tmp/out

`--exact-int` was added for `chain_relax` and `rail_transfer`, matching
`lab/compare/run_task.py`'s `EXACT_INT_TASKS`. `--strict` sets `AIL_NO_GENERAL=1`, so every
build was refused (exit 3); the strict report lists every typed-path blocker it could find.
`strictmode` may stop with "the list may be incomplete"; the next blocker was found by
neutralising the reported one and rebuilding.

## Reasons, ranked by how many tasks each blocks

| # | Reason | Tasks blocked | Where |
|---|--------|---------------|-------|
| 1 | None / a return path mixing `None` with one scalar kind | 3 | berth_sim (`wait = [None, ...]`), chain_relax (`return None` in `parse`), echo_pack (`unpack` returns bytes or None) |
| 2 | Unsupported `re` use on the typed path | 2 (3 with tally_lang's general-path note) | scar_life (`m.groups()`), tree_fold (`NODE.match(s, pos)` and `match = NODE.match`); tally_lang (`TOK` as a value) |
| 3 | Nested `def` inside a loop | 2 | ledger_bin (`rv`), scar_life (`count4`) |
| 4 | Integer literal / operation beyond int64 | 2 | chain_relax (`18446744073709551615`), rail_transfer (`1 << 200`) |
| 5 | Entry function cannot return checked bytes (strict-mode only) | 2 | term_rank, ticket_audit; the generated regex helpers are appended after the real entry, so the strict probe sees a helper as `fns[-1]`; normal builds pass the entry explicitly |
| 6 | One task each | 1 | berth_sim: step slice, `del`, free variable in a key lambda; echo_pack: dict of containers (`idx`); ledger_bin: dict of containers; tally_lang: `exec`/`locals`; term_rank: module constant assigned a Call, `heapq.nsmallest`, empty module dict; ticket_audit: a local holds bytes then int (`cents`); tree_fold: `reversed()` and a list holding `()` beside `[]` |

The next blocker behind the top reason was checked for echo_pack: after None handling was
fixed the refusal moved to `idx` being a dict of containers.

## Fix for the top reason

Two front-end defects kept the None / Optional reason alive:

1. `sys.argv[i]` was typed as `int` in `_etype` (pyfunc) and at call sites (`_claim`). A
   parameter that only used the value as a str (a str method, or the subject of a generated
   regex helper) was therefore inferred `int`, and the helper's own `s: str` annotation then
   disagreed. Both now answer `str`.
2. The Optional lowering only knew the return kind of *annotated* helpers. An unannotated
   helper that always returns one scalar kind (e.g. `pack` returning bytes) was treated as
   possibly-None, so `res = pack(data)` beside `res = unpack(data)` refused to lower.
   `optlib._return_kinds` now infers those plain return kinds and `Lowerer.nonnull` uses them.

Effect: echo_pack now gets past the None reason (next blocker: its dict of containers), and
the typed-path helper conflicts in scar_life/term_rank disappeared. No lab task is fully
typed yet: every task still has at least one blocker from rows 2-6 above. In particular
`echo_pack`, the closest task, needs a bytes-keyed dict of int lists (`idx`).

## Verification

Probes (see the report): `argv_starts.py` (a str method on `sys.argv[1]`), `argv_re.py`
(generated regex helper), `optret3.py` (unannotated helper assigned into an Optional local),
`optbytes.py`, `optret2.py`, `nestedappend.py`, `dictbyteslist.py`. The first three build on
the typed path and match CPython; the dict-of-containers probe still refuses by name.
`AIL_CURRENT/test_ail_pytyped_reach.py` pins the two fixes.
