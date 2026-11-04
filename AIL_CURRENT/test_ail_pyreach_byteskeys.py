"""Python-syntax reach, s6: bytes as dict/set keys and bytes dict values.

K1  A bytes-keyed dict built from `stdin.read().split()` counts words with `d.get(w, 0) + 1`
    and iterates `sorted(d)`, all through content hashing (BTAB), including 0x00 and 0xff.
K2  Fixed keys sort by raw byte value, `d[k] += n`, membership and `len` all agree with CPython.
K3  Keys are owned copies: rebinding the source list and the data name afterwards leaves them.
K4  A set of concatenated bytes keys de-duplicates by content and supports add/discard/in.
K5  A bytes-keyed dict holds bytes, str or int values, inferred or annotated, with `get` defaults.
K6  A read assigned inside `if True:` (what `ail_syntax` emits for a binary `with open`) still
    makes `lines = data.split(...)` a bytes list, so `t = parts[0]` stays bytes -- the shape that
    used to be pre-bound int before this fix.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = ROOT / 'ail_chatgpt.py'
HAVE_CC = shutil.which('gcc') is not None

BIN_INPUT = b'a|1\nb|22\na|333\n\x00x|4\n\xffy|5\n'


WORD_COUNT = '''import sys

def main():
    data = sys.stdin.buffer.read()
    words = data.split()
    d = {}
    for w in words:
        d[w] = d.get(w, 0) + 1
    out = []
    for k in sorted(d):
        out.append(str(d[k]) + " " + str(len(k)) + " " + k.decode('latin-1'))
    sys.stdout.write("\\n".join(out) + "\\n")
main()
'''

SORTED_KEYS = '''import sys

def main():
    d = {}
    d[b'a'] = 1
    d[b'ab'] = 2
    d[b''] = 3
    d[b'\\xff'] = 4
    d[b'\\x00'] = 5
    d[b'\\x80a'] = 6
    d[b'aa'] = 7
    out = []
    for k in sorted(d):
        out.append(str(d[k]) + ":" + k.decode('latin-1'))
    sys.stdout.write("\\n".join(out) + "\\n")
    sys.stdout.write(str(d[b'a']) + " " + str(d.get(b'zz', 99)) + " " + str(len(d)) + "\\n")
    d[b'a'] += 10
    sys.stdout.write(str(d[b'a']) + " " + str(b'ab' in d) + " " + str(b'zz' in d) + "\\n")
main()
'''

ALIAS = '''import sys

def main():
    data = sys.stdin.buffer.read()
    lines = data.split(b'\\n')
    d = {}
    for ln in lines:
        parts = ln.split(b'|')
        if len(parts) > 1:
            d[parts[0]] = len(parts[1])
    lines = [b'changed|source']
    data = b''
    out = []
    for k in sorted(d):
        out.append(k.decode('latin-1') + "=" + str(d[k]))
    sys.stdout.write("\\n".join(out) + "\\n")
main()
'''

SET_CONCAT = '''import sys

def main():
    s = set()
    a = b'a'
    b = b'b'
    k1 = a + b'|' + b'1'
    k2 = a + b'|' + b'2'
    s.add(k1)
    s.add(k2)
    s.add(k1)
    sys.stdout.write(str(len(s)) + " " + str(k1 in s) + " " + str(k2 in s) + "\\n")
    s.discard(k1)
    s.discard(b'none')
    sys.stdout.write(str(len(s)) + " " + str(k1 in s) + " " + str(k2 in s) + "\\n")
    t = set()
    t.add(b'\\x00')
    t.add(b'\\xff')
    t.add(b'\\x00')
    sys.stdout.write(str(len(t)) + " " + str(b'\\x00' in t) + " " + str(b'\\xff' in t) + "\\n")
main()
'''

VALUES = '''import sys

def main():
    ev_vc = {}
    ev = b'100001'
    vc = b'ABC'
    ev_vc[ev] = vc
    other = b'200002'
    ev_vc[other] = b'XYZ'
    sys.stdout.write(ev_vc[ev].decode() + " " + ev_vc[other].decode() + "\\n")
    x: dict[bytes, bytes] = {}
    x[ev] = vc
    x[other] = b'Q'
    sys.stdout.write(x[ev].decode() + " " + x[other].decode() + "\\n")
    y: dict[bytes, str] = {}
    y[ev] = "hello"
    y[other] = "world"
    sys.stdout.write(y[ev] + " " + y[other] + "\\n")
    z: dict[bytes, int] = {}
    z[ev] = 7
    z[other] = 9
    z[ev] += 3
    sys.stdout.write(str(z[ev]) + " " + str(z.get(other, 0)) + " " + str(z.get(b'no', 42)) + "\\n")
    w: set[bytes] = set()
    w.add(ev)
    w.add(other)
    w.discard(ev)
    sys.stdout.write(str(len(w)) + " " + str(ev in w) + " " + str(other in w) + "\\n")
main()
'''

STDIN_IF_WRAP = '''import sys

def main():
    if True:
        data = sys.stdin.buffer.read()
    lines = data.split(b'\\n')
    n = len(lines)
    for i in range(1, n):
        parts = lines[i].split(b'|')
        t = parts[0]
        sys.stdout.write(t.decode('latin-1') + "\\n")
main()
'''

FILE_WITH_WRAP = '''import sys

def main():
    with open(sys.argv[1], 'rb') as f:
        data = f.read()
    lines = data.split(b'\\n')
    n = len(lines)
    for i in range(1, n):
        parts = lines[i].split(b'|')
        t = parts[0]
        sys.stdout.write(t.decode('latin-1') + "\\n")
main()
'''


def build_source(tmp, name, source):
    exe = Path(tmp) / name
    env = dict(os.environ, AIL_NO_GENERAL='1', AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', '--strict', '-o', str(exe)],
                            capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def build_probe(tmp, name, source, unified):
    exe = Path(tmp) / (name + ('_unified' if unified else '_default'))
    env = dict(os.environ, AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    env.pop('AIL_NO_GENERAL', None)
    if unified:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source),
                             '--syntax', 'python', '-o', str(exe)],
                            capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def run(exe, stdin=b'', args=()):
    return subprocess.run([str(exe), *args], input=stdin, capture_output=True, timeout=120)


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class PyreachBytesKeys(unittest.TestCase):
    def _typed(self, name, text, expected, stdin=b'', args=()):
        with tempfile.TemporaryDirectory(prefix='ail-s6-') as tmp:
            source = Path(tmp) / (name + '.py')
            source.write_text(text, encoding='utf8')
            reference = subprocess.run([sys.executable, str(source), *args], input=stdin,
                                       capture_output=True, timeout=120)
            self.assertEqual(reference.returncode, 0, name)
            self.assertEqual(reference.stdout.decode('utf-8'), expected, name)
            result, exe = build_source(tmp, name, source)
            self.assertEqual(result.returncode, 0, (name, result.stderr[-3000:]))
            got = run(exe, stdin, args)
            self.assertEqual(got.returncode, reference.returncode, name)
            self.assertEqual(got.stdout.decode('utf-8'), expected, name)

    def _both(self, name, text, expected, stdin=b'', args=()):
        with tempfile.TemporaryDirectory(prefix='ail-s6-') as tmp:
            source = Path(tmp) / (name + '.py')
            source.write_text(text, encoding='utf8')
            for unified in (False, True):
                result, exe = build_probe(tmp, name, source, unified)
                self.assertEqual(result.returncode, 0, (name, unified, result.stderr[-3000:]))
                got = run(exe, stdin, args)
                self.assertEqual(got.returncode, 0, (name, unified))
                self.assertEqual(got.stdout.decode('utf-8'), expected, (name, unified))

    def test_word_count_over_stdin(self):
        expected = '1 4 \x00x|4\n1 3 a|1\n1 5 a|333\n1 4 b|22\n1 4 \u00ffy|5\n'
        self._typed('word_count', WORD_COUNT, expected, BIN_INPUT)
        self._both('word_count', WORD_COUNT, expected, BIN_INPUT)

    def test_sorted_raw_byte_order(self):
        expected = ('3:\n5:\x00\n1:a\n7:aa\n2:ab\n6:\x80a\n4:\u00ff\n'
                    '1 99 7\n11 True False\n')
        self._typed('sorted_keys', SORTED_KEYS, expected)
        self._both('sorted_keys', SORTED_KEYS, expected)

    def test_keys_survive_source_rebind(self):
        expected = '\x00x=1\na=3\nb=2\n\u00ffy=1\n'
        self._typed('alias', ALIAS, expected, BIN_INPUT)
        self._both('alias', ALIAS, expected, BIN_INPUT)

    def test_set_of_concatenated_keys(self):
        expected = '2 True True\n1 False True\n2 True True\n'
        self._typed('set_concat', SET_CONCAT, expected)
        self._both('set_concat', SET_CONCAT, expected)

    def test_bytes_key_dict_value_kinds(self):
        expected = 'ABC XYZ\nABC Q\nhello world\n10 9 42\n1 False True\n'
        self._typed('values', VALUES, expected)
        self._both('values', VALUES, expected)

    def test_stdin_read_inside_if_keeps_split_bytes(self):
        expected = 'b\na\n\x00x\n\u00ffy\n\n'
        self._typed('stdin_if', STDIN_IF_WRAP, expected, BIN_INPUT)
        self._both('stdin_if', STDIN_IF_WRAP, expected, BIN_INPUT)

    def test_binary_with_open_read_keeps_split_bytes(self):
        expected = 'b\na\n\x00x\n\u00ffy\n\n'
        with tempfile.TemporaryDirectory(prefix='ail-s6-') as tmp:
            fixture = Path(tmp) / 'input.bin'
            fixture.write_bytes(BIN_INPUT)
            self._typed('file_with', FILE_WITH_WRAP, expected, args=(str(fixture),))
            self._both('file_with', FILE_WITH_WRAP, expected, args=(str(fixture),))


if __name__ == '__main__':
    unittest.main()
