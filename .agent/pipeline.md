# job job-std_cmath-11020039  started 2026-11-01T15:46:25Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Done.

- Added `cmath` support (12/12 lab programs build; all match CPython stdout/exit) via `cmathlib.py` + `prelude_cmath.py`, including CPython-compatible complex repr, arithmetic and hash.
- `RESULTS.md` records the before/after refusals; `DIFFERENCES.md` and `DEVLOG.md` updated.
- Generated surface for all 10 `lab/compare` tasks is byte-identical to HEAD (verified by diffing `python_surface` output).
- Probes: `pcm1`, `pforms`, `pflow`, `pnum`, `pspecial`, `pstrings`, `phash`, `phash2` — all pass on forced-general and default builds.
- Tests on final commit: `test_ail_std_cmath`, `test_ail_stdlib5`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all OK (1 Windows-target skip).
- Manifest check passes. Commit `7cdf71f` on `job-std_cmath-11020039`.
[cost $0.0365, opencode tokens {"total": 2565902, "input": 108146, "output": 7526, "reasoning": 14134, "cache.write": 0, "cache.read": 2436096}]
    tool time: bash 83.9 min, write 0.0 min
       1528s bash   cd AIL_CURRENT && python3 -m unittest -v test_ail_std_cmath test_ail_stdlib5 > /tmp/testA.log 2>&1; rc=$?; tai
       1465s bash   cd AIL_CURRENT && timeout 1800 python3 -m unittest -v test_ail_std_cmath 2>&1 | tail -30
       1168s bash   cd AIL_CURRENT && python3 -m unittest -v test_ail_safetynet test_ail_files test_ail_corpus_findings3 > /tmp/te
        268s bash   cd /tmp/probes && printf '%s\n' pcm1 pforms pflow pnum pspecial pstrings phash phash2 | xargs -P2 -I{} bash -c
        129s bash   bash ~/tools/cmp.sh /tmp/probes/phash.py "$PWD" | tee /tmp/probes/phash.cmp
        128s bash   bash ~/tools/cmp.sh /tmp/probes/phash.py "$PWD" | tee /tmp/probes/phash.cmp
        113s bash   python3 - <<'PY' import random, math random.seed(12345) pairs=[] for _ in range(120):     a=random.uniform(-1e
        112s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/prelude_cmath.py') t=p.read_text(

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Adds `cmathlib.py` + `prelude_cmath.py`, lowering `cmath`, complex literals and `complex(...)` onto a new `_AilComplex` class on the general path. The 12 lab programs do build and match CPython.

**Probes** (in `/tmp/rprobes`, run with `cmp.sh` on HEAD; every base build refuses `cmath`/complex by name, so no difference here is pre-existing):
- `p_pow.py` — DIFF (defects 1–2)
- `p_special.py` — DIFF (defect 3); the other 207 special-value lines match
- `p_complex2.py` — DIFF (defects 4–7)
- `p_forms.py` — DIFF (defect 8)
- `p_repr.py` — same stdout, both builds
- `p_plain.py`, `lab/compare/src/berth_sim/main.py` — `program.c` byte-identical to `/tmp/basework`

**Defects**
1. `p_pow.py`: `(2+0j) ** float('inf')` (also `-inf`, `nan`) — CPython `(nan+nanj)`; AIL `ValueError: cannot convert float NaN to integer` (`math.floor` in `_AilComplex.__pow__`).
2. `p_pow.py`: `0j ** -1` — CPython `ZeroDivisionError: 0.0 to a negative or complex power`; AIL `ZeroDivisionError: complex division by zero`.
3. `p_special.py`: `cmath.log(2.0, 1.0)` — CPython `ValueError: math domain error`; AIL `ZeroDivisionError: complex division by zero` (wrong exception type).
4. `p_complex2.py`: `complex(real=1+2j)` — CPython `(1+2j)`, AIL `TypeError`; `complex(1+2j, 3)` — CPython `(1+5j)`, AIL `TypeError`.
5. `p_complex2.py`: `cmath.rect(1+0j, 0.0)` — CPython `TypeError: must be real number, not complex`; AIL prints `(1+0j)`.
6. `p_complex2.py`: `cmath.isclose(1.0, 1.0, 1e-9)` — CPython `TypeError: isclose() takes exactly 2 positional arguments (3 given)`; AIL returns `True` (tolerances must be keyword-only).
7. `p_complex2.py`: wrong messages: `complex("++1j")`, `complex("1++2j")` → CPython `ValueError: complex() arg is a malformed string`, AIL `could not convert string to float: '+'`/`'1+'`; `complex("1", 2)` → CPython `complex() can't take second arg if first is a string`, AIL generic message; `complex(1, "2")` → CPython `complex() second arg can't be a string`, AIL generic; `cmath.sqrt("4")` → CPython `must be real number, not str`, AIL `complex() argument must be a string or a number, not 'str'`.
8. `p_forms.py`: `cmath.log(8.0, base=2.0)` — CPython `TypeError: cmath.log() takes no keyword arguments` (exit 1); AIL prints `(3+0j)` (exit 0).

**Report claims**
- 12/12 build and match: verified (`test_ail_std_cmath` PASS, 599.9 s).
- repr/arithmetic/hash: repr verified; arithmetic false at power/infinity edges (1–2); hash not independently verified.
- `lab/compare` C byte-identical: verified for `p_plain`, `berth_sim`, `echo_pack`, `ledger_bin`, `term_rank`, `ticket_audit`; the other 5 fail to compile identically on base.
- RESULTS/DIFFERENCES/DEVLOG/tests.d: verified. Manifest `--check`: rc=0. Tests `test_ail_std_cmath`, `test_ail_safetynet`: PASS. Commit `7cdf71f`: verified.
- “all probes pass”: their probes were not rerun; the counterexamples above lie outside them.

**Pre-existing:** `chain_relax`, `rail_transfer`, `scar_life`, `tally_lang`, `tree_fold` (`lab/compare` `main.py`) fail to compile identically on base (e.g. `int64 literal out of range`) — not caused by this change.

**Unverified:** full suite; hash/dict behaviour beyond their probes; those 5 compare surfaces; speed (change is not hot code).

VERDICT: FIX
[cost $0.0429, opencode tokens {"total": 1682181, "input": 96662, "output": 8746, "reasoning": 30789, "cache.write": 0, "cache.read": 1545984}]
    tool time: bash 13.7 min, read 0.0 min
        480s bash   cd /home/runner/work/_temp/w2 && rm -rf /tmp/cmpAll && mkdir -p /tmp/cmpAll && fail=0; for t in lab/compare/ta
        130s bash   cd /tmp/rprobes && printf '%s\n' p_pow p_repr p_forms p_complex p_special | xargs -P2 -I{} bash -c 'bash ~/too
        120s bash   sleep 120; tail -8 /tmp/rev_tests.log; ps -p $(cat /tmp/rev_tests.pid) >/dev/null && echo RUNNING || echo DONE
         66s bash   cd /tmp/rprobes && printf '%s\n' 'HEAD p_complex2' 'BASE p_pow' 'BASE p_special' | xargs -P2 -I{} bash -c 'set
         26s bash   mkdir -p /tmp/cmpC2/head /tmp/cmpC2/base && cp /home/runner/work/_temp/w2/lab/compare/src/berth_sim/main.py /t
          1s bash   mkdir -p /tmp/cmpC/head /tmp/cmpC/base && cp /tmp/rprobes/p_plain.py /tmp/cmpC/head/ && cp /tmp/rprobes/p_plai
          0s bash   cd /home/runner/work/_temp/w2 && python3 tools/update_manifest.py --check > /tmp/manifest_check.log 2>&1; echo
          0s bash   cd /home/runner/work/_temp/w2 && git worktree add /tmp/basework work 2>&1 | tail -3; ls /tmp/basework | head

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed all 8 review defects and committed as `84f2280`.

Changes:
- `z ** n`: finite-only integer fast path; inf/NaN exponents give CPython's `(nan+nanj)`; zero base with negative/complex exponent raises `0.0 to a negative or complex power`.
- `cmath.log(z, base)` raises `ValueError: math domain error` for a zero base logarithm.
- `complex(...)`: CPython `complex_new` semantics (`real=` alone, two-arg combination, signed zeros, exact TypeError texts).
- `cmath.rect` is real-only; all `cmath` args use `must be real number, not <type>`.
- `cmath` keyword calls are rejected with `cmath.<name>() takes no keyword arguments`; `isclose` tolerances are keyword-only and a third positional argument is rejected.
- Malformed complex strings (`++1j`, `1++2j`, etc.) raise `complex() arg is a malformed string`.
- Added `test_review_regressions` to `test_ail_std_cmath.py`.

Verification (on `84f2280`):
- Probes `p_pow`, `p_special`, `p_complex2`, `p_forms` and the earlier `pcm1`, `pforms`, `pflow`, `pnum`, `pspecial`, `pstrings`, `phash`, `phash2`: **g and d match CPython**.
- `lab/compare` generated C: 5 built tasks byte-identical (`berth_sim`, `echo_pack`, `ledger_bin`, `term_rank`, `ticket_audit`); the other 5 fail identically on base (not compared).
- Tests: `test_ail_std_cmath` OK (2 tests, 614.7s), `test_ail_safetynet` OK, `test_ail_files` OK (1 skipped), `test_ail_corpus_findings3` OK.
- `update_manifest.py --check`: rc=0.
[cost $0.0715, opencode tokens {"total": 6166484, "input": 156085, "output": 17514, "reasoning": 32821, "cache.write": 0, "cache.read": 5960064}]
    tool time: bash 31.2 min, edit 0.0 min, read 0.0 min
        615s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && printf '%s\n' test_ail_std_cmath test_ail_safetynet test_ail_file
        391s bash   cd /tmp/probes && printf '%s\n' pcm1 pforms pflow pnum pspecial pstrings phash phash2 p_pow p_special p_comple
        237s bash   cat > /tmp/cmpAll.sh <<'EOF' #!/bin/bash t=$1 root=/tmp/cmpAll mkdir -p $root/head/$t $root/base/$t AIL_NO_CAC
        192s bash   cd /tmp/probes && printf '%s\n' p_complex2 p_pow p_special p_forms pforms pstrings | xargs -P2 -I{} bash -c 'b
        155s bash   cd /tmp/probes && printf '%s\n' pflow pnum pspecial phash | xargs -P2 -I{} bash -c 'bash ~/tools/cmp.sh /tmp/p
        117s bash   cd /tmp/probes && printf '%s\n' p_pow p_special p_complex2 p_forms | xargs -P2 -I{} bash -c 'bash ~/tools/cmp.
         61s bash   cd /tmp/probes && bash ~/tools/cmp.sh /tmp/probes/p_complex2.py /home/runner/work/_temp/w2 2>&1 | tail -20
         44s bash   cd /tmp/tkw && cat > k3.py <<'EOF' import cmath def raise_it(msg, *args):     raise TypeError(msg) try:     ra

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change really does.** Commit `84f2280` adjusts the `cmath` prelude/lowering: complex `**` routes non-finite exponents through `_ail_cm_pow`, zero bases raise CPython's power error, `cmath.log(z, base)` rejects a zero log-base, `complex()` follows `complex_new`, `cmath` arguments are type-checked, and keyword calls are lowered to runtime `TypeError`s. No compiler/runtime change outside this path.

**Probes** (in `/tmp/rprobes`, run with `cmp.sh`; g and d agree with each other throughout):
- `p_log2`, `p_ctor2`, `p_args2`, `p_parse2` — **same stdout** as CPython (base-vs-log, constructor forms/messages, malformed strings, argument types, keyword/isclose rules).
- `p_pow2`, `p_pow3` — **DIFF** (defect 1).
- `p_star2` — **DIFF** (defect 2).
- `p_types2` — DIFF only in type names (pre-existing resolver, below).
- `p_plain2` and `lab/compare` `berth_sim`, `echo_pack`, `ledger_bin`, `term_rank`, `ticket_audit` — `program.c` byte-identical to `/tmp/basework` (`work`).
- Worker's original probes `p_pow`, `p_special`, `p_complex2`, `p_forms`: same stdout (8 review defects fixed).

**Defects**
1. Non-finite exponents are still wrong for bases whose argument is non-zero. `_ail_cm_pow` lets `math.cos(inf)`/division raise `ValueError`/`ZeroDivisionError: float division by zero`; CPython maps this to `ZeroDivisionError: 0.0 to a negative or complex power`.
   ```python
   import cmath
   try: print(2j ** float("inf"))
   except Exception as e: print(type(e).__name__ + ": " + str(e))
   ```
   Expected `ZeroDivisionError: 0.0 to a negative or complex power`; actual `ValueError: math domain error`. Same for `2j ** -inf`, `(1+1j) ** inf`, `(-2+0j) ** inf`, `(2+0j) ** complex(0.0, inf)` (actual `ZeroDivisionError: float division by zero`), etc. The report's "inf/NaN exponents give `(nan+nanj)`" is false in general.
2. The new keyword-rejection lowering mishandles `**mapping`: `cmathlib.py:145` only excludes `ast.Starred` positional arguments, not keywords with `arg is None`.
   ```python
   import cmath
   print(cmath.isclose(1.0, 1.0, **{}))
   ```
   Expected `True`; actual `TypeError: 'None' is an invalid keyword argument for isclose()`. Likewise `cmath.sqrt(**{})`: expected `TypeError: cmath.sqrt() takes exactly one argument (0 given)`; actual `TypeError: cmath.sqrt() takes no keyword arguments`.

**Report claims.** 8 defects fixed: verified. `log` base / `complex()` / malformed strings / explicit keyword rejection: verified. `lab/compare` 5 C files identical: verified. `test_ail_std_cmath` + `test_ail_safetynet`: pass (760 s). Manifest `--check`: rc=0. "all cmath args use ... not `<type>`": false for user types (below). `test_ail_files` and `test_ail_corpus_findings3`: unverified (not rerun, per scope).

**Pre-existing.** `_ail_cm_tname` falls back to `"object"`, so `cmath.sqrt(Thing())` says `not object` where CPython says `not Thing` (and a function gives `not object` vs `not function`); the fallback predates this commit. The other `lab/compare` tasks fail to compile on base too.

**Unverified.** Earlier worker probes `pcm1`/`pforms`/`pflow`/`pnum`/`pspecial`/`pstrings`/`phash`/`phash2` (not rerun); speed (no hot code touched); full suite.

VERDICT: FIX
[cost $0.0374, opencode tokens {"total": 1728757, "input": 84863, "output": 11965, "reasoning": 21049, "cache.write": 0, "cache.read": 1610880}]
    tool time: bash 17.4 min
        325s bash   cmp /tmp/cmpdep/head/dd/program.c /tmp/cmpdep/base/dd/program.c && echo PLAIN_C_IDENTICAL; cd /home/runner/wor
        149s bash   cd /tmp/rprobes && python3 - <<'PY' from pathlib import Path p=Path('p_ctor2.py') t=p.read_text() t=t.replace(
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && (python3 ../tools/par_check.py -j 2 test_ail_std_cmath test_ail_s
        120s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && setsid nohup bash -c 'python3 ../tools/par_check.py -j 2 test_ail
        103s bash   ls /tmp/probes 2>/dev/null | head -20; cd /tmp/probes 2>/dev/null && for p in p_pow p_special p_complex2 p_for
         66s bash   cat > /tmp/rprobes/p_types2.py <<'EOF' import cmath   class Thing:     pass   def fn(x):     return x + 1   de
         62s bash   cd /tmp/rprobes && for p in p_pow2 p_log2 p_ctor2 p_args2 p_parse2; do (bash ~/tools/cmp.sh /tmp/rprobes/$p.py
         51s bash   cd /tmp/rprobes && python3 - <<'PY' from pathlib import Path p=Path('p_pow2.py') t=p.read_text() t=t.replace('

FINAL VERDICT: FIX  2026-11-01T18:52:48Z
