# job job-pre192-10251808  started 2026-10-25T09:28:04Z  worker=oc reviewer=oc (GitHub)
## qoder discovery
1.1.78
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
MODEL
Auto
Ultimate
Fast
Efficient
Sonus
Cantus
Qwen3.8-Max
Qwen3.8-Flash
Kimi-K3.1-Pro
Kimi-K2.8-Preview
GLM-5.3
GLM-5.3-Flash
DeepSeek-V4-Pro
DeepSeek-Flash
MiniMax-M3.1-Flash
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":409,"duration_api_ms":291,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":392,"duration_api_ms":277,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed item 1: `int(bytearray(b"x"), base)` now reports `b'x'`, not `bytearray(b'x')`, on both builds. Also applied CPython's 200-char repr cut; `float(bytearray(...))` and valid parses are unchanged.

- Commit: `f8a0327`
- Test: new `test_ail_pre192.py`
- Probes: `p_intba.py`, `p_intba2.py`, `p_intba_long.py`, `p_intba_routes.py` — all match CPython on `g` and `d`
- Final tests: 7 modules (`pre192`, `pre180`, `pre182`, `bytearray_decimal`, `safetynet`, `files`, `corpus_findings3`), 0 failed
- `update_manifest.py --check`: passes

Not changed: keyword `base=` with a bytearray still hits a separate pre-existing `TypeError`; item 1 used a positional base.
[cost $0.0000, opencode tokens {"total": 3624491, "input": 91499, "output": 11068, "reasoning": 12292, "cache.write": 0, "cache.read": 3509632}]
    tool time: bash 10.2 min
        238s bash   python3 tools/par_check.py -j 2 test_ail_pre192 test_ail_pre180 test_ail_pre182 test_ail_bytearray_decimal tes
        186s bash   python3 tools/par_check.py -j 2 test_ail_pre192 test_ail_pre180 test_ail_pre182 test_ail_bytearray_decimal tes
         41s bash   python3 - <<'EOF' from pathlib import Path p=Path('/tmp/probes/p_intba_routes.py') lines=[l for l in p.read_te
         26s bash   bash ~/tools/cmp.sh /tmp/probes/p_intba_long.py $PWD > /tmp/p3b.log 2>&1; grep -E 'same stdout|DIFF|^< |^> ' /
         18s bash   bash ~/tools/cmp.sh /tmp/probes/p_intba.py $PWD > /tmp/p1.log 2>&1; bash ~/tools/cmp.sh /tmp/probes/p_intba2.p
         16s bash   cat > AIL_CURRENT/test_ail_pre192.py <<'PYEOF' """Pre-192: the `int(bytearray, base)` ValueError names a bytes
         15s bash   python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/prelude_bytes.py') s=p.read_text
         15s bash   cat > /tmp/probes/p_intba_routes.py <<'EOF' class Box:     def __init__(self, v, b):         self.v = v       

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review

**What the diff does:** In `AIL_CURRENT/python/pkg-v12/prelude_bytes.py`, `_ail_b_int` now cuts its message text to 200 chars, `bytearray.__int__` uses the bytes repr, and `_ail_int2` uses the bytes repr for bytearray plus the 200-char cut (`prelude_bytes.py:476`, `:733`, `:823`). It also adds `test_ail_pre192.py`, DEVLOG/DIFFERENCES rows, `ail_check.py`, and manifest updates.

**Claims:** fixed item 1 on both builds — verified. 200-char cut also fixes long `bytes` — verified (base differs, HEAD matches CPython). `float(bytearray(...))` and valid parses unchanged — verified. Keyword `base=` remains a separate pre-existing `TypeError` — verified identical on base. Exact worker probe files and their 7-module run — not rerun (reviewer scope); equivalent probes pass.

**Probes (`/tmp/rprobes`, HEAD `g` and `d` both match CPython):**
- `p_basic.py`: positional/arg/list/attribute/dict/alias routes, bases 0/2/8/10/16/36, empty, valid, signed, whitespace, underscore, prefix, bytes baseline, `float`.
- `p_reprchars.py`: every byte value 0–255 plus quote/control/backslash cases, bytes and bytearray.
- `p_long.py`: lengths 198–202, 300, 1000, mixed long inputs, base 10/0, with and without base; exact message lengths match.
- `p_seq.py`: mixed quote/escape sequences and long inputs whose repr is truncated mid-string.
- Base `/tmp/base`: p_basic and p_long differ exactly where expected; HEAD fixes them.

**Pre-existing:** `int(bytearray(b'x'), base=10)` and even `int(b'x', base=10)` raise `TypeError: int() can't convert non-string with explicit base` on both HEAD and base (`p_kw.py`), so not caused by this change.

**Other checks:** non-feature program (`list` loop) generated `program.c` is byte-identical between HEAD and base. `test_ail_pre192` + `test_ail_safetynet`: 2 modules, 0 failed. `update_manifest.py --check`: passes.

**Unverified:** worker's full 7-module run, exact `/tmp/probes/p_intba*` files, instruction counts (change is not in hot generic code).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 442118, "input": 27708, "output": 4358, "reasoning": 9284, "cache.write": 0, "cache.read": 400768}]
    tool time: bash 2.6 min
         79s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre192 tes
         39s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_basic p_reprchars p_long p_kw; do echo "===== $p HEAD"; bash 
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for p in p_basic p_kw; do echo "===== $p BASE"; bash ~/tools/cmp.sh /tmp
          9s bash   cd /home/runner/work/ail-ci/ail-ci && date; bash ~/tools/cmp.sh /tmp/rprobes/p_long.py /tmp/base 2>&1 | tail -
          8s bash   cd /tmp/rprobes && cat > p_seq.py <<'EOF' def show(label, f):     try:         print(label, repr(f()))     exc
          2s bash   mkdir -p /tmp/rcmp && cd /tmp/rcmp && printf 'xs = [1, 2, 3]\ntotal = 0\nfor x in xs:\n    total = total + x\n
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git worktree add /tmp/base work 2>&1 | tail -3; date
          0s bash   cd /home/runner/work/ail-ci/ail-ci && grep -rni "memsafe2\|int(bytearray" --exclude=MANIFEST.json . | head -40

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T10:33:31Z
