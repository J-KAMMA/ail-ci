# rc1: where tree_fold's memory and the reference-count work go

Measure-only. No compiler, runtime or C-compiler file was changed. Base `origin/integ`, branch
`job-rc1-11051645`. Everything here comes from `lab/rc/run.py` and is reproduced in `lab/rc/PRICE.json`.

## Method and limits

- 16/16 programs built through AIL's default path with `--debug-dir` (no general-path fallback), ran under
  `ulimit -v 1500000` and `-j 2`, and matched CPython 3.12 stdout and exit status. The counting build also matched
  the plain gcc `-O2` build, so the counters did not change behaviour.
- Retain/release counts are exact dynamic calls. The scratch counting build adds `RC_HIT` at helper entry and
  marks the helpers `noinline`; the plain build is untouched.
- **Instruction shares are estimates, not hardware-retired instructions.** This runner has no CPU PMU
  (`/sys/bus/event_source/devices/cpu` is absent) and `perf_event_open` for hardware `INSTRUCTIONS` fails with
  ENOENT; `tools/icount.c` is therefore unusable here. The estimate is gcov line-execution counts on a separate
  `-O2 -g` copy multiplied by the static instruction count of each C function from `objdump`, with the helper
  function's estimated instructions divided by the estimated program total. Treat the share as an order estimate,
  not as a calibrated cycle/instruction measurement.
- Peak RSS is `/usr/bin/time -v` "Maximum resident set size". The split wraps `malloc/calloc/realloc/free` in the
  scratch C copy at link time (`--wrap`, 32-byte header) and tracks live requested bytes per allocation call site;
  each call site is classified by its inlined call chain (`addr2line -a -f -i`). At the global peak we snapshot
  every call site. Tracked bytes are requested live bytes, so a program that reserves capacity without touching it
  can show tracked > RSS (tree_fold, 103%). The remainder is code, libc, stacks and pool free lists.
- tree_fold uses the compare input from `lab/compare/tasks/tree_fold/gen.py` at `N=3,000,000`, chain 0.35.
  `typed.py` peaked at 404 MiB, below the 1 GB rule. `main.py` is CPython, not AIL; at 3M it peaked at 1149 MiB,
  above the rule, so the table value is the 2M measurement scaled by 1.5 (2M = 701 MiB, scaled = 1051 MiB); the
  measured 3M value was 1149 MiB.

## (a) Peak RSS split by allocation kind

MiB. `tracked` is the sum of live requested heap bytes at the peak; `split/RSS` is `tracked`/RSS.

| program | peak RSS | input bytes | list buffers | str objects | class objects | other | tracked | split/RSS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| tree_fold typed.py | 404.4 | 32.0 | 384.4 | 0.0 | 0.1 | 0.0 | 416.4 | 103% |
| binarytrees | 1.5 | 0.0 | 0.0 | 0.0 | 0.2 | 0.0 | 0.2 | 16% |
| cfold | 1.9 | 0.0 | 0.0 | 0.0 | 0.7 | 0.0 | 0.7 | 36% |
| deriv | 7.5 | 0.0 | 0.0 | 0.0 | 6.3 | 0.0 | 6.3 | 84% |
| linkedlist | 5.9 | 0.0 | 0.0 | 0.0 | 4.6 | 0.0 | 4.6 | 78% |
| objscan | 16.5 | 0.0 | 4.0 | 0.0 | 11.5 | 0.0 | 15.5 | 94% |
| rbtree | 5.2 | 0.0 | 0.0 | 0.0 | 3.9 | 0.0 | 3.9 | 75% |
| tree_fold main.py (CPython, 2M scaled x1.5) | 1051 | - | - | - | - | - | - | - |

For `typed.py`, **list buffers are 384.4 MiB, 95% of peak RSS**; input bytes are 32.0 MiB (7.9%); class objects
and strings are effectively zero. The tree is four parallel lists (`nm`, `w`, `dep`, `par`) that grow once and are
rebuilt by `sort`/`mirror`/`fold`/`prune`, so the memory is list capacity, not node headers. The tracked sum
exceeds RSS by 3% because the reserved list capacity is not all resident.

