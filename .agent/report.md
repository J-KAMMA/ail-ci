# job job-stdlib15-10290429  started 2026-10-28T19:31:02Z  worker=oc reviewer=oc (GitHub)
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
Qwen3.8-Flash
DeepSeek-Flash
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"96606ca8-342a-4e13-9b20-af5bbc6b4454","session_id":"dd2a184d-a7a8-462c-a465-764638cb8b57"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"6243fa88-24f9-45fc-b33f-71d23d3ecad4","session_id":"abb8ebd0-3153-4ca0-8586-3f4ea6d1bbee"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed as `563e0f4` on `job-stdlib15-10290429`.

- Chose `struct`: 2 corpus programs + 4 `language_examples` files import it, the next most-imported still-refused module.
- Built `struct.pack`, `struct.unpack`, `struct.calcsize` for literal formats with `< > ! =`, integer codes `b B h H i I l L q Q`, `x` and repeat counts.
- Other struct forms remain named compile-time refusals. Declared difference: `struct.error` maps to `ValueError` in `except` clauses.
- Added `AIL_CURRENT/test_ail_stdlib15.py` (5 tests, general path + `AIL_IR=0/1`) and registered it in `ail_check.MODULES`.
- Updated `DEVLOG.md`, `DIFFERENCES.md`, and `MANIFEST.json`; `update_manifest.py --check` passes.

Probes in `/tmp/probes/stdlib15` on both builds: `p_basic`, `p_errors`, `p_roundtrip`, `p_from_import` match CPython; `p_refuse_dynamic`, `p_refuse_float`, `p_refuse_native`, `p_refuse_unpack_from` are refused by name. `p_type_name` differs only in the declared `struct.error` type name.

