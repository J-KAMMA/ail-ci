# job job-fz244-11090611  started 2026-11-08T21:12:26Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Here's the short report.

## Result: no difference on this tree; seed is refused by name

**Reproduction** — `lab/fuzz/run.py --start 2076520850 --count 1 --modes default,ir` classes the seed `refused`/`refused` (2 modes, 0 DIFF). The compiler exits 3: `p.ail:53:9: not in the subset: a constant integer expression overflows int64` — the unreachable `-9223372036854775807 << 1` in the `except ZeroDivisionError` arm. The sort that produced the fuzz-run `TypeError '<' not supported ... 'object' and 'int'` now matches CPython everywhere I could route it. With `--exact-int` the whole seed builds and matches CPython's 32 stdout lines + exit 1 on default and IR. No compiler change made.

**Minimized construct**: `v3.sort(key=lambda q: (-q, q))` over `[min(-1, b), b]` with `b = 9223372036854775807`, list doubled 20× (2,097,152 elements). Also built on the general path (`pyc.py --general-only`) — same stdout.

**Probes** (`cmp.sh` g/d plus a default/IR loop; all match CPython unless noted):
- `fz244` (full seed) — refused, exit 3, both modes; with `--exact-int` same stdout/rc
- `p_full_ok` (seed minus the out-of-range constant) — default, `AIL_UNIFIED_FORCE=1`, general, IR: same
- `p_h0`, `p_h0b`, `p_h0c`, `p_sortkey`, `p_sortbig`, `p_sortbig2`, `p_sortneg` — same
- `q_sort_tup3`, `q_sort_mixed`, `q_sort_arg`, `q_sort_attr`, `q_sort_dictval`, `q_sort_huge`, `q_sort_listitem`, `q_sort_float`, `q_sort_dup`, `q_sort_minabs`, `q_obj_mix`, `q_obj_neg`, `q_obj_bool` — same, both builds
- `q_refuse_shift` — refused by name, but at load time with **exit 2** (`int64 constant expression out of range`) vs exit 3 for the full seed

**Other difference seen**: the same out-of-range constant gets two different diagnostics/exits depending on context (exit 2 load-time vs exit 3 "not in the subset"). `lab/fuzz/run.py` counts only exit 3 as `refused`, so a fuzz program containing just that constant would be reported as a `crash`. Not fixed here (outside this finding).

**Committed** on `job-fz244-11090611` (8290071): `test_ail_fz244.py` (7 tests), `tests.d/test_ail_fz244.txt`, DIFFERENCES row `C?-job-fz244-11090611-1`, DEVLOG entry, manifest pins (`--check` clean). Tests on the final commit: `test_ail_fz244` 7 OK, `test_ail_safetynet` 5 OK, `test_ail_files` 18 OK (1 skip), `test_ail_corpus_findings3` 2 OK.
[commandcode stop=end_turn turns=57 out_tokens=38921]

## review 0
[model commandcode/deepseek-v4.1-flash]
**What the diff really does:** no compiler or runtime change. It adds a test module (`test_ail_fz244.py`, 7 tests, both builds), registers it in `tests.d/`, adds a DIFFERENCES "no difference" row, a DEVLOG entry, and two manifest pins. Matches the report.

**Reproduction check**
- `lab/fuzz/run.py --start 2076520850 --count 1 --modes default,ir` → `refused` 1 / `refused` 1, 0 DIFF. Verified.
- Full seed compiles to exit 3, both default and IR, and on the base worktree too: `p.ail:53:9: not in the subset: a constant integer expression overflows int64`. So the reported DIFF does not reproduce, and the refusal is pre-existing, not introduced. Verified.
- `--exact-int`: seed builds, 32 stdout lines, exit 1, identical to CPython on default and IR. Verified.

**My probes** (`bash ~/tools/cmp.sh <p> $PWD`, HEAD and base)
- `p_sort_bound` — keyed sort at ±9223372036854775807, empty list, duplicates, via arg / list item / attribute / dict value, 8 doublings: same stdout both builds.
- `p_sort_scale` — exact seed construct at full 20 doublings (2,097,152 elements), called with `a=91,b=INT64_MAX`: same stdout both builds.
- `p_sort_obj2` — `list[object]`, float list, reverse, aliasing (`x = box[0]`, `d['k']`): same.
- `p_full_ok` — seed minus the out-of-range constant: same stdout, exit 1, general and default.
- `p_sort_min` — `-INT64_MIN` inside the key: **DIFF** (AIL loud `OverflowError` exit 1 vs CPython `[1, 0, -9223372036854775808]`), **identical on base** → pre-existing declared int64 contract.
- `p_shift` — out-of-range constant alone: exit 2 load-time, vs exit 3 in the seed; **identical on base** → pre-existing, as the worker reported.
- A no-feature program needs no C comparison: the diff touches no compiler/runtime file.

**Claim audit:** "no repro / refused by name" verified; "run.py classes refused/refused" verified; "--exact-int matches 32 lines, exit 1, both builds" verified; "minimized sort + routes match" verified by my own probes; "q_refuse_shift exit 2" verified (pre-existing); "manifest `--check` clean" verified; "tests 7 OK, safetynet 5 OK" verified by re-running those two modules; `test_ail_files` / `test_ail_corpus_findings3` not re-run (out of reviewer scope) → **unverified**.

**Pre-existing** (identical on `/tmp/base`, does not block): `-INT64_MIN` in a sort key raises the loud int64 overflow (exit 1) instead of CPython's value; out-of-range constants report exit 2 at load time but exit 3 "not in the subset" when inside a larger program (worker's "other difference", correctly flagged).

**Unverified:** the original fuzz-run root cause — a sort comparing a boxed `object` with `int` — is never explained; it is merely masked by the unrelated pre-existing constant refusal, so it could still exist on a program that reaches that path. I could not reproduce it on this tree with 2M-element keyed sorts over `list[int]`/`list[object]`. No `icount` run: no hot code changed.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=24 out_tokens=15137]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T22:46:15Z