## (b) Retain/release calls per helper and instruction share (16/16)

Abbreviations: `obj.ret/obj.rel` = `ail_obj_retain/release`; `blk.rel` = `ail__blk_release`;
`bpay.rel` = `ail__bpay_release`; `ba` = `ail_bytearray_*`; `bl` = `ail_blist_*`;
`ol.store` = `ail_olist_store`; `exc` = `ail_exception_*`.

| program | obj.ret | obj.rel | blk.rel | bpay.rel | ba.ret | ba.rel | ba.store | bl.ret | bl.rel | bl.store | ol.store | exc.ret | exc.rel | total | helper insn share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| berth_sim | 0 | 2 | 3000066 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3000068 | 0.012% |
| chain_relax | 0 | 0 | 27 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 27 | 0.000% |
| echo_pack | 0 | 0 | 1 | 0 | 0 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0.000% |
| ledger_bin | 0 | 2 | 373946 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 373948 | 0.003% |
| rail_transfer | 981191 | 2239989 | 184971 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 672158 | 0 | 0 | 4078309 | 1.103% |
| scar_life | 0 | 2 | 1002 | 0 | 3000 | 3007 | 3003 | 0 | 0 | 0 | 0 | 0 | 0 | 10014 | 0.000% |
| tally_lang | 2 | 8 | 67 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 3 | 81 | 0.000% |
| term_rank | 1 | 4 | 10593231 | 0 | 16206770 | 33484579 | 16206771 | 0 | 0 | 0 | 0 | 0 | 0 | 76491356 | 1.249% |
| ticket_audit | 1 | 4 | 8464008 | 19874065 | 0 | 0 | 0 | 11443202 | 17164809 | 14304004 | 0 | 1 | 2 | 71250096 | 1.471% |
| tree_fold | 25 | 52 | 1768092 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1768169 | 0.005% |
| binarytrees | 49133 | 180152 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 229285 | 30.537% |
| cfold | 81916 | 491497 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 573413 | 23.106% |
| deriv | 360446 | 1966062 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2326508 | 19.920% |
| linkedlist | 1000005 | 1600011 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2600016 | 31.716% |
| objscan | 1500007 | 2000017 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 500006 | 0 | 0 | 4000030 | 31.610% |
| rbtree | 26453314 | 89318294 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 115771608 | 10.789% |

Helper emission/definition sites:

- `ail_obj_retain` definition `AIL_CURRENT/python/pkg-v12/pyfunc.py:34661`; stores emitted at
  `pyfunc.py:34701`, `pyfunc.py:34800`, `pyfunc.py:35034`, `pyfunc.py:35039`, `pyfunc.py:35104`.
- `ail_obj_release` definition `pyfunc.py:34670`; stores/cleanup at `pyfunc.py:34702`, `pyfunc.py:34801`,
  `pyfunc.py:35009`, `pyfunc.py:35040`, `pyfunc.py:35105`, and `ir/emit_c.py:463` (owner cleanup) and
  `ir/emit_c.py:527` (last-use release).
- `ail_olist_store` `pyfunc.py:34700`; `ail__blk_release` `cruntime.py:1068`; `ail_exception_retain/release`
  `cruntime.py:449/456`; `ail__bpay_release` `cruntime.py:7708`; `ail_blist_retain/release`
  `cruntime.py:7738/7749`; `ail_blist_store` `cruntime.py:7762`; `ail_bytearray_retain/release/store`
  `cruntime.py:27191/27199/27207`.
- List/int buffers have no refcount: `ail_list_push/reserve` `cruntime.py:3926/3937`,
  `ail_slist_push/reserve` `cruntime.py:2948/2963`, `ail_pslist_*` `cruntime.py:4119-4152`.

## Pricing for rc2-rc5

Pricing follows the brief: Amdahl bound = `1/(1-s)`, assumed roof removes 60% of the target (`1/(1-0.6*s)`),
then halve that gain. Go if the halved projection is at least 1.03x or reach >=5% peak RSS on at least two
programs. `s` is a share of estimated run instructions.