Tests on the final commit: `test_ail_stdlib15`, `test_ail_python_syntax`, `test_ail_stdlib_batch1`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 52 run, OK, 1 skip (no zig for Windows target).
[cost $0.0842, opencode tokens {"total": 8555564, "input": 170955, "output": 21340, "reasoning": 34565, "cache.write": 0, "cache.read": 8328704}]
    tool time: bash 33.6 min
        717s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_stdlib15 test_ail_python_syn
        600s bash   mkdir -p /tmp/census/corpus && cd /tmp/headtree && find /home/runner/work/ail-ci/ail-ci/lab/corpus/programs -n
        120s bash   pkill -f 'ail_chatgpt.py compile' 2>/dev/null; ls /tmp/census/corpus/*.rc 2>/dev/null | wc -l; cd /tmp/census/
        117s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && python3 -m unittest -v test_ail_stdlib15 2>&1 | tail -60
        109s bash   cd /tmp/probes/stdlib15 && for f in p_*.py; do echo "########## $f"; bash ~/tools/cmp.sh "/tmp/probes/stdlib15
        100s bash   cd /tmp/probes/stdlib15 && python3 - <<'PY' from pathlib import Path p=Path('p_basic.py') s=p.read_text().repl
         90s bash   cd /tmp/probes/stdlib15 && python3 - <<'PY' from pathlib import Path p=Path('p_basic.py') s=p.read_text().repl
         54s bash   cd /tmp/probes/stdlib15 && for f in p_basic.py p_errors.py p_type_name.py; do echo "########## $f"; bash ~/too

## review 0
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** adds a `struct` small-module lowering in `ail_syntax.py` — a literal-format parser (`< > ! =`, integer codes, `x`, counts), `_ail_struct_pack`/`_ail_struct_unpack` helpers, `struct.error -> ValueError`, plus a test module; the compiler's other paths are untouched.

**Tests / checks:** `test_ail_stdlib15` and `test_ail_safetynet` pass (2 modules, 183s). `update_manifest.py --check` rc 0. A non-struct program's generated C is byte-identical HEAD vs base (`--debug-dir`).

**Probes that matched CPython (general + both default builds):** `p_bool` (bool via literal/arg/list/dict/attr), `p_big` (Q max/min), `p_ws`, `p_repeat` (`>10B`, `>2x3BQ`, zero counts), `p_fuzz` (66 generated formats: sizes, endianness, unpack), `p_mutate` (bytearray mutated after unpack, slice copy), `p_errmsg` (count/range/buffer messages), `p_toplevel`, `p_gen` (pack in a generator), `p_alias`, `p_errors`. Corpus `t475.py` now compiles and matches CPython on `>I` input.

**Report claims:** counts verified (2 corpus programs, 4 `language_examples`); supported formats/codes verified; new test registered; manifest/DEVLOG/DIFFERENCES present; `struct.error` mapping verified as declared (`p_type_name`; `p_errcatch` also shows `except ValueError` now catches, exit 0 vs CPython 1 — the declared consequence of the mapping). "Next most-imported" is unverified: I reproduced the counts but not the census (argparse appears in 9 example files, though only in CLI harnesses). Full 52-test batch and speed were not re-run.

**Pre-existing:** any on-base use of `struct` already fails with `not in the subset: class.<name> ...`; HEAD refusals (float/native/`unpack_from`/dynamic) still show that same `class.pack` primary error alongside the new named note. `memoryview` is unsupported language-wide.

VERDICT: FIX
1. **Format parser is not ASCII-restricted.** `_struct_format` uses `str.isspace()`/`str.isdigit()`, so it accepts characters CPython rejects.
   Probe:
   ```python
   import struct
   print(struct.calcsize(">\x1cI"))
   print(list(struct.pack(">\x1cI", 7)))
   ```
   Expected (CPython): exit 1, no stdout, `struct.error: bad char in struct format`.
   Actual (HEAD, both builds): exit 0, prints `4` and `[0, 0, 0, 7]`. Same class of bug with `">\u0661I"` (CPython `UnicodeEncodeError`; AIL prints `4` / `[0, 0, 0, 7]`). Base refuses `struct` entirely.
2. **`struct.unpack` accepts any sized iterable of ints.** The helper delegates to `int.from_bytes` without requiring bytes/bytearray.
   Probe:
   ```python
   import struct
   print(struct.unpack(">2H", (0, 1, 0, 2)))
   print(struct.unpack(">I", range(4)))
   print(struct.unpack(">I", [0, 0, 0, 1]))
   ```
   Expected (CPython): exit 1, no stdout, `TypeError: a bytes-like object is required, not 'tuple'`.
   Actual (HEAD, both builds): exit 0, prints `(1, 2)`, `(66051,)`, `(1,)`. Base refuses `struct` entirely.
[cost $0.0558, opencode tokens {"total": 2773566, "input": 98198, "output": 12685, "reasoning": 42651, "cache.write": 0, "cache.read": 2620032}]
    tool time: bash 11.9 min
        185s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 1800 python3 tools/par_check.py -j 2 test_ail_stdlib15 test_ail_
        117s bash   cd /tmp/rprobes && for f in p_bool.py p_big.py p_ws.py p_repeat.py p_mutate.py p_errors.py p_basic2.py; do ech
         79s bash   cat > /tmp/rprobes/p_errmsg.py <<'PY' import struct   def case(label: str, run) -> None:     try:         prin
         71s bash   cat > /tmp/rprobes/p_xonly.py <<'PY' import struct  print(struct.calcsize(">3x"), struct.unpack(">3x", b"abc")
         56s bash   cd /tmp/probes/stdlib15 && for f in p_basic.py p_type_name.py p_refuse_float.py p_refuse_native.py p_refuse_un
         52s bash   cat > /tmp/rprobes/p_toplevel.py <<'PY' import struct  print(list(struct.pack(">I", 1))) print(struct.unpack("
         34s bash   python3 - <<'PY' import random, struct rng=random.Random(7) codes={'B':(0,255),'b':(-128,127),'H':(0,65535),'h
         29s bash   cat > /tmp/rprobes/p_unpack_seq.py <<'PY' import struct  print(struct.unpack(">2H", (0, 1, 0, 2))) print(struc

## worker report 1
[model opencode-go/deepseek-v4.1-flash]
Fixed both review defects and committed as `e76fa8b`.

- Format parser now accepts only ASCII `0-9` and the six ASCII whitespace characters; `\x1c`, `\u0661` and `\xa0` are named compile-time refusals.
- `unpack` now requires `bytes`/`bytearray`, raising CPython's `TypeError: a bytes-like object is required, not '<type>'`.
- Added regression coverage in `test_ail_stdlib15.py`; updated DEVLOG/DIFFERENCES; `update_manifest.py` and `--check` pass.

Probes (`/tmp/probes/stdlib15fix`, both builds): `p_unpack_types` and `p_whitespace` match CPython; `p_bad1c`, `p_bad0661`, `p_bad00a0`, `p_badz` are refused by name.

Final-commit tests: `test_ail_stdlib15`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (467s).
[cost $0.0226, opencode tokens {"total": 1650140, "input": 66424, "output": 6430, "reasoning": 6854, "cache.write": 0, "cache.read": 1570432}]
    tool time: bash 21.5 min, edit 0.0 min
        561s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_stdlib15 test_ail_
        471s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 2400 python3 tools/par_check.py -j 2 test_ail_stdlib15 test_ail_
        177s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
         59s bash   cd /tmp/probes/stdlib15fix && python3 - <<'PY' p='p_whitespace.py' s=open(p).read().replace('print(struct.calc
         17s bash   cd /tmp/probes/stdlib15fix && python3 - <<'PY' p='p_whitespace.py' s=open(p).read().replace('">\\t2 H"','">\\t
          1s bash   cd /tmp/probes/stdlib15fix && cat > p_unpack_types.py <<'PY' import struct   def show(label: str, run) -> None
          0s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/update_manifest.py && python3 tools/update_manifest.py --c
          0s bash   cd /home/runner/work/ail-ci/ail-ci && git add AIL_CURRENT/ail_syntax.py AIL_CURRENT/test_ail_stdlib15.py AIL_C

## review 1
[model opencode-go/deepseek-v4.1-flash]
**What the change does:** Adds `struct` to the modeled small-module surface, lowering literal-format `pack`/`unpack`/`calcsize` with prefixes `< > ! =`, codes `b B h H i I l L q Q x` and repeat counts to AIL helpers; maps `struct.error` to `ValueError`; adds `test_ail_stdlib15.py` and registers it. The review commit narrows the parser to ASCII digits/whitespace and adds the bytes-like check in `unpack`. This matches the report.

**Probes (both builds, `cmp.sh`, vs CPython 3.12):**
- `p_basic`, `p_bool`, `p_repeat`, `p_big`, `p_xonly`, `p_errmsg`: same stdout/exit as CPython (all codes, both orders, `=`/`!`, repeats, `x`, zero/prefix-only formats, values via argument/list/alias/attribute/dict, bytes/bytearray).
- `p_errors` (count/range/buffer messages): same. `p_types` (tuple/list/range/str/int rejected; bytes/bytearray accepted): same. `p_alias` (mutate bytearray after unpack, slice copy): same. `p_ws`: same. `p_fuzz_lit`: 120 random literal formats with boundary values and range errors — same.
- Refused by name: `p_bad1c`, `p_bad0661`, `p_bad00a0`, `p_badz`, `p_dyn`, `p_star`, `p_funval`, `p_countws`. Worker's `/tmp/probes/stdlib15fix` probes reproduce too.
- Non-feature program `p_plain`: `program.c` identical between base (`/tmp/headtree`) and HEAD.

**Claims:** ASCII-only parser, bytes-like `unpack`, test registration, manifest check (`--check` passes), commit trailers and all four claimed modules (`test_ail_stdlib15`, `safetynet`, `files`, `corpus_findings3`: 0 failed) verified. "Sizes match CPython" is false at the size boundary below. "Next most-imported still refused" is at best arguable: `argparse` (9 files) and `tempfile` (7) are also unbuilt in the two directories, though only in `language_examples` harnesses.

**Defects:**

1. Missing total-size guard. Probe `/tmp/rprobes/p_huge2.py`:
```python
import struct
def main() -> None:
    print(struct.calcsize(">99999999999999999999I"))
    print("end")
main()
```
Expected (CPython): `struct.error: total struct size too long`, exit 1, no stdout. Actual (both builds): prints `399999999999999999996` and `end`, exit 0. CPython accepts sizes up to `2**62-1` and rejects `2**62` and above (`calcsize(">4611686018427387904x")` fails); `_struct_format` has no such cap. The same missing check means `pack` with an `x` count above the limit would attempt an enormous zero allocation instead of raising `struct.error`.

**Notes / pre-existing:** `calcsize("")` is a named refusal in AIL vs `0` in CPython (empty string has no prefix; acceptable as a refusal, but "empty formats match" only holds for prefix-only bodies). `memoryview` is not a known AIL builtin, so `struct.unpack` of one is a named refusal, not caused by this change.

VERDICT: FIX
[cost $0.0347, opencode tokens {"total": 1646505, "input": 72883, "output": 9868, "reasoning": 21994, "cache.write": 0, "cache.read": 1541760}]
    tool time: bash 15.7 min
        290s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_files test_ail_corpus_f
        175s bash   cd /home/runner/work/ail-ci/ail-ci && date && python3 tools/par_check.py -j 2 test_ail_stdlib15 test_ail_safet
        105s bash   cat > /tmp/rprobes/p_basic.py <<'PY' import struct  class Box:     def __init__(self, v: int) -> None:        
         79s bash   cd /tmp/rprobes && date && for p in p_basic p_bool p_errors p_types p_alias p_ws; do echo "########## $p"; bas
         64s bash   cd /tmp/rprobes && python3 - <<'PY' import random rng=random.Random(4242) codes={'b':(-128,127),'B':(0,255),'h
         60s bash   cd /home/runner/work/ail-ci/ail-ci && date && nohup python3 tools/par_check.py -j 2 test_ail_stdlib15 test_ail
         42s bash   cd /tmp/rprobes && date && for p in /tmp/probes/stdlib15fix/p_badz.py /tmp/probes/stdlib15fix/p_unpack_types.p
         42s bash   python3 - <<'PY' import struct for f in ['>2147483648I','>4611686018427387904I','>99999999999999999999I','>0x7

FINAL VERDICT: FIX  2026-10-28T21:40:55Z
