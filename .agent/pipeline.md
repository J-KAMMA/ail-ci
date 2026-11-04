# job job-std_hashlib-11041240  started 2026-11-04T03:42:42Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Committed on branch `job-std_hashlib-11041240` as `e5075c9`.

- Added 12 programs in `lab/stdlib/hashlib/` plus stdin data files and `RESULTS.md`.
- Result: **11/12 typed and equal to CPython** in the default build; `11_digest_integer.py` matches with `--exact-int` (its 8-byte digest value is beyond int64).
- SHA-256 of 256 MiB: AIL **0.21 s**, CPython **0.20 s**, `sha256sum` **0.18 s**; SHA-NI available and used (`AIL_HASH_NO_SHANI=1` gives 0.93 s).
- Registered `test_ail_std_hashlib.py` and updated the manifest.
- Passing: `test_ail_std_hashlib`, `test_ail_crypto`, `test_ail_std_base64`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`.

No push or 20-shard CI run was done, per the runner instruction not to push.
[cost $0.0000, opencode tokens {"total": 3902873, "input": 102189, "output": 16450, "reasoning": 23466, "cache.write": 0, "cache.read": 3760768}]
    tool time: bash 13.4 min
        324s bash   python3 tools/par_check.py -j 2 test_ail_safetynet test_ail_files test_ail_corpus_findings3 2>&1 | tail -80
        238s bash   python3 tools/par_check.py -j 2 test_ail_std_hashlib test_ail_crypto test_ail_std_base64 2>&1 | tail -80
        108s bash   set -u rm -rf /tmp/hlforce && mkdir -p /tmp/hlforce for f in lab/stdlib/hashlib/*.py; do   b=$(basename "$f" .
         25s bash   git add AIL_CURRENT/manifest.d/14.txt AIL_CURRENT/manifest.d/d7.txt && python3 tools/par_check.py -j 2 test_ai
         24s bash   set -u for b in 05_copy_running 11_digest_integer; do   f=lab/stdlib/hashlib/$b.py   rm -f /tmp/hlbuild/$b   p
         23s bash   set -u rm -rf /tmp/hlbuild && mkdir -p /tmp/hlbuild for f in lab/stdlib/hashlib/*.py; do   b=$(basename "$f" .
         12s bash   set -u rm -rf /tmp/hlbuild && mkdir -p /tmp/hlbuild for f in lab/stdlib/hashlib/*.py; do   b=$(basename "$f" .
         11s bash   cat > /tmp/probes/p6.py <<'EOF' import hashlib import sys   def main() -> None:     data = sys.stdin.buffer.re

## review 0
[model opencode/deepseek-v4.1-flash-free]
**Review of `e5075c9` (`work..HEAD`)** — 2026-11-04

**What the change really does:** adds 12 hashlib/hmac sample programs, two stdin data files, `RESULTS.md`, `test_ail_std_hashlib.py`, and the `tests.d`/manifest registration. No compiler or runtime code is touched.

**Probes** (`bash ~/tools/cmp.sh`, HEAD vs `/tmp/base`, default + `AIL_UNIFIED_FORCE=1`):

| probe | result |
|---|---|
| `p_construct.py` (names, aliases, bad names) | all equal except `shake_128`; same difference on base (pre-existing) |
| `p_blake2.py` (digest_size 0/1/33/64/65, salt/person/key limits) | both builds equal to CPython |
| `p_hmac.py` (key lengths 0/1/63/64/65/200, empty msg, ctor/hyphen name, compare types) | equal |
| `p_pbkdf2.py` (iter 0/1, dklen 0/1/65/100, md5/sha1/sha512, bad name) | equal |
| `p_alias2.py` (bytearray mutated after constructor and after `update`; digest stability) | equal |
| `p_values.py` (hash via argument, list item, dict value, attribute) | equal |
| `p_bigint.py` (unsigned 8-byte `int.from_bytes`, both orders) | default stops `OverflowError` on HEAD **and** base (pre-existing) |
| `hello.py` (`--debug-dir`) | `program.c` byte-identical HEAD vs base |

`memoryview` input is refused by name on both builds (acceptable).

**Programs/tests:** all 12 build; all 12 carry no general-path note in the default build. 01–10 and 12 print CPython's output; 11 stops in default and matches CPython only with `--exact-int` (general path). That is 11/12 typed and equal, meeting the ≥10/12 done-check. `test_ail_std_hashlib` (24 s) and `test_ail_safetynet` (244 s) pass; `update_manifest.py --check` passes.

**Throughput:** reproduced on 256 MiB: AIL median 0.28 s (0.26–0.30), CPython 0.27 s, `sha256sum` 0.22 s, `AIL_HASH_NO_SHANI=1` 1.77 s; all three printed the same digest. SHA-NI is present and used; the worker's absolute figures differ somewhat but the conclusion is right.

**Claims:** 11/12 typed+equal = verified; 11 beyond-int64 with `--exact-int` = verified; SHA-NI = verified; no changes to `hashlower.py`/`hash_prelude.py`/`ailhash_core.h` = verified; 20-shard CI = unverified (no push, per runner instruction); `test_ail_crypto`, `test_ail_std_base64`, `test_ail_files`, `test_ail_corpus_findings3` = unverified (not re-run, per review step 3; no code they depend on changed). "All 12 print CPython's stdout/exit" is true only with `--exact-int` for 11; the report discloses this. The "05 was general before" claim is unverified (pre-fix state is not in git), but current 05 is typed and equal. The only "fix" is a rewrite of `05_copy_running.py` to avoid the list-literal typed-path refusal; no compiler code changed.

**Pre-existing differences (non-blocking):** `shake_128` unsupported; unsigned 8-byte `int.from_bytes` overflows int64 in the default build; `memoryview` refused by name.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1538622, "input": 45447, "output": 8574, "reasoning": 30521, "cache.write": 0, "cache.read": 1454080}]
    tool time: bash 15.0 min, write 0.0 min
        244s bash   date; cd /home/runner/work/_temp/w2/AIL_CURRENT && timeout 900 python3 ../tools/par_check.py -j 2 test_ail_std
        193s bash   cd /home/runner/work/_temp/w2; for p in /tmp/rprobes/*.py; do echo "########## $(basename $p)"; bash ~/tools/c
        146s bash   mkdir -p /tmp/rprobes; cd /home/runner/work/_temp/w2 for f in lab/stdlib/hashlib/*.py; do echo "########## $f"
         68s bash   cd /tmp/rprobes; python3 - <<'EOF' p='p_alias2.py' s=open(p).read().replace('    mv = memoryview(b"abc")\n    
         66s bash   cat > /tmp/rprobes/p_values.py <<'EOF' import hashlib   class Box:     def __init__(self) -> None:         sel
         42s bash   cat > /tmp/rprobes/p_bigint.py <<'EOF' import hashlib   def main() -> None:     d = hashlib.sha256(b"abc").dig
         39s bash   cd /home/runner/work/_temp/w2; for p in /tmp/rprobes/p_construct.py; do echo "=== base $p"; bash ~/tools/cmp.s
         27s bash   cd /home/runner/work/_temp/w2; rm -rf /tmp/hlchk && mkdir /tmp/hlchk; for f in lab/stdlib/hashlib/*.py; do b=$

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T05:37:24Z
