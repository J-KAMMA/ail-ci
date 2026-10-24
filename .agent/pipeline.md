# job job-perf5-10240813  started 2026-10-23T23:14:10Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Finished and committed (`d45c359`).

**What I found:** the branch already had the decode change: `json_query_file`’s `data.decode("utf-8")` is compiled to `ail_bytes_decode_utf8_view`, so the 1.3 MB copy is gone and only strict validation remains. The missing piece was the stale `cruntime.py` MANIFEST pin plus DEVLOG/measurement records.

**Measurement** (`perf_event_open` is blocked here, so profiling used a /tmp generated-C build with the residual decode validation no-op’d):
- Residual decode validation: 6.757 → 6.251 ms, i.e. 0.506 ms / 7.5% of runtime. Amdahl cap 1.081x for removing it completely.

`python3 bench/compare.py --app json_query`:

| | before (5f10aaa) | after (412156c) |
|---|---:|---:|
| AIL/C ratio | 1.660 [1.635, 1.669] | **1.423 [1.378, 1.447]** |
| AIL median | 7.834 ms | 6.801 ms |
| C median | 4.721 ms | 4.823 ms |
| AIL RSS / binary | 2784 KiB / 154936 B | 2720 KiB / 159416 B |
| C RSS / binary | 2612 KiB / 29512 B | 2612 KiB / 29512 B |

Gain: 14.3% lower AIL/C; ranges are disjoint, above the 3% keep threshold. No `bench/apps` source changed.

**Probes** (`/tmp/probes`, both g and d builds): `decode_sources.py` (literal/argument/slice/list item/attribute/dict value, empty, NUL, 1–4-byte points, invalid sequences), `decode_views.py` (aliasing/rebinding), `decode_unused.py` (validate-only locals), `decode_temporary.py` (ephemeral decode) — all match CPython. `decode_nonbmp.py`: d matches CPython; g refuses by name (`code point above U+FFFF in the 16-bit v2 runtime`).

