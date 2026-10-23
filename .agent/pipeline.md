# job job-perf4-10240013  started 2026-10-23T15:16:00Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Done. Commit `10bb04e` on `job-perf4-10240013`.

- `field += ch` was already in-place via `ail_str_cat` (adjacent view, then the newest arena block with amortized growth). Forcing the builder-local path was slower (3.29 s vs 2.48 s on a 263 MB file).
- Next cost: `utf8_decode_feed` scanned for the last character boundary, then `decode("utf-8")` scanned again to validate. Profiling share was 11.2% (`_utf8_complete_length`); Amdahl bound ~11%.
- Change: `_utf8_tail_complete` checks the last byte plus at most three continuation bytes; the full scan remains only for chunks that end mid-character.

`python3 bench/compare.py --app csv_table --base 500f82f`:

| | ms ail/base/c/rust | ail/base | ail/c | ail/rust |
|---|---|---:|---:|---:|
| before | 16.5/16.5/6.9/7.8 | 1.006 tie | 2.387 | 2.126 |
| after | 15.3/16.4/6.8/7.8 | **0.929 faster (7.1%)** | **2.236** | **1.964** |

RSS, binary size, and build disk unchanged within noise; output and boundary controls identical.

Tests: 18 targeted (utf8/csv modules) and 25 required (`safetynet`, `files`, `corpus_findings3`, 1 skipped) pass. Probe `/tmp/probes/utf8_tail.py` via `cmp.sh`: 5,232 cases, same stdout in both builds, 0 mismatches. Not pushed.
[cost $0.0000, opencode tokens {"total": 11073113, "input": 827754, "output": 33122, "reasoning": 61325, "cache.write": 0, "cache.read": 10150912}]

## review 0 failed to run: (no final text) [cost $0.0000, opencode tokens {"total": 1010716, "input": 60391, "output": 5252, "reasoning": 14385, "cache.write": 0, "cache.read": 930688}] (cut off after 60 minutes) 

## review 0
[model opencode/deepseek-v4.1-flash-free]
(no final text)
[cost $0.0000, opencode tokens {}]
(cut off after 60 minutes)

FINAL VERDICT: ERROR  2026-10-23T18:08:33Z
