# job job-pyreachs6-11040853  started 2026-11-03T23:53:56Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed pyreach s6 as `81304ed7` on `job-pyreachs6-11040853`.

- Added `BTAB` content-hashed bytes keys with owned copies and int/str/bytes values, plus the eval-order segfault fix.
- Fixed the `if True:` / binary `with open` wrapper so `data.split(...)` stays a bytes list and `t = parts[0]` is no longer pre-bound int.
- Added `test_ail_pyreach_byteskeys.py` (7 tests) and registered it.
- All 10 probes matched CPython on default, unified and strict builds, including `\x00`/`\xff` stdin.
- Targeted tests passed: byteskeys, pyreach_unpack, pytyped_reach, safetynet, files, corpus_findings3.
- `ticket_audit` still has 5 non-s6 blockers: regex annotation/caller mismatch, `CODES[cat]`, and three s5 dict-of-containers cases.
[cost $0.0000, opencode tokens {"total": 24352148, "input": 597263, "output": 53887, "reasoning": 50694, "cache.write": 0, "cache.read": 23650304}]
    tool time: bash 20.3 min, edit 0.0 min, write 0.0 min
        339s bash   cd /home/runner/work/ail-ci/ail-ci && for t in test_ail_safetynet test_ail_files test_ail_corpus_findings3; do
        135s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/ticket.s; timeout 300 python3 -B AIL_CURRENT/ail_chatgpt.py c
        120s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/bk_t3.s /tmp/bk_t5.s && for f in bk_t3 bk_t5; do echo ==== $f
        116s bash   cd /home/runner/work/ail-ci/ail-ci && for t in test_ail_pyreach_byteskeys test_ail_pyreach_unpack test_ail_pyt
         81s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/ta && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/compa
         79s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 600 python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/compare/sr
         79s bash   cd /home/runner/work/ail-ci/ail-ci && rm -f /tmp/ta && python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/compa
         64s bash   cd /home/runner/work/ail-ci/ail-ci && cat > /tmp/runprobes.sh <<'SH' #!/bin/bash set -u wt=/home/runner/work/a

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review: pyreach s6 — owned bytes as dict/set keys

**What the diff really does.** It reworks `BTAB` so each inserted key is copied (`ail_btab_key_dup`) and freed at `del`/`clear`/`free`, and makes the value array a union (`int64_t`/`ail_bytes`/`ail_str`) with `put/get/need/pop` variants. In `pyfunc.py` it adds bytes-dict value-kind inference (`bkeyvals`), routes `.get/.pop/.items/.values/sorted/list` through the right accessor, and recognises binary `read()` inside `with open(...,'rb')` and the `if True:` wrapper. That matches the report.

**Probes** (`bash ~/tools/cmp.sh`, default + unified, all CPython-matched unless noted):

| probe | covers | result |
|---|---|---|
| p1/p10 | bytes value from `.strip()` | match |
| p2 | key/value from `split` then source rebound | match |
| p3 | empty key `b''`, get defaults, sorted | match |
| p4 | delete + reinsert dict and set | dict match; set order differs (pre-existing) |
| p5 | `.items()` int values, set iteration | match |
| p6 | keys from list items | match |
| p7 | `get` defaults for int/str/bytes values | match |
| p8 | 400 keys, deletes, regrowth | match |
| p9 | `sorted(reverse=True)`, `list(d)`, keys/values counts | match |
| p11–p13 | `d[k] += n`, `.items/.values`, `remove` missing | match / named refusals |
| p4b | int set delete+reinsert on base | same divergence on base |

`.ail` codegen: all ten `lab/compare/src/*/main.ail` hashes and the codegen pins are identical to `work`. `test_ail_pyreach_byteskeys.py` passes directly (7 tests, 43 s); `test_ail_safetynet.py` passes directly (5 tests, 131 s). `ticket_audit --strict` still reports the five claimed non-s6 blockers.

**Defect**

1. **New test module is not pinned in the manifest.** `python3 tools/update_manifest.py --check` reports:
   ```
   unpinned test_ail_pyreach_byteskeys.py
   unpinned tests.d/test_ail_pyreach_byteskeys.txt
   ```
   and `par_check.py -j 2 test_ail_pyreach_byteskeys test_ail_safetynet` aborts with `ValueError: hash mismatch: test_ail_pyreach_byteskeys.py` before running anything. Expected: manifest updated (`update_manifest.py`, then `--check` clean) so the required module runs; actual: missing pins. The report's "registered it" is only half true (tests.d was added, the manifest was not).

