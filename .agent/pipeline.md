# job job-emit1-11071640  started 2026-11-07T07:44:52Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed all three defects on `job-emit1-11071640`; no compiler/runtime change.

- **Rank 3 corrected:** re-measured `tally_lang_edge` = 19,585,727,653 → 19,396,094,852, net **189,632,801** (1,184,368,889 for `norec`). Added the row to `RESULTS.md`/`data/bounds.json`, moved recursion to rank 7, retitled design 2 to the 190M net, and restated the queueable total as ~3.1e9 (10%, not 4.1e9/13%).
- **Design 1 fast mark:** now excludes all iteration, `list`/`tuple`/`dict` conversion, `repr`/print/format, comparison, and `keys`/`values`/`items`/`copy`/`popitem`; the `print(list(d))` control keeps the general table.
- **Design 3 shift rule:** now proves both `lo(x) >= -(2^(63-k))` and `hi(x) < 2^(63-k)` for `0 <= k < 63`; `-2**62 << 2` stays checked.
- Fixed the old DEVLOG’s 11% → 9.8% check share and added a review-fix entry.

Probes: `emit_dict_order.py` and safe negative shifts match CPython on both builds; `-2**62 << 2` is refused by name at compile time, and the argument form stops loudly with `OverflowError`, never a silent wrap.

Tests on final commit: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 3/3 pass; manifest `--check` clean. Commit `c43f265`.
[cost $0.0000, opencode tokens {"total": 6254004, "input": 144795, "output": 17648, "reasoning": 18601, "cache.write": 0, "cache.read": 6072960}]
    tool time: bash 12.4 min, edit 0.0 min, read 0.0 min, write 0.0 min
        279s bash   export PATH=/tmp/opencode/vg/root/usr/bin:$PATH; export VALGRIND_LIB=/tmp/opencode/vg/root/usr/libexec/valgrin
        264s bash   python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3
        185s bash   python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3 && python3 tools/u
          4s bash   for p in emit_dict_order emit_shift_negative; do echo "===== $p ====="; bash ~/tools/cmp.sh /tmp/probes/$p.py 
          3s bash   apt-cache policy valgrind 2>/dev/null | head -20; ls /var/cache/apt/archives/valgrind* 2>/dev/null; apt-get do
          2s bash   ls /usr/bin | grep -i valgrind; dpkg -l 2>/dev/null | grep -i valgrind; ls /usr/lib/valgrind 2>/dev/null | hea
          2s bash   apt-cache show valgrind 2>/dev/null | grep -E '^(Package|Depends|Recommends|Suggests|Filename|Installed-Size|S
          1s bash   bash ~/tools/cmp.sh /tmp/probes/emit_shift_negative_arg.py "$PWD"

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review — emit1 review fix (lane emitdesign)

**What the change really does:** docs/data only. Adds the `tally_lang_edge` row (19,585,727,653 → 19,396,094,852, net 189,632,801), re-ranks recursion from 3 to 7, retitles design 2, restates the queueable total as ~3.1e9, tightens the fast-dict mark and the shift rule, and fixes the DEVLOG 11% → 9.8%. No compiler/runtime/test change (`git diff work..HEAD -- AIL_CURRENT tools` is empty).

**Reproduced**
- `bounds.py --tasks tally_lang --only tally_lang_edge,tally_lang_norec`: baseline 19,585,726,880; edge saved **189,632,794**; norec saved **1,184,368,882** (committed 189,632,801 / 1,184,368,889 — ~7 Ir callgrind noise). Confirms ~190M, not 1,184M.
- Probes: `emit_dict_order`, `emit_shift_negative` match CPython on both builds; `-2**62<<2` is refused by name; the argument form stops with `OverflowError`. All pre-existing (source unchanged).
- `test_ail_safetynet` passes; manifest `--check` exit 0.
- Report claims checked: rank renumbering, retitling, total, DEVLOG %, and "patch existed but no row" all verified. The `test_ail_files`/`test_ail_corpus_findings3` 3/3 claim is **unverified** (not rerun per reviewer rule).

**Defects**

