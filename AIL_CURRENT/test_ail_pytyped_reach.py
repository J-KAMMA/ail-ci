"""Python-syntax sources reaching the typed path: sys.argv elements and Optional helper returns.

P1  `sys.argv[i]` is a str, so it satisfies a parameter used with a str method (and a generated
    regex helper) instead of the caller defaulting that parameter to int.
P2  an unannotated helper that always returns one scalar kind is known not to return None, so its
    result can be assigned to a variable the Optional lowering has made a (flag, value) pair.
P3  a local `d = {}` used only through `d.setdefault(k, []).append(v)` and a truth-tested
    `d.get(k)` lowers to the typed dict-of-int-lists shape (a key -> slot dict plus rows).
P4  an unannotated helper whose every return is `bytes(...)` owns its result like `-> bytes`.
P5  a bytearray passed to a bytes/sequence parameter is read through a read-only bytes view.
P6  a nested `def` written directly in a loop body is lifted with its captured values.
P7  `for part in m.groups()` is built when every group always takes part.
P8  generated helpers appended after the script do not hide the script's real entry point.
P9  the ten lab/compare Python sources: echo_pack now builds on the typed path.
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

ARGV_STR = '''import sys

def has_hi(s):
    return s.startswith("hi")

def main():
    if has_hi(sys.argv[1]):
        sys.stdout.write("yes\\n")
    else:
        sys.stdout.write("no\\n")

main()
'''

OPTIONAL_HELPER = '''import sys

def pack(d: int):
    return d + 1

def unpack(d: int) -> int | None:
    if d < 2:
        return None
    return d - 1

def main():
    data = int(sys.argv[1])
    res = pack(data)
    if data > 5:
        res = unpack(data)
    if res is None:
        sys.stdout.write("none\\n")
    else:
        sys.stdout.write("%d\\n" % res)

main()
'''


def build(tmp, name, text):
    source = Path(tmp) / (name + '.py')
    source.write_text(text, encoding='utf8')
    exe = Path(tmp) / name
    env = dict(os.environ, AIL_NO_GENERAL='1', AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source), '--syntax', 'python',
                             '--strict', '-o', str(exe)], capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def run(exe, *args):
    return subprocess.run([str(exe), *args], capture_output=True, text=True, timeout=60)


@unittest.skipUnless(HAVE_CC, 'needs gcc')
class TypedReach(unittest.TestCase):
    def test_argv_element_is_a_str(self):
        with tempfile.TemporaryDirectory(prefix='ail-pyreach-') as tmp:
            result, exe = build(tmp, 'argv_str', ARGV_STR)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertEqual(run(exe, 'hi').stdout, 'yes\n')
            self.assertEqual(run(exe, 'no').stdout, 'no\n')

    def test_plain_helper_return_is_known_not_none(self):
        with tempfile.TemporaryDirectory(prefix='ail-pyreach-') as tmp:
            result, exe = build(tmp, 'optional_helper', OPTIONAL_HELPER)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertEqual(run(exe, '3').stdout, '4\n')
            self.assertEqual(run(exe, '9').stdout, '8\n')
    def test_dict_of_lists_lowering(self):
        with tempfile.TemporaryDirectory(prefix='ail-pyreach-') as tmp:
            result, exe = build(tmp, 'dlist', DICT_OF_LISTS)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertEqual(run(exe).stdout, '3 3 5\nnone\n')

    def test_unannotated_bytes_helper_owns_its_result(self):
        with tempfile.TemporaryDirectory(prefix='ail-pyreach-') as tmp:
            result, exe = build(tmp, 'owned_bytes', OWNED_BYTES)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertEqual(run(exe).stdout.encode('latin-1'), bytes([7, 8, 1, 2]) + b'\n')

    def test_bytearray_reads_as_a_bytes_view(self):
        with tempfile.TemporaryDirectory(prefix='ail-pyreach-') as tmp:
            result, exe = build(tmp, 'ba_view', BYTEARRAY_VIEW)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            expected = subprocess.run([sys.executable, str(Path(tmp) / 'ba_view.py')],
                                      capture_output=True, text=True, timeout=120).stdout
            self.assertEqual(run(exe).stdout, expected)

    def test_nested_def_directly_in_a_loop_is_lifted(self):
        with tempfile.TemporaryDirectory(prefix='ail-pyreach-') as tmp:
            result, exe = build(tmp, 'loop_def', LOOP_DEF)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertEqual(run(exe).stdout, '10 11 12 13 14 15\n')

    def test_groups_iteration_when_every_group_takes_part(self):
        with tempfile.TemporaryDirectory(prefix='ail-pyreach-') as tmp:
            result, exe = build(tmp, 'groups_loop', GROUPS_LOOP)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertEqual(run(exe).stdout, 'abc/123\n2 x\n2 4\n')

    def test_entry_survives_generated_regex_helpers(self):
        with tempfile.TemporaryDirectory(prefix='ail-pyreach-') as tmp:
            result, exe = build(tmp, 'entry_re', ENTRY_AFTER_RE)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            self.assertEqual(run(exe).stdout, 'yes\nno\n')

    def test_lab_echo_pack_builds_on_the_typed_path(self):
        with tempfile.TemporaryDirectory(prefix='ail-pyreach-') as tmp:
            result, exe = build_source(tmp, 'echo_pack', ECHO_PACK)
            self.assertEqual(result.returncode, 0, result.stderr[-2000:])
            data = b'abcabcabcabc' * 50
            expected = subprocess.run([sys.executable, str(ECHO_PACK), 'pack'], input=data,
                                      capture_output=True, timeout=120)
            got = run_bytes(exe, data, 'pack')
            self.assertEqual(got.returncode, expected.returncode)
            self.assertEqual(got.stdout, expected.stdout)
            unpacked = run_bytes(exe, got.stdout, 'unpack')
            self.assertEqual(unpacked.returncode, 0)
            self.assertEqual(unpacked.stdout, data)


DICT_OF_LISTS = '''def main():
    d = {}
    source = [3, 4, 5]
    for i in range(len(source)):
        d.setdefault("k", []).append(source[i])
    row = d.get("k")
    if row:
        print(len(row), row[0], row[-1])
    miss = d.get("z")
    if miss:
        print("bad")
    else:
        print("none")


main()
'''

OWNED_BYTES = '''import sys

def make(n):
    return bytes([n % 256])

def both(a, b):
    return bytes([a, b])

def main():
    a = make(7)
    b = make(8)
    c = both(1, 2)
    sys.stdout.buffer.write(a + b + c + bytes([]))
    sys.stdout.buffer.write(b"\\n")

main()
'''

BYTEARRAY_VIEW = '''import sys

def hsh(data):
    h = 0
    for b in data:
        h = (h * 257 + b + 1) & 0xFFFFFFFF
    return h

def main():
    a = bytearray()
    for i in range(300):
        a.append((i * 7) & 255)
    before = hsh(a)
    a.append(5)
    after = hsh(a)
    sys.stdout.write("%d %d %d\\n" % (before, after, hsh(bytearray())))

main()
'''

LOOP_DEF = '''import sys

def main():
    total = 10
    out = []
    for i in range(5):
        def add(k):
            return k + total
        out.append(add(i))
    def keep():
        return total + len(out)
    out.append(keep())
    sys.stdout.write(" ".join(str(x) for x in out) + "\\n")

main()
'''

GROUPS_LOOP = '''import re

def main():
    m = re.fullmatch(r"([a-z]+)-([0-9]+)", "abc-123")
    if m:
        out = []
        for part in m.groups():
            out.append(part)
        print("/".join(out))
    z = re.fullmatch(r"([a-z]+)([0-9]+)", "xy42")
    if z:
        for part in z.groups():
            print(len(part), part[0])

main()
'''

ENTRY_AFTER_RE = '''import re

NUM = re.compile(r"[0-9]+")

def helper(s: str) -> str:
    if NUM.fullmatch(s):
        return "yes"
    return "no"

def main():
    print(helper("123"))
    print(helper("12a"))

main()
'''

ECHO_PACK = ROOT.parent / 'lab' / 'compare' / 'src' / 'echo_pack' / 'main.py'


def build_source(tmp, name, source):
    exe = Path(tmp) / name
    env = dict(os.environ, AIL_NO_GENERAL='1', AIL_NO_CACHE='1')
    env.pop('AIL_STRICT', None)
    result = subprocess.run([sys.executable, '-B', str(CLI), 'compile', str(source), '--syntax', 'python',
                             '--strict', '-o', str(exe)], capture_output=True, text=True, timeout=600, env=env)
    return result, exe


def run_bytes(exe, data, *args):
    return subprocess.run([str(exe), *args], input=data, capture_output=True, timeout=120)


if __name__ == '__main__':
    unittest.main()
