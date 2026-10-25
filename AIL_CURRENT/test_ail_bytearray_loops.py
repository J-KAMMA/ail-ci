"""Per-byte bytearray loops (append/get/set by name, bytearray out, nested counting loops) match CPython.

Regression: `out.append(s[i])`, `tbl[b]` and `tbl[i] = v` retained and released the bytearray twice per
byte and validated it in full each time, loops that only touch bytes ran the string-arena checkpoint,
and `write_stdout_bytes(bytes(buf))` copied the whole output first (reverse_complement ran 5x the
instructions of C, regex_redux 5x, with a 50 MB extra copy).
"""
import subprocess
import os
import sys
# The C-text assertions below describe the legacy emitter; with AIL_IR set, functions in the IR's
# subset are emitted by the IR (same behaviour, different text), so only the behaviour is checked.
LEGACY_C = os.environ.get('AIL_IR', '0').strip().lower() in ('', '0', 'off', 'no')
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
fn emit(out: bytearray, s: bytearray) -> void {
    let i = len(s) - 1;
    let col = 0;
    while i >= 0 {
        out.append(s[i]);
        col += 1;
        if col == 5 { out.append(10); col = 0; }
        i -= 1;
    }
    if col > 0 { out.append(10); }
}

fn count_pat(seq: bytes, mask: bytearray) -> int {
    let n = len(seq);
    let cnt = 0;
    let i = 0;
    while i <= n - 3 {
        let ok = 0;
        if mask[seq[i]] == 1 {
            ok = 1;
            for k in range(1, 3) {
                if mask[k * 256 + seq[i + k]] == 0 { ok = 0; break; }
            }
        }
        if ok == 1 { cnt += 1; i += 3; } else { i += 1; }
    }
    return cnt;
}

fn main() {
    let tbl = bytearray();
    for i in range(0, 256) { tbl.append(i); }
    let src = b"ACGT";
    let dst = b"TGCA";
    for i in range(0, 4) { tbl[src[i]] = dst[i]; }
    tbl[b"a"[0]] = tbl[65] + 1;
    let seq = bytearray();
    let line = b"GATTACAGATTACAGGCCAATT";
    for b in line { seq.append(tbl[b]); }
    let out = bytearray();
    emit(out, seq);
    out.append(out[0]);
    out.append(out[-1]);
    let big = bytearray();
    big.append(7);
    for i in range(0, 5000) { big.append(big[i] ^ (i & 255)); }
    let mask = bytearray();
    for k in range(0, 768) { mask.append(0); }
    mask[65] = 1; mask[256 + 71] = 1; mask[512 + 84] = 1;
    let hay = b"AGTAGTxAGTAGT";
    print(count_pat(hay, mask), len(out), len(big), big[4999], big[-2], out[3]);
    let bad = 300;
    try { out.append(bad); } except ValueError { print("value error"); }
    try { tbl[3] = bad; } except ValueError { print("value error set"); }
    try { print(out[len(out)]); } except IndexError { print("index error"); }
    try { print(seq[-100]); } except IndexError { print("index error neg"); }
    let total = 0;
    for i in range(0, len(big)) { total += big[i]; }
    print(total);
    write_stdout_bytes(bytes(out));
}
"""

PYTHON = """
import os
import sys
def emit(out, s):
    i = len(s) - 1
    col = 0
    while i >= 0:
        out.append(s[i]); col += 1
        if col == 5:
            out.append(10); col = 0
        i -= 1
    if col > 0: out.append(10)
def count_pat(seq, mask):
    n = len(seq); cnt = 0; i = 0
    while i <= n - 3:
        ok = 0
        if mask[seq[i]] == 1:
            ok = 1
            for k in range(1, 3):
                if mask[k * 256 + seq[i + k]] == 0:
                    ok = 0; break
        if ok == 1: cnt += 1; i += 3
        else: i += 1
    return cnt
tbl = bytearray(range(256))
src = b"ACGT"; dst = b"TGCA"
for i in range(4): tbl[src[i]] = dst[i]
tbl[b"a"[0]] = tbl[65] + 1
seq = bytearray()
for b in b"GATTACAGATTACAGGCCAATT": seq.append(tbl[b])
out = bytearray()
emit(out, seq)
out.append(out[0]); out.append(out[-1])
big = bytearray([7])
for i in range(5000): big.append(big[i] ^ (i & 255))
mask = bytearray(768)
mask[65] = 1; mask[256 + 71] = 1; mask[512 + 84] = 1
print(count_pat(b"AGTAGTxAGTAGT", mask), len(out), len(big), big[4999], big[-2], out[3])
bad = 300
try: out.append(bad)
except ValueError: print("value error")
try: tbl[3] = bad
except ValueError: print("value error set")
try: print(out[len(out)])
except IndexError: print("index error")
try: print(seq[-100])
except IndexError: print("index error neg")
print(sum(big))
sys.stdout.flush()
sys.stdout.buffer.write(bytes(out))
"""


class BytearrayLoopTests(unittest.TestCase):
    def test_matches_cpython_and_skips_per_byte_bookkeeping(self):
        with tempfile.TemporaryDirectory() as directory:
            source, exe = Path(directory, "p.ail"), Path(directory, "p")
            debug = Path(directory, "debug")
            source.write_text(SOURCE)
            built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                                    "-o", str(exe), "--debug-dir", str(debug)],
                                   capture_output=True, text=True, timeout=300)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            program = (debug / "program.c").read_text()
            if LEGACY_C:
                # a stable receiver and a pure operand need no retain/release temporaries
                self.assertIn("int64_t _argument=ail_bytearray_get(v_s, v_i); ail_bytearray_append(_receiver,_argument);",
                              program)
                self.assertIn("ail_bytearray_set(v_tbl, _index, _value);", program)
                # the output is written from the bytearray itself, not from a frozen copy
                self.assertIn("ail_stdout_write_bytes(ail_bytearray_span(", program)
                self.assertNotIn("ail_bytearray_freeze(&", program)
                # integer-only loops carry no string-arena checkpoint
                count_body = program[program.index("int64_t count_pat(ail_bytes v_seq, ail_bytearray *v_mask) {"):]
                count_body = count_body[:count_body.index("\n}\n")]
                self.assertNotIn("ail_sarena_keep_roots(", count_body)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            expected = subprocess.run([sys.executable, "-c", PYTHON], capture_output=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout)


# These tests pin the C text of the legacy emitter, the AIL_IR=0 opt-out (the IR is the default since
# 2026-10-19 and has its own text, pinned in test_ail_ir_*): the whole module builds with AIL_IR=0
# unless the caller set AIL_IR.
_SAVED_AIL_IR = []


def setUpModule():
    import os as _os
    _SAVED_AIL_IR.append(_os.environ.get('AIL_IR'))
    if _SAVED_AIL_IR[-1] is None:
        _os.environ['AIL_IR'] = '0'


def tearDownModule():
    import os as _os
    if _SAVED_AIL_IR.pop() is None:
        _os.environ.pop('AIL_IR', None)


if __name__ == "__main__":
    unittest.main()
