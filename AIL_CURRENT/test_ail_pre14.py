"""A class object reached through a value still answers attribute and method lookup (atomics).

A class used as a plain value (`k = C`, a list/dict element, an attribute, an argument) is
already a CLASS object at run time. Its class attributes and methods previously went through
the instance-attribute path, which only knows INST/EXC, so `k.K` and `k.make()` raised
`AttributeError: 'type' object has no attribute ...` while CPython answered normally. The
general path now dispatches on the CLASS value itself; the typed path refuses the class-as-value
shape by name. Both builds are compared with CPython 3.12.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


VALUE_FORMS = r'''class A:
    I = -7
    F = 2.5
    S = "hi"
    B = True
    N = None
    E = 1 + 2

    @classmethod
    def make(cls):
        return cls()

    @staticmethod
    def inc(x: int) -> int:
        return x + 1

    def val(self) -> int:
        return self.I + 100


class B(A):
    K = 2


class C(B):
    pass


class Holder:
    def __init__(self, k) -> None:
        self.k = k


def via_arg(k):
    return k.I, k.make().val(), k.inc(4)


alias = C
more = alias
pairs = [A, B, C]
mapping = {"a": A, "c": C}
h = Holder(B)
print(alias.K, more.I, alias.F, alias.S, alias.B, alias.N, alias.E)
print(via_arg(A)[0], via_arg(B)[0], via_arg(C)[0])
print(pairs[0].K, pairs[1].K, pairs[2].K, pairs[2].I)
print(mapping["a"].make().val(), mapping["c"].inc(1), h.k.K)
print(alias.make().val(), alias.inc(3), alias.val(alias()))
print(A.make().val(), B.make().val(), C.make().val())
'''


class Pre14Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre14-') as directory:
            oracle = Path(directory, slug + '_cpython.py')
            oracle.write_text(text, encoding='utf-8')
            want = subprocess.run([sys.executable, '-B', str(oracle)], capture_output=True,
                                  timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
            source = Path(directory, slug + '.ail')
            source.write_text(text, encoding='utf-8')
            for general in (True, False):
                exe = Path(directory, slug + ('_g' if general else '_d'))
                env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
                env.pop('AIL_NO_GENERAL', None)
                if general:
                    env['AIL_UNIFIED_FORCE'] = '1'
                else:
                    env.pop('AIL_UNIFIED_FORCE', None)
                built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'),
                                        'compile', source.name, '--syntax', 'python', '-o', exe.name],
                                       cwd=directory, capture_output=True, text=True, timeout=900, env=env)
                self.assertEqual(built.returncode, 0,
                                 '%s (general=%s)\n%s' % (text[:2000], general, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], capture_output=True, timeout=120)
                self.assertEqual(got.stdout.decode(), want.stdout.decode(),
                                 '%s (general=%s)' % (text[:2000], general))
                self.assertEqual(got.returncode, want.returncode,
                                 '%s (general=%s)' % (text[:2000], general))

    def test_class_object_values(self):
        self.check('value_forms', VALUE_FORMS)


if __name__ == '__main__':
    unittest.main()
