# job job-pre196-10252020  started 2026-10-25T11:20:59Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":525,"duration_api_ms":406,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server
DeepSeek-Flash -> {"type":"result","subtype":"error_during_execution","duration_ms":596,"duration_api_ms":478,"is_error":true,"num_turns":1,"stop_reason":"stop_sequence","total_cost_usd":0,"total_credits":0,"usage":{"input_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0,"output_tokens":0,"server

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Fixed the pre-existing class-value repr difference.

- **Cause/change:** v2 runtime `ail__write_repr_body` had no `AIL_T_CLASS` case; user classes printed `<object>`. Added CPython-style `<class '__main__.C'>` in `python/pkg-v12/cruntime.py`. Base confirmed `<object>`; now both builds match CPython.
- **Probes** (`bash ~/tools/cmp.sh`, both builds): `p1,p9,p10,p16,p18` match CPython (direct, alias, argument/default, list, dict, attribute, return, containers, `str`/`print`, f-string, `%`). `p6,p7,p17,p14,p15` are refused by name. `p8` (rebinding `__name__`) remains a separate pre-existing `__module__` limitation.
- **Unverified:** builtin-class repr branch is unreachable via tested constructs; explicit `format(C)` still hits the pre-existing non-int formatter; speed check not run (`perf_event_open` denied).
- **Tests on commit `635f179`:** `test_ail_pre196` ok 4.8s, `test_ail_safetynet` ok 101.9s, `test_ail_files` ok 109.3s, `test_ail_corpus_findings3` ok 165.5s — 4 modules, 0 failed. `update_manifest.py --check` rc 0.
- **Added:** `test_ail_pre196.py`, DIFFERENCES row, DEVLOG entry, manifest pins.
[cost $0.0206, opencode tokens {"total": 1235834, "input": 46762, "output": 4489, "reasoning": 12231, "cache.write": 0, "cache.read": 1172352}]
    tool time: bash 6.4 min, edit 0.0 min
        269s bash   cd AIL_CURRENT && timeout 3000 python3 ../tools/par_check.py -j 2 test_ail_pre196 test_ail_safetynet test_ail_
         50s bash   for f in /tmp/probes/pre196/*.py; do echo "===== $f"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | tail -12; done
         19s bash   mkdir -p /tmp/probes/pre196 && cat > /tmp/probes/pre196/p14_builtin_type_objects.py <<'EOF' print(repr(type(1)
         13s bash   for f in /tmp/probes/pre196/p1_class_repr.py /tmp/probes/pre196/p9_repr_routes.py /tmp/probes/pre196/p16_class
         12s bash   grep -o '.\{0,300\}rbpre170.\{0,500\}' /home/runner/work/_temp/work0.jsonl | head -20
         11s bash   bash ~/tools/cmp.sh /tmp/probes/pre196/p12_format_class.py "$PWD"; echo ====; bash ~/tools/cmp.sh /tmp/probes/
          5s bash   cd AIL_CURRENT && timeout 900 python3 -m unittest -q test_ail_pre196 2>&1 | tail -20
          3s bash   cat > /tmp/probes/pre196/p19_class_attr.py <<'EOF' class C:     pass c = C() print(repr(c.__class__)) print(re

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review of `635f179`

**What the change really does:** Adds an `AIL_T_CLASS` case to the v2 runtime repr writer (`python/pkg-v12/cruntime.py:16248`), emitting `<class '__main__.NAME'>` for user classes and `<class 'NAME'>` for builtin classes, plus the test/DIFFERENCES/DEVLOG/manifest records. The report describes this accurately.

**Probes (both builds unless noted; base = `/tmp/base`):**
- Worker probes `p1,p9,p10,p16,p18`: all match CPython — verified.
- Mine: `r2` (user/builtin exception subclasses), `r5` (argument/attribute/dict/tuple), `r13`, `r15` (dataclass/namedtuple), `r17` (class variable rebound), `r19` (GC pressure then repr): all match.
- Refused by name on both builds: `r1` (bare builtin classes), `r3` (non-ASCII name), `r4`/`r12` (`for`/`try`-nested class), `p6`/`p7`/`p14`/`p15`/`p17` (nested/local/`type()`/`Exception`/`if`-class).
- `p8`/`r6` (`__name__ = 'foo'`): HEAD `<class '__main__.C'>` vs CPython `<class 'foo.C'>`; base `<object>`. Construct already wrong on base; documented `__module__` gap, not introduced.
- Pre-existing, identical on base: `p12`/`r9` (`format(C)` TypeError), `r7`/`r10`/`r11` (`__base__`/`__class__`/name mutation raise), `r14` (enum class repr), `r16` (class unhashable), `p5` (duplicate class definition refused).
- Non-feature gdev: `g00_000` matches on HEAD and base; `g01_008` differs identically on both.

**Claims:** base `<object>` / both builds now match — verified; builtin-class branch unreachable — verified; nested/local/`if` classes refused — verified; `format(C)` pre-existing — verified; `p8` pre-existing `__module__` limitation — verified (with the text-change nuance above); `test_ail_pre196` + `test_ail_safetynet` pass — verified; `update_manifest.py --check` rc 0 — verified. Claim that this was the **first item recorded by the rbpre170 review** is **unverified**: the supplied task contains no item list and no rbpre170 review artifact is available.

**Tests:** `par_check.py -j 2 test_ail_pre196 test_ail_safetynet` → 2 modules, 0 failed (5.5s, 101.3s). `test_ail_files`/`test_ail_corpus_findings3` not re-run (unverified; outer review rule limits reruns).

**Not checked:** instruction-count speed (repr-only switch case; `perf_event_open` denied). Generated `.c` for non-class programs is not byte-identical because the runtime text is embedded in every build; behavior on such programs was verified instead.

No defect introduced by the change.

VERDICT: ACCEPT
[cost $0.0469, opencode tokens {"total": 3777324, "input": 107549, "output": 8211, "reasoning": 24828, "cache.write": 0, "cache.read": 3636736}]
    tool time: bash 6.8 min
        103s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && date && timeout 1200 python3 ../tools/par_check.py -j 2 test
         87s bash   cd /home/runner/work/ail-ci/ail-ci && for f in ~/corpus/gdev/g00_000.py ~/corpus/gdev/g01_008.py; do echo "###
         41s bash   grep -n "class\|repr\|print" ~/corpus/gdev/g01_008.py | head -20; echo ---; cd /home/runner/work/ail-ci/ail-ci
         36s bash   cd /tmp/rprobes && cat > r8_shadow.py <<'EOF' class int:     pass class C:     pass print(repr(int)) print(rep
         25s bash   cd /home/runner/work/ail-ci/ail-ci && for f in /tmp/rprobes/*.py; do echo "########## $f"; timeout 300 bash ~/
         21s bash   cd /home/runner/work/ail-ci/ail-ci && for f in p1_class_repr p9_repr_routes p10_custom_instance_repr p16_class
         20s bash   cd /tmp/rprobes && cat > r14_enum_class.py <<'EOF' from enum import Enum, IntEnum, Flag, auto class Color(Enum
         14s bash   cd /tmp/rprobes && cat > r10_name_mutation.py <<'EOF' class C:     pass C.__name__ = 'X' print(repr(C)) print(

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-10-25T12:45:48Z
