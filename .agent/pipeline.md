# job job-prog27-11021551  started 2026-11-02T06:54:06Z  worker=oc reviewer=oc (GitHub)

## worker report 0
(free quota used up; paid model from here)
[model opencode-go/deepseek-v4.1-flash]
Committed as `8c135d9` on `job-prog27-11021551`.

**What changed**
- `python/pkg-v12/pyfunc.py`: parameter defaults may now be compile-time `str`/`bytes` literals (previously int/float/bool only). Kind mismatches are still refused by name; list/dict/None defaults are unchanged.
- This unblocks all hot functions of `g05_026` (`build_histogram` 52.4%, `count_words_per_line` 30.5%, `main`), now typed as a whole.
- Table with profiles and follow-ups: `lab/progfix/prog27.md`.
- Follow-ups left by name: `g07_016` (slice assignment + mutable list params), `t223` (nested bool lists + deque of tuples), `t176` (`json.loads` into `list[dict]`), `g17_018` (`singledispatch` repeated `_` names).
- New `AIL_CURRENT/test_ail_prog27.py`, registered via `tests.d/test_ail_prog27.txt`.

**Verification**
- cProfile over all 8 programs; hot-set shares reproduced in the table.
- Generated C for all 10 `lab/compare/src/*/main.ail` tasks: 10/10 SHA-256 identical to base.
- 14 probes in `/tmp/probes/prog27_*` under `cmp.sh`: all matched CPython on both general and default builds; strict refusal cases are covered by the test module.
- Tests: 43 passed, 1 skipped (`--target windows`, no zig); post-commit `test_ail_prog27` 5/5 passed; `update_manifest.py --check` clean.
[cost $0.0376, opencode tokens {"total": 947409, "input": 198335, "output": 4966, "reasoning": 4396, "cache.write": 0, "cache.read": 739712}]
    tool time: bash 14.8 min
        632s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 AIL_EXTRA_CFLAGS=-Werror=incompatible-pointer-types python3 -B -m unittest -v
        125s bash   for f in /tmp/probes/prog27_*.py; do echo "########## $f"; bash ~/tools/cmp.sh "$f" "$PWD" 2>&1 | grep -E 'cpy
         50s bash   sed -i 's/import sys, json/import sys, json, hashlib/' /tmp/codegen_compare27.py && python3 /tmp/codegen_compa
         37s bash   cd AIL_CURRENT && AIL_NO_CACHE=1 python3 -B -m unittest -v test_ail_prog27 2>&1 | tail -60
         35s bash   python3 tools/update_manifest.py --check && echo manifest-ok; cd AIL_CURRENT && AIL_NO_CACHE=1 python3 -B -m u
          7s bash   tmp=$(mktemp -d); for p in lab/census/programs/gdev/g07_016.py lab/corpus/programs/glm-5.3-flash-free/t223.py 
          2s bash   cat > /tmp/codegen_compare27.py <<'PY' import hashlib, json, subprocess, sys, tempfile from pathlib import Pat
          1s bash   tmp=$(mktemp -d); AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py compile lab/corpus/programs/glm-5.3-flash-

## review 0
[model opencode-go/deepseek-v4.1-flash]
## Review: prog27 typed reach

**What the change really does:** Widens the typed-path parameter-default gate in `python/pkg-v12/pyfunc.py` from int/float/bool constants to also accept `str`/`bytes` literals, adding name-based refusals for str↔bytes kind mismatches. Adds `test_ail_prog27.py`, `lab/progfix/prog27.md`, DEVLOG/manifest updates. No programs edited.

**Probes (own, `/tmp/rprobes/`, run on HEAD and `/tmp/base`):**
- `str_kw_default`, `default_ops`, `default_via_containers`, `default_repeat`, `bytes_exotic` (NUL/0xff/quotes/newline), `str_exotic` (NUL/Unicode/quotes): both cmp.sh builds match CPython.
- Strict builds: all these compile typed on HEAD; base refuses `g05_026` at `build_histogram` str default and my strict str-default probes.
- `default_unicode_sem` / `literal_unicode_sem`: match; non-BMP refusal is identical on base (pre-existing).
- `default_ownership`, `default_bytes_return`: 200–300 repeated calls/slices/returns of str/bytes defaults match CPython; no ownership/free corruption.
- `mismatch_int_for_str`, `mismatch_bool_for_str`, `mismatch_int_for_bytes`: AIL matches CPython's TypeError exit/not-output; the same acceptance exists on base (pre-existing).
- Unary `-"a"` / `+b"a"` defaults: non-strict matches CPython; strict refuses by name.
- `g05_026` itself: both builds match CPython; `--strict` succeeds on HEAD, base refuses with the recorded message.
- Strict checks of all 8 programs reproduce the table's typed/refused split and first messages (t176 first reason is the `json.loads` type message; g17_018 fails hard with the duplicate-`_` message).
- Generated C via `--debug-dir` for all 10 `lab/compare/src/*/main.ail`: byte-identical to base (all 10 `program.c` cmp equal).

**Tests:** `par_check.py -j 2 test_ail_prog27 test_ail_refusal_messages test_ail_corpus_findings3 test_ail_files test_ail_safetynet` → 5/5 modules OK, 0 failed (365s). `update_manifest.py --check` clean; commit trailer present.

**Report claims:** verified: what changed; g05_026 now typed as a whole; base refusal message; 10/10 byte-identical C; tests/manifest/DEVLOG/test registration. Minor overstatement: "kind mismatches are still refused by name" only covers the new str/bytes directions — an int/bool default for a `str` parameter is accepted (pre-existing on base, still matches CPython's runtime error), not introduced here.

**Pre-existing (not blocking):** int-default-for-str acceptance; non-BMP string literal refused in the general build. Neither is caused by this change.

**Unverified:** worker's `/tmp/probes/prog27_*` (not present) and exact cProfile percentages (the programs are too small to reproduce without their harness).

VERDICT: ACCEPT
[cost $0.0375, opencode tokens {"total": 1112451, "input": 155586, "output": 7404, "reasoning": 11477, "cache.write": 0, "cache.read": 937984}]
    tool time: bash 9.8 min
        366s bash   cd /home/runner/work/ail-ci/ail-ci; date; python3 tools/par_check.py -j 2 test_ail_prog27 test_ail_refusal_mes
         85s bash   cd /home/runner/work/ail-ci/ail-ci; d=$(mktemp -d); fail=0; for src in lab/compare/src/*/main.ail; do n=$(base
         36s bash   cd /home/runner/work/ail-ci/ail-ci; for f in /tmp/rprobes/*.py; do echo "########## HEAD $f"; bash ~/tools/cmp
         20s bash   cat > /tmp/rprobes/unary_neg_str.py <<'PY' def f(x: str = -"a") -> str:     return x + "!"  def main() -> None
         10s bash   cd /home/runner/work/ail-ci/ail-ci; d=$(mktemp -d); i=0; for f in lab/census/programs/gdev/g05_026.py lab/cens
          9s bash   cd /home/runner/work/ail-ci/ail-ci; d=$(mktemp -d); AIL_NO_CACHE=1 python3 AIL_CURRENT/ail_chatgpt.py compile 
          9s bash   cd /home/runner/work/ail-ci/ail-ci; bash ~/tools/cmp.sh /tmp/rprobes/bytes_exotic.py "$PWD" 2>&1 | tail -12
          9s bash   cat > /tmp/rprobes/bytes_exotic.py <<'PY' def show(data: bytes = b"\x00\xffA\n\\'\"") -> int:     total = len(

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-02T11:54:27Z
