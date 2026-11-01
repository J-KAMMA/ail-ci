# job job-decexact2-11011010  started 2026-11-01T01:12:22Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0840, opencode tokens {"total": 9645490, "input": 181625, "output": 20701, "reasoning": 26844, "cache.write": 0, "cache.read": 9416320}]
    tool time: bash 87.5 min
       2111s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_stdtop1 test_ail_int64_default test_
        563s bash   cd /home/runner/work/_temp/w2 for task in $(ls lab/compare/src); do for file in main.ail main.py; do syn=ail; 
        377s bash   cd /home/runner/work/_temp/w2 for task in berth_sim echo_pack ledger_bin term_rank ticket_audit; do echo "====
        300s bash   cd /home/runner/work/_temp/w2 && for f in p_dec_accept p_dec_ops p_dec_args p_dec_str2 p_dec_module p_frac2 p_
        270s bash   cd /home/runner/work/_temp/w2 && env -u AIL_EXACT_INT python3 AIL_CURRENT/test_ail_stdtop1.py 2>&1 | tail -40;
        225s bash   cd /home/runner/work/_temp/w2 for name in dec_int_big dec_pow_int frac_int_big dec_user_int64 dec_user_parse d
        205s bash   cd /home/runner/work/_temp/w2 && python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/test_ail_stdto
        201s bash   cd /home/runner/work/_temp/w2 && python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/test_ail_stdto
(cut off after 100 minutes)

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review report

**What the change really does (one line):** adds `cx->exact_depth`; generated Decimal/Fraction prelude functions/methods increment it on entry and decrement on both normal and error exits; the int64 overflow handlers and the `int()` conversion paths stop loudly when depth is 0; `pyboxed2.build` keeps the big-int runtime (`mode='on'`) for any program whose source contains the Decimal/Fraction prelude.

**Checked / verified**
- `p_accept` (all 6 acceptance lines), `p_frac`, `p_paths` (arg/list/dict/attribute), `p_fint`, `p_intvis`: match CPython on both `g` and `d`; `int(Decimal("-1e30"))` and `int(Fraction(2)**100)` stop with `OverflowError: integer overflow in int()`.
- `p_use_then_user`: user `INT64_MAX+1` still stops loudly after Decimal use (intended).
- `p_nouse` (no Decimal): `--debug-dir` `program.c` is byte-identical HEAD vs base `/tmp/base_w2` at `e466453`.
- `par_check -j 2 test_ail_stdtop1 test_ail_int64_default test_ail_safetynet`: all 3 pass (720s/725s/181s).
- Report/DEVLOG/DIFFERENCES claim "ints handed back to the program follow its mode" is **false** (see defect).
- Pre-existing: `p_excleak` compile timed out on **both** HEAD and base under the current machine load (cf. `ps`: several other jobs), so not attributable.

**Defect (introduced by this change: base cannot even compute these values)**
1. Big ints still escape the library into user code silently, violating "user-visible ints out of Decimal follow the user mode: they stop loudly if they exceed int64" and the Fraction prelude's own declared difference ("numerator or denominator beyond [int64] is an OverflowError").
   - Probe `/tmp/rprobes/p_dec_big_arith.py`:
     ```python
     from decimal import Decimal
     r = (Decimal(2) ** 100).as_integer_ratio()
     print(r[0] + 1)
     print(r[0] * r[1])
     ```
     Expected (default int64 mode): exit 1, `OverflowError: integer overflow in int()`-style stop (or a named compile refusal). Actual: prints `1267650600228229401496703205377` and a 61-digit product, exit 0. `print((Decimal(2)**100).as_integer_ratio())` and `print((Fraction(2)**100).numerator)` likewise hand big ints to user code, which then does arbitrary big arithmetic at depth 0. Only `int()`/`__index__`/`__trunc__` results are guarded; `as_integer_ratio` and Fraction `numerator`/`denominator` are not.

**Unverified**
- Byte-identical C for all 10 `lab/compare` tasks (only the small non-Decimal `p_nouse` was diffed).
- An explicit runtime probe that an exception inside Decimal/Fraction leaves `exact_depth` at 0 (generated C shows `ail_exact_leave` before both `AIL_FRAME_LEAVE` exits, so this looks correct).
- The worker's own `/tmp/probes` files.

VERDICT: FIX

