"""rdiff2: calling a local variable, parameter or container item that holds an instance with ``__call__``.

``m = Scale(3); m(2)`` stopped at run time with ``TypeError: 'Scale' object is not callable``
because a call through a value was dispatched only to function objects; only a call through an
instance attribute (``self.f(2)``) knew about ``__call__``.  A call through any value now goes
through the class's ``__call__`` when the program defines one.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
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


MATCHING = {
    'local_variable': 'class Scale:\n    def __init__(self, k: int) -> None:\n        self.k = k\n\n    def __call__(self, x: int) -> int:\n        return self.k * x\n\n\ndef main() -> None:\n    m = Scale(3)\n    print(m(2), m(-4) + 1)\n\n\nmain()\n',
    'parameter': 'class Scale:\n    def __init__(self, k: int) -> None:\n        self.k = k\n\n    def __call__(self, x: int) -> int:\n        return self.k * x\n\n\ndef apply(f: Scale, v: int) -> int:\n    return f(v) + f(v + 1)\n\n\ndef main() -> None:\n    print(apply(Scale(2), 5))\n\n\nmain()\n',
    'container_item': 'class Scale:\n    def __init__(self, k: int) -> None:\n        self.k = k\n\n    def __call__(self, x: int) -> int:\n        return self.k * x\n\n\ndef main() -> None:\n    fs = [Scale(1), Scale(10)]\n    d = {"a": Scale(5)}\n    print(fs[1](3), d["a"](4), [f(2) for f in fs])\n\n\nmain()\n',
    'subclass_and_plain_function': 'class Scale:\n    def __init__(self, k: int) -> None:\n        self.k = k\n\n    def __call__(self, x: int) -> int:\n        return self.k * x\n\n\nclass Twice(Scale):\n    def __call__(self, x: int) -> int:\n        return 2 * super().__call__(x)\n\n\ndef double(x: int) -> int:\n    return x * 2\n\n\ndef main() -> None:\n    t = Twice(3)\n    f = double\n    print(t(1), f(4))\n    for g in [t, Scale(7)]:\n        print(g(2))\n\n\nmain()\n',
}


class Rdiff2Tests(unittest.TestCase):
    def test_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-rdiff2-') as directory:
            for slug, text in MATCHING.items():
                want = cpython(directory, slug, text)
                for general in (True, False):
                    exe, built = build(directory, '%s_%s' % (slug, 'g' if general else 'd'), text, general)
                    self.assertEqual(built.returncode, 0, (slug, general, built.stdout + built.stderr))
                    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
                    self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                                     (slug, general, got.stderr[-800:]))
                    self.assertEqual(got.returncode, want[1], (slug, general, got.stderr[-800:]))


if __name__ == '__main__':
    unittest.main()
