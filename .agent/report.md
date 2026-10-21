Final report

**Scope:** 72 generated programs in the collections area (Counter arithmetic / `most_common` ties, defaultdict factories, OrderedDict `move_to_end`/`popitem`, deque rotate / item access / maxlen, namedtuple `_replace`/`_asdict`, heapq, bisect), each run with `bash ~/tools/cmp.sh` on both builds; plus 8 probes in `/tmp/probes/`.

**Silent wrong answers found: 10 programs, 6 distinct causes. Fixed 3.**

Fixed (each with a typed/general-path regression test in `AIL_CURRENT/test_ail_fuzz9.py`):
1. `C?-job-fuzz9-10220555-1` (`collib.py`): `print(f, f["y"])` of a defaultdict / OrderedDict / deque froze the repr text before the later arguments ran — `defaultdict(<class 'int'>, {'x': 1}) 0` vs CPython's `..., 'y': 0}) 0`; also poisoned `print(len(f), f, f["w"])`. Arguments not themselves converted are now bound to locals in order; a converted collection keeps its own name (no alias/copy). Fixed 9 of the 72 programs (p07, p49, p50, p62, p65, p67, p72, d3, d5).
2. `C?-job-fuzz9-10220555-2` (`cruntime.py`): `q[0] = x` / `del q[i]` / `q[a:b]` on a deque indexed the two-element wrapper instead of the data list — after `q += [3]`, `q[0] = 9` gave `len(q) == 122` (and a segfault in another variant), `q[1:]` printed `[None]` where CPython raises TypeError. Now the data list is indexed (`IndexError: deque index out of range`) and slices / non-int indices raise CPython's TypeError.
3. `C?-job-fuzz9-10220555-3` (`cruntime.py`): `del c[missing]` on a Counter raised KeyError and dropped the rest of the output; the Counter flag is honoured, defaultdict still raises KeyError.

Not fixed (listed in `DEVLOG.md`, `test_ail_fuzz9.py` docstring): `b.c["k"] += 2` where the Counter is a class field raises KeyError (`/tmp/probes/unfixed/p_field_counter_augassign.py`, both builds — differs); `list(od)` of an OrderedDict with int keys raises TypeError "argument of type 'int' is not iterable" on the general path; `move_to_end(k, last=False)` and `print(d, d.popitem())` remain compile-time refusals (the general path cannot build them either).

**Probes** (all `bash ~/tools/cmp.sh /tmp/probes/<p>.py $PWD`, both builds): `p_dds_order` (int/float/str/list factories, read through an argument, an attribute, an empty dict, negative + 10^9 values) — same; `p_od_order` (str and int keys, `setdefault`, `pop`) — same; `p_deque_order` (popleft/count/empty/negative/huge/float/maxlen) — same; `p_deque_items` (setitem/delitem, negative, 99, non-int, slices, empty deque, attribute, dict value) — same; `p_counter_del` (missing/present, int keys, 10^9, via argument, via attribute, defaultdict contrast) — same; `p_where_from` (attribute, list item, dict value) — same; `p_field2` (del through an attribute) — same; `p_alias` (`e = d` aliasing) — refused by the typed path, correct output via the general path.

**Tests on the final commit `fc3d67a`** (`tools/par_check.py -j 2`): test_ail_fuzz9 10 tests ok (77 s), test_ail_collections, test_ail_deqctr, test_ail_silent2, test_ail_stdlib5, test_ail_heapq_bisect, test_ail_safetynet, test_ail_files, test_ail_corpus_findings3 — all ok, 0 failed. `update_manifest.py --check` exits 0; `DEVLOG.md` added (dated 2026-10-21; this export has no DIFFERENCES.md, so the `C?-job-fuzz9-10220555-N` rows live in the DEVLOG/test docstring). Committed with explicit `git add`; nothing pushed.
[cost $0.39, turns 192]
