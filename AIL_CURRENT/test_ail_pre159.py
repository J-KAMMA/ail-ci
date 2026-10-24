"""Out-of-range int64 constant expressions are refused by name (job pre159).

The int64 runtime cannot represent a value above INT64_MAX, but only a bare integer literal was
checked before lowering.  `10 ** 30` in a return, an argument, a list item, an attribute, a dict
value or a module constant was built and then stopped at run time with `integer overflow`; an
`__index__` returning that value reached the boxed dispatcher and printed a misleading
`TypeError`.  Every pure integer constant expression whose value leaves int64 is now refused at
compile time with `int64 literal out of range: ...`, on both the general path and the default
build.  In-range constant expressions still compile and match CPython.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which('gcc') is not None


def _env(mode):
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'general':
        env['AIL_UNIFIED_FORCE'] = '1'
    return env


def _build(directory, name, text, mode):
    source = Path(directory) / (name + '_' + mode + '.py')
    source.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    built = subprocess.run(
        [sys.executable, '-B', CHATGPT, 'compile', source.name, '--syntax', 'python', '-o', exe.name],
        cwd=directory, capture_output=True, text=True, timeout=300, env=_env(mode))
    return built, exe


REFUSED = {
    'literal': 'def main() -> None:\n    print(9223372036854775808)\n\nmain()\n',
    'expression': 'def main() -> None:\n    print(10 ** 30)\n\nmain()\n',
    'power': 'def main() -> None:\n    print(2 ** 63)\n\nmain()\n',
    'negative': 'def main() -> None:\n    print(-(10 ** 30))\n\nmain()\n',
    'shift': 'def main() -> None:\n    print(1 << 64)\n\nmain()\n',
    'multiply': 'def main() -> None:\n    print((1 << 62) * 4)\n\nmain()\n',
    'huge_exponent': 'def main() -> None:\n    print(10 ** 4000)\n\nmain()\n',
    'return': 'def big() -> int:\n    return 10 ** 30\n\ndef main() -> None:\n    print(big())\n\nmain()\n',
    'indexonly': ('class FI:\n    def __index__(self) -> int:\n        return 10 ** 30\n\n'
                  'def main() -> None:\n    print([0] * FI())\n\nmain()\n'),
    'argument': ('def show(x: int) -> None:\n    print(x)\n\n'
                 'def main() -> None:\n    show(10 ** 30)\n\nmain()\n'),
    'list_item': 'def main() -> None:\n    print([1, 10 ** 30])\n\nmain()\n',
    'attribute': ('class Box:\n    pass\n\n'
                  'def main() -> None:\n    b = Box()\n    b.value = 10 ** 30\n    print(b.value)\n\nmain()\n'),
    'dict_value': 'def main() -> None:\n    print({"big": 10 ** 30}["big"])\n\nmain()\n',
    'aliased': ('BIG = 10 ** 30\n\n'
                'def main() -> None:\n    x = BIG\n    print(x)\n\nmain()\n'),
}

VALID = ('def main() -> None:\n'
         '    print(2 ** 62)\n'
         '    print((1 << 62) - 1)\n'
         '    print(-(2 ** 62))\n'
         '    print(2 ** (63 - 1))\n'
         '    print(3 ** 20)\n'
         '    print(~0)\n'
         '    print(1 ^ 2 ^ 4)\n'
         '    print(7 // 2, 7 % 4)\n\n'
         'main()\n')


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class Int64ConstantExpressions(unittest.TestCase):
    def test_out_of_range_is_refused_before_lowering(self):
        for name, text in REFUSED.items():
            for mode in ('general', 'default'):
                with self.subTest(name=name, mode=mode), tempfile.TemporaryDirectory() as d:
                    built, _ = _build(d, name, text, mode)
                    self.assertNotEqual(built.returncode, 0, name)
                    output = built.stdout + built.stderr
                    self.assertIn('int64 literal out of range', output, output[-800:])

    def test_in_range_expressions_match_cpython(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d, 'valid_cpython.py')
            source.write_text(VALID, encoding='utf-8')
            want = subprocess.run([sys.executable, '-B', str(source)], capture_output=True, timeout=120)
            for mode in ('general', 'default'):
                with self.subTest(mode=mode):
                    built, exe = _build(d, 'valid', VALID, mode)
                    self.assertEqual(built.returncode, 0, built.stderr[-2000:])
                    got = subprocess.run([str(exe)], cwd=d, capture_output=True, timeout=120)
                    self.assertEqual(got.returncode, want.returncode, got.stderr[-500:])
                    self.assertEqual(got.stdout, want.stdout)


if __name__ == '__main__':
    unittest.main()
