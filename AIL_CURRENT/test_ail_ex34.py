"""ex34: a Python-syntax program that uses `@export` builds normally and matches CPython.

`@export` (from ail_ffi) is the marker of `ail build --lib`, but a normal build of the file used to
be refused as an unsupported decorator, although CPython runs the decorated function unchanged.
language_examples/c_export/geometry.py was the only standalone Python-syntax example refused this
way.  The decorator is now dropped before lowering on both builds, and the file's export
declarations are checked the way CPython's decorator checks them: an invalid export (missing
annotation, default, *args, unsupported type, a dataclass named before it is defined) is refused by
name instead of running where CPython stops at import.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXAMPLES = ROOT / 'language_examples'
CHATGPT = str(ROOT / 'ail_chatgpt.py')
REFUSAL = 'ail_ffi @export:'


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    env = dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore', PYTHONPATH=str(ROOT))
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120, env=env)
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


MARKER = '''from ail_ffi import export


@export()
def add(a: int, b: int) -> int:
    return a + b


@export
def scale(x: float) -> float:
    return x * 1.5


@export
def flag(ok: bool) -> bool:
    return not ok


@export
def shout(text: str) -> str:
    return text.upper() + "!"


@export
def reverse(data: bytes) -> bytes:
    out = bytearray()
    i = len(data) - 1
    while i >= 0:
        out.append(data[i])
        i -= 1
    return bytes(out)


@export
def total(values: list[int]) -> int:
    t = 0
    for v in values:
        t += v
    return t


@export
def halves(values: list[float]) -> list[float]:
    out = []
    for v in values:
        out.append(v / 2.0)
    return out


@export
def nothing(n: int) -> None:
    if n < 0:
        raise ValueError("negative")


class Box:
    def __init__(self, value: int):
        self.value = value


def plus_one(v):
    return add(v, 1)


xs = [1, 2, 3]
d = {"k": 10}
box = Box(7)
print(add(2, 3), add(-7, 4))
print(scale(0.0), scale(-2.0))
print(flag(True), flag(False))
print(shout(""), shout("h\u00e9llo"))
print(reverse(b"").hex(), reverse(b"\\x01\\x02\\x03\\x00\\xff").hex())
print(total([]), total([1, 2, 3, 4]))
print(halves([]), halves([1.0, 2.0, 4.5]))
nothing(0)
print(plus_one(5), add(xs[1], d["k"]), add(box.value, 1))
try:
    nothing(-1)
except ValueError as error:
    print("error", str(error))
'''

ATTRIBUTE = '''import ail_ffi


@ail_ffi.export
def twice(n: int) -> int:
    return n * 2


print(twice(21))
'''

REFUSED = {
    'missing_parameter_annotation': '''from ail_ffi import export

@export
def f(a) -> int:
    return 1

print(f(1))
''',
    'default_parameter': '''from ail_ffi import export

@export
def f(a: int = 2) -> int:
    return a

print(f())
''',
    'unsupported_result': '''from ail_ffi import export

@export
def f(a: int) -> dict:
    return {}

print(f(1))
''',
    'missing_result_annotation': '''from ail_ffi import export

@export
def f(a: int):
    return a

print(f(1))
''',
    'varargs': '''from ail_ffi import export

@export
def f(*a: int) -> int:
    return 1

print(f(1))
''',
    'dataclass_defined_later': '''from dataclasses import dataclass
from ail_ffi import export


@export
def f(p: Point) -> int:
    return p.x


@dataclass
class Point:
    x: int


print(f(Point(1)))
''',
}


class Ex34Tests(unittest.TestCase):
    def test_examples_match_cpython(self):
        cases = {
            'geometry': (EXAMPLES / 'c_export' / 'geometry.py').read_text(encoding='utf-8'),
            'marker': MARKER,
            'attribute': ATTRIBUTE,
        }
        with tempfile.TemporaryDirectory(prefix='ail-ex34-') as directory:
            for slug, text in cases.items():
                want = cpython(directory, slug, text)
                self.assertEqual(want[1], 0, slug)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))

    def test_invalid_export_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex34-') as directory:
            for slug, text in REFUSED.items():
                self.assertNotEqual(cpython(directory, slug, text)[1], 0, slug)
                for general in (True, False):
                    _, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    output = built.stdout + built.stderr
                    self.assertNotEqual(built.returncode, 0, (slug, general, output[-1200:]))
                    self.assertIn(REFUSAL, output, (slug, general, output[-1200:]))


if __name__ == '__main__':
    unittest.main()
