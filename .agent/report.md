# job job-csv1-10282318  started 2026-10-28T14:19:11Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> uests":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You have reached the daily usage limit. Please try again later."],"error_code":110,"fast_mode_state":"off","uuid":"1f4a6677-26ac-4e3c-b46d-f9bea36b3be7","session_id":"0e83913e-61b4-4d97-bf24-de2b88328ae8"}
DeepSeek-Flash -> l_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your daily usage limit for Chat. Come back tomorrow to continue working with me. Report Issue (input /feedback)"],"error_code":110,"fast_mode_state":"off","uuid":"cb774e13-db56-48ce-87ee-d0a0c8b9d7be","session_id":"27dd3a30-7005-4255-b664-6271448c1c39"}

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Implemented and committed as `e1e79fc` on `job-csv1-10282318`.

**Cause:** CI’s setup-python installs the latest 3.12 (3.12.15); CPython 3.12.5 changed `csv.QUOTE_NONNUMERIC` so a field starting with `escapechar` is parsed as a number. The sandbox has 3.12.3, where the old behaviour matches the old prelude.

**Fix:**
- `prelude_csv.py` now follows the interpreter it is built with; `csvgen.py` substitutes the compiler’s CPython version.
- Typed `csvlib` reader now refuses `QUOTE_NONNUMERIC` by name instead of silently returning strings; the general path handles it.
- Added deterministic escaped-field cases to `test_ail_cov2` and a typed-reader refusal case to `test_ail_stdlib_batch4`.
- Added DEVLOG and DIFFERENCES entries; `update_manifest.py --check` passes.

**Probes** (`cmp.sh`, both builds, system 3.12.3 and hosted 3.12.15):
- `csv_escaped.py` — escaped start/middle, quoted, empty, minimal/all/none, blank, spaces: all matched.
- `csv_routes.py` — source via argument, list item, attribute, dict value, dynamic quoting: all matched.
- `csv_typed.py` — general path matched; default build now falls back to it and matched (previously a C build failure).

**Tests on final commit:**
- `PreludeCsv`: 3/3 pass on both 3.12.3 and 3.12.15.
- `test_ail_stdlib_batch4`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: pass.
- `test_ail_cov2`: only 3 pre-existing failures remain (`fl2b` both builds, `test_wide_flag_member`); all reproduced unchanged on base `bb4574e`.
[cost $0.0000, opencode tokens {"total": 4951325, "input": 120471, "output": 13231, "reasoning": 17623, "cache.write": 0, "cache.read": 4800000}]
    tool time: bash 19.6 min, websearch 0.0 min, edit 0.0 min
        412s bash   python3 ../tools/par_check.py -j 2 test_ail_cov2 test_ail_stdlib_batch4 test_ail_safetynet test_ail_files test
        406s bash   python3 ../tools/par_check.py -j 2 test_ail_cov2 test_ail_stdlib_batch4 test_ail_safetynet test_ail_files test
        176s bash   git worktree add /tmp/base HEAD >/tmp/wt.log 2>&1 && cd /tmp/base/AIL_CURRENT && python3 -m unittest test_ail_
        120s bash   find / -path /proc -prune -o -name "_csv.c" -print 2>/dev/null | head; find /opt/hostedtoolcache/Python/3.12.1
         13s bash   for p in /tmp/probes/csv_escaped.py /tmp/probes/csv_routes.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$
         13s bash   export PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH; python3 --version; for p in /tmp/probes/csv_esc
          8s bash   export PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH; python3 --version; for p in /tmp/probes/csv_esc
          7s bash   for p in /tmp/probes/csv_escaped.py /tmp/probes/csv_routes.py; do echo "===== $p"; bash ~/tools/cmp.sh "$p" "$

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review of `e1e79fc` (`job-csv1-10282318`)

**What the change really does.** The general-path `csv` prelude sets the QUOTE_NONNUMERIC numeric flag for a field that starts with the escapechar only when the *compiling* CPython is `>= 3.12.5`; `csvgen.py` bakes the compiler's version into the prelude. The typed `csvlib` reader now refuses QUOTE_NONNUMERIC by name instead of silently returning strings. It matches the report.