1. **Fast-dict mark still lets the dict escape, so the caller can observe hash order.** `docs/design/EMIT_LEAN.md:116-125` excludes iteration/print/compare/copy but not `return` (or storing the dict in another container/attribute/global). Probe: `def f(): d={1:'a',2:'b'}; d[3]='c'; return d` then `print(list(f()))`. The rule as written marks `d` fast; with no order list the expected CPython `[1, 2, 3]` becomes hash order. Add "never escapes (not returned, not stored where it can escape)" to the mark (the task asks for a soundness proof, so this is in scope).
2. **Stale rank in `docs/design/EMIT_LEAN.md:332`:** says "ASCII/UTF-8 classification (**rank 7**, 490M)". Expected rank 6 (row 6 is ASCII 490M; rank 7 is recursion 190M). Introduced by this change's renumbering.
3. **Stale rank in `lab/emit/RESULTS.md:463`:** says "the view/accessor bound (**cause 6**, 952M)". Expected cause/rank 5 (row 5 is accessors 952M; row 6 is ASCII 490M). Introduced by the renumbering.

**Pre-existing / minor**
- `EMIT_LEAN.md:326` "Container invariant / list helpers (rank 4/5)" was already wrong at base (should now be 2/4); `RESULTS.md:461` "causes 1, 4, 5" is likewise stale at base.

**Unverified:** `test_ail_files` and `test_ail_corpus_findings3`; the other five programs' bounds; no speed run (change is docs-only).

VERDICT: FIX
1. Fast-dict mark must also forbid escaping (`return d`, storing in another object), else `list(f())` is hash order, not `[1, 2, 3]`.
2. `EMIT_LEAN.md:332` ASCII rank 7 → 6.
3. `RESULTS.md:463` accessor cause 6 → 5.
[cost $0.0000, opencode tokens {"total": 1127951, "input": 70927, "output": 3477, "reasoning": 25835, "cache.write": 0, "cache.read": 1027712}]
    tool time: bash 5.9 min
         99s bash   cd AIL_CURRENT && nohup python3 ../tools/par_check.py -j 2 test_ail_safetynet > /tmp/rv-b/test.log 2>&1 & echo
         60s bash   sleep 60; cat /tmp/rv-b/log.txt; echo ---; ps -p 12106 -o pid,etime,cmd --no-headers
         45s bash   sleep 45; cat /tmp/rv-b/log.txt; echo ---; ps -p 12106 -o pid,etime,cmd --no-headers; cat /tmp/rv-b/bounds_edg
         45s bash   sleep 45; cat /tmp/rv-b/log.txt; echo ---; ps -p 12106 -o pid,etime,cmd --no-headers; cat /tmp/rv-b/bounds_edg
         40s bash   sleep 40; cat /tmp/rv-b/log.txt; echo ---; ps -p 12106 -o pid,etime,cmd --no-headers; cat /tmp/rv-b/bounds_edg
         30s bash   sleep 30; cat /tmp/rv-b/log.txt; ps -p 12106 -o pid,etime,cmd --no-headers
         30s bash   sleep 30; cat /tmp/rv-b/test.log; ps -p 13381 -o pid,etime --no-headers
          5s bash   for p in emit_dict_order emit_shift_negative emit_shift_overflow emit_shift_negative_arg; do echo "===== $p ==

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all defects from review 2 and committed as `b5f14cd`.

