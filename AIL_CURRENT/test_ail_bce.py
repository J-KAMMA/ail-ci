"""Bounds-check-elision probes (bce s1): the checks the IR already drops must be sound.

Every program in `PROBES` is compiled and run three ways -- the default build, the forced general
path (`AIL_UNIFIED_FORCE=1`) and the audit build (`AIL_BCE_AUDIT=1`, where every removed index check
is emitted again as a loud stop).  A .ail probe's oracle is the Python `tools/ail2py.py` produces,
run under CPython 3.12.  stdout, the exit status and the last stderr line must agree; the audit
build must never print AIL-BCE-AUDIT or exit 86.  Later bce steps append their probes here.

The one exception is `big_text_index`: `int("9223372036854775808")` stops at int() in this language
(ints are 64-bit) while CPython goes on to the index.  It stays the same stop as today in all three
builds; the test pins that, rather than pretending it matches CPython.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None
sys.path.insert(0, str(REPO / 'tools'))
import ail2py  # noqa: E402

BOX = "struct Box { v: list[int]; n: int; }\n"

PROBES = [
    ('range_read_store', r"""
fn main() {
    let xs = [5, 7, 11, 13, 17, 19];
    for i in range(len(xs)) { xs[i] = xs[i] * 2 + i; }
    let s = 0;
    for i in range(len(xs)) { s += xs[i]; }
    print(s);
    print(xs[0], xs[len(xs) - 1]);
}
"""),
    ('range_offset_read', r"""
fn main() {
    let xs = [3, 1, 4, 1, 5, 9, 2, 6];
    let s = 0;
    for i in range(1, len(xs)) { s += xs[i] - xs[i - 1]; }
    print(s);
}
"""),
    ('guarded_next_read', r"""
fn main() {
    let xs = [1, 2, 3, 4, 5];
    let s = 0;
    for i in range(len(xs)) {
        if i + 1 < len(xs) { s += xs[i + 1]; } else { s += xs[i]; }
    }
    print(s);
}
"""),
    ('bytes_scan', r"""
fn main() {
    let d = b"\x41\x42\x0a\x43\x44\x0a\x45";
    let n = len(d);
    let i = 0;
    let lines = 0;
    while i < n {
        while i < n and d[i] != 10 { i += 1; }
        if i < n { i += 1; lines += 1; }
    }
    print(lines);
    let j = 0;
    while j < n and d[j] != 10 { j += 1; }
    print(j);
}
"""),
    ('list_boundaries_ok', r"""
fn main() {
    let xs = [10, 20, 30, 40];
    print(xs[-1], xs[-len(xs)], xs[0], xs[len(xs) - 1]);
}
"""),
    ('list_index_len_raises', r"""
fn main() {
    let xs = [10, 20, 30];
    print(xs[len(xs)]);
}
"""),
    ('list_index_neg_len_minus_one_raises', r"""
fn main() {
    let xs = [10, 20, 30];
    print(xs[-len(xs) - 1]);
}
"""),
    ('bytes_boundaries_ok', r"""
fn main() {
    let d = b"\x0a\x14\x1e\x28";
    print(d[-1], d[-len(d)], d[0], d[len(d) - 1]);
}
"""),
    ('bytes_index_len_raises', r"""
fn main() {
    let d = b"\x0a\x14\x1e";
    print(d[len(d)]);
}
"""),
    ('bytes_index_neg_len_minus_one_raises', r"""
fn main() {
    let d = b"\x0a\x14\x1e";
    print(d[-len(d) - 1]);
}
"""),
    ('field_boundaries_ok', BOX + r"""
fn main() {
    let b = Box([100, 200, 300, 400], 4);
    print(b.v[-1], b.v[-len(b.v)], b.v[0], b.v[len(b.v) - 1]);
}
"""),
    ('field_index_len_raises', BOX + r"""
fn main() {
    let b = Box([100, 200, 300], 3);
    print(b.v[len(b.v)]);
}
"""),
    ('field_index_neg_len_minus_one_raises', BOX + r"""
fn main() {
    let b = Box([100, 200, 300], 3);
    print(b.v[-len(b.v) - 1]);
}
"""),
    ('mutation_pop_in_loop', r"""
fn main() {
    let xs = [10, 20, 30, 40, 50];
    for i in range(len(xs)) {
        xs.pop();
        print(xs[i]);
    }
}
"""),
    ('big_text_index', r"""
fn make() -> str { return "9223372036854775808"; }
fn main() {
    let xs = [10, 20, 30];
    let k = int(make());
    print(xs[k]);
}
"""),
]

STOPS = {
    'big_text_index': 'OverflowError: integer overflow in int() (ints are 64-bit; --exact-int gives exact ints)',
}


def _last_line(data):
    lines = [x for x in data.decode('utf-8', 'replace').splitlines() if x.strip()]
    return lines[-1] if lines else ''


def _same_last_line(got, want):
    if got == want:
        return True
    # this runtime's index traps print the message alone, and name the sequence they indexed;
    # CPython prefixes the exception name and, for bytes, leaves the message generic.
    if want.startswith('IndexError: '):
        msg = want[len('IndexError: '):]
        return got == msg or got == 'bytes ' + msg
    return False


def _cpython(directory, name, source):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(ail2py.convert(source), encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _build_run(directory, name, source, mode):
    text, suffix, flags = source, '.ail', []
    if mode == 'force':
        # the forced general path is a Python-surface build; the .ail oracle is the same program
        text, suffix, flags = ail2py.convert(source), '.py', ['--syntax', 'python']
    src = Path(directory) / (name + '_' + mode + suffix)
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_BCE', 'AIL_BCE_AUDIT'):
        env.pop(key, None)
    if mode == 'force':
        env['AIL_UNIFIED_FORCE'] = '1'
    elif mode == 'audit':
        env['AIL_BCE_AUDIT'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '-o', exe.name] + flags
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-2000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr),
            got.stderr.decode('utf-8', 'replace')), None


@unittest.skipUnless(HAVE_CC, 'no C compiler')
class BceProbeTests(unittest.TestCase):
    maxDiff = None

    def _runs(self, directory, name, source):
        runs = {}
        for mode in ('default', 'force', 'audit'):
            got, err = _build_run(directory, name, source, mode)
            self.assertIsNotNone(got, '%s (%s build)\n%s' % (name, mode, err))
            runs[mode] = got
        return runs

    def test_probes_match_cpython_and_audit_is_quiet(self):
        with tempfile.TemporaryDirectory(prefix='ail-bce-') as directory:
            for name, source in PROBES:
                with self.subTest(probe=name):
                    runs = self._runs(directory, name, source)
                    for mode, got in runs.items():
                        self.assertNotEqual(got[1], 86, '%s (%s) hit the audit stop\n%s'
                                            % (name, mode, got[3]))
                        self.assertNotIn('AIL-BCE-AUDIT', got[3], '%s (%s)' % (name, mode))
                    if name in STOPS:
                        self.assertEqual({got[:3] for got in runs.values()}, {runs['default'][:3]}, name)
                        self.assertEqual(runs['default'][2], STOPS[name], name)
                        self.assertEqual(runs['default'][1], 1, name)
                        continue
                    want = _cpython(directory, name, source)
                    for mode, got in runs.items():
                        self.assertEqual(got[0], want[0], '%s (%s) stdout' % (name, mode))
                        self.assertEqual(got[1], want[1], '%s (%s) status' % (name, mode))
                        self.assertTrue(_same_last_line(got[2], want[2]),
                                        '%s (%s) stderr: %r != %r' % (name, mode, got[2], want[2]))


if __name__ == '__main__':
    unittest.main()
