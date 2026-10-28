"""`__file__` in Python-syntax programs matches CPython 3.12 on both builds.

CPython binds a main module's `__file__` to the source argument as typed, made absolute against
the current directory (`./p.py` keeps its `./`, `sub/../p.py` its `..`), and an imported module's
to the absolute path of its file (a package's to its `__init__.py`). A compiled program has no
source file at run time, so the entry's reads are replaced by that path at each parsed position
(order-independent: the general path runs top-level statements as written), and a merged sibling
module's reads become its own absolute path. A source that binds `__file__` itself is not
rewritten; an unrelated module-level read there is refused by name, as before.

The entry, an argument, a list item, an attribute, a dict value, a default argument, an f-string,
slicing and `len()` are compared with CPython on the default build and with the general path
forced. Object identity between two reads of a string is a compiler-wide limitation (a control
probe with an ordinary string constant differs the same way), so it is not asserted here.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')


def _cpython(directory, spelling):
    done = subprocess.run([sys.executable, '-B', spelling], cwd=directory, capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_run(directory, spelling, tag, general):
    exe = Path(directory) / ('exe_' + tag + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    built = subprocess.run([sys.executable, '-B', CHATGPT, 'compile', spelling, '--syntax', 'python',
                            '-o', str(exe)], cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], cwd=directory, capture_output=True, timeout=120)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-800:]


class FileNameTests(unittest.TestCase):
    def check(self, files, spelling='p.ail'):
        with tempfile.TemporaryDirectory(prefix='ail-ex6-') as directory:
            for name, text in files.items():
                path = Path(directory, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding='utf-8')
            want = _cpython(directory, spelling)
            self.assertEqual(want[1], 0, 'CPython failed for %s' % spelling)
            for general in (True, False):
                got, err = _build_run(directory, spelling, 'e', general)
                self.assertIsNotNone(got, 'general=%s\n%s' % (general, err))
                self.assertEqual(got, want, 'general=%s\n%s' % (general, err))

    def test_entry_reads(self):
        self.check({'p.ail': """\
def take(path):
    return path[-4:]


class Box:
    pass


box = Box()
box.where = __file__
alias = __file__
values = [__file__, 'tail']
mapping = {'file': __file__}


def with_default(path=__file__):
    return path


print('entry', __file__)
print('arg', take(__file__))
print('list', values[0])
print('attr', box.where)
print('dict', mapping['file'])
print('default', with_default())
print('fstring', f'[{__file__}]')
print('len', len(alias) > 0)
"""})

    def test_spelling_is_kept(self):
        for spelling in ('p.ail', './p.ail', 'sub/../p.ail'):
            with self.subTest(spelling=spelling):
                self.check({'p.ail': "print(__file__)\n", 'sub/keep.txt': ''}, spelling=spelling)

    def test_imported_module(self):
        self.check({
            'p.ail': """\
import helper_file

print('entry', __file__)
print('attr', helper_file.__file__)
print('func', helper_file.name())
print('copy', helper_file.where)
""",
            'helper_file.py': """\
where = __file__


def name():
    return __file__
""",
        })

    def test_package(self):
        self.check({
            'p.ail': """\
import helper_pkg

print('attr', helper_pkg.__file__)
print('copy', helper_pkg.where)
""",
            'helper_pkg/__init__.py': "where = __file__\n",
        })

    def test_rebinding_in_entry_matches(self):
        self.check({'p.ail': "__file__ = 'replaced.py'\nprint(__file__)\nprint(len(__file__))\n"})

    def test_read_in_dead_branch(self):
        self.check({'p.ail': "print('ok')\nif False:\n    saved = __file__\n"})

    def test_local_binding_is_refused_by_name(self):
        text = "def f():\n    __file__ = 'local'\n    return __file__\n\n\nprint(__file__)\nprint(f())\n"
        with tempfile.TemporaryDirectory(prefix='ail-ex6-') as directory:
            Path(directory, 'p.ail').write_text(text, encoding='utf-8')
            for general in (True, False):
                got, err = _build_run(directory, 'p.ail', 'r', general)
                self.assertIsNone(got, 'general=%s built\n%s' % (general, err))
                self.assertIn('__file__', err, 'general=%s\n%s' % (general, err))

    def test_namespace_package_is_refused_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-ex6-') as directory:
            Path(directory, 'p.ail').write_text("import helper_ns\nprint(helper_ns.__file__)\n", encoding='utf-8')
            (Path(directory) / 'helper_ns').mkdir()
            for general in (True, False):
                got, err = _build_run(directory, 'p.ail', 'n', general)
                self.assertIsNone(got, 'general=%s built\n%s' % (general, err))
                self.assertIn('__file__', err, 'general=%s\n%s' % (general, err))


if __name__ == '__main__':
    unittest.main()
