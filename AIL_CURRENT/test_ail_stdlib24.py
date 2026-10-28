"""Standard library batch 24: the `tempfile` subset, compared with CPython 3.12 on both builds.

Every program below is ordinary Python. CPython is the oracle; the compiled program (AIL_IR=0 and
AIL_IR=1) prints the same stdout and exits with the same status, or the spelling is refused by name
at compile time. Built: gettempdir(), mkdtemp(suffix, prefix, dir) and TemporaryDirectory(...) with
its name, cleanup(), __enter__ and __exit__, from positional arguments, keywords, sys.argv-style
values, function arguments, list items, attributes and dict values. The name is not compared (it is
random in CPython); the directory's existence, parent, prefix and suffix are. Refused by name:
NamedTemporaryFile, mkstemp, tempdir, gettempprefix and TemporaryDirectory(ignore_cleanup_errors= /
delete=).
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BASIC = r'''import os
import tempfile


def main() -> None:
    base = tempfile.gettempdir()
    print(os.path.isdir(base))
    name = tempfile.mkdtemp(prefix='ail-probe-', suffix='.d')
    print(os.path.isdir(name), os.path.basename(name).startswith('ail-probe-'), name.endswith('.d'))
    print(os.path.dirname(name) == base)
    with open(os.path.join(name, 'x.txt'), 'w') as handle:
        handle.write('hi')
    with open(os.path.join(name, 'x.txt')) as handle:
        print(handle.read())
    os.remove(os.path.join(name, 'x.txt'))
    os.rmdir(name)
    print(os.path.isdir(name))


main()
'''

CONTEXT = r'''import os
import tempfile


def main() -> None:
    with tempfile.TemporaryDirectory(prefix='ail-probe-') as directory:
        print(isinstance(directory, str), os.path.isdir(directory))
        print(os.path.basename(directory).startswith('ail-probe-'))
        os.mkdir(os.path.join(directory, 'nested'))
        with open(os.path.join(directory, 'nested', 'x.txt'), 'w') as handle:
            handle.write('hi')
    print(os.path.isdir(directory))
    kept = tempfile.TemporaryDirectory(suffix='.z', prefix='ail-p-')
    path = kept.name
    print(os.path.isdir(path), os.path.basename(path).startswith('ail-p-'), path.endswith('.z'))
    kept.cleanup()
    print(os.path.isdir(path))
    try:
        with tempfile.TemporaryDirectory(prefix='ail-raise-') as inner:
            raise ValueError('inside')
    except ValueError as error:
        print('ValueError', error)
    print(os.path.isdir(inner))


main()
'''

ROUTES = r'''import os
import tempfile


class Box:
    prefix: str

    def __init__(self, prefix: str) -> None:
        self.prefix = prefix


def make(suffix: str, prefix: str, directory: str) -> None:
    name = tempfile.mkdtemp(suffix, prefix, directory)
    print(os.path.dirname(name) == directory, os.path.basename(name).startswith(prefix), name.endswith(suffix))
    os.rmdir(name)


def main() -> None:
    root = tempfile.mkdtemp(prefix='ail-root-')
    prefixes = ['ail-list-']
    values = {'prefix': 'ail-dict-'}
    box = Box('ail-attr-')
    make('.s', 'ail-pos-', root)
    make('.s', prefixes[0], root)
    make('.s', values['prefix'], root)
    make('.s', box.prefix, root)
    with tempfile.TemporaryDirectory(prefix=prefixes[0], suffix='.r') as directory:
        print(os.path.basename(directory).startswith('ail-list-'), directory.endswith('.r'))
    with tempfile.TemporaryDirectory('.t', 'ail-c-', root) as directory:
        print(os.path.dirname(directory) == root, os.path.basename(directory).startswith('ail-c-'), directory.endswith('.t'))
    with tempfile.TemporaryDirectory(dir=root, suffix='.u') as directory:
        print(os.path.dirname(directory) == root, os.path.basename(directory).startswith('tmp'), directory.endswith('.u'))
    os.rmdir(root)


main()
'''

ENVIRONMENT = r'''import os
import tempfile


def main() -> None:
    root = os.path.join(os.getcwd(), 'ail-env-root')
    os.mkdir(root)
    os.environ['TMPDIR'] = root
    first = tempfile.gettempdir()
    print(first == root)
    os.environ['TMPDIR'] = '/definitely/not/here'
    print(tempfile.gettempdir() == first)
    with tempfile.TemporaryDirectory(prefix='ail-env-') as directory:
        print(os.path.dirname(directory) == root)
    os.rmdir(root)


main()
'''

IMPORT_FORMS = r'''import os
from tempfile import TemporaryDirectory, gettempdir


def main() -> None:
    with TemporaryDirectory(prefix='ail-from-') as directory:
        print(os.path.basename(directory).startswith('ail-from-'), os.path.isdir(directory))
    print(os.path.isdir(gettempdir()))
    name = TemporaryDirectory(prefix='ail-keep-').name
    print(os.path.basename(name).startswith('ail-keep-'))


main()
'''

CASES = (
    ("basic", BASIC, ()),
    ("context", CONTEXT, ()),
    ("routes", ROUTES, ()),
    ("environment", ENVIRONMENT, ()),
    ("import_forms", IMPORT_FORMS, ()),
)


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=900, env=dict(os.environ, **env))
    return built, source, exe


class Stdlib24Tests(unittest.TestCase):
    def check(self, name, text, argv, ir):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(AIL_IR="1" if ir else "0")
            built, source, exe = compile_python(directory, text, name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s"
                             % (name, env["AIL_IR"], built.stdout, built.stderr))
            oracle = Path(directory, "oracle.py")
            oracle.write_text(text, encoding="utf-8")
            want = subprocess.run([sys.executable, "-X", "utf8", str(oracle), *argv], capture_output=True,
                                  timeout=300, cwd=directory)
            got = subprocess.run([str(exe), *argv], capture_output=True, timeout=300, cwd=directory)
            self.assertEqual(got.returncode, want.returncode, "%s (AIL_IR=%s): %s"
                             % (name, env["AIL_IR"], got.stderr[-400:]))
            self.assertEqual(got.stdout, want.stdout, name)

    def test_programs_match_cpython(self):
        for name, text, argv in CASES:
            for ir in (False, True):
                with self.subTest(program=name, ir=ir):
                    self.check(name, text, argv, ir)

    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        self.refused("import tempfile\n\n\n"
                     "def main() -> None:\n"
                     "    handle = tempfile.NamedTemporaryFile()\n"
                     "    print(handle.name)\n\n\nmain()\n",
                     "tempfile.NamedTemporaryFile is not built")
        self.refused("import tempfile\n\n\n"
                     "def main() -> None:\n"
                     "    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:\n"
                     "        print(directory)\n\n\nmain()\n",
                     "tempfile.TemporaryDirectory(ignore_cleanup_errors=) is not built")


if __name__ == "__main__":
    unittest.main()
