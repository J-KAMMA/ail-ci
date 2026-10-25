"""pre235: a statically known local constant expression outside int64 is refused by name.

The pre216 review left `lo - 1` / `hi + 1` (with `lo = -(2**63)` and `hi = 2**63 - 1` in a
function) stopping both builds with an uncatchable run-time ``integer overflow``, where CPython
keeps the bignum.  A local bound once from a constant expression is now folded for this check,
and a binary or unary expression using it that leaves int64 is refused at compile time with
``int64 constant expression out of range``.  In-range uses, a parameter of the same name, and a
rebound local keep their old behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

REFUSED = {
    'local_min': '''def main():
    lo = -9223372036854775807 - 1
    print(lo - 1)
main()
''',
    'local_max': '''def main():
    hi = 9223372036854775807
    print(hi + 1)
main()
''',
    'module': '''lo = -9223372036854775807 - 1
hi = 9223372036854775807
print(lo - 1)
print(hi + 1)
''',
    'alias': '''def main():
    lo = -9223372036854775807 - 1
    a = lo
    print(a - 1)
main()
''',
    'argument': '''def show(v):
    print(v)

def main():
    lo = -9223372036854775807 - 1
    show(lo - 1)
main()
''',
    'list_item': '''def main():
    lo = -9223372036854775807 - 1
    print([lo - 1][0])
main()
''',
    'attribute': '''class Box:
    pass

def main():
    lo = -9223372036854775807 - 1
    b = Box()
    b.v = lo - 1
    print(b.v)
main()
''',
    'dict_value': '''def main():
    hi = 9223372036854775807
    print({"v": hi + 1}["v"])
main()
''',
    'unary': '''def main():
    lo = -9223372036854775807 - 1
    print(-lo)
main()
''',
    'multiply': '''def main():
    hi = 9223372036854775807
    print(hi * 2)
main()
''',
    'mixed': '''def main():
    lo = -9223372036854775807 - 1
    hi = 9223372036854775807
    print(lo - hi)
main()
''',
}

IN_RANGE = r'''def sub(lo):
    return lo - 1


def rebound(c):
    lo = -9223372036854775807 - 1
    if c:
        lo = 0
    return lo - 1


def main():
    lo = -9223372036854775807 - 1
    hi = 9223372036854775807
    print(lo + 1, hi - 1)
    print(lo + hi, hi * 0, lo * 1)
    print(lo // 2, hi // 2, lo % 3, hi % 3)
    print(lo & 1, hi >> 1)
    print(sub(5), sub(-5))
    print(rebound(True))
main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.py')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_UNIFIED_FORCE', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name, '--syntax', 'python',
                            '-o', exe.name], cwd=directory, capture_output=True, text=True, env=env)
    return built, exe


class Pre235Tests(unittest.TestCase):
    def test_local_constant_overflow_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre235-') as directory:
            directory = Path(directory)
            for slug, text in REFUSED.items():
                for general in (False, True):
                    built, exe = _build(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                        text, general)
                    output = built.stdout + built.stderr
                    label = '%s (general=%s)\n%s' % (slug, general, output[-3000:])
                    self.assertEqual(built.returncode, 2, label)
                    self.assertFalse(exe.exists(), label)
                    self.assertIn('int64 constant expression out of range', output, label)

    def test_in_range_and_dynamic_cases_still_match_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre235-') as directory:
            directory = Path(directory)
            want, want_rc = _cpython(directory, 'in_range', IN_RANGE)
            for general in (False, True):
                built, exe = _build(directory, 'in_range_%s' % ('g' if general else 'd'),
                                    IN_RANGE, general)
                label = 'in_range (general=%s)\n%s' % (general, (built.stdout + built.stderr)[-3000:])
                self.assertEqual(built.returncode, 0, label)
                ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
                self.assertEqual(ran.stdout, want, label)
                self.assertEqual(ran.returncode, want_rc, label)


if __name__ == '__main__':
    unittest.main()