### rc2 (borrow parameters) and rc3 (borrow loop cursors)

The two techniques address disjoint helper sites, so for each one we use a conservative half of the measured
union share (`s = measured_share/2`). The same table applies to rc2 and rc3 individually; the table is not a
claim that both can be taken together.

| program | measured share | s = half | Amdahl (all) | roof 60% | halved | go |
|---|---:|---:|---:|---:|---:|:--:|
| berth_sim | 0.012% | 0.006% | 1.0001x | 1.0000x | 1.0000x | |
| chain_relax | 0.000% | 0.000% | 1.0000x | 1.0000x | 1.0000x | |
| echo_pack | 0.000% | 0.000% | 1.0000x | 1.0000x | 1.0000x | |
| ledger_bin | 0.003% | 0.001% | 1.0000x | 1.0000x | 1.0000x | |
| rail_transfer | 1.103% | 0.552% | 1.0055x | 1.0033x | 1.0017x | |
| scar_life | 0.000% | 0.000% | 1.0000x | 1.0000x | 1.0000x | |
| tally_lang | 0.000% | 0.000% | 1.0000x | 1.0000x | 1.0000x | |
| term_rank | 1.249% | 0.624% | 1.0063x | 1.0038x | 1.0019x | |
| ticket_audit | 1.471% | 0.736% | 1.0074x | 1.0044x | 1.0022x | |
| tree_fold | 0.005% | 0.003% | 1.0000x | 1.0000x | 1.0000x | |
| binarytrees | 30.537% | 15.269% | 1.1802x | 1.1009x | 1.0504x | yes |
| cfold | 23.106% | 11.553% | 1.1306x | 1.0745x | 1.0372x | yes |
| deriv | 19.920% | 9.960% | 1.1106x | 1.0636x | 1.0318x | yes |
| linkedlist | 31.716% | 15.858% | 1.1885x | 1.1052x | 1.0526x | yes |
| objscan | 31.610% | 15.805% | 1.1877x | 1.1048x | 1.0524x | yes |
| rbtree | 10.789% | 5.394% | 1.0570x | 1.0334x | 1.0167x | |

Headline rc2/rc3: share 9.96-15.86% (half of 19.9-31.7%) on five new programs; Amdahl 1.11-1.19x; roof
1.06-1.10x; halved 1.032-1.053x. **Go** (five programs >= 1.03x). rbtree is 1.017x (no), and the ten compare
tasks all miss 1.03x. tree_fold is not moved: 0.005% share, Amdahl 1.00005x.

`rc2`/`rc3` would edit `pyfunc.py` (helper/emission rules), `ir/ownership.py` (S3b move/rename and borrow
context), and `ir/emit_c.py` (release insertion), with runtime borrow variants in `cruntime.py`. `pyfunc.py` is
busy (codegen), `optlib.py` is busy, and `ir/passes/*` is busy (bce-ranges, pyreach); `ir/ownership.py` has
existing borrowed-list tests (`test_ail_borrowed_*`) that rc2 must extend rather than redo.

### rc4 (reuse) and rc5 (drop specialisation)

Both are priced on the same measured event: a `free` immediately followed by a same-size `malloc` in the same
function. The table row is the reuse peak of those call sites; `pair insn share` assumes ~170 instructions per
malloc/free pair. The two techniques target the same sites, so their gains are not additive.

