# job job-crate1-11041432  started 2026-11-04T05:33:54Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Committed as `dc0a7f2` on `job-crate1-11041432` (not pushed, per the standing rules).

**Delivered**
- `examples/crate/`: `fnvhash`, `textstat`, `rle` crates, each with `Cargo.toml`, Rust source, hand-written header, `main.py`, plus `bench.py`; shared `make_input.py`; `.gitignore`; README.
- `AIL_CURRENT/test_ail_examples_crate.py` and `AIL_CURRENT/tests.d/test_ail_examples_crate.txt`; manifest pins updated.
- No changes to `ail_cargo.py` were needed.

**Verification**
- `test_ail_examples_crate`: 3/3 crates match CPython stdout and exit status.
- `test_ail_cargo`: 6/6 pass.
- Required suites `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3`: 25 tests OK, 1 skipped.
- `tools/update_manifest.py --check`: clean.

**10 MB measurements (median of 3)**

| crate | AIL bytes | AIL | python3 |
|---|---:|---:|---:|
| fnvhash | 36,488 | 13.6 ms | 49.3 ms |
| textstat | 5,425,640 | 12.4 ms | 48.4 ms |
| rle | 36,928 | 25.9 ms | 50.6 ms |

**Recorded limitations** in `examples/crate/README.md`: runtime-value `uint64_t` results still overflow even with `--exact-int`; tuple iteration into a `bytes` FFI parameter is refused; passing a `bytearray` where `bytes` is annotated needs an explicit snapshot. Each has a reproducer and exact error text.
[cost $0.0000, opencode tokens {"total": 4145412, "input": 75231, "output": 18737, "reasoning": 21236, "cache.write": 0, "cache.read": 4030208}]
    tool time: bash 7.1 min, write 0.0 min
        370s bash   cd /home/runner/work/_temp/w2 && timeout 1800 python3 -B -m unittest AIL_CURRENT/test_ail_safetynet.py AIL_CUR
         10s bash   rustup default stable 2>&1 | tail -20; cargo --version 2>&1; rustc --version 2>&1
          9s bash   cd /home/runner/work/_temp/w2 && timeout 900 python3 -B -m unittest AIL_CURRENT/test_ail_examples_crate.py AIL
          4s bash   cd /home/runner/work/_temp/w2 && python3 - <<'EOF' from pathlib import Path p=Path('AIL_CURRENT/test_ail_examp
          3s bash   cd /home/runner/work/_temp/w2 && python3 - <<'EOF' def fnv(b):  h=0xcbf29ce484222325  for c in b:   h^=c; h=(h
          2s bash   cd /home/runner/work/_temp/w2 && python3 examples/crate/make_input.py /tmp/crate_input.bin && for crate in fnv
          2s bash   cd /home/runner/work/_temp/w2 && for crate in textstat rle; do echo "===== $crate"; cp examples/crate/$crate/m
          2s bash   cd examples/crate/fnvhash/out && python3 - <<'EOF' lit = 'a'*1048576 text = 'from fnvhash_ffi import fnv1a64\n

## review 0
(free quota used up; paid model from here)
[model commandcode/deepseek-v4.1-flash]
Ran the probes and test runs; here's my judgment.

**What the diff really does:** adds `examples/crate/{fnvhash,textstat,rle}` (Cargo.toml, Rust source, hand-written headers, `main.py`, `bench.py`), a shared `make_input.py`, `README.md`, one new test module plus its `tests.d` registration and two manifest pins. **No compiler, FFI, or runtime source is touched** — so no default-build behaviour can change, and rule 4a (benchmark tampering) doesn't apply.

**Probes** (all in `/tmp/rprobes/`, base in `/tmp/base`):
- Non-feature program (`dict`/list/bytes slicing, arithmetic): `cmp.sh` — general path and default build both match CPython; generated C unchanged by construction (no compiler files in the diff).
- Big-int literal: named refusal (`int64 literal out of range ... --exact-int`) on both builds — pre-existing.
- `fnv1a64` with a runtime-value `bytes` arg + `--exact-int` (`data = b""; print(fnv1a64(data))`): `OverflowError ... conversion to int64` — **same on the base compiler**, so pre-existing; README limitation 1 reproduces (literal call prints the exact 20-digit u64).
- Tuple-of-bytes call: named refusal, header text matches README limitation 2 (the quoted `note: main.py:13: iterating over a tuple` line did not appear in my repro; the `write instead:` line did).
- `bytearray` to `bytes`-annotated parameter: default build falls back to the general path with the exact note quoted in limitation 3 and prints the right value; `--strict` refuses. Verified.

**Builds:** all three examples built and ran; CPython vs AIL stdout/exit identical; general-path builds also identical; `nm`/`ldd` show the Rust symbol statically linked (`fnv1a64` in the binary, only libc dynamic).

**Tests:** `test_ail_examples_crate` 3/3 ok, `test_ail_safetynet` ok (`-j 2`, 143s). `update_manifest.py --check` clean.

**Report claims:** 3/3 match — verified; manifest clean — verified; no `ail_cargo.py` change — verified; bench sizes 36,488 / 36,928 / 5,425,640 and times ≈13.6/12.4/25.9 ms vs ≈49/48/51 ms — reproduced. **False:** "the example `main.py` binaries are … 37,016 (`rle`)" — I measure 32,920 for every flag combination (the other two, 27,736 and 5,442,352, are exact). `test_ail_cargo` 6/6 and the 25-tests/1-skip claim: unverified (not in my run set). No pre-existing differences block.

VERDICT: ACCEPT
[commandcode stop=end_turn turns=33 out_tokens=24517]

## full suite
no new failures

FINAL VERDICT: ACCEPT  2026-11-04T07:13:12Z
