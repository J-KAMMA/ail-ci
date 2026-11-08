# job job-shparse1-11081851  started 2026-11-08T09:59:47Z  worker=chain reviewer=chain (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed all four review defects in `selfhost/src/ailparse.py` and committed as `a59af76`.

- `a[*b]` now yields `Subscript(..., slice=Tuple([Starred(...)]))`.
- Format specs now emit the empty `Constant` before every `{{` group (`{{}}{{}}`, `{y}{{}}`, etc.).
- Empty plain strings adjacent to f-strings are dropped; `u`-string kind follows the first literal in a run.
- Invalid syntax is now refused by name: `(*a)`, `lambda /...`, bare `*`, duplicate `/`, and lone `yield`.

Verification (all run on the final commit):
- Full S376: 164,248 segments; 164,105 identical, 0 accepted-but-different, 143 both refused (141 `yield`, 2 starred assignment targets), 0 cases where CPython refuses but `ailparse` accepts.
- Stage 2 on the 30 fixed S376 files: 13,486 segments, byte-identical to stage 1; also identical under `AIL_UNIFIED_FORCE=1` on a 30-case defect probe.
- `test_ail_selfhost_parse`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: all pass (`par_check.py -j 2`, 189s).
- `tools/update_manifest.py --check` passes; only the allowed files plus the generated manifest shard changed.
[cost $0.0000, opencode tokens {"total": 7058116, "input": 123437, "output": 17813, "reasoning": 32770, "cache.write": 0, "cache.read": 6884096}]
    tool time: bash 11.3 min, edit 0.0 min
        239s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && timeout 1500 python3 tools/par_check.py -j 2 test_a
        190s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && timeout 1500 python3 tools/par_check.py -j 2 test_a
        120s bash   python3 --version; python3 -c "import sys; print(sys.version)"; find / -name "python.gram" 2>/dev/null | head;
         41s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && rm -rf /tmp/probes/s2 /tmp/probes/expr_drv && mkdir
         30s bash   cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/probes/defects && mkdir -p /tmp/probes/defects && python3 - 
         19s bash   find / -name "action_helpers.c" 2>/dev/null | head; find / -name "python.gram" 2>/dev/null | head
         10s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && time PYTHONPATH=selfhost/src python3 -B selfhost/dr
          9s bash   cd /home/runner/work/ail-ci/ail-ci && mkdir -p /tmp/probes/s376 && ulimit -v 1500000 && time python3 -B selfho

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**What the change does:** In `selfhost/src/ailparse.py` it makes a single starred subscript a one-element `Tuple`, inserts the empty `Constant` before each escaped-brace group in format specs, drops empty plain-string constants from `JoinedStr` (merging kinds), and refuses bad lambda `/`/bare-`*` forms, unparenthesized `(*a)` and lone `yield`; it also extends the test and `PARSE.md`. This matches the worker report.

**Verified**
- All four prior defects fixed: `a[*b]` → one-element `Tuple`; `f'{x:{{}}{{}}}'`, `f'{x:{y}{{}}}'`, `f'{x:a{{}}{{}}}'`, `f'{x:{{}}{{}}{{}}}'` match CPython; `f'{x}' ''` and `'' f'{x}'` drop the empty constant; `(*a)`, `lambda /: 1`, `lambda *,: 1` refused by name.
- Full S376 at HEAD: 164,248 segments, 164,105 identical, **0 different**, 143 both refused (141 `yield`, 2 starred targets), 0 CPython-refused-but-accepted. Exactly the report.
- Stage 2 on the 30 fixed files: 13,486 segments byte-identical to stage 1; also identical with `AIL_UNIFIED_FORCE=1` on a 30-case defect set.
- 14,096 generated format-spec/string-concat expressions: zero differences or wrong refusals. 1,488 mixed expression cases: only the pre-existing lambda case below.
- `test_ail_selfhost_parse` and `test_ail_safetynet` pass (`-j 2`); `update_manifest.py --check` passes; non-feature program's `--debug-dir/program.c` is byte-identical to base.

**Claim check:** all numeric claims verified. `test_ail_files`/`test_ail_corpus_findings3` are unverified (outside reviewer scope).

**Pre-existing (identical on base):** accepted-invalid `x.yield`, `lambda x, *a, /`, `lambda x, y=1, /, z`, `lambda *a, *b`; `f'{x:{y=}}'` accepted where CPython `ast.parse` raises `ValueError`.

**Unverified:** `test_ail_files`, `test_ail_corpus_findings3`; instruction counts (change is not on the compiler path).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1469957, "input": 79693, "output": 10035, "reasoning": 24965, "cache.write": 0, "cache.read": 1355264}]
    tool time: bash 2.9 min
         81s bash   date; cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && timeout 900 python3 tools/par_check.py -j 2 t
         38s bash   date; cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000 && python3 - <<'PY' import sys sys.path.insert(0
         30s bash   date; cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/rprobes/s2u && mkdir -p /tmp/rprobes/s2u/seg && python
         20s bash   date; cd /home/runner/work/ail-ci/ail-ci && rm -rf /tmp/rprobes/s376 && ulimit -v 1500000 && time python3 -B s
          2s bash   cat > /tmp/rprobes/simple.py <<'PY' def f(n):     s = 0     for i in range(n):         s += i * 2     return s
          1s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/rprobes/fuzz4.py <<'PY' import ast,sys,itertools,json sys.pat
          0s bash   git worktree add /tmp/base work 2>&1 | tail -3; ls /tmp/base/selfhost/src | head
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 - <<'PY' def load(p):     d={}; cur=None; buf=[]     for line in

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-08T11:44:27Z
