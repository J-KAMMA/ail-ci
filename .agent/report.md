# job job-pre105-10242140  started 2026-10-24T12:41:03Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":655,"duration_api_ms":524,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":695,"duration_api_ms":567,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the recorded unverified errmsg3 case on the current tree.

**Change:** `import math, html` with `html` used still produced `import of 'math, html'` at `1:1` on the default typed path. The scan now names the first module outside the modelled set (`html`, or `html.parser`), so the refusal names only the unsupported module. The general path already refused by name; an unused `html` import still matches CPython.

Commit: `92daf18` (6 files, +105/−7), trailer correct. No push.

**Probes** (`/tmp/probes/pre105_*.py`, both builds, `cmp.sh`):
- `01,02,10,12,19,20,21,22` — CPython exit 0; both builds refuse by name (`html`), default located at `1:1` with `import of 'html'`.
- `17` — same, names `html.parser`.
- `unused` — both builds match CPython (`2`).
- Covered plain/reversed/three-name imports, and `html` through an argument, list item, attribute and dict value.

**Tests on final commit:** `test_ail_pre105`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (333 s). Also `test_ail_modules`, `test_ail_refusal_messages` — 2 modules, 0 failed (179 s). `update_manifest.py --check` exit 0.

Pre-existing and untouched: the unlocated `try: import html` refusal remains on this base (the accepted pre52 branch carries that separate fix).
[cost $0.0000, opencode tokens {"total": 8660489, "input": 599585, "output": 15095, "reasoning": 22641, "cache.write": 0, "cache.read": 8023168}]
    tool time: bash 16.4 min
        335s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre105 test_ail_safetynet test_ail_files test_ai
        181s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_modules test_ail_refusal_messages 2>&1 | tail -2
        126s bash   cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre105 test_ail_safetynet 2>&1 | tail -30
         48s bash   for p in html_escape html_escape_arg html_two_name except_star class_try local_try plain_two_unused plain_two_
         47s bash   cd /tmp/probes/imp && for f in v09.py v10.py v11.py v12.py v13.py v14.py v15.py v16.py v17.py v18.py v19.py v2
         40s bash   mkdir -p /tmp/probes && cd /tmp/probes && for n in 01 02 10 12 17 19 20 21 22; do cp /tmp/probes/imp/m$n.py /t
         36s bash   cd /tmp/probes/imp && for f in v*.py; do out=$(AIL_NO_CACHE=1 AIL_QUIET_FALLBACK=1 python3 /tmp/errmsg3/AIL_CU
         33s bash   mkdir -p /tmp/probes/imp && cd /tmp/probes/imp && cat > v01.py <<'EOF' import math, html print(html) EOF cat >

## review 0
[model opencode/deepseek-v4.1-flash-free]
**What the diff does.** In `_scan_module_consts` (`AIL_CURRENT/python/pkg-v12/pyfunc.py:1699-1749`), the fallback import refusal now substitutes the first alias whose top-level name is outside a hardcoded 9-module set, instead of the comma-joined import list. Plus tests/records.

**Probes** (HEAD vs `/tmp/base` = `work`, both builds, `cmp.sh`; CPython oracle exit 0 in every case):
- `pre105_01` `import math, html` used in `main`: HEAD default `p.ail:1:1 ... import of 'html'`; base `import of 'math, html'`; general both name html at the use. Intended fix.
- `pre105_12` reversed: HEAD `html`; base `html, math`. `pre105_10` three names: HEAD `html`; base `math, html, sys`. `pre105_17` dotted: HEAD `html.parser`; base `math, html.parser`.
- `pre105_19/20/21/22` (list item, attribute, dict value, argument): HEAD `html`; base joined list; all named refusals.
- `p17` alias `import math, html as h`: HEAD `html`; base `math, html`.
- `p15` `import math, xml`: HEAD `xml`; base `math, xml`. `p18` `import xml, html`: HEAD `xml`; base `xml, html`.
- `pre105_unused`/`p5` unused html: both builds compile, print `2`, match CPython. `p9`/`p7` unused xml/json controls also fine.
- `control` (math/sys, dict/list/loop): both builds compile and print `3 ok`; `program.c` sha256 identical (`5f0b7375…`) on HEAD and base; only `native_report.json` paths differ.
- `p10-p14,p19,p20` (module-level plain value, `json`/`itertools` value, `from html import escape`): byte-identical refusals on HEAD and base.
- `q_csv/q_pathlib/q_sqlite3/q_os/r_datetime/r_time`: library-pass lowered imports before the scan, so HEAD still names `html`; same refusal class as base.
- `q_struct`: pre-existing message rewriter turns `struct` into `class` (base `class, html`, HEAD `class`); not introduced here. `r_http`/`r_socket` name `http`/`socket` first; both are outside the typed path's modelled set and base also named them, so not caused by this change.

**Claims.** Fixed errmsg3 case: verified. Names the first module outside the modelled set: verified for html/html.parser, aliases, reversed and three-name forms; fallback when all names are modelled was not reachable in probes. General path already named html: verified. Unused html builds on both: verified. Commit `92daf18`, 6 files +105/−7, correct trailer: verified. `update_manifest.py --check` exit 0. Tests `test_ail_pre105`, `test_ail_safetynet`: 2 modules, 0 failed (127 s); `test_ail_files`, `test_ail_corpus_findings3`: 2 modules, 0 failed (215 s). The remaining `try: import html` refusal is unlocated and identical to base: verified. Full suite not run, by design.

**Pre-existing (identical on base, not blocking).** `print(html)` at module level (`module html used as a plain value`); `pathlib`/`sqlite3` + html (`read before assigned`); the `struct`→`class` message rewrite; `html.escape` use-site refusal; `http`/`socket` first-name refusals.

**Unverified.** Speed/icount: not run; the change is on a refusal-only path. Full suite: not run by design.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1585576, "input": 55703, "output": 6251, "reasoning": 23462, "cache.write": 0, "cache.read": 1500160}]
    tool time: bash 9.9 min
        217s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1200 python3 ../tools/par_check.py -j 2 test_a
        129s bash   date; cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && timeout 1500 python3 ../tools/par_check.py -j 2 test_a
         35s bash   cd /tmp/rprobes && for p in p1 p2 p3 p4 p5 p6 p7 p8 p9; do echo "===== $p HEAD ====="; timeout 300 bash ~/tool
         29s bash   cd /tmp/rprobes && for p in p14 p15 p16 p17 p18 p19 p20; do echo "===== $p BASE ====="; timeout 300 bash ~/too
         28s bash   cd /tmp/rprobes && cat > p14.py <<'EOF' import json def main():     print(json) main() EOF cat > p15.py <<'EOF
         27s bash   cd /tmp/probes && for p in pre105_01 pre105_02 pre105_12 pre105_17 pre105_19 pre105_22 pre105_unused; do echo 
         21s bash   cd /tmp/rprobes && for p in q_csv q_pathlib q_sqlite3 q_os q_struct; do echo "===== $p BASE ====="; timeout 30
         20s bash   cd /tmp/rprobes && for m in csv pathlib sqlite3 os struct; do cat > q_$m.py <<EOF import $m, html def main(): 

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-24T14:36:09Z
