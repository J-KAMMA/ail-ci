# job job-qtest2-10241617  started 2026-10-24T07:17:44Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.73
  -m, --model <model>                  Model for the current session. Default
                                       and New Models use model name; Custom
                                       uses modelID
  --reasoning-effort <level>           Set reasoning effort level
  --thinking <mode>                    Set thinking mode (auto, adaptive,
                                       enabled, or disabled)
--
                                       models
  --list-models                        List available models for the current
                                       user
  -i, --prompt-interactive <text>      Execute prompt and continue in
                                       interactive mode
### --list-models
Failed to fetch model list: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.
deepseek-v4.1-flash -> An unexpected critical error occurred:QoderAuthError: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.     at bue (file:///usr/local/lib/node_modules/@qoder-ai/qodercli/bundle/qoderc
DeepSeek-V4.1-Flash -> An unexpected critical error occurred:QoderAuthError: The QODER_PERSONAL_ACCESS_TOKEN environment variable contains a token that was rejected. It overrides any saved login, so unset it or set a valid token, then restart.     at bue (file:///usr/local/lib/node_modules/@qoder-ai/qodercli/bundle/qoderc

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed and committed as `092765c`.

**Bug:** literal `maxsplit=None` was silently read as `0` on both builds.
- `"a b".split(maxsplit=None)` → `['a b']` (CPython: `TypeError`)
- `"a,b,c".rsplit(",", maxsplit=None)` → `['a,b,c']` (CPython: `TypeError`)

Both split paths now refuse the literal `None` by name (`maxsplit cannot be None`). Dynamic `None` still raises the correct `TypeError`.

**Probes (23 in `/tmp/probes`):**
- Matched CPython on both builds: `p01`–`p13`, `p15`, `p16`, `p18`, `p20`, `p22` (whitespace runs, tabs/newlines, Unicode whitespace, maxsplit 0/1/-1/huge, empty strings/seps, args/list/attribute/dict sources, keyword forms, matrix).
- Now refused by name on both builds: `p21`, `p23` (the `maxsplit=None` cases).
- Other differences seen, not changed: `p14` maxsplit constants above int64 fail to compile with `integer overflow` where CPython raises `OverflowError`; `p17`/`p19` a separator that is `None` at run time through a variable/list/dict gives `ValueError: empty separator` where CPython treats it as whitespace.

**Tests:** `test_ail_qtest2`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`, `test_ail_fuzz33` all passed; `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 3955847, "input": 123476, "output": 13306, "reasoning": 17337, "cache.write": 0, "cache.read": 3801728}]
    tool time: bash 8.7 min
        345s bash   python3 tools/par_check.py -j 2 test_ail_qtest2 test_ail_safetynet test_ail_files test_ail_corpus_findings3 te
         42s bash   for f in /tmp/probes/p*.py; do echo "=== $(basename $f)"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | grep -E "cpyt
         32s bash   for f in p02_ws_max.py p04_sep.py p10_edges.py p13_kw.py p18_max_none_var.py p20_matrix.py p21_none_lit.py p23
         25s bash   cd /tmp/probes && cat > p11_typed.py <<'EOF' def f(s: str, n: int) -> None:     print(repr(s), n, s.split(None
         14s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/test_ail_qtest2.py') s=p.read_text() s=s.replace
         14s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyfunc.py') s=p.read_text() old='
         14s bash   cd /tmp/probes && cat > p17_sep_none_var.py <<'EOF' def main():     sep = None     n = 1     for s in ["  a  b
         11s bash   cat > AIL_CURRENT/test_ail_qtest2.py <<'PY' """qtest2: str.split/rsplit maxsplit=None must not be read as maxs

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the change does:** refuses a literal `None` maxsplit at compile time in both the boxed/general split emitter (`pyboxed2.py:9101-9104`) and the typed slist shape detector (`pyfunc.py:6313-6315`); adds `test_ail_qtest2.py` and manifest/devlog/differences entries. Nothing else.

**Probes** (`/tmp/rprobes`, both builds; base `/tmp/base`):
- `n1` `split(maxsplit=None)`: HEAD refused by name on both builds; base printed `['a b']`, exit 0 (bug confirmed).
- `n4` `rsplit(",", maxsplit=None)`, `n5` `sep=None,maxsplit=None`, `n6` `rsplit(None, maxsplit=None)`: refused by name; base silently wrong.
- `n2` `split(None, None)`, `n3` `split(",", None)`: not refused, but both builds raise the correct `TypeError` and exit 1 (base same).
- `r1`/`r3` runtime `None` via variable/dict: correct `TypeError`, exit 1 on both builds.
- `valid`: whitespace runs, tabs/newlines, empty strings, maxsplit 0/1/2/-1, separators — identical to CPython on both builds.
- `t1`/`t2` wrong-type maxsplit (`str`, `float`): correct `TypeError` like CPython, unchanged from base.
- No-feature program and valid split program: generated `program.c` byte-identical to base in both default and general modes (only diagnostic paths differ).

**Claims:**
- Bug and fix: verified.
- "Both split paths refuse the literal None by name": partially false — two-positional-argument forms (`split(None, None)`) still succeed and raise the correct runtime `TypeError`; no silent-wrong case remains.
- Dynamic `None` raises `TypeError`: verified.
- p14 bigint overflow and p17/p19 runtime separator `None`: verified; both identical on base.

**Pre-existing (not blocking):** runtime `sep=None` via variable/list/dict gives `ValueError: empty separator` instead of whitespace split (verified identical on base); maxsplit constants above int64 fail to compile (verified identical on base).

**Tests:** `test_ail_qtest2`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (256s, 0 failed); `update_manifest.py --check` passes. Speed not checked: change is compile-time only and does not touch hot code.

**Unverified:** full suite (per instructions).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 566617, "input": 34058, "output": 5042, "reasoning": 9757, "cache.write": 0, "cache.read": 517760}]
    tool time: bash 6.0 min
        258s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_qtest2 test_ail_
         24s bash   cd /tmp/rprobes for f in n1 n2 n3 n4 n5 n6; do echo "===== $f"; bash ~/tools/cmp.sh "$f.py" /home/runner/work/
         17s bash   cd /tmp/rprobes for f in r1 r2 r3 valid; do echo "===== $f"; bash ~/tools/cmp.sh "$f.py" /home/runner/work/ail
         16s bash   cd /tmp/rprobes for f in n1 n2 n3 r2; do echo "===== BASE $f"; bash ~/tools/cmp.sh "$f.py" /tmp/base 2>&1 | gr
         15s bash   cd /tmp/rprobes cat > t1.py <<'EOF' def main():     print("a b c".split(None, "2")) main() EOF cat > t2.py <<'
         15s bash   cd /tmp/dbg && rm -rf hd_* bd_* h_nf_* b_nf_* h_v_* b_v_* for mode in d g; do   if [ "$mode" = g ]; then expor
          9s bash   cd /tmp/probes && cat p14_bigint.py; for wt in /home/runner/work/ail-ci/ail-ci /tmp/base; do echo "===== $wt";
          4s bash   cd /tmp/rprobes && bash ~/tools/cmp.sh n2.py /home/runner/work/ail-ci/ail-ci 2>&1 | tail -20

FINAL VERDICT: ACCEPT  2026-10-24T07:40:33Z
