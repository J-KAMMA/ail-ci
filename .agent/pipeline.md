# job job-rails2_rr1-11062252  started 2026-11-06T14:01:29Z  worker=chain reviewer=chain (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Done. Final report:

**What I applied:** fetched `origin/job-rails2-11031344`, cherry-picked `a5517c28` ("worker: uncommitted edits") cleanly onto this branch, skipped `b43b6b3b` ("agent worker report"). That branch's log shows the run was cut off with no review — so its runtime work was never verified.

**Measurement:** `perf_event` is dead on this runner (paranoid=4, no PMU hardware event source). I used callgrind Ir, and validated the method by reproducing the design numbers exactly on the pre-change tree: p0 2.26M, p1 84.5M (`input()` 453/line), p2 147.6M (`.split()` 350/line), p3 210.1M (4×`int()` 345/line), matching `rail-design.md`.

**p3.ail on q0.in (180,389 lines), per line:**

| piece | before | after |
|---|---|---|
| `input()` (decode+memchr) | 453 | 71 |
| `.split()` | 350 | 256 |
| 4×`int()` + loop + keep_roots | 345 | 336 |
| loop floor (p0) | 12 | 12 |
| **total** | **1,164 (210.1M)** | **830 (149.7M)** |

-4.92% is split 256 (30.9%), int/loop 336 (40.5%), line copy 80, arena 59 — no single piece under 15%.

**Changes (3 commits):** the branch's four fast paths (one-pass copy+classify in `ail_utf8_decode`, single-block release in `ail_sarena_keep_roots`, ASCII fast path + spine reuse in `ail__str_split_ws_scan` with `ail_str_split_ws_into`, inline 1-18-digit `ail_str_to_int`), plus two of mine on the same path: split pieces written straight into the vector (no 32-offset stack list + second pass, -2.4%) and an overlapping 8-byte word for the line tail (-2.6%). Together -4.92%, which reaches the named 150M; `ail_slist_get` was already inlined by GCC, so that sub-step had nothing to do.

**Tests, final commit `c43b4673`:** new `test_ail_stdin_split_fast.py` (6 tests, registered in `tests.d/`, manifest `--check` exit 0) covering tabs, CRLF, blanks, empty lines, no final newline, 40 fields, U+3000/U+00A0, `-0`/`+5`/`007`, 18/19/20 digits, both int64 ends, 2**70 (loud stop / exact), EOFError, UnicodeDecodeError — default and `AIL_UNIFIED_FORCE=1`. Also green: `test_ail_stdin_list_batch`, `test_ail_splitlines_utf8`, `test_ail_int64_default`, `test_ail_int64_edges`, `test_ail_hostile_input`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

**Probes:** `split_containers.py` (list item, dict value, attribute, argument, 40 fields, U+3000/U+00A0) — both builds match CPython; `int_forms.py` (`-0`,`+5`,`007`, 18 digits, int64 ends through a dict/attribute/argument) — both builds match; `stdin_split.py` (tabs, CRLF, blanks, no final `\n`) — default/force/exact all match; `int_overflow.py` — default stops loudly at 2**70 with `OverflowError`, stdout unchanged before it.

**Not done:** `tools/par_check.py` and the 20 CI shards (job rules forbid running the whole suite locally; that's CI's job). Invalid UTF-8 has no CPython twin here — CPython's stdin uses `surrogateescape`, so the test asserts the documented stop (C?-diffs3-3) instead.
[commandcode stop=end_turn turns=94 out_tokens=61839]

## review 0
[model commandcode/deepseek-v4.1-flash]
Both targeted modules pass. I have enough to report.

**What the change really does** (one line): it makes the per-line stdin path cheaper in the shared C runtime — `ail_utf8_decode` copies+classifies a line in one word pass, `ail_sarena_keep_roots` releases the single new block inline, `ail__str_split_ws_scan` gets an ASCII-only scan plus reuse of the destination spine (`ail_str_split_ws_into`, emitted for `str_split_ws` rebinds), and `ail_str_to_int` inlines the 1–18-digit parse. That matches the report.

**Speed (measured myself, callgrind Ir; `perf_event_open` returns ENOENT here, so `tools/icount.c` cannot run):** p3.ail on a regenerated q0.in (180,389 4-int lines): 210,633,447 → 150,695,774 (**-28.5%**, 1,167 → 835 per line), stdout identical (180555394168). The report's 210.1M → 149.7M is consistent; on my input it lands just at the 150M line rather than under it, which is input-dependent, not a defect (floor was -10%).

**Probes** (`/tmp/rprobes`, each run on the default and `AIL_UNIFIED_FORCE=1` builds vs CPython 3.12; `run.sh` = cmp.sh with stdin):

| probe | covers | result |
|---|---|---|
| p_keep | piece kept across 3 rebinds (root retention vs the new one-block release) | match, both builds |
| p_slice | slice/concat of a piece held across rebinds | match |
| p_alias | `b = a` then rebind of `a` (spine reuse vs copy) | match |
| p_selfsplit | `f = f[0].split()` rebind, source read from destination | match |
| p_attr | field destination `self.f = line.split()` | default build match; `--strict` refuses by name |
| p_sep | `split(",")` path (untouched) | match |
| p_int | `-0`,`+5`,`007`," 42 ","1_000", 18 digits, slice, `f[0][-3:]` | match |
| p_tail | 8/9/15/16/17-byte lines, multi-byte tail (overlapping-word corner) | match |
| p_forty | 40 fields, leading/trailing blanks (count-then-fill with reuse) | match |
| p_nonascii | U+3000, U+00A0, 日本語, 33 non-ASCII pieces | match |
| p_mut | mutation during iteration: `for w in f: f = input().split()` | **differs**: `a,e,` vs CPython `a,b,c,` — **identical on base** |
| p_hello | program not using the feature | user-code C byte-identical to base; only prelude bodies differ |

`p_mut` is pre-existing (same output on `/tmp/base`); it does not even reach the new code (that rebind is lowered to the old temp+move shape, `into` count = definition only).

**Report claims:** cherry-pick/3 commits — verified by log; perf_event dead → callgrind — verified; total 1,164→830/line — verified (-28.5%, per-piece split of 256/336/71/59 **unverified**, I did not build the stub variants); "`ail_slist_get` already inlined by GCC, nothing to do" — the diff indeed doesn't touch it (claim about codegen unverified); tests green — verified for `test_ail_stdin_split_fast` and `test_ail_safetynet` on HEAD (`-j 2`, 2 modules, 0 failed, 181s). No `bench/apps` or benchmark program is edited (4a clean).

**Unverified:** the other six modules the report lists; the exact per-piece instruction attribution; the `--exact-int` 2**70 case (only via the gate module, which passed); wider suite/shards (out of scope by instruction).

**Pre-existing:** mutation during iteration (`p_mut`) prints `a,e,` where CPython prints `a,b,c,` on both base and HEAD.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=30 out_tokens=38090]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-06T15:52:47Z
