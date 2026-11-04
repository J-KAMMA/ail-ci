# `hashlib` / `hmac` coverage (job-std_hashlib-11041240)

Environment: CPython 3.12.3, the default build
`python3 AIL_CURRENT/ail_chatgpt.py compile X.py --syntax python` (typed path first, general path as
the fallback), and `AIL_UNIFIED_FORCE=1` for the general-path census. Date: 2026-11-04.

## Before the fixes

| program | default result | first message |
| --- | --- | --- |
| `01_checksum_stdin.py` | typed, equal | |
| `02_text_digests.py` | typed, equal | |
| `03_new_by_name.py` | typed, equal | |
| `04_blake2_options.py` | typed, equal | |
| `05_copy_running.py` | general, equal | `note: ...:8:5: built on the general path ... because a direct iterable list requires flat uniform int, float, or str elements` |
| `06_hash_properties.py` | typed, equal | |
| `07_hmac_messages.py` | typed, equal | |
| `08_pbkdf2_key.py` | typed, equal | |
| `09_content_store.py` | typed, equal | |
| `10_merkle_root.py` | typed, equal | |
| `11_digest_integer.py` | typed, stopped at run time | `OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints)` |
| `12_empty_inputs.py` | typed, equal | |

Before: 11 built typed, 1 built general, 10 typed programs equal; `11_digest_integer.py` built but
the default int64 run stopped on the 8-byte unsigned `int.from_bytes`.

## After the fixes

| program | default result | `AIL_UNIFIED_FORCE=1` | CPython stdout + exit |
| --- | --- | --- | --- |
| `01_checksum_stdin.py` | typed | general | match |
| `02_text_digests.py` | typed | general | match |
| `03_new_by_name.py` | typed | general | match |
| `04_blake2_options.py` | typed | general | match |
| `05_copy_running.py` | typed | general | match |
| `06_hash_properties.py` | typed | general | match |
| `07_hmac_messages.py` | typed | general | match |
| `08_pbkdf2_key.py` | typed | general | match |
| `09_content_store.py` | typed | general | match |
| `10_merkle_root.py` | typed | general | match |
| `11_digest_integer.py` | general with `--exact-int` | general with `--exact-int` | match |
| `12_empty_inputs.py` | typed | general | match |

After: 11 of 12 are typed in the default build and all 12 print CPython's stdout and exit code.
`11_digest_integer.py` deliberately reads
`int.from_bytes(hashlib.sha256(b"abc").digest()[:8], "big")`, whose value is
`13436514500253700074`, beyond int64. The default AIL int mode is int64, so this one program is
built with `--exact-int` (exact big ints) and therefore takes the general path; it does not stop.
The other eleven use the default command and have no general-path note.

Every program that reads stdin was run with its file in `data/`:
`01_checksum_stdin.py` with `data/checksum_input.bin` (232000 bytes, so the 64 KiB read loop runs
four times) and `02_text_digests.py` with `data/digest_text.txt`. The other programs read no stdin.

## Fixes

* `05_copy_running.py`: the snapshot loop iterated a literal list of bytes, which the typed path
  does not take (a direct iterable list needs flat uniform int, float or str elements). The program
  now updates and copies the running hash in explicit steps; it is typed and still exercises
  `copy()` independence.
* `11_digest_integer.py` keeps the beyond-int64 value and is built with `--exact-int`. The default
  int64 build builds but stops loudly at run time (`OverflowError`), which is the documented int64
  behaviour, not a silent wrap. This is recorded as a finding below.

`hashlower.py`, `hash_prelude.py` and `ailhash_core.h` needed no change; no program was refused and
no program needed a file outside the allowed list.

## Finding: `int.from_bytes` of an 8-byte unsigned slice in the default int mode

`int.from_bytes(hashlib.sha256(...).digest()[:8], "big")` can leave int64. The default typed path
has int64 only, so the value stops with:

```
OverflowError: integer overflow in * (ints are 64-bit; --exact-int gives exact ints)
```

`--exact-int` builds the program (general path, exact ints) and matches CPython. Keeping such a
value inside int64 (e.g. a 7-byte slice, or `signed=True` on 8 bytes) stays on the typed path. A
typed-path exact big-int `from_bytes` would need the prelude integer conversion to use tagged ints;
that is outside this lane's files.

## Throughput: sha256 of 256 MiB from stdin

`head -c 268435456 /dev/urandom > /tmp/big.bin` (268435456 bytes, not in git). The program is
`01_checksum_stdin.py`; every run read the same file on stdin. Values are the median of three wall
times under `ulimit -v 1500000`.

| command | median seconds |
| --- | --- |
| AIL binary, default typed build (`AIL_NO_CACHE=1`) | **0.21** |
| `python3 -B lab/stdlib/hashlib/01_checksum_stdin.py` (OpenSSL hashlib) | **0.20** |
| `sha256sum /tmp/big.bin` | **0.18** |

SHA-NI: `/proc/cpuinfo` contains `sha_ni`, and the AIL binary uses `ailhs_sha256_blocks_ni`
(runtime CPUID dispatch in `ailhash_core.h`). As a check, `AIL_HASH_NO_SHANI=1` gives a median of
**0.93 s**, so the default AIL run used the SHA-NI path. All three commands printed the same digest,
`ca74662af14072c9344ee64ca144ae2a664c310a82b24a3a791de27e5d81d344`.

## Test

`AIL_CURRENT/test_ail_std_hashlib.py` (registered by `AIL_CURRENT/tests.d/test_ail_std_hashlib.txt`)
builds the eleven typed programs in the default mode, asserts no general-path note, and compares
stdout and exit code with CPython; it builds `11_digest_integer.py` with `--exact-int` and compares
it too.
