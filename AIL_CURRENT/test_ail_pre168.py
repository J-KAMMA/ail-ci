"""`list(itertools.permutations(...))` on the default build (pre-existing difference from job pre137).

A `permutations` / `combinations` / `combinations_with_replacement` / `product` stream yields tuples.
Materialising one with `list(...)` (or `return list(...)`) on the typed path passed the inner list
to `ail_list_push(int64_t)` and the C compiler rejected the program, so the default build failed
while the general path matched CPython.  The typed lowering now refuses that exact construct by
name, so the default build falls back to the general path (which matches CPython) and
`AIL_NO_GENERAL=1` reports the refusal.  The programs below cover literal and variable `r`, values
from an argument, a list item, an attribute and a dict value, int / float / str / tuple / empty
pools, and the three tuple-yielding itertools functions.

stdout, the exit status and the last stderr line are compared with CPython for the general and the
default build; the typed path alone must refuse with the construct's name.
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


def _last_line(err):
    lines = [x for x in err.decode('utf-8', 'replace').splitlines() if x.strip() and 'raised near' not in x]
    return lines[-1] if lines else ''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1', PYTHONWARNINGS='ignore'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, _last_line(done.stderr)


def _build_run(directory, name, text, mode):
    src = Path(directory) / (name + '_' + mode + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + '_' + mode)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    env.pop('AIL_UNIFIED_FORCE', None)
    if mode == 'typed':
        env['AIL_NO_GENERAL'] = '1'
    elif mode == 'general':
        env['AIL_UNIFIED_FORCE'] = '1'
    cmd = [sys.executable, '-B', CHATGPT, 'compile', src.name, '--syntax', 'python', '-o', exe.name]
    built = subprocess.run(cmd, cwd=directory, capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-1500:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode, _last_line(got.stderr)), None


LITERAL = r'''import itertools


def main() -> None:
    out = list(itertools.permutations([1, 2, 3], 1))
    print(out)
    out5 = list(itertools.permutations([1, 2, 3], 5))
    print(out5)
    print(list(itertools.permutations([1, 2, 3], 0)))


main()
'''

RETURN_AND_SOURCES = r'''import itertools


class Box:
    def __init__(self, r: int) -> None:
        self.r = r


def made(r: int) -> list:
    return list(itertools.permutations([1, 2, 3], r))


def main() -> None:
    print(made(1))
    print(made(5))
    rs = [2, 3]
    print(made(rs[1]))
    b = Box(1)
    print(made(b.r))
    d = {"r": 5}
    print(made(d["r"]))


main()
'''

TYPES = r'''import itertools


def main() -> None:
    print(list(itertools.permutations([1, 2, 3], 1)))
    print(list(itertools.permutations([1.5, 2.5], 1)))
    print(list(itertools.permutations(["a", "b"], 1)))
    print(list(itertools.permutations((7, 8), 1)))
    print(list(itertools.permutations([], 0)))
    print(list(itertools.combinations([1, 2, 3], 2)))
    print(list(itertools.combinations_with_replacement([1, 2], 2)))
    print(list(itertools.product([1, 2], [3, 4])))


main()
'''

POOLS = r'''import itertools


class Box:
    def __init__(self) -> None:
        self.items = [4, 5]


def show(pool, r: int) -> None:
    print(list(itertools.permutations(pool, r)))


def main() -> None:
    rows = [[1, 2], [3, 4, 5]]
    b = Box()
    d = {"xs": [6, 7]}
    show(rows[0], 1)
    show(b.items, 2)
    show(d["xs"], 5)
    show("ab", 1)


main()
'''

CASES = [
    ('literal_and_return', LITERAL),
    ('r_from_argument_item_attribute_dict', RETURN_AND_SOURCES),
    ('element_types_and_empty', TYPES),
    ('pool_from_item_attribute_dict_argument', POOLS),
]


@unittest.skipUnless(HAVE_CC, 'gcc is required')
class ListOfTuples(unittest.TestCase):
    def check(self, name, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre168-') as directory:
            want = _cpython(directory, name, text)
            for mode in ('general', 'default'):
                got, error = _build_run(directory, name, text, mode)
                self.assertIsNone(error, '%s %s: %s' % (name, mode, error))
                self.assertEqual(got, want, '%s %s' % (name, mode))

    def test_literal_r_and_return(self):
        self.check('literal', LITERAL)

    def test_values_through_argument_item_attribute_dict(self):
        self.check('sources', RETURN_AND_SOURCES)

    def test_element_types_empty_and_other_tuple_streams(self):
        self.check('types', TYPES)

    def test_pool_from_argument_item_attribute_dict(self):
        self.check('pools', POOLS)

    def test_typed_path_refuses_the_construct_by_name(self):
        with tempfile.TemporaryDirectory(prefix='ail-pre168-') as directory:
            _, error = _build_run(directory, 'literal', LITERAL, 'typed')
            self.assertIsNotNone(error)
            self.assertIn('list(itertools.permutations(...))', error)
            self.assertIn('typed path', error)


if __name__ == '__main__':
    unittest.main()
