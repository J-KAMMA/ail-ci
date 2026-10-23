# job job-pre23-10240315  started 2026-10-23T18:15:52Z  worker=oc reviewer=oc (GitHub)

## worker report 0
[model opencode/deepseek-v4.1-flash-free]
Fixed the first still-differing item: encoding-name normalization.

- `utf\t8`, `iso-8859-1:1987`, `UTF_8`, whitespace/control-punctuated aliases now normalize like CPython in the bytes prelude and both compile-time codec checks.
- Added `AIL_CURRENT/test_ail_pre23.py`; updated DEVLOG, DIFFERENCES (`C?-job-pre23-10240315-1`), manifest.
- Commit: `deeac6c`

Probes on final commit (`cmp.sh`, both `g` and `d` builds): `p1.py`, `p3.py`, `p4.py`, `p5.py` — all same stdout as CPython. `p2.py` still shows the separate, untouched codec-support differences.

Final-commit tests: `test_ail_pre23`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` — 4 modules, 0 failed (155s). Manifest `--check` passes.
[cost $0.0000, opencode tokens {"total": 3245875, "input": 91515, "output": 12591, "reasoning": 16521, "cache.write": 0, "cache.read": 3125248}]
    tool time: bash 7.7 min
        157s bash   python3 tools/par_check.py -j 2 test_ail_pre23 test_ail_safetynet test_ail_files test_ail_corpus_findings3 && 
        120s bash   python3 tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3
         80s bash   python3 tools/par_check.py -j 2 test_ail_pre23 test_ail_safetynet
         32s bash   for p in p1 p3 p4 p5; do echo ==== $p; bash ~/tools/cmp.sh /tmp/probes/$p.py $PWD; done
         16s bash   mkdir -p /tmp/probes && cat > /tmp/probes/p1.py <<'EOF' names = ["utf\t8", "iso-8859-1:1987", "UTF\t8", "iso_8
         16s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/probes/p3.py') s=p.read_text() s=s.replace('        for
         11s bash   python3 - <<'PY' from pathlib import Path p=Path('AIL_CURRENT/python/pkg-v12/pyfunc.py') s=p.read_text() old="
          9s bash   cat > /tmp/probes/p5.py <<'EOF' class Holder:     def __init__(self, name):         self.name = name   def dec

## review 0
[model opencode/deepseek-v4.1-flash-free]
Review report

- Diff read: normalization helper added to `prelude_bytes.py` and `safetyrt.py`; literal-codec checks now use it (`pyboxed2.py`, `pyfunc.py`); new test, DEVLOG, DIFFERENCES, manifest.
- Probes (both `g` and `d` builds vs CPython):
  - `p1` normalized names/aliases through arg, list item, attribute, dict value, `bytes`/`str`/`bytearray`, empty and unknown names: HEAD same stdout on both builds; base refuses literals.
  - `p2` non-ASCII boundaries (é, Arabic digit, NBSP, ZWSP, fullwidth): HEAD same stdout on both builds; base differs on the fixed names.
  - `p3` mutation while iterating, list/dict/attribute paths: HEAD same on both; base refuses.
  - `p4`, `p5` (worker probes): HEAD same on both builds.
  - `p6` every old alias plus case variants: HEAD same on both; base fails only `utfé_8`.
  - `p7` dotted names, `p8` non-str encoding names: HEAD identical to base (pre-existing).
- Non-feature C: `--debug-dir` `program.c` identical HEAD vs base for `g00_000` and `g05_012`, both builds.
- Tests on HEAD: `test_ail_pre23`, `test_ail_safetynet`, `test_ail_files`, `test_ail_corpus_findings3` all pass (0 failed). `update_manifest.py --check` passes.
- Speed: no hot path; a 300k dynamic-decode loop measured 0.19 s HEAD vs 0.13 s base (small absolute cost). Instruction counts not measured (`perf` unavailable).

Report claims: all verified (fixed normalization, both compile-time checks, test/DEVLOG/DIFFERENCES/manifest, commit `deeac6c`, worker probe results, four test modules).

Pre-existing (identical on base, not blocking):
- CPython's dot→underscore fallback (`us.ascii`, `iso.8859.1`, `ansi.x3.4.1968`) still raises `LookupError`.
- `decode()` with a non-str encoding reports `encode()` in the TypeError text.
- utf-16/utf-32 dynamic codecs remain unsupported.
- Non-BMP decode and missing exception attributes (r6/r7) were out of scope and not re-probed.

Unverified: instruction-count speed and the untouched non-BMP/r6/r7 items.

VERDICT: ACCEPT
[cost $0.0000, opencode tokens {"total": 1443334, "input": 49196, "output": 7180, "reasoning": 21838, "cache.write": 0, "cache.read": 1365120}]
    tool time: bash 5.9 min
        120s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_files test_ail_corpus_findings3 2>&1 | tai
         75s bash   date; cd AIL_CURRENT && python3 ../tools/par_check.py -j 2 test_ail_pre23 test_ail_safetynet 2>&1 | tail -15
         32s bash   date; for p in p1 p3 p4 p5; do echo "==== $p"; bash ~/tools/cmp.sh /tmp/probes/$p.py $PWD 2>&1 | grep -E 'cpyt
         18s bash   python3 - <<'PY' from pathlib import Path p=Path('/tmp/rprobes/p3.py'); s=p.read_text().replace('print(repr(b"
         16s bash   cat > /tmp/rprobes/p8.py <<'EOF' def dec(data, name):     return data.decode(name)  def main():     for name i
         16s bash   cat > /tmp/rprobes/p6.py <<'EOF' def main():     names = ["utf-8", "utf8", "u8", "utf", "cp65001", "ascii", "u
         16s bash   cat > /tmp/rprobes/p7.py <<'EOF' def main():     for n in ["utf.8", "latin.1", "ascii.", "us.ascii", "iso.8859
         15s bash   date; echo "==== p2 HEAD"; bash ~/tools/cmp.sh /tmp/probes/p2.py $PWD 2>&1 | tail -30; echo "==== p2 BASE"; ba

FINAL VERDICT: ACCEPT  2026-10-23T18:39:47Z
