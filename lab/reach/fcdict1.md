# fcdict1: a dict whose values are lists, sets or dicts

Base: commit `6a46ab1` (the job branch; `fclist1` is in this tree — `lab/reach/fclist1.md`).
This run started from an ERROR continuation with no earlier fcdict1 commits in the branch
(`git log --oneline` is one commit), so every sub-step below was done here.

## Before

| program | default build | `--strict` blockers |
|---|---|---|
| `lab/compare/src/ledger_bin/main.py` | general | 15: 9 × "a nested def inside a loop ('rv')" (parse, lines 46–75), 1 × dict of containers (`acc[r[1]] = [r[2], r[3], True]`, line 116), 4 × one-argument `acc.get(r[1])` (Optional values, s8, lines 118/119/132/140) |
| `lab/compare/src/ticket_audit/main.py` | general | 3: dict of containers (`events[ev] = [vc, cents, set()]`, line 98), one-argument `events.get(ev)` (s8, lines 111 and 133) |
| `lab/pyperf/run.py --help` | refused | dict of containers (`info['wall_cpython'] = [round(...)]`, line 218) plus `statistics.median` (element type unknown) and `a path passed to parameter 'work' of build_icount(), which is not annotated Path` |

So the brief's premise ("the dict of containers is the only blocker") does not hold on this
tree: `ledger_bin` also needs a nested def defined inside a loop (a `nonlocal` closure per
iteration), which is unrelated to dict values, and `lab/pyperf/run.py` has three unrelated
blockers. `ticket_audit` is the one program where the dict-of-containers shape and the
one-argument `get` are the whole list.

What already exists in this tree (pyreachs5c/s6b, `ail_syntax.py`): a local `d = {}` whose every
store is a fixed-arity list literal (`d[k] = [a, b, True]`) or `setdefault(k, [0, 0, 0])`
lowers to a key → slot `dict[K, int]` plus one typed list per position, with a set position
kept as a one-field set box. That lowering is reached for these probes: `p03`, `p08` and `p11`
are typed. The gap is the one-argument `d.get(k)` (s8 for row values) and any use of `d` the
rewrite does not model (`print(d)`, a `for` over the keys, an alias read by subscript).

## Probes

Every probe is in `lab/reach/fcdict1/`; run in the default build and with `AIL_UNIFIED_FORCE=1`
(`bash ~/tools/cmp.sh <probe> $PWD`), compared with `python3` (stdout and exit status).

| probe | shape | default | `--strict` |
|---|---|---|---|
| p01_repro | `v = d[k]; v[0] = v[1]` in a loop | matches | general |
| p02_alias_append | `v = d['a']; v.append(9)` | matches | general |
| p03_set_value | `d.setdefault('s', set()).add(3)` | matches | **typed** |
| p04_dict_counter | dict literal of inner dicts, `d[a][n] += 1` | matches | general |
| p05_setdefault_record | `setdefault(1, [0, 0, 0])` twice, then `d[1][1] += 5` | matches | general |
| p06_print_record | store a record, `print(d[7])`, `print(d)` | matches | general |
| p07_del_alias | `v = d[1]; del d[1]; v[0] = 99` | matches | general |
| p08_int64_record | record int position past int64 | loud stop (both builds), as documented | **typed** |
| p09_get_none | `x = d.get(2)` missing, `x is None` | matches | general |
| p10_get_present | `x = d.get(1)` present, write through `x` | matches | general |
| p11_values_items | `sum(a[1] for a in d.values() if a[2])`, `d.items()` | matches | **typed** |
| p12_mixed_index | `[7, "x", True]` read by a variable index | matches | general |
| p13_grows | `d[1] = [1]; d[1].append(2)` | matches | general |
| p14_del_read | `del d[1]; d.get(1)` | matches | general |
| p15_bool_position | `a = d[1]; a[2] = False` (bool stays bool) | matches | general |
| p16_get_guarded | `if 1 in d: a = d.get(1)` | matches | **typed** |

p08 prints nothing and exits 1 with `OverflowError: integer overflow in +` in both builds
(CPython prints the exact value); that is the declared int64 contract, not a defect of this
task. Every other probe matches CPython's stdout and exit status in both builds.

## After

No compiler change landed. The work needed to move the numbers is real, but it cannot be
finished inside the files this job allows. What was tried and what the tree says:

1. `ticket_audit`'s customer-visible blocker is not only the store. With the store shape the
   existing `ail_syntax.lower_dict_of_records` already handles, the fallback happens at
   `events.get(ev)` (line 111), and there are two further obstacles to lowering `events` at all:
   - `e` is also bound by `for ev, e in top:` where `top = sorted(events.items(), key=...)[:3]`;
     `_record_roles` does not recognise a *slice* of `sorted(d.items())` as the `items` role, so
     the row-alias binding count check (`_lower_record_dict`) refuses the whole dict. A bare
     `items`-role name in `top[:3]` is also refused by the transformer's `visit_Name`.
   - even when the role check is satisfied (a prototype split `top` and appended a
     `if _i >= 3: break` counter), the lowering's own generated code does not type:
     its set position is boxed as `_AilRowSet.s: set[int]` while these sets hold `bytes`
     seats, and `_rkey`-style temporaries are shared between dicts, so a `dict[int, ...]`
     key temp is assigned a `bytes` key ("`_rkey__` is an int and is being assigned a
     bytes", "a bytes list accepts only bytes elements", "a set[int] requires an int
     element").  Those are `ail_syntax.py` (`_lower_record_dict` / `_RecordTransformer`)
     changes, and this lane may not edit that file.
2. `ledger_bin` additionally needs a nested `def` with `nonlocal` created once per loop
   iteration (9 of its 15 strict blockers, `parse` lines 46-75). That feature is unrelated to
   dict values; without it `ledger_bin` cannot be typed however the dict is handled.
3. `lab/pyperf/run.py` additionally needs `statistics.median` on an unknown element type and
   a `Path`-annotated parameter forwarding (its other strict blockers), so removing the
   dict-of-containers refusal would still leave it refused.

A prototype that rewrites `x = d.get(k)` + `if x is None: <never returns>` into
`if k not in d: <body>; x = d[k]` (plus the `x is None or <test>` split) was implemented in
`optlib.py` and does remove the `get` blocker (the first fallback line moves from the `get`
to the store), but it cannot produce a typed program without the `ail_syntax.py` changes above.
It was reverted so the tree carries no half-reachable lowering.

Files that would have to change for this task: `AIL_CURRENT/ail_syntax.py`
(`_record_roles`, `_lower_record_dict`, `_RecordTransformer`, the `_AilRowSet` box type and its
key temporaries).  For `ledger_bin` also the nested-def-in-loop lowering in `pyfunc.py`
(`_nested_def` refusal at `pyfunc.py:37420`).

The probes above stay as the acceptance suite for that follow-up: every one already matches
CPython in both builds, so they pin the semantics the lowering must keep.