1. Library big ints escape to user code via `Decimal.as_integer_ratio` and `Fraction.numerator`/`denominator`; see probe above — expected a loud int64 stop, actual prints big ints and continues (exit 0).
[cost $0.0265, opencode tokens {"total": 1140294, "input": 66465, "output": 6600, "reasoning": 15709, "cache.write": 0, "cache.read": 1051520}]
    tool time: bash 31.4 min
        542s bash   cat > /tmp/rprobes/p_escape.py <<'EOF' from decimal import Decimal from fractions import Fraction d = Decimal(
        333s bash   cd /home/runner/work/_temp/w2 && for p in p_accept p_frac p_paths p_use_then_user p_nouse; do echo "===== $p";
        300s bash   cat > /tmp/rprobes/p_intvis.py <<'EOF' from decimal import Decimal from fractions import Fraction print(int(De
        150s bash   cd /tmp && rm -rf /tmp/leakbase && mkdir /tmp/leakbase && cp /tmp/rprobes/p_excleak.py /tmp/leakbase/p.ail && 
        120s bash   cd /home/runner/work/_temp/w2 && rm -f /tmp/tests.log && nohup python3 tools/par_check.py -j 2 test_ail_stdtop
        120s bash   cd /tmp && rm -rf /tmp/leak && mkdir /tmp/leak && cp /tmp/rprobes/p_excleak.py /tmp/leak/p.ail && cd /tmp/leak
         90s bash   sleep 90; date; tail -10 /tmp/tests.log; pgrep -af "par_check.py -j 2 test_ail_stdtop1" | head
         77s bash   cd /tmp && rm -rf /tmp/dbgA && mkdir /tmp/dbgA && cp /tmp/rprobes/p_accept.py /tmp/dbgA/p.py && cd /tmp/dbgA &

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
(no final text)
[cost $0.0577, opencode tokens {"total": 6202305, "input": 139205, "output": 12224, "reasoning": 19004, "cache.write": 0, "cache.read": 6031872}]
    tool time: bash 48.2 min
        865s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_int64_default test_ail_stdtop1 test_
        429s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_int64_default test_ail_stdtop1 2>&1 
        426s bash   cd /tmp/probes && for p in p_dec_ratio p_dec_ratio_print p_frac_num p_frac_den p_frac_ratio p_small p_arg p_li
        351s bash   cd AIL_CURRENT && python3 - <<'PY' from pathlib import Path p=Path('test_ail_stdtop1.py') s=p.read_text() s=s.
        204s bash   mkdir -p /tmp/cdcheck && cd /tmp/cdcheck && cat > run.sh <<'EOF' #!/bin/bash set -u task=$1 extra="" case "$ta
        120s bash   cd /home/runner/work/_temp/w2 && rm -f /tmp/tests2.log && nohup python3 tools/par_check.py -j 2 test_ail_int64
         89s bash   cd /tmp/probes && rm -rf /tmp/exprobe && mkdir /tmp/exprobe && cp p_exact.py /tmp/exprobe/p.py && cd /tmp/expr
         80s bash   cd /tmp/dbg1 && rm -rf dbg && python3 -B /home/runner/work/_temp/w2/AIL_CURRENT/ail_chatgpt.py compile p.py --
(cut off after 60 minutes)

## review 1
[model opencode-go/deepseek-v4.1-flash]
## Review: `job decexact2` (Decimal/Fraction exact internals in int64 mode)

**What the change really does.** Adds `exact_depth` to the runtime: overflow in `+ - * unary- // << **` and int-from-string construction promotes to a big int only when `exact_depth > 0` (or in `--exact-int`, where `main` starts it at 1). A program using Decimal/Fraction is forced onto the big-int runtime (`pyboxed2.build`); prelude functions/methods enter/leave the depth and scan their return value for a big int when leaving to user code. Fraction's fields become `_n`/`_d` with `numerator`/`denominator` properties. This matches the report.

**Verified (probes run with `cmp.sh` on HEAD and `/tmp/base_w2`):**
- Acceptance values (`p_accept`): both builds match CPython for `1/3`, `sqrt`, `10.50*3`, `2**100`, prec 50, `1e30+1`, Fraction cases.
- Visible ints: `int()`, `__int__`, `__trunc__`, `__floor__`, `__ceil__`, `as_integer_ratio`, `.numerator`, `.denominator`, `round(Decimal(...))` stop loudly in int64 mode; `int(Decimal(2)**62)` works, `**63` stops, `INT64_MIN` works. `as_tuple` refused by name identically to base (pre-existing).
- Exact mode: `p_ratio_dec`, `p_num`, `p_int_dec`, `p_userbig2` with `AIL_EXACT_INT=1` match CPython.
- No depth leak after a Decimal exception; user code still stops on `x**100` after a Decimal call.
- No-Decimal C: `program.c` byte-identical base vs HEAD for all 10 `lab/compare` `main.ail` and the 6 `main.py` that build; report JSON differs only in temp paths.
- Tests: `test_ail_int64_default`, `test_ail_stdtop1`, `test_ail_safetynet` all pass (542 s); `update_manifest.py --check` clean.

**Claims / false:** DEVLOG/DIFFERENCES say `int()`, `__trunc__`, `__floor__`, `__ceil__`, `__round__` and `as_integer_ratio` are "covered by the same return check". False: the guard is inserted only before the function's final `return AIL_OK` (`pyboxed2.py:4263-4267`), so source-level early returns bypass it.

### Defects
1. Big ints escape to user code through prelude early returns, enabling arbitrary-precision *user* arithmetic (the behaviour the task forbids).
   - `p_roundfrac.py`: `print(round(Fraction(2) ** 100))` — expected named stop (base: `OverflowError: integer overflow in **`); actual HEAD: exit 0, prints `1267650600228229401496703205376`.
   - `p_floordivfrac.py`: `print((Fraction(2) ** 100) // 1)` — expected stop; actual prints the big int, exit 0.
   - `p_dec_mathfloor.py`: `math.floor(Decimal(2) ** 100)` / `math.ceil(...)` — expected stop; actual prints `1267650600228229401496703205000` (the `_ail_dec_floor` helper's early return leaks it).
   - `p_leaktyped.py`: leaked `n = (Fraction(2)**100) // 1` then `print(add(n, 1))` — expected stop; actual prints `1267650600228229401496703205377` (base stopped). Same leak works through a list item, dict value and `n+1`, `n*2`, `n%7`.
   Cause: `Fraction.__floordiv__`/`__round__` (and the stdtop `_ail_dec_floor`/`_ail_dec_ceil` helpers) return from inside `if` branches; only the tail return gets `ail_exact_visible`.
2. Minor: `Fraction(1,2).numerator = 3` silently succeeds and has no effect; CPython raises `AttributeError`. Base also differed (it allowed it with effect), so this is a new mismatch, not a fixed defect.

**Pre-existing:** `Decimal.as_tuple()` refused by name on both base and HEAD; `Fraction.numerator` assignment was already non-CPython on base.

**Unverified:** gdev `icount` runs (non-Decimal `program.c` is byte-identical, so no run-count change expected); Decimal paths beyond those probed.

VERDICT: FIX
1. Apply the `exact_depth == 1` visibility check to every successful return of a Decimal/Fraction prelude function, not only the final tail return (at minimum `Fraction.__floordiv__`, `Fraction.__round__`, `Fraction.__hash__`, and the stdtop `_ail_dec_floor`/`_ail_dec_ceil` helpers); otherwise `round(Fraction(2)**100)`, `(Fraction(2)**100)//1`, `math.floor/ceil(Decimal(2)**100)` print big ints and user code then computes with them exactly in int64 mode. Expected: loud `OverflowError: integer overflow in int()` (exit 1); actual: exit 0 with the big value printed.
[cost $0.0400, opencode tokens {"total": 2647079, "input": 99057, "output": 9222, "reasoning": 20144, "cache.write": 0, "cache.read": 2518656}]
    tool time: bash 51.2 min
        608s bash   cd /tmp/rprobes && for p in p_accept p_int_dec p_int_frac p_ratio_dec p_ratio_frac p_num p_den p_round p_trunc
        543s bash   cd /home/runner/work/_temp/w2 && timeout 1500 python3 tools/par_check.py -j 2 test_ail_int64_default test_ail_
        470s bash   cd /tmp && rm -rf cdiff && mkdir cdiff && cd cdiff && for f in /home/runner/work/_temp/w2/lab/compare/src/*/ma
        341s bash   cd /tmp/rprobes && for p in p_roundfrac p_mathfloorfrac p_floordivfrac p_intfrac p_num p_floor2 p_ratio_frac p
        330s bash   cd /tmp/rprobes && cat > p_boundary.py <<'EOF' from decimal import Decimal from fractions import Fraction prin
        243s bash   cd /tmp/rprobes && cat > p_floor2.py <<'EOF' from fractions import Fraction print((Fraction(2) ** 100).__floor
        123s bash   cd /tmp/rprobes && for n in p_dec_mathfloor p_decint p_divmodfrac p_roundfrac2; do :; done cat > p_dec_mathflo
         99s bash   cd /tmp/rprobes && cat > p_leak2.py <<'EOF' import sys from decimal import Decimal try:     Decimal(1) / Decim

FINAL VERDICT: FIX  2026-11-01T05:45:25Z
