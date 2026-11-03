# job job-onelangs13-11032017  started 2026-11-03T11:18:16Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed `453b685` on `job-onelangs13-11032017`.

Fixed all three review defects:
- Converted `language_examples/byte_search_core.ail` to Python syntax; the quickstart `from byte_search_core import *` block now builds with `--object byte_native.o` and prints `3`.
- Inlined `parse_int64_text` into the `environment_config` example; `AIL_CONFIG_COUNT=9223372036854775808` now raises `ValueError`.
- Rewrote the contract paragraph: `assert` is catchable, may appear anywhere, and `_ail_result` is an ordinary local name.

Probes: byte_search doc block `3`/exit 0; env out-of-int64 `ValueError`; contract probe `caught requires failed in f: n >= 0`, `0`, `1`, exit 0.

Tests:
- `test_ail_reference_docs` OK (skips: `make`, `number_batch`, one non-quickstart reference block)
- `test_ail_quickstart_docs` OK
- `test_ail_reference_examples` OK (1 skip)
- `test_ail_files` OK (1 skip)
- `test_ail_corpus_findings3` OK
- `test_ail_safetynet` fails only pre-existing `S4_generators_gc`
- `update_manifest.py --check` passes.
[cost $0.0000, opencode tokens {"total": 4620221, "input": 70025, "output": 15702, "reasoning": 18526, "cache.write": 0, "cache.read": 4515968}]
    tool time: bash 9.7 min
        332s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; echo '=== files ==='; timeout 1200 python
        123s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ls test_ail_safetynet* && ulimit -v 1500000; echo '=== safet
         66s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; timeout 900 python3 -B test_ail_reference
         17s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; timeout 900 python3 -B test_ail_reference
         17s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; timeout 900 python3 -B test_ail_reference
         10s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; for m in test_ail_quickstart_docs.py test
          2s bash   cd /tmp/bsc && rm -f doc_noobj && python3 -B /home/runner/work/ail-ci/ail-ci/AIL_CURRENT/ail_chatgpt.py compil
          1s bash   cd /tmp/probes && cat > env_base.ail <<'AIL' use environment_config;  fn main() -> int {     try {         pri

## review 0
[model opencode/deepseek-v4.1-flash-free]
## Review 2

**Change.** Converts `language_examples/byte_search_core.ail` to Python syntax, makes the doc test build `byte_native.o` and run that block, inlines `parse_int64_text` in the `environment_config` example, and rewrites the contract paragraph; manifest/DEVLOG updated.

**Claims**
- byte_search_core doc block builds with `--object byte_native.o` and prints `3`: **verified** (also `compile-module` from the preceding example works).
- Out-of-int64 env value raises `ValueError`: **verified** (min/max int64 exact; ±overflow, empty, whitespace/plus, Arabic digit all match the CPython oracle).
- Contract prose: catchable, may appear mid-body/inside `if`, `_ail_result` ordinary local, method names: **verified** by probes matching CPython on both builds.
- Test/manifest claims: **verified** (`test_ail_reference_docs`, `test_ail_quickstart_docs`, `test_ail_reference_examples`, `test_ail_files`, `test_ail_corpus_findings3` OK; `update_manifest.py --check`, `git diff --check` clean).

**Probes (all in /tmp/rprobes, HEAD vs CPython, general + default unless noted)**
- `text_parse.py` 25 boundaries (empty, `+/-`, int64 min/max, ±overflow, Unicode digits, whitespace, leading zeros): same.
- `text_sources.py` values via list item, attribute, dict value, then mutation: same.
- `env_probe.py` 8 env values: default build matches oracle; general path refuses `get_env` by name identically on base.
- `contract.py`, `isqrt_method.py` (incl. method assert): same.
- `byte_scan_stdin.ail` with `--object`: HEAD and base produce the same binary sha256 and `bytes=5\nzeros=2`.
- Unrelated `text_parse.py` `--debug-dir` `program.c`: byte-identical base vs HEAD.

**Pre-existing**
- `test_ail_safetynet` `S4_generators_gc` (general path prints only `5530537`); test file and compiler unchanged on base.
- General path rejects `from ail import get_env` by name; identical on base.

**Unverified.** Full 20-shard CI, speed (docs/example only; no hot-path change).

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 969580, "input": 56255, "output": 9092, "reasoning": 12457, "cache.write": 0, "cache.read": 891776}]
    tool time: bash 7.2 min
        268s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; date; timeout 900 python3 ../tools/par_ch
        130s bash   cd /home/runner/work/ail-ci/ail-ci/AIL_CURRENT && ulimit -v 1500000; date; timeout 1100 python3 ../tools/par_c
          7s bash   cd /tmp/base && for p in text_parse contract; do echo "===== $p BASE ====="; ulimit -v 1500000; timeout 300 ba
          6s bash   cd /home/runner/work/ail-ci/ail-ci && for p in text_parse contract; do echo "===== $p HEAD ====="; ulimit -v 1
          5s bash   cat > /tmp/rprobes/text_sources.py <<'PY' def parse_int64_text(text: str) -> int:     body = text.strip('\t\n\
          5s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/isqrt_me
          3s bash   cat > /tmp/rprobes/contract.py <<'PY' def req(n: int) -> int:     assert n >= 0, 'requires failed in req: n >=
          2s bash   cd /home/runner/work/ail-ci/ail-ci && ulimit -v 1500000; timeout 300 bash ~/tools/cmp.sh /tmp/rprobes/contract

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-03T12:59:37Z
