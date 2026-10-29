# job job-stdlib32-10291014  started 2026-10-29T01:37:52Z  worker=oc reviewer=oc (GitHub)
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
DeepSeek-Flash -> ts":0},"service_tier":"standard","cache_creation":{"ephemeral_1h_input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["Your personal Credits have been exhausted. Please check your plan."],"error_code":118,"fast_mode_state":"off","uuid":"b4bab375-5ab6-4085-a460-da17f61e7fa6","session_id":"069983f2-ab3d-443c-9d80-2461ebb26fa2"}
DeepSeek-Flash -> input_tokens":0,"ephemeral_5m_input_tokens":0},"inference_geo":"","iterations":[],"speed":"standard"},"modelUsage":{"<synthetic>":{"inputTokens":0,"outputTokens":0,"cacheReadInputTokens":0,"cacheCreationInputTokens":0,"webSearchRequests":0,"costUSD":0,"contextWindow":0,"maxOutputTokens":0}},"permission_denials":[],"errors":["You've reached your credit usage limit. Please upgrade your subscription plan to get more resources. Report Issue (input /feedback)"],"error_code":118,"fast_mode_state":"off","uuid":"b6070c6d-16ee-4659-8a62-080d0285e0a0","session_id":"27c7318f-133f-4218-9ad1-36bb8939139e"}

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Implemented and committed on `job-stdlib32-10291014` (code commit `dbfe75f`, records follow-up `32c6565`).

**Result**
- `unicodedata` was the next most-imported still-refused module: 3 corpus programs (`t081.py`, two `t489.py`).
- Built `name`, `category`, and `normalize` (NFC/NFD/NFKC/NFKD) from Unicode 15.0 data generated from CPython 3.12.3: 30 categories, 32,943 names, 14 algorithmic ranges, 5,857 decompositions, 941 composition pairs.
- Everything else, non-string defaults, and literal non-character arguments are refused by name on both builds.
- Added `AIL_CURRENT/test_ail_stdlib32.py` (5 tests) and registered it in `ail_check.MODULES`.

**Probes** (`cmp.sh`, both builds unless noted)
- `u_smoke`, `u_more`, `u_routes`, `u_alias`: match CPython.
- `u_astral`: typed matches; general refuses the non-BMP literal by name (pre-existing 16-bit limitation).
- `u_default_none`, `u_default_int`, `u_badargs`, `u_str_errors`, `u_exc_type`: refused by name.
- Corpus `deepseek t489` on empty input: both builds match.

**Final tests**
- `test_ail_stdlib32` 5 OK; `test_ail_stdlib_batch4` 19 OK; `test_ail_stdlib5` 10 OK.
- `test_ail_check` 7 OK; `test_ail_files` 18 OK (1 skipped); `test_ail_corpus_findings3` 2 OK; `test_ail_safetynet` 5 OK.
- `tools/update_manifest.py --check` passes.

No push performed.
[cost $0.0726, opencode tokens {"total": 7625016, "input": 137740, "output": 21747, "reasoning": 27705, "cache.write": 0, "cache.read": 7437824}]
    tool time: bash 51.0 min
        650s bash   cd AIL_CURRENT && python3 test_ail_stdlib_batch4.py 2>&1 | tail -10
        484s bash   cd AIL_CURRENT && python3 test_ail_stdlib5.py 2>&1 | tail -10
        442s bash   cd AIL_CURRENT && python3 test_ail_corpus_findings3.py 2>&1 | tail -8
        343s bash   cat > /tmp/probes/u_routes.py <<'PY' import unicodedata   class Box:     def __init__(self, ch: str) -> None: 
        245s bash   python3 - <<'PY' lines = ["import unicodedata", "", "def main() -> None:"] def emit(label, expr):     lines.ap
        244s bash   cd AIL_CURRENT && python3 test_ail_safetynet.py 2>&1 | tail -12
        231s bash   for p in u_default_none u_default_int u_badargs u_more u_astral; do d=$(mktemp -d); cp /tmp/probes/$p.py $d/p.
        175s bash   cd AIL_CURRENT && python3 test_ail_files.py 2>&1 | tail -8

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: stdlib32 (`unicodedata`)

**What the change really does:** adds a tree-to-tree `unicodedata` lowering pass plus a generated Unicode 15.0 data core (`ailuni_core.h`) with typed and general adapters, supporting `name`, `category` and `normalize`, and refusing the other members. This matches the report.