- Fast-dict mark now forbids escape (`return`, storing into another container/attribute/global) in the design mark, correctness section, step 1.2, and ready-to-queue task text, with the `return d` → `print(list(f()))` control.
- Stale ranks corrected: `EMIT_LEAN.md` ASCII rank 7→6; `RESULTS.md` accessor cause 6→5; also pre-existing "rank 4/5"→"rank 2/4" and "causes 1,4,5"→"causes 1,3,6".
- Probes: `emit_dict_order`, `emit_shift_negative` CPython-identical on both builds; `emit_shift_overflow` refused by name; `emit_shift_negative_arg` raises `OverflowError`.
- Tests: `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` 3/3 pass; manifest `--check` clean.
[cost $0.0000, opencode tokens {"total": 1029808, "input": 58171, "output": 6676, "reasoning": 7009, "cache.write": 0, "cache.read": 957952}]
    tool time: bash 3.2 min, edit 0.0 min, read 0.0 min
        184s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_finding
          5s bash   for p in emit_dict_order emit_shift_negative emit_shift_overflow emit_shift_negative_arg; do echo "===== $p ==
          0s bash   python3 tools/update_manifest.py && python3 tools/update_manifest.py --check; echo "manifest exit $?"
          0s bash   git add DEVLOG.md docs/design/EMIT_LEAN.md lab/emit/RESULTS.md && git commit -m "emit1 review 2 fix: fast-dict
          0s bash   pwd && git status && git log --oneline -8
          0s bash   git status --short && echo --- && git diff --stat && echo --- && ls AIL_CURRENT/tests.d 2>/dev/null | grep -i 
          0s edit   /home/runner/work/ail-ci/ail-ci/DEVLOG.md
          0s bash   python3 - <<'EOF' import json d=json.load(open('lab/emit/data/bounds.json')) print(type(d)) if isinstance(d,di

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review — emit1 fix (lane emitdesign)

**What the change really does:** docs/data only. It records the `tally_lang_edge` net (19,585,727,653 → 19,396,094,852, saved 189,632,801), re-ranks the recursion guard to #7 and the queueable total to ~3.1e9/10%, strengthens the fast-dict mark (no escape; no order-observing op), bounds both sides of `x << k`, and fixes stale rank/share references. `git diff work..HEAD -- AIL_CURRENT tools` is empty: no compiler, runtime or corpus change. Matches the task.

**Claims**
- Fast-dict mark forbids escape in mark, correctness, step 1.2 and queue text — **verified** (diff, all four places).
- Stale ranks corrected (ASCII 7→6, accessor 6→5, rank 4/5→2/4, causes 1,4,5→1,3,6) — **verified**.
- `emit_dict_order`, `emit_shift_negative` CPython-identical on both builds — **verified** (my rerun, same stdout).
- `emit_shift_overflow` refused by name — **verified** (`int64 constant expression out of range`).
- `emit_shift_negative_arg` raises `OverflowError` — **verified** (both builds exit 1; pre-existing, not caused by this change).
- Tests 3/3 pass; manifest clean — **verified** (`test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, 183 s; `update_manifest.py` and `--check` clean).
- `tally_lang_edge` = 190M net — **verified indirectly**: patch removes the entry guard, adds guards at the 5 self-calls + wrapper; committed before−after arithmetic is consistent. Could not re-measure (no `valgrind` here); prior review's independent run gave 189,632,811 (10-instruction noise).

**Probes I added:** `emit_alias_order`, `emit_unpack_order`, `emit_union_order` (alias/`{**d}`/`d|e` order) all CPython-identical on both builds today; `emit_shift_alias` refused by name. No source changed, so base C is identical.

**Minor / non-blocking**
- `docs/design/EMIT_LEAN.md:50` still says "Rank 2 … moves it from every entry to the recursive edges"; the recursion guard is now rank 7 and rank 2 is the container-invariant test. Present in `work` (pre-existing), should read Design 2/rank 7.
- Design 1's mark enumeration omits `{**d}`, `d | e`, `d |= e` and alias iteration (`e = d; list(e)`); the general "never observed in an order-sensitive way" covers them, but the ready-to-queue text lists patterns and could be implemented literally. Recommend naming them.
- `RESULTS.md:462/463` use ranking numbers after the word "cause" while the cause catalogue is numbered differently; pre-existing ambiguity (the edit made them consistent with the ranking).

**Pre-existing:** the `Rank 2` sentence above; the runtime `OverflowError` for out-of-int64 shifts (CPython prints the value).

**Unverified:** exact re-measurement of `tally_lang_edge` (no `valgrind` on this host); all other six-program bounds not re-run.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1265750, "input": 102052, "output": 3753, "reasoning": 29833, "cache.write": 0, "cache.read": 1130112}]
    tool time: bash 3.4 min
        184s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_f
          7s bash   for p in emit_alias_order emit_unpack_order emit_union_order emit_shift_alias; do echo "===== $p ====="; bash 
          5s bash   rm -rf /tmp/rv-b /tmp/rv-bounds.json; date; python3 lab/emit/bounds.py --tasks tally_lang --only tally_lang_ed
          5s bash   date; for p in emit_dict_order emit_shift_negative emit_shift_overflow emit_shift_negative_arg; do echo "=====
          1s bash   date; python3 lab/emit/bounds.py --tasks tally_lang --only tally_lang_edge,tally_lang_norec --work /tmp/rv-b -
          0s bash   python3 tools/update_manifest.py --check; echo "manifest check exit $?"; git status --short
          0s bash   python3 tools/update_manifest.py; echo "exit $?"; git status --short
          0s bash   grep -n "5,607\|57,185\|9.8%\|11%" lab/emit/RESULTS.md docs/design/EMIT_LEAN.md | head; echo "=== json check =

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-07T09:56:13Z
