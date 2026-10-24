"""pre72: a user method fetched as a value is refused by name.

`class U: def upper(self): ...` followed by `U.upper` (or `u.upper`) used to compile and
then raise `AttributeError: 'type' object has no attribute 'upper'` at run time on both
builds, while CPython returns the plain function (or the bound method).  A method in this
runtime is a C function, not an attribute of the class or instance object, so the construct
is now refused by name (DIFFERENCES C?-job-pre72-10241830-1) when the receiver is provably a
user class or instance: a class name, a class alias, or a statically known instance type.
Calling the same methods, reading class attributes, fields and properties are unchanged.
A receiver of unknown static type keeps the older run-time AttributeError -- the open
non-provable-receiver difference recorded for job pre63 (p12).

Programs are built with the general path forced and with the default build; stdout and the
exit status must match CPython for the accepted programs, and the refused ones must name the
difference in the build message on both builds.
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
MARKER = 'C?-job-pre72-10241830-1'


def cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python',
                                '-o', exe.name], cwd=directory, capture_output=True, text=True, timeout=900, env=env)


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre72-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0], (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre72-') as directory:
        for general in (True, False):
            _, built = build(directory, name + ('g' if general else 'd'), text, general)
            test.assertNotEqual(built.returncode, 0, (name, general))
            message = built.stdout + built.stderr
            test.assertIn(MARKER, message, (name, general, message[-1200:]))
            test.assertIn('fetched as a value', message, (name, general, message[-1200:]))


REFUSED = {
    'class_receiver': '''
class U:
    def upper(self) -> str:
        return "HI"


def main() -> None:
    f = U.upper
    print(f(U()))


main()
''',
    'inherited_method': '''
class B:
    def hi(self) -> str:
        return "base"


class U(B):
    pass


def main() -> None:
    f = U.hi
    print(f(U()))


main()
''',
    'instance_receiver': '''
class U:
    def __init__(self) -> None:
        self.x = 1

    def m(self) -> int:
        return 42


def main() -> None:
    u = U()
    v = u
    f = v.m
    print(f())


main()
''',
    'constructor_receiver': '''
class U:
    def __init__(self) -> None:
        self.x = 1

    def m(self) -> int:
        return self.x


def main() -> None:
    f = U().m
    print(f())


main()
''',
    'local_alias': '''
class U:
    def m(self) -> str:
        return "ok"


def main() -> None:
    K = U
    L = K
    f = L.m
    print(f(U()))


main()
''',
    'global_alias': '''
class U:
    def m(self) -> str:
        return "ok"


K = U


def main() -> None:
    f = K.m
    print(f(U()))


main()
''',
}

MATCH = {
    'method_calls': '''
class U:
    def __init__(self) -> None:
        self.x = 7

    def m(self, k: int) -> int:
        return self.x + k

    @staticmethod
    def sm(v: int) -> int:
        return v * 2

    @classmethod
    def cm(cls, v: int) -> str:
        return "c" + str(v)


def main() -> None:
    u = U()
    print(u.m(1), U.m(u, 2), u.x)
    print(U.sm(3), U.cm(4))


main()
''',
    'class_attributes': '''
class B:
    title = "b"


class U(B):
    n = 5


def main() -> None:
    print(U.title, U.n)


main()
''',
    'fields_through_data': '''
class U:
    def __init__(self) -> None:
        self.x = 8


def show(h):
    print(h.x)


def main() -> None:
    u = U()
    xs = [u]
    d = {"u": u}
    print(u.x, xs[0].x, d["u"].x)
    show(u)


main()
''',
    'property_read': '''
class U:
    def __init__(self) -> None:
        self.x = 3

    @property
    def p(self) -> int:
        return self.x * 2


def main() -> None:
    u = U()
    print(u.p)


main()
''',
    'callable_bound_method': '''
class U:
    def __init__(self) -> None:
        self.x = 1

    def m(self) -> int:
        return self.x


def main() -> None:
    u = U()
    print(callable(u.m), callable(u.x))


main()
''',
}


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class MethodValue(unittest.TestCase):
    def test_refused_by_name(self):
        for name, text in sorted(REFUSED.items()):
            check_refused(self, 'refuse_' + name, text)

    def test_calls_and_attributes_unchanged(self):
        for name, text in sorted(MATCH.items()):
            check_program(self, 'match_' + name, text)


if __name__ == '__main__':
    unittest.main()