| program | reuse pairs | pair insn share | reuse peak MiB | reuse/tracked | Amdahl (all) | roof 60% | halved | RSS >=5% |
|---|---:|---:|---:|---:|---:|---:|---:|:--:|
| berth_sim | 1185 | 0.000% | 0.00 | 0.0% | 1.0000x | 1.0000x | 1.0000x | |
| chain_relax | 0 | 0.000% | 0.00 | 0.0% | 1.0000x | 1.0000x | 1.0000x | |
| echo_pack | 0 | 0.000% | 0.00 | 0.0% | 1.0000x | 1.0000x | 1.0000x | |
| ledger_bin | 0 | 0.000% | 0.00 | 0.0% | 1.0000x | 1.0000x | 1.0000x | |
| rail_transfer | 140 | 0.001% | 0.12 | 0.4% | 1.0000x | 1.0000x | 1.0000x | |
| scar_life | 0 | 0.000% | 0.00 | 0.0% | 1.0000x | 1.0000x | 1.0000x | |
| tally_lang | 10 | 0.000% | 0.00 | 2.7% | 1.0000x | 1.0000x | 1.0000x | |
| term_rank | 9352966 | 2.413% | 12.02 | 7.7% | 1.0247x | 1.0147x | 1.0073x | yes |
| ticket_audit | 293721 | 0.069% | 15.68 | 7.0% | 1.0007x | 1.0004x | 1.0002x | yes |
| tree_fold | 1110756 | 0.192% | 22.89 | 5.5% | 1.0019x | 1.0012x | 1.0006x | yes |
| binarytrees | 0 | 0.000% | 0.00 | 0.0% | 1.0000x | 1.0000x | 1.0000x | |
| cfold | 0 | 0.000% | 0.00 | 0.0% | 1.0000x | 1.0000x | 1.0000x | |
| deriv | 0 | 0.000% | 0.00 | 0.0% | 1.0000x | 1.0000x | 1.0000x | |
| linkedlist | 0 | 0.000% | 0.00 | 0.0% | 1.0000x | 1.0000x | 1.0000x | |
| objscan | 0 | 0.000% | 0.00 | 0.0% | 1.0000x | 1.0000x | 1.0000x | |
| rbtree | 0 | 0.000% | 0.00 | 0.0% | 1.0000x | 1.0000x | 1.0000x | |

Headline rc4/rc5: the instruction share is 2.41% at best (term_rank), Amdahl 1.025x, roof 1.015x, halved
1.007x, so instructions alone miss 1.03x. The RSS criterion is met on three programs: term_rank 7.7%,
ticket_audit 7.0%, tree_fold 5.5%. **Go, marginal and RSS-only** (>=5% on at least two programs), but not
additive and not justified by instruction count. The class-object programs (binarytrees, cfold, deriv, linkedlist,
objscan, rbtree) already reuse through AIL's per-size pool (`ail_pool_head`), so rc4/rc5 add nothing there.

### tree_fold applicability

`typed.py` peak is 404 MiB: list buffers 384 MiB (95%), input bytes 32 MiB (7.9%). rc2/rc3 touch 0.005% of
estimated instructions (1.77M `ail__blk_release` plus 77 object inc/dec) and do not move it. rc4/rc5 touch
22.9 MiB, 5.5% of tracked peak, below the 10% bar: **rc4/rc5 do not move tree_fold**. The row that would is
**list buffers** (list growth / `ail_list_reserve`, `ail_pslist_*`, `ail_slist_*` capacity), followed by
**input bytes**. A follow-up should be list-buffer reuse/growth policy, not node reuse.

`rc4`/`rc5` would edit `pyfunc.py` (pool/specialised drop emission), `cruntime.py` (allocator/pool and
`ail__bpay_release`/`ail__blk_release`), `pyboxed2.py` (general path), and `ir/emit_c.py` (drop insertion).
`pyfunc.py`, `optlib.py` and `ir/passes/*` (codegen, bce-ranges, pyreach) are busy; a reuse pass also needs the
`ir/ownership.py` ownership information, which is shared with rc2/rc3.

## Recommendation

- **rc2: go** (parameters) and **rc3: go** (loop cursors): five of six new programs reach 1.03x halved even
  when each technique is charged only half the measured share; output/compare tasks are unaffected.
- **rc4: go (marginal, RSS-only)** and **rc5: go (marginal, RSS-only, same sites)**: instruction gain is below
  the bar, but three programs clear 5% peak RSS. Build them behind an opt-in and target term_rank/ticket_audit
  string/dict churn; do not sell them for tree_fold.
- tree_fold needs a list-buffer row, not node reuse. Borrow inference does not move it either.
