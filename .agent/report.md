# job job-shparse1-11081724  started 2026-11-08T08:25:24Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed on `job-shparse1-11081724` as `2b8d7dee` (not pushed; pipeline forbids push).

- S376: 164,248 statement-parent expression segments; 164,105 CPython-eval-parseable; **164,105 identical (100%), 0 accepted-but-different, 0 parser refusals**. The 143 reference-refused are `yield` (106), `yield from` (35), starred targets (2). That is 99.9129% of all extracted nodes.
- Stage 2: on 30 fixed S376 files (13,486 segments) output is byte-identical to stage 1, 0 different/refused. Times: stage 1 1.23 s, stage 2 1.31 s; full S376 stage 1 20.6 s / 233 MB; AIL build 59.8 s.
- Probes: 83 edge expressions (f-strings incl. `=`, nested specs, bytes/raw strings, lambdas, comprehensions, displays, slices, walrus, `await`, `...`) matched stage 0, stage 1 and stage 2.
- Tests: `test_ail_selfhost_parse` plus `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass on final commit (4 modules, 297 s).
- `PARSE.md` written; no miscompile, so `MISCOMPILE.md` untouched.
[cost $0.0000, opencode tokens {"total": 8396485, "input": 86790, "output": 33055, "reasoning": 37408, "cache.write": 0, "cache.read": 8239232}]
    tool time: bash 25.9 min
        346s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_selfhost_parse test_ail_safetynet test_ail_files
        300s bash   cat > /tmp/parseprobe/scan.py <<'EOF' import ast, sys, collections paths=[l.split('  ',1)[1] for l in open('se
        299s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_selfhost_parse test_ail_safetynet test_ail_files
        120s bash   mkdir -p /tmp/parseprobe && cat > /tmp/parseprobe/scan.py <<'EOF' import ast, sys, collections, json paths=[l.
         63s bash   python3 - <<'EOF' p='selfhost/src/ailparse.py' s=open(p).read() old="""                if not self.at('NAME'):
         61s bash   python3 - <<'EOF' p='AIL_CURRENT/test_ail_selfhost_parse.py' s=open(p).read() s=s.replace("    return [p for p
         60s bash   rm -f /tmp/parseprobe/expr_drv; /usr/bin/time -f "build %e s %M KB" env AIL_NO_CACHE=1 AIL_PATH=selfhost/src p
         59s bash   cat > AIL_CURRENT/test_ail_selfhost_parse.py <<'PYEOF' """shparse1: selfhost/src/ailparse.py parses expression

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does.** Adds a new self-hosted expression parser `selfhost/src/ailparse.py` (AIL-compatible Python), stage-0 extractor/reference `selfhost/ref/expr_ref.py`, stage-1/2 driver `selfhost/drv/expr_drv.py`, a registered test, `lab/selfhost/PARSE.md`, and manifest entries. No compiler or runtime code is touched; only the listed files change. This matches the report.

**Claims checked.**
- Commit `2b8d7dee`, not pushed: verified.
- S376 headline: independently reproduced on all 376 files — 164,248 segments, 143 CPython-eval refusals (`yield`/`yield from`/starred target), **164,105 identical, 0 different, 0 parser refusals**: verified.
- `test_ail_selfhost_parse` and `test_ail_safetynet` pass (`par_check -j 2`, 131 s): verified. `test_ail_files`/`test_ail_corpus_findings3`: not re-run (per review rules), unverified.
- `tools/update_manifest.py --check`: passes. `PARSE.md` written, `MISCOMPILE.md` untouched: verified.
- Stage-2 30-file byte equality / 1.31 s and the worker's 83 probes: not independently run, unverified (the test does cover stage 2 on 20 segments + EDGE and passes).
- No programs use the feature, so no base regression probe applies; all changed files are new.

**Defects found by probing `ailparse.parse_expr` against `ast.parse(..., mode="eval")` on valid expressions** (not in S376, so the headline number is unaffected, but these are accepted-but-different, which the task forbids):

1. f-string `=` debug text drops leading whitespace. Source `f'{ x=}'`.
   Expected: `JoinedStr(values=[Constant(value=' x='), FormattedValue(value=Name(id='x', ctx=Load()), conversion=114)])`
   Actual: `JoinedStr(values=[Constant(value='x='), FormattedValue(value=Name(id='x', ctx=Load()), conversion=114)])`
   Cause: `parse_replacement_field` starts the debug slice at the first token, not at the `{`, so whitespace after `{` is lost. Same for `f'{ x + y = }'`, multiline specs, etc.

2. Empty leading `FSTRING_MIDDLE` in a format spec is dropped. Source `f'{x:{{}}}'`.
   Expected: `...format_spec=JoinedStr(values=[Constant(value=''), FormattedValue(value=Dict(keys=[], values=[]), conversion=-1), Constant(value='')])`
   Actual: `...format_spec=JoinedStr(values=[FormattedValue(value=Dict(keys=[], values=[]), conversion=-1), Constant(value='')])`
   Cause: the `txt != '' or len(values) > 0` guard in `parse_format_spec` discards the leading empty constant.

3. Bytes literals apply string (`str`) escapes. Source `b'\u0041'`.
   Expected: `Constant(value=b'\\u0041')`
   Actual: `Constant(value=b'A')`
   Related: `b'\N{BULLET}'` is refused though CPython yields `b'\\N{BULLET}'`, and `b'\400'` raises an uncaught `ValueError: bytes must be in range(0, 256)` instead of a named `ailparse:` refusal (CPython yields `b'\x00'`).

4. Uppercase `U` prefix incorrectly records `kind='u'`. Source `U'x'`.
   Expected: `Constant(value='x')`
   Actual: `Constant(value='x', kind='u')`
   Cause: `_split_string_token` lowercases the prefix, while CPython only records kind for lowercase `u`. Also affects `U'a' 'b'` and `U'a' f'{x}'`.

VERDICT: FIX
1. `f'{ x=}'` must produce `Constant(value=' x=')` before the `FormattedValue`; it produces `Constant(value='x=')`.
2. `f'{x:{{}}}'` must keep the leading `Constant(value='')` in the format-spec `JoinedStr`; it is omitted.
3. `b'\u0041'` must be `Constant(value=b'\\u0041')`, not `Constant(value=b'A')`; `b'\400'` must not raise an unnamed `ValueError`.
4. `U'x'` must be `Constant(value='x')` (no `kind`), not `Constant(value='x', kind='u')`.
[cost $0.0000, opencode tokens {"total": 1129610, "input": 59451, "output": 6629, "reasoning": 26474, "cache.write": 0, "cache.read": 1037056}]
    tool time: bash 2.6 min
        132s bash   date && cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_selfhost_parse test_ail_safe
         21s bash   date && cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && timeout 420 python3 - <<'PY' import ast, sy
          0s bash   git diff work..HEAD -- AIL_CURRENT/manifest.d && python3 tools/update_manifest.py --check; echo check_exit=$?
          0s bash   cat > /tmp/rprobes/e8.txt <<'PY' f'{x:{y!r:>{z}}}' f'{x:>{y!r}}' f'{x:{y=}}' f'{x:{y:}}' f'{x:{{}}}' f'{x:{{y}
          0s bash   cd /tmp/rprobes && sed -i "s/^f'{(yield)}'$//" e8.txt && cd /home/runner/work/ail-ci/ail-ci && python3 /tmp/rp
          0s bash   date && git log --oneline work..HEAD && git status --short && pwd && ls
          0s bash   cd /tmp/rprobes && sed -i 's/    except SyntaxError as e:/    except Exception as e:/' cmp_expr.py && cd /home
          0s bash   cat > /tmp/rprobes/e6.txt <<'PY' f(a, *b, *c) f(**a, **b) f(*a, **b) f(a, b=1, *c, d=2, **e) f(a=1, **b, c=2) 

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed all four reviewer defects in `selfhost/src/ailparse.py` and committed as `26c1aa5f` (not pushed, per brief).

Fixes:
1. f-string `=` debug text now starts just after `{`, keeping leading/trailing whitespace.
2. Format specs beginning with `{{` now keep CPython's leading empty `Constant`.
3. Bytes literals no longer apply `\u`/`\U`/`\N` str escapes; octal escapes truncate to a byte (`b'\400'`→`b'\x00'`, `b'\777'`→`b'\xff'`).
4. Uppercase `U` prefix no longer records `kind='u'`.

Verification:
- S376 stage 1 re-run: 164,248 segments, 143 CPython eval refusals, **164,105 identical, 0 different, 0 parser refusals**.
- 63-case probe over the four areas: all valid-and-accepted outputs match; only pre-existing documented `'\N{...}'` str refusal remains.
- Stage 2 on 30 fixed S376 files: 13,457 parseable segments, **byte-identical to stage 1**.
- Required tests on final commit: `test_ail_selfhost_parse`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — all pass (4 modules, 0 failed).
- `tools/update_manifest.py --check` passes; diff touches only the listed files.
[cost $0.0000, opencode tokens {"total": 1892815, "input": 71215, "output": 10234, "reasoning": 16422, "cache.write": 0, "cache.read": 1794944}]
    tool time: bash 7.4 min, edit 0.0 min, read 0.0 min
        298s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && timeout 1800 python3 tools/par_check.py -j 2 test_a
         63s bash   cat > /tmp/probes/stage2_30.py <<'PY' import os, sys, time, subprocess, tempfile from pathlib import Path root
         62s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && timeout 600 python3 tools/par_check.py -j 2 test_ai
         21s bash   cat > /tmp/probes/s376_check.py <<'PY' import ast, sys, collections sys.path.insert(0, '/home/runner/work/ail-
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          1s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && timeout 1200 python3 tools/par_check.py -j 2 test_a
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' import sys, ast sys.path.insert(0,'selfhost/ref') impor

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review

**What the change does:** adds the new AIL-written recursive-descent expression parser (`selfhost/src/ailparse.py`, 1213 lines), its CPython stage-0 reference/extractor, the stage-1/2 driver, a registered test module, and `PARSE.md`. It does not touch the compiler or runtime. The worker report describes only the four fix-ups in `26c1aa5f`, but `work..HEAD` is the whole parser (both commits); that matches the task.

**Verified claims**
- S376 stage 1 independently re-run: 164,248 segments, 164,105 CPython-accepted, **164,105 identical, 0 different, 0 parser refusals**; the 143 CPython eval refusals are 106 `yield`, 35 `yield from`, 2 starred assignment targets. Exactly as reported.
- Four fixes match CPython: `f'{x = }'`, `f'{ x=}'`, multiline debug; leading `{{` specs `f'{x:{{}}}'`, `f'{x:a{{}}}'`, `f'{x:{{a}}}'`; bytes `b'\u0041'`, `b'\U00000041'`, `b'\N{...}'`, `b'\400'`, `b'\777'`; `U'x'` kind `None`, `u'x'` kind `'u'`.
- `test_ail_selfhost_parse` and `test_ail_safetynet` pass on HEAD (`par_check.py -j 2`, 130s).
- `update_manifest.py --check` passes; diff touches only allowed files.
- Non-feature program: `--debug-dir/program.c` is byte-identical between `/tmp/base` and HEAD.
- Stage-2 `cmp.sh` probe (general and default builds) matches CPython on 13 expressions, including the defect cases.

**Defects (accepted-but-different vs CPython 3.12)**
1. Single starred subscript without a trailing comma. Probe `/tmp/rprobes/final_probe.py`: `a[*b]`.
   Expected `Subscript(..., slice=Tuple(elts=[Starred(...)], ctx=Load()), ...)`; actual `Subscript(..., slice=Starred(...), ...)`. (`a[*b,]` and `a[*b, c]` are correct.)
2. The `{{` format-spec fix is incomplete for repeated groups. Probe `f'{x:{{}}{{}}}'`.
   Expected format_spec `JoinedStr([Constant(''), FV(Dict), Constant(''), FV(Dict), Constant('')])`; actual omits the middle `Constant('')`. Same for `f'{x:{y}{{}}}'`, `f'{x:a{{}}{{}}}'`, `f'{x:{{}}{{}}{{}}}'`.
3. Empty string adjacent to an f-string. Probe `f'{x}' ''`.
   Expected `JoinedStr([FV(x)])`; actual `JoinedStr([FV(x), Constant('')])`. Also `'' f'{x}'` expected `JoinedStr([FV(x)])`, actual `JoinedStr([Constant(''), FV(x)])`.
4. (minor) Invalid Python is accepted instead of refused: `(*a)` → `Tuple([Starred(a)])` (CPython: `cannot use starred expression here`); `lambda /: 1` and `lambda *,: 1` → `Lambda(...)` (CPython: `invalid syntax` / `named arguments must follow bare *`).

**Claim check:** the report's “63-case probe over the four areas: all valid-and-accepted outputs match” is false as a statement about those areas — its 63 cases may pass, but probes 2 and 3 above are valid, accepted, and different. All other numeric claims checked are correct.

**Pre-existing:** none; the documented `'\N{...}'` str refusal is an allowed named refusal (`ailparse: \N named escape not supported`), and bytes `\N` matches CPython. Named refusals such as `(yield)` and `f'{a, b}'` are allowed by the task.

**Unverified:** stage 2 on the 30-file set (I ran the test's 20 + edge and the 13-expression `cmp.sh` probe, all byte-identical); `test_ail_files`/`test_ail_corpus_findings3` (outside the review's test scope); `PARSE.md` stage-2 build time/binary size; instruction counts (change is not on the compiler path, so not applicable).

VERDICT: FIX
[cost $0.0000, opencode tokens {"total": 1445546, "input": 41927, "output": 10923, "reasoning": 29752, "cache.write": 0, "cache.read": 1362944}]
    tool time: bash 5.1 min, read 0.0 min
        131s bash   date; cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && timeout 1200 python3 tools/par_check.py -j 2 
         92s bash   cat > /tmp/rprobes/parse_probe.py <<'PY' import ailast import ailparse   def main():     cases = [         "a 
         42s bash   cat > /tmp/rprobes/parse_probe.py <<'PY' import sys sys.path.insert(0, '/home/runner/work/ail-ci/ail-ci/selfho
         21s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && timeout 600 python3 - <<'PY' 2>&1 | tail -30 import
          7s bash   mkdir -p /tmp/rprobes && cat > /tmp/rprobes/simple.py <<'PY' def f(n):     s = 0     for i in range(n):       
          5s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && timeout 300 python3 - <<'PY' 2>&1 | tail -20 import
          5s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && timeout 300 python3 - <<'PY' 2>&1 | tail -25 import
          1s bash   git worktree add /tmp/base work 2>&1 | tail -3; echo ---; git show work:selfhost/src/ailparse.py 2>&1 | head -

FINAL VERDICT: FIX  2026-11-08T09:37:06Z
