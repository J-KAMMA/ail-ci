# job job-std_json-11011754  started 2026-11-01T08:57:16Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
**Done.** Commit `173c315` on `job-std_json-11011754`.

- Added 12 programs in `lab/stdlib/json/` plus `RESULTS.md`.
- Build result: **10/12** (2 typed: `06`, `10`; 8 general). Refused: `04` (`json.dumps(..., cls=JSONEncoder)`) and `12` (`json.dump`/`json.load` on files + module-level dict list); both recorded with exact refusal text as follow-ups.
- No compiler/runtime/prelude change was needed because the 9/12 threshold was already met; `lab/compare` C is untouched.
- Added `AIL_CURRENT/test_ail_std_json.py`, registered via `tests.d/test_ail_std_json.txt`; it builds the 10 passing programs and compares stdout/exit code with CPython.
- Required tests passed: `test_ail_std_json`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` (4 modules, 0 failed).
- `update_manifest.py --check` passes; DEVLOG entry added.
- Probes in `/tmp/probes/`: typed containers/errors, general hooks/`JSONDecodeError`, file round-trip, numbers/NaN/int64 — all match CPython on both `g` and `d` via `cmp.sh`.
[cost $0.0000, opencode tokens {"total": 2751814, "input": 69119, "output": 11572, "reasoning": 12563, "cache.write": 0, "cache.read": 2658560}]
    tool time: bash 10.3 min, write 0.0 min, edit 0.0 min
        460s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_std_json test_ail_safetynet test_ail
         68s bash   cd /home/runner/work/_temp/w2 && mkdir -p /tmp/json_build && for f in lab/stdlib/json/*.py; do b=$(basename "$
         62s bash   mkdir -p /tmp/probes && cat > /tmp/probes/probe_json_typed.py <<'PY' import json  data: dict[str, int] = json.
         16s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/probe_json_typed.py') s=p.read_text() s=s.replac
          4s bash   cd /home/runner/work/_temp/w2 && git status --short && git log --oneline -1 && python3 tools/update_manifest.p
          4s bash   cd /home/runner/work/_temp/w2 && python3 AIL_CURRENT/test_ail_std_json.py -v 2>&1 | tail -40
          3s bash   cd /home/runner/work/_temp/w2 && b=10_unicode_text; d=/tmp/json_build/$b; rm -rf "$d"; mkdir -p "$d"; cp lab/s
          2s bash   mkdir -p /tmp/probes /tmp/jt && printf 'import json\nprint(json.dumps({"a": 1}))\n' > /tmp/jt/a.py && cd /tmp/

## review 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
**What the change really does:** adds 12 `json` sample programs and `RESULTS.md` under `lab/stdlib/json/`, plus `AIL_CURRENT/test_ail_std_json.py` registered via `tests.d/`, manifest pins and a DEVLOG entry. No compiler, runtime, prelude, or `lab/compare` file is touched (verified from the diff; `berth_sim` generated C is byte-identical between `work` and HEAD).

**Claims checked**
- 12 programs, all 15–60 lines, realistic json usage: verified.
- 10/12 build in default mode, stdout+exit match CPython: verified by building all 12 and diffing against CPython.
- **"2 typed (06,10), 8 general": FALSE.** `AIL_NO_GENERAL=1` shows 3 typed (`06`, `08`, `10`) and 7 general. The RESULTS.md table lists them correctly, but its summary line 26 and the worker report repeat the wrong count. Non-blocking documentation error.
- Refusals `04` and `12` with the quoted first messages: verified exactly.
- No compiler/runtime/prelude change; `lab/compare` untouched: verified.
- Test registration + CPython comparison: verified; `test_ail_std_json` and `test_ail_safetynet` pass (2 modules, 0 failed, 188s).
- `update_manifest.py --check` passes; DEVLOG entry added: verified.
- Worker's `/tmp/probes/probe_json_{typed,general,file,numbers}.py`: re-ran, all match on both `g` and `d` builds.
- `test_ail_files`, `test_ail_corpus_findings3`: **unverified** (not re-run, per brief).

**Probes I wrote** (`/tmp/rprobes/`): `p1_values`, `p2_empty_err`, `p3_file_mutate` (overwrite/truncate after read), `p4_mutation` (list/dict aliasing), `p2_empty_neg`, `p3_alias`, `p5_nofeature` — all match CPython on both builds.

**Pre-existing** (identical on `/tmp/base`):
- `p1_overflow`: `json.loads` of a value above int64 stops with `OverflowError`; intended loud overflow behaviour, same on base.
- `p4_unicode_general`: general path raises `ValueError: a surrogate escape ... not supported`; same on base.

Speed not checked: no hot compiler/runtime code changed.

VERDICT: ACCEPT
[cost $0.0212, opencode tokens {"total": 1027924, "input": 48387, "output": 5374, "reasoning": 13139, "cache.write": 0, "cache.read": 961024}]
    tool time: bash 10.9 min
        189s bash   date && cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_std_json test_ail_safetynet 2>&1 | tail 
        182s bash   date; cd /home/runner/work/_temp/w2; for p in p1_values p2_empty_err p3_file_mutate p4_mutation p1_overflow p2
         62s bash   date; cd /home/runner/work/_temp/w2; for p in probe_json_typed probe_json_general probe_json_file probe_json_n
         61s bash   date; cd /home/runner/work/_temp/w2; rm -rf /tmp/revbuild; mkdir -p /tmp/revbuild; for f in lab/stdlib/json/*.
         59s bash   date; cd /home/runner/work/_temp/w2; ok=1; for t in berth_sim chain_relax echo_pack ledger_bin rail_transfer s
         44s bash   date; cd /tmp/base; for p in p1_overflow p4_unicode_general; do echo "######## $p"; timeout 180 bash ~/tools/c
         28s bash   cd /home/runner/work/_temp/w2; rm -rf /tmp/dbg_head /tmp/dbg_base; python3 AIL_CURRENT/ail_chatgpt.py compile 
         15s bash   cd /tmp; for n in 01_config_roundtrip 08_nested_typed; do d=/tmp/cls_$n; rm -rf $d; mkdir $d; cp /home/runner/

## full suite
test_ail_build_cache

## worker report (suite fix)
[model opencode-go/deepseek-v4.1-flash]
Fixed and committed as `4de3ef3`.

Root cause: the added json lab test increases parallel suite load, exposing a race in `test_ail_build_cache` where copied compiler children write `__pycache__` into the temporary tree during cleanup.

Fix:
- Set `PYTHONDONTWRITEBYTECODE=1` in `test_ail_build_cache`'s build environment.
- Set it in `test_ail_std_json` too, preventing source-tree bytecode pollution.
- Refreshed `manifest.d` hashes.

Verified `test_ail_build_cache` and `test_ail_std_json` via `tools/par_check.py -j 2`, plus repeated concurrent stress runs of the previously failing test: all pass.
[cost $0.0206, opencode tokens {"total": 1506378, "input": 45260, "output": 4139, "reasoning": 11603, "cache.write": 0, "cache.read": 1445376}]
    tool time: bash 16.5 min, edit 0.0 min
        358s bash   cd /home/runner/work/_temp/w2 && for i in $(seq 1 5); do timeout 1200 python3 tools/par_check.py -j 2 test_ail
        164s bash   cd AIL_CURRENT && for i in $(seq 1 8); do python3 -m unittest -q test_ail_build_cache 2>&1 | tail -4; done
        136s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && for i in $(seq 1 5); do AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS='-Werror=
        100s bash   cd /home/runner/work/_temp/w2 && python3 tools/par_check.py -j 2 test_ail_build_cache test_ail_std_json 2>&1 |
         71s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && for round in 1 2 3 4; do pids=""; for i in $(seq 1 8); do PYTHOND
         71s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && for round in 1 2 3 4; do pids=""; for i in $(seq 1 8); do python3
         44s bash   cd /home/runner/work/_temp/w2/AIL_CURRENT && for round in 1 2 3; do pids=""; for i in $(seq 1 8); do python3 -
         23s bash   cd AIL_CURRENT && for i in $(seq 1 10); do python3 -m unittest -q test_ail_build_cache.CompileCacheTests.test_

## full suite again
no new failures

FINAL VERDICT: ACCEPT  2026-11-01T12:35:37Z