**Pre-existing** (identical on `work`): set iteration order is AIL insertion order, not CPython's hash order (`p4`, `p4b`); not introduced here.

**Unverified:** key survival after the source buffer is actually freed (only rebinding was probed); memory/RSS and the 3.0x gate (ticket_audit is still not typed); the worker's private probe list; test modules other than byteskeys/safetynet (blocked by the manifest defect).

VERDICT: FIX

1. Run `python3 tools/update_manifest.py`, verify `--check` passes, and commit the new `test_ail_pyreach_byteskeys.py` and `tests.d/test_ail_pyreach_byteskeys.txt` manifest pins; otherwise `par_check.py`/CI preflight fails with `hash mismatch: test_ail_pyreach_byteskeys.py`.
[cost $0.0000, opencode tokens {"total": 2444754, "input": 90445, "output": 7614, "reasoning": 20935, "cache.write": 0, "cache.read": 2325760}]
    tool time: bash 11.7 min
        131s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 280 python3 -B test_ail_safetynet.py > /tmp/safetyne
        120s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup python3 -B test_ail_safetynet.py > /tmp/safetynet_dire
        120s bash   cd /home/runner/work/ail-ci/ail-ci && nohup timeout 420 python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/comp
        120s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 120 python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/compare/sr
         74s bash   cd /tmp/rprobes cat > p2_alias.py <<'PY' import sys def main():     data = b'a|hello'     parts = data.split(b
         43s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && nohup python3 -B test_ail_pyreach_byteskeys.py > /tmp/bytesk
         41s bash   cd /tmp/rprobes cat > p10_strip.py <<'PY' import sys def main():     d = {}     k = b'kk'     v = b'  hi  '.st
         31s bash   cd /home/runner/work/ail-ci/ail-ci args=() for f in lab/compare/src/*/main.ail; do args+=(--source "$(cat "$f"

## worker report 1
[model opencode/deepseek-v4.1-flash-free]
Fixed the review defect and committed.

- Regenerated manifest pins for `test_ail_pyreach_byteskeys.py` + `tests.d/test_ail_pyreach_byteskeys.txt`; `tools/update_manifest.py --check` is clean.
- Re-ran probes (`/tmp/probes/bk*`, `/tmp/rprobes/p1`–`p18`, default + `AIL_UNIFIED_FORCE=1`): all CPython-matched except the pre-existing set-iteration-order divergences (`p4`, `p4b`).
- Required tests on final commit (`par_check -j 2`): byteskeys, safetynet, files, corpus_findings3 — 4 modules, 0 failed.
- Commit: `6e76d0de job pyreachs6: pin the byteskeys test module in the manifest`.
[cost $0.0000, opencode tokens {"total": 471506, "input": 27547, "output": 3493, "reasoning": 1938, "cache.write": 0, "cache.read": 438528}]
    tool time: bash 12.0 min, edit 0.0 min
        202s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1500 python3 tools/par_check.py -j 2 test_ail_pyreach_byteskeys 
        141s bash   cd /tmp/rprobes && for f in p1_strip p2_alias p3_empty p4_reinsert p4b_intset p5_items p6_keysources p7_getdef
        135s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 500 python3 tools/par_check.py -j 2 test_ail_pyreach_byteskeys t
        132s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_files test_ail_cor
         61s bash   cat > /tmp/rprobes/run_input_probes.sh <<'SH' #!/bin/bash wt=/home/runner/work/ail-ci/ail-ci infile=/tmp/rprob
         43s bash   cd /tmp/probes && for f in bk1 bk2 bk3 bk_alias bk_loop1 bk_set bk_sorted bk_t bk_t2 bk_t3 bk_t4 bk_t5 bk_t6 b
          6s bash   cd /tmp/rprobes && cat input.bin | head -c 100; echo; d=$(mktemp -d /tmp/cmp14XXXX); cp p14_openread.py $d/p.a
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py 2>&1 | tail -20 && python3 tools/update

## review 1
[model opencode/deepseek-v4.1-flash-free]
## Review: pyreach s6 review fix (owned bytes keys)

**What the diff really does.** `81304ed7` reworks `BTAB` (owned key copies freed at `del`/`clear`/`free`, union values int/str/bytes) and adds bytes-key/value-kind inference in `pyfunc.py`; `6e76d0de` only pins the new test module in `manifest.d` and adds the DEVLOG entry. That matches the report.

**Gate checks.** `python3 tools/update_manifest.py --check` exits 0 (fixed). `par_check -j 2 test_ail_pyreach_byteskeys` passed (42 s) and `test_ail_safetynet` passed (134 s, 0 failed). `ticket_audit --strict` still exits 3 with 5 blockers: regex `s: bytes`/int caller, `CODES[cat]`, `events[ev] = [vc, cents, set()]`, `out` mixed str/non-str, `per.setdefault(vc, [0,0,0])` — i.e. two, not three, are dict-of-container blockers; the rest are outside s6. The task's stated "ticket_audit typed" outcome was not reached, but the stop rule allows landing with this list.

**Defect (regression, default typed build; general path matches CPython, base matches CPython).**

`/tmp/rprobes2/q19_key_after_del.py`:

```python
import sys
def main():
    d = {}
    d[b'A' * 32] = 1
    d[b'B' * 32] = 2
    keep = b''
    for k in d:
        if k[0:1] == b'B':
            keep = k
    del d[b'B' * 32]
    e = {}
    for i in range(16):
        e[bytes([90 - i]) * 32] = i
    sys.stdout.write(keep.decode('latin-1') + "\n")
main()
```

- Expected (CPython, base, and the general path): `BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB`
- Actual (HEAD, typed build): `ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ`

The owned-key change frees a key's buffer at `del d[k]`, but iteration still yields `T->order[_i]` views directly, so a variable bound from iteration dangles. `q20_val_alias_del.py` (the same key stored as another dict's bytes value, then deleted from the source dict) shows the same corruption. The base keeps keys in the arena and matches CPython, so this is introduced here. Values read this way must stay stable or iteration must yield a copy.

**Claims.** manifest fix: verified. Test claim (4 modules, 0 failed): verified for byteskeys and safetynet; files/corpus_findings3 not re-run. "All probes matched except pre-existing set order": false as a correctness statement — q19 is a new divergence. `.ail` C unchanged: no compiler source changed in `6e76d0de`; inherited verified from the prior review of `81304ed7`. Speed/icount and RSS: unverified.

**Pre-existing.** Set iteration order is insertion order, not CPython hash order (same on base).

VERDICT: FIX

1. Use-after-free on keys obtained by iterating a bytes-keyed dict: `q19_key_after_del.py` gives `ZZZ…` on HEAD vs `BBB…` from CPython/base after `del d[key]` (the freed owned key buffer is reused); `q20_val_alias_del.py` shows the same when the key was stored as a bytes dict value. Iteration/`.keys()`/`.items()` must expose a key that survives deletion of its table entry (e.g. copy into the arena), not the table's owned buffer.
[cost $0.0000, opencode tokens {"total": 1633180, "input": 97961, "output": 7878, "reasoning": 16301, "cache.write": 0, "cache.read": 1511040}]
    tool time: bash 13.1 min
        147s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 280 python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/compare/sr
        135s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 400 python3 tools/par_check.py -j 2 test_ail_safetynet > /tmp/r2
        120s bash   cd /home/runner/work/ail-ci/ail-ci && nohup python3 tools/par_check.py -j 2 test_ail_pyreach_byteskeys test_ai
        120s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 300 python3 -B AIL_CURRENT/ail_chatgpt.py compile lab/compare/sr
         60s bash   sleep 60; tail -20 /tmp/r2_par.log; ps aux | grep -E 'par_check|test_ail' | grep -v grep | head
         50s bash   cd /tmp/rprobes2 && for f in q1_clear q2_items q3_alias q4_aug q5_prefix q6_attr; do echo "===== $f"; timeout 
         41s bash   cd /tmp/rprobes2 cat > q17_key_after_clear.py <<'PY' import sys def main():     d = {}     d[b'A' * 32] = 1   
         37s bash   cd /tmp/rprobes2 cat > q7_setdef.py <<'PY' import sys def main():     d = {}     for k in [b'a', b'b', b'a']: 

FINAL VERDICT: FIX  2026-11-04T01:17:37Z
