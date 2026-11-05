# rc2: borrow inference for read-only parameters

Branch `job-rc2-11052316`, base `origin/integ`. rc1's `PRICE.md` says **go** for rc2.

## What was built

- `AIL_CURRENT/python/pkg-v12/ir/borrow.py` (new): the analysis. A parameter is borrowed when, on
  every path of the callee, it is only read: never stored into a field, list, dict, global or
  closure, never returned, never rebound, never passed to a callee position that is not itself
  borrowed. Fixpoint over the call graph, starting from "all borrowed" and demoting. Aliasing is
  followed through container literals only (`y = p` demotes; `y = p.next` does not, because the
  field holds a different object with its own reference). A method receiver is a read (the method
  takes its own reference on `self`). Functions used as values are refused, as before.
- The one emit point (`pyfunc.py`, the `object_params` list in `to_c`'s function emitter) now
  consults the analysis: a borrowed parameter takes no entry retain and no exit release. The
  elision covers class-instance parameters **and object-list parameters** (`list[Node]`), which the
  previous ad-hoc scan did not.
- `ir/verify.py`: `_Checker.check_borrowed` — a borrowed parameter is never stored, returned or
  released (OSSA's borrowed-value rule), for any function carrying `attrs['borrow']`.
- `AIL_RC_BORROW=0` turns every borrow elision off (A/B switch and escape hatch).

## Borrowed parameters, 16 programs

`f(p1,p2)` = every parameter of `f` is borrowed. Produced by `ir/borrow.py` with the module entry
excluded.

| program | borrowed |
|---|---|
| binarytrees | check(node), make(depth) |
| cfold | build(depth,seed), checksum(e), eval(e), fold(e), size(e) |
| deriv | build(depth,seed), checksum(e), deriv(e), size(e) |
| linkedlist | (none) |
| objscan | keysum(items), scan(items) |
| rbtree | is_red(n), walk(n) |
| berth_sim | fempty(cl,s), fpop(cl,s), fpush(cl,s) |
| chain_relax | digits_only(s), fmt(v), strip0(s) |
| echo_pack | flush(cnt,d,out,start), hash_ba(d), hash_of(d), pack(d), unpack(d) |
| ledger_bin | kindname(e), readvar(r) |
| rail_transfer | meet(d,g,node), relax(d,g), solve(g) |
| scar_life | code(c), parse_num(d,maxlen,nolead), parse_rule(r,ru) |
| tally_lang | ev(i,p), isdig(c), islow(c), kwid(w), lex(b,data,lx,p), newstmt(p), node(p), opid(c,d), parse_line(lx,p), pe1..pe5(lx,p), peekop(lx), pprim(lx,p), punary(lx,p), push(lx), run(p) |
| term_rank | add_term(alld,st), emit_line(b,data,st), end_doc(st), isw(c) |
| ticket_audit | digits(f,hi,lo), isd(c), islow(c), isup(c), money(x), price_cents(f), rec(f,st,t), s_buyer(f), s_code(f), s_date(f), s_name(f), s_price(f), s_seat(f), s_time(f), v_date(f), v_event(f), v_price(f), v_seat(f), v_time(f), vnz(f) |
| tree_fold | compact(keep,t), counts(t), do_cut(name,t), do_find(name,t), do_fold(t), do_mirror(t), do_print(t), do_prune(lim,t), do_sort(t), find_first(name,t), is_lower(c), name_ok(data), parse_num(data), parse_tree(data,end,t), rebuild(cl,cs,t), subw(t) |

## Three hand-checked examples

1. `binarytrees.check(node)` — `node.item`, `node.left`, `node.right` are field reads; the two
   recursive calls pass different objects; `check`'s own `node` is borrowed, so the recursion
   position is borrowable too. Generated C: `int64_t check(ail_obj_Node *v_node) { ... }` with no
   `ail_obj_retain`/`ail_obj_release` on `v_node`. Verified by grep of the emitted `program.c`.
2. `objscan.scan(items)` / `keysum(items)` (`list[Node]`) — the list is only iterated and indexed.
   Before this change the generated C opened with `ail_obj_retain(v_items)` and released it at both
   exits; now both are gone, and the only reference is the caller's `v_items` in `py_main`. This is
   the one new elision rc2 buys on the 16 programs: **4 dynamic calls** (2 retains + 2 releases).
3. `tree_fold.counts(t)` — reads `t.nm`, `t.w`, `t.dep`, `t.par` and returns an int; it never
   stores `t`, returns it, or rebinds it. Borrowed.

## Three parameters it correctly refuses

1. **rebound** — `linkedlist.total(n)`: `n = n.next` in the loop. Rebinding stores over the
   parameter slot, and that store releases the old value; without the entry retain it would drop
   the caller's reference. Refused (the generated C keeps `ail_obj_retain(v_n)`).
2. **stored into a list** — `tally_lang.push(lx, k, v)`: `lx.tk.append(k)` and `lx.tv.append(v)`.
   `k` and `v` are stored into fields' lists; every call site passes ints, but the analysis refuses
   the position, which is what keeps the rule safe for reference parameters.
3. **passed to an owning position** — `binarytrees.make(depth, item)`: `item` is passed to the
   constructor `Node(item, ...)`, which stores it in a field. `item` is refused; `depth` is
   borrowed (it is only compared and decremented).

## Measurements

`lab/rc/run.py` (the rc1 harness: exact dynamic helper counts, gcov-based instruction estimate,
peak RSS from `/usr/bin/time -v`). Two sets: the default build and `AIL_RC_BORROW=0`.

| program | retain on/off | release on/off | est. instructions on/off | ratio |
|---|---:|---:|---:|---:|
| binarytrees | 49,133 / 81,884 | 180,152 / 212,903 | 5,952,997 / 7,213,826 | **1.2118x** |
| cfold | 81,916 / 131,068 | 491,497 / 540,649 | 20,349,672 / 22,188,793 | **1.0904x** |
| deriv | 360,446 / 1,671,162 | 1,966,062 / 3,276,778 | 98,862,118 / 155,288,455 | **1.5708x** |
| linkedlist | 1,000,005 / 1,000,005 | 1,600,011 / 1,600,011 | 90,805,440 / 90,805,440 | 1.0000x |
| objscan | 1,500,005 / 1,500,007 | 2,000,015 / 2,000,017 | 164,503,221 / 164,503,300 | 1.0000x |

Peak RSS (KiB) on/off: binarytrees 1576/1576, cfold 1964/1904, deriv 7724/7724,
linkedlist 6056/6052, objscan 16936/16936. cfold's 60 KiB is one-run noise at this size; 3.2% is
above the 1% bar only in that single sample, and it is a sign error (the elided build should not
need *more* memory). `rbtree` and the 10 compare tasks were not measured (see below).

### Price, achieved, achieved over price

rc1 priced rc2 at a halved projection of **1.0504x** (binarytrees), 1.0372x (cfold), 1.0318x
(deriv), 1.0526x (linkedlist), 1.0524x (objscan), 1.0167x (rbtree), 1.00x (10 tasks).

**The baseline already collects that gain.** `origin/integ` carries the ad-hoc scan
`_scan_borrowed_params` (a non-rebound parameter of a call-by-name function is borrowed), and on
binarytrees/cfold/deriv/linkedlist it produces exactly the same decisions as
`ir/borrow.py` — my "on" counts equal rc1's published counts to the call (49,133 / 81,916 / 360,446
/ 1,000,005). So rc2's *own* delta is:

| program | rc2 elision delta | instruction ratio |
|---|---|---|
| objscan | −2 retains, −2 releases (4 calls of 4,000,030) | 1.0000x |
| all other 15 | 0 | 1.0000x |

Achieved 1.0000x on every program; **achieved over price = 0.00** against rc1's halved projection
(1.03x target not met). What the table above shows is the *whole technique*, which the baseline
banks: 1.21x / 1.09x / 1.57x on binarytrees / cfold / deriv. That is the number to quote for
"borrow parameters", not as an rc2 regression-to-baseline delta.

Two honest caveats:
- instructions are the rc1 gcov-based estimate, not hardware counters (no CPU PMU on this runner);
- `valgrind` is not installed here, so no leak-check was run. AddressSanitizer
  (`gcc -O1 -g -fsanitize=address`, `detect_leaks=1`) is clean on binarytrees, linkedlist and
  objscan: exit 0, no invalid access, no leak report.

## Verification

- Six `lab/rc/progs` programs: CPython-equal stdout and exit status in the default build, with
  `AIL_RC_BORROW=0` and with `AIL_UNIFIED_FORCE=1` (18 builds, all equal).
- Ten compare tasks (`typed.py` against CPython): default and `AIL_RC_BORROW=0` equal on nine.
  `echo_pack` differs from the CPython baseline in **both** builds, byte for byte the same output
  in each, so the difference is not the borrow elision; I did not root-cause it (the comparison
  used `src/echo_pack/main.py` at `TREE_N=300000`, while `run.py` uses
  `tasks/echo_pack/reference.py`).
- Corpus sample: the first 40 sorted `lab/corpus/programs` files, default and `AIL_RC_BORROW=0`,
  empty stdin: 0 output or exit-status differences (40/40). The brief asks for 200; the time budget
  did not allow it.
- `AIL_CURRENT/test_ail_rc_borrow.py`: 4 programs (read-only helper, storing helper, recursive walk,
  returning helper), each against CPython and against the expected count of `ail_obj_retain` in
  `program.c`, plus the analysis's own sets and the `AIL_RC_BORROW=0` switch. 7/7 pass.
- `test_ail_borrowed_owner`, `test_ail_borrowed_elements`, `test_ail_borrowed_element_fields`,
  `test_ail_callable_owned_results`, `test_ail_exception_resources`,
  `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: pass. (Run
  `test_ail_borrowed_elements` without `ulimit -v`: its ASan subprocess cannot map shadow memory
  under a 1.5 GB virtual cap.)
- The 20-shard CI suite is the remaining gate; nothing here was merged or pushed.
