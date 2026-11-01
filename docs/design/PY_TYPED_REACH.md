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

Effect: echo_pack gets past the None reason and the typed-path helper conflicts in
scar_life/term_rank disappeared.

## Review fix: echo_pack now builds typed

The review correctly found that no lab task was fully typed yet. The remaining echo_pack
blockers were the bytes-keyed dict of int lists (`idx`), one-argument `dict.get`, and a
bytearray passed to a sequence parameter. Three general front-end changes close them:

1. **A plain dict of lists.** A local `d = {}` whose only uses are
   `d.setdefault(k, []).append(v)` and a truth-tested `x = d.get(k)` is lowered to the typed
   shape the compiler already has: a key -> slot dict plus `rows: list[list[T]]`. The slot
   dict is O(1); row 0 is a shared empty sentinel so a missing key stays a read-only empty
   row. Any other use of `d`, a mutation of the fetched row, or a non-truth-tested `get`
   leaves the source unchanged and the old by-name refusal intact.
2. **Unannotated owned-bytes helpers.** A Python-surface helper whose every value return is
   `bytes(...)` and which cannot fall off its end now owns its result exactly like an explicit
   `-> bytes`, so `res = pack(data)` may cross a function boundary.
3. **Bytearray as a read-only bytes view.** A bytearray argument to a bytes/sequence parameter
   is passed through `ail_bytearray_readonly_arg`, and call-site inference claims bytes for an
   unannotated sequence parameter when the caller supplies a bytearray.

Two supporting fixes found while validating the other blockers: a nested `def` that is a
direct statement of a loop body is lifted with its captured values (late binding preserved by
passing them at each call), and `for part in m.groups()` is lowered to `m.group(i)` when every
pattern the match can hold has the same groups and all of them always take part. Generated
helpers appended after a script no longer hide the script's real entry point (`_script_entry`),
which is what the old row 5 misreported as "entry returns checked bytes".

Result: `echo_pack` builds with `--syntax python --strict` (exit 0), passes all 57 public +
hidden cases plus the perf input against CPython, and reports `ail-py path: typed` in
`lab/compare/run_task.py`. The other nine Python sources still have their row 2-6 blockers
(chain_relax/rail_transfer need exact big ints; tally_lang executes generated code; the rest
need dict-of-containers, module tables or slice/tuple work).

## Verification

Probes: `p_dlist3.py` (dict-of-lists through a list item, missing key, truth test),
`p_owned_bytes2.py` (unannotated bytes helpers including empty), `p_ba_view.py` (bytearray,
empty and non-empty), `p_loop_def.py` (loop-body nested def capturing an outer local),
`p_groups_loop3.py` (str groups), `p_entry_re2.py` (entry after generated regex helpers), and
the earlier `argv_starts`/`argv_re`/`optret3` cases. All match CPython on the default and
general builds; `p_groups_optional.py` (a group that may be absent) is refused by name because
the typed path has no None. `AIL_CURRENT/test_ail_pytyped_reach.py` pins the behaviour,
including building `lab/compare/src/echo_pack/main.py` itself.

The generated C for all ten `.ail` sources is byte-identical to the parent commit, and all ten
`.ail` sources still build typed. Instruction counts could not be measured on this runner:
`perf_event_open` is denied (`perf_event_paranoid=4`) and valgrind is not installed, so
`run_task.py --icount auto` reports `none`; wall time on the perf input was 1.06 s (`.ail`) vs
4.88 s (`.ail-py`).