**Probes** (HEAD, both builds; 3.12.3 and hosted 3.12.15 unless noted):
- `csv_esc_start.py` (escaped start, trailing escape), `csv_esc_mid.py` (escaped delimiter/quote/newline, quoted, empty), `csv_skipspace.py`, `csv_nonnumeric.py`, `csv_dict.py`, `csv_from.py`, `csv_qvar.py`, `csv_opts.py` (quoting/escapechar through argument, list item, attribute, dict): all same stdout as CPython on both versions and both builds.
- `csv_routes.py` (source via argument/list item/attribute/dict/splitlines): matched both versions.
- `diffcsv2.py`: 30,000 random dialect cases, prelude vs `csv`: 0 diffs on 3.12.3 and 3.12.15.
- Base `/tmp/base` on 3.12.15 gives strings where HEAD gives floats, confirming the fix.
- `csv_typed.py`/`csv_typed_esc.py`: default build matches; `AIL_NO_GENERAL=1` refuses with “QUOTE_NONNUMERIC”.

**Tests on HEAD.**
- 3.12.15 `par_check.py -j 2 test_ail_cov2 test_ail_stdlib_batch4 test_ail_safetynet test_ail_files test_ail_corpus_findings3`: only `test_ail_cov2` fails, with exactly the 3 pre-existing failures (`fl2b` both builds, `test_wide_flag_member`). Base 3.12.15 has those plus the target `test_reader`.
- 3.12.3 `test_ail_cov2`: same 3 pre-existing failures; `PreludeCsv` 3/3.
- `PreludeCsv` under `LC_ALL=C`, `LANG` unset, 3.12.15: OK.
- `tools/update_manifest.py --check`: exit 0.

**Report claims.** Cause (3.12.5 escaped-start numeric, sandbox 3.12.3 old) verified; prelude/csvgen version handling verified; typed refusal verified; added tests, DEVLOG, DIFFERENCES, manifest verified. Two inaccuracies: “the general path handles it” is overbroad — `csv.reader(sys.stdin, quoting=QUOTE_NONNUMERIC)` now fails to compile with `not in the subset: sys.stdin used as a plain value` (base compiled, wrongly on 3.12.15); and “previously a C build failure” was not reproduced — base compiled and silently returned strings. The stdin failure is a named compile-time refusal, so acceptable under the rules, but it does not name QUOTE_NONNUMERIC.

**Pre-existing.** `fl2b` both builds; `test_wide_flag_member`; eager reader snapshot (mutating the source list after `csv.reader` is constructed is ignored, same on base); general-path csv over `sys.stdin` with a typed-refused construct already failed with “sys.stdin used as a plain value”; on 3.13/3.14 the prelude lacks CPython's new “bad escapechar or quotechar value” validation (outside the 3.12 CI).

**Unverified.** The worker's exact probe files; speed (not hot code); `test_ail_stdlib_batch4` under 3.12.3.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 4435889, "input": 73857, "output": 15058, "reasoning": 34270, "cache.write": 0, "cache.read": 4312704}]
    tool time: bash 16.1 min, websearch 0.0 min
        363s bash   cd /home/runner/work/ail-ci/ail-ci && export PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH && python3
        183s bash   cd /tmp/base/AIL_CURRENT && export PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH && python3 -m unitte
        179s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -q test_ail_cov2 2>&1 | grep -E "^(FAIL|
         30s bash   cd /tmp/rprobes export PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH python3 --version for p in csv_e
         23s bash   cd /tmp/rprobes cat > csv_esc_start.py <<'EOF' import csv  def p1():     r = csv.reader("1\\.5,\\.5,.5".splitl
         22s bash   export PATH=/opt/hostedtoolcache/Python/3.12.15/x64/bin:$PATH d=$(mktemp -d /tmp/spXXXX); cd $d cat > p.py <<'
         20s bash   cd /tmp/rprobes for p in csv_esc_start.py csv_esc_mid.py csv_skipspace.py csv_routes.py csv_nonnumeric.py; do 
         18s bash   cd /tmp/rprobes cat > csv_from.py <<'EOF' from csv import reader, QUOTE_NONNUMERIC  lines = ["1\\.5,\\.5", "\\

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-28T16:21:17Z