**Probes run** (`bash ~/tools/cmp.sh` unless noted)
- `u_bmp_all`: all BMP code points, `category` + `name(ch,"?")` — both builds match CPython (surrogates excluded; see Pre-existing).
- `u_nonbmp_sample`: every 13th non-BMP code point, typed-only build — 80,661 lines match CPython.
- `u_astral2`: typed-only — algorithmic ranges, Hangul, astral decompositions/composition, all four forms match.
- `u_normrand`: 60 edge/random BMP strings × 4 forms — both builds match.
- `u_routes`: argument, list item, slice, attribute, dict value, runtime form — both builds match.
- `u_errs`, `u_types`: **differ** (defects below).
- `u_surr`, `u_localimport`, `u_condimport`, `u_litrefuse*`: refused by name (pre-existing limitations) or match.
- Non-user program: `--debug-dir` `program.c` byte-identical to base (`git worktree` at `work`).

**Report claims**
- 3 corpus imports (`t081.py`, two `t489.py`): verified.
- 30 categories / 32,943 names / 14 ranges / 5,857 decompositions / 941 pairs: verified; regenerating the header is byte-identical to the committed one.
- “Everything else … refused by name”: verified for literals, unsupported members and non-string defaults, but **false** for a runtime string that is not one character: it compiles and raises the wrong exception (defect 1).
- New test module registered, 5 tests: verified; `test_ail_stdlib32`, `test_ail_safetynet`, `test_ail_check` pass on HEAD.
- Other final tests (`batch4`, `stdlib5`, `files`, `corpus_findings3`): not re-run (per instructions only new/changed + safetynet).

**Pre-existing:** the general path’s refusal of non-BMP literals/`chr`, and of lone-surrogate literals, is the 16-bit runtime limitation present on the base; not caused by this change.

**Unverified:** exhaustive non-BMP names (sampled every 13th); instruction counts (not run — non-user generated C is byte-identical, so no hot-path change).

### Defects

1. **Typed/default build raises `ValueError` instead of `TypeError` for a runtime string that is empty or longer than one character** (`name`, `category`, and two-argument `name`). The general build is correct; the typed adapter raises `AIL_EXC_VALUE` for the wrong-length case.
   Probe:
   ```python
   import unicodedata
   def probe(x: str) -> None:
       try: print(unicodedata.name(x))
       except Exception as e: print(type(e).__name__, e)
       try: print(unicodedata.category(x))
       except Exception as e: print(type(e).__name__, e)
   def main() -> None:
       probe("ab"); probe("")
   main()
   ```
   Expected (CPython and general build): `TypeError name() argument 1 must be a unicode character, not str` / `TypeError category() argument must be a unicode character, not str`.
   Actual (typed/default build): `ValueError` with the same text, for both strings and both functions; same for `name(x, "d")`.

2. **General path names `bytes`/`bytearray` as “instance” in the TypeError text.**
   Probe:
   ```python
   import unicodedata
   def main() -> None:
       b = b"a"
       try: unicodedata.name(b)
       except Exception as e: print(type(e).__name__, e)
       try: unicodedata.category(b)
       except Exception as e: print(type(e).__name__, e)
       try: unicodedata.normalize("NFC", b)
       except Exception as e: print(type(e).__name__, e)
   main()
   ```
   Expected: `... not bytes` (and `not bytearray` for a bytearray).
   Actual (general and default builds): `... not instance` for both `bytes` and `bytearray`, in `name`, `category` and `normalize` argument 2.

VERDICT: FIX
1. Typed/default build: wrong `ValueError` for runtime empty/multi-character str in `name`/`category` (probe `u_rtchar2`; expected `TypeError`, actual `ValueError`).
2. General/default build: `not instance` instead of `not bytes` / `not bytearray` in the TypeError messages (probe `u_types`).
[cost $0.0419, opencode tokens {"total": 2888558, "input": 86705, "output": 10836, "reasoning": 23529, "cache.write": 0, "cache.read": 2767488}]
    tool time: bash 6.2 min
        138s bash   cd AIL_CURRENT && date && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_stdlib32 test_ail_safetynet 
        120s bash   python3 - <<'PY' import random, unicodedata rng = random.Random(20261029) pool = [] for cp in range(0x10000): 
         20s bash   cat > /tmp/rprobes/u_errs.py <<'PY' import unicodedata   def main() -> None:     vals = [None, 7, 1.5, b"a", [
         19s bash   python3 - <<'PY' import random, unicodedata rng = random.Random(20261030) pool = [] for cp in range(0x10000): 
         18s bash   cat > /tmp/rprobes/u_types.py <<'PY' import unicodedata   def main() -> None:     b = b"a"     ba = bytearray(
          7s bash   cat > /tmp/rprobes/u_plain.py <<'PY' def main() -> None:     xs = [1, 2, 3]     total = 0     for x in xs:    
          6s bash   cat > /tmp/rprobes/u_bmp_all.py <<'PY' import unicodedata   def main() -> None:     cp = 0     while cp < 0x10
          5s bash   python3 - <<'PY' p="/tmp/rprobes/u_routes.py" s=open(p).read() s=s.replace('    default = "nope"\n    print(un

## fix round skipped: only 82 minutes left

FINAL VERDICT: FIX  2026-10-29T05:10:20Z
