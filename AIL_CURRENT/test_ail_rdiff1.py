"""rdiff1: an f-string replacement field calls a user-defined ``__format__`` like CPython.

``f"{x}"`` is ``format(x, "")``: when the class defines ``__format__`` it is called with the empty
spec.  The general runtime stringified the value with ``__str__`` instead, so ``f"{m}"`` printed the
``__str__`` text while ``"{}".format(m)``, ``format(m)`` and ``f"{m:>5}"`` used ``__format__``.
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
    'plain_field': 'class M:\n    def __init__(self, c: int) -> None:\n        self.c = c\n\n    def __str__(self) -> str:\n        return "str" + str(self.c)\n\n    def __repr__(self) -> str:\n        return "repr"\n\n    def __format__(self, spec: str) -> str:\n        return "fmt[" + spec + "]"\n\n\ndef main() -> None:\n    m = M(1)\n    print(f"{m}", f"<{m}>", f"{m:>5}", "{}".format(m), format(m), str(m), f"{m!s}", f"{m!r}")\n\n\nmain()\n',
    'in_function_and_list': 'class M:\n    def __init__(self, c: int) -> None:\n        self.c = c\n\n    def __str__(self) -> str:\n        return "str" + str(self.c)\n\n    def __repr__(self) -> str:\n        return "repr"\n\n    def __format__(self, spec: str) -> str:\n        return "fmt[" + spec + "]"\n\n\ndef label(x: M) -> str:\n    return f"item={x} n={x.c}"\n\n\ndef main() -> None:\n    xs = [M(1), M(2)]\n    print(label(xs[0]), [f"{x}" for x in xs], f"{xs[1]}-{xs[0]}")\n\n\nmain()\n',
    'inherited': 'class M:\n    def __init__(self, c: int) -> None:\n        self.c = c\n\n    def __str__(self) -> str:\n        return "str" + str(self.c)\n\n    def __repr__(self) -> str:\n        return "repr"\n\n    def __format__(self, spec: str) -> str:\n        return "fmt[" + spec + "]"\n\n\nclass N(M):\n    pass\n\n\ndef main() -> None:\n    print(f"{N(3)}", f"{M(4)}", f"{N(5):x}")\n\n\nmain()\n',
    'no_format_class_unchanged': 'class P:\n    def __init__(self, c: int) -> None:\n        self.c = c\n\n    def __str__(self) -> str:\n        return "p" + str(self.c)\n\n\nclass Q(P):\n    def __format__(self, spec: str) -> str:\n        return "q" + spec\n\n\ndef main() -> None:\n    print(f"{P(1)}", f"{Q(2)}", f"{3}", f"{2.5}", f"{\'s\'}", f"{True}", f"{None}")\n    print(format(P(1)), "{}".format(P(1)), format(Q(1), "z"))\n    print([f"{x}" for x in [P(1), Q(2)]])\n\n\nmain()\n',
}


class Rdiff1Tests(unittest.TestCase):
    def test_matches_cpython(self):
        with tempfile.TemporaryDirectory(prefix='ail-rdiff1-') as directory:
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