**Tests on final commit:** `test_ail_memory_shapes`, `test_json_query_file`, `test_json_query_cli`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 6/6 passed. `update_manifest.py --check` clean.
[cost $0.0000, opencode tokens {"total": 4877492, "input": 193998, "output": 25874, "reasoning": 7764, "cache.write": 0, "cache.read": 4649856}]
    tool time: bash 14.6 min
        353s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_memory_shapes test_json_query_f
        275s bash   cd /home/runner/work/ail-ci/ail-ci && python3 tools/par_check.py -j 2 test_ail_memory_shapes test_json_query_f
         54s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/decode_sources.py'); s=p.read_text(); s=s.replac
         52s bash   cd /home/runner/work/ail-ci/ail-ci && python3 bench/compare.py --app json_query 2>&1 | tee /tmp/before_json_qu
         45s bash   cat > /tmp/probes/decode_sources.py <<'PY' class Holder:     def __init__(self, raw: bytes):         self.raw 
         31s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/decode_sources.py'); s=p.read_text(); s=s.replac
         23s bash   cd /home/runner/work/ail-ci/ail-ci && ls /tmp/probes/*.py | xargs -P2 -n1 -I{} bash -c 'echo ==={}===; bash ~/
          9s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/decode_sources.py'); s=p.read_text(); s=s.replac

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Scope.** `work..HEAD` (d45c359) adds only records: MANIFEST cruntime pin, DEVLOG, and the 412156c benchmark JSON. The actual decode-view implementation is in the squashed tree; I reviewed and probed that behaviour as the original task requires.

**Probes** (`/tmp/rprobes`, both g and d), all match CPython unless noted:
- sources/aliasing: parameter, return value, slice, list item, attribute, dict value, literal, empty, NUL, 1–4-byte points, invalid sequences, caught `UnicodeDecodeError`, codec args (`decode_sources`, `p_sources`, `p_retlocal`, `p_retparam`, `p_alias`, `p_nul`, `p_codecargs`, `p_unused2`).
- lifetime/escape: views returned, stored in object fields, dicts, list fields, adopted list fields, early byte-buffer release with intervening allocations (`decode_views`, `p_escape`, `p_field`, `p_dictstore`, `p_listfield`, `p_list_adopt`, `p_escape_early`); generated C confirms container stores copy the view and `ail_str_return_owned` copies before arena free.
- loops/slices: per-line slice views, checkpoints, unused-decode validation (`p_sliceloop`, `p_ckpt*`, `decode_unused`, `p_unused_bad`).
- string ops on views: len/index/slice/find/count/split/join/sort/dict key/compare/encode (`p_ops`, `p_nonascii`, `p_mutate`).
- no-feature program: generated C byte-identical between HEAD and `/tmp/base`; output matches CPython (`p_nofeature`).

**Tests/records.** Six modules (`test_ail_memory_shapes`, `test_json_query_file`, `test_json_query_cli`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`): 6/6 pass on HEAD. `update_manifest.py --check` clean.

**Speed.** Recorded before (5f10aaa) AIL/C `1.660 [1.635,1.669]`; recorded after (412156c) `1.423 [1.378,1.447]`; my fresh rerun `1.362 [1.328,1.393]`, AIL RSS 2.7 MiB, binary 155 KiB. Ranges disjoint, gain >3%. Generated `entry.c` shows `ail_bytes_decode_utf8_view` for the whole input and token slices.

**Pre-existing.** The g (unified/16-bit) build rejects non-BMP input at runtime (`AIL internal error: ... code point above U+FFFF ...`, exit 1 vs CPython 0); identical on `/tmp/base`. Invalid-UTF-8 stderr text also differs from CPython, identical on base.

**Claims.** View emission, stale manifest pin, before/after table, probe results, tests, manifest: verified. "Compile-time refusal" for non-BMP: false (it is a pre-existing runtime error). Profile `6.757 -> 6.251 ms`/Amdahl and the 5f10aaa whole-tree/no-app-source claims: unverified (no artifact; shallow repo). The DEVLOG entry is placed above the `# DEVLOG` title (cosmetic only).

**Unverified.** The residual-validation profile and Amdahl figure; a fresh old-code build (5f10aaa object absent, numbers checked only from committed JSON); instruction-count comparison (timing used instead).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 7682236, "input": 355533, "output": 44575, "reasoning": 19536, "cache.write": 0, "cache.read": 7262592}]
    tool time: bash 11.8 min
        293s bash   cd AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_memory_shapes test_json_query_file t
         52s bash   for f in /tmp/probes/*.py; do echo "=== $f ==="; timeout 300 bash ~/tools/cmp.sh "$f" $PWD 2>&1 | tail -12; do
         46s bash   for f in /tmp/rprobes/*.py; do echo "=== $f ==="; timeout 300 bash ~/tools/cmp.sh "$f" $PWD 2>&1 | tail -25; d
         38s bash   cat > /tmp/rprobes/p_loopfree.py <<'PY' def base() -> bytes:     return b"ABCDEFGHIJ"  def make(i: int) -> byt
         31s bash   cd /home/runner/work/ail-ci/ail-ci && timeout 600 python3 bench/compare.py --app json_query 2>&1 | tail -15; d
         17s bash   cat > /tmp/rprobes/p_ops.py <<'PY' def base() -> bytes:     return "caf\u00e9 \u65e5\u672c\u8a9e abc end".enco
         14s bash   cat > /tmp/rprobes/p_unused2.py <<'PY' def f(b: bytes) -> str:     text = b.decode("utf-8")     return "ok"  d
         14s bash   cat > /tmp/rprobes/p_slices.py <<'PY' def base() -> bytes:     return "caf\u00e9 \u65e5\u672c\u8a9e abc end".e

FINAL VERDICT: ACCEPT  2026-10-24T00:01:51Z
