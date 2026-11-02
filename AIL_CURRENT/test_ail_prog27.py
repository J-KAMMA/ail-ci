"""Typed reach for eight real programs: hot functions, and the one small blocker fixed.

CPython 3.12 `cProfile` over repeated `main()` calls (the published inputs are tiny) gives the
own-time shares in `lab/progfix/prog27.md`.  Three programs were already wholly typed (t110,
g03_010, t375).  The g05_026 histogram functions were the hot set blocked by one compiler rule:
`build_histogram(counts, symbol: str = "*")` used a str default, and the typed path accepted only
int/float/bool defaults.  A str or bytes literal is immutable and is already a buildable constant,
so `python/pkg-v12/pyfunc.py` now accepts it (and refuses a literal whose kind does not match the
parameter, still by name).  g05_026 is typed as a whole program after this.

The remaining programs need big features and are recorded in the same file: g07_016 mutates a list
parameter (slice assignment plus the read-only list-parameter ABI), t223 needs nested bool lists
and a deque of tuples, t176 needs `json.loads` into `list[dict]`, and g17_018 needs
`singledispatch`/repeated-name registration.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = str(ROOT / 'ail_chatgpt.py')
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None

PROGRAMS = (
    ('g05_026', 'lab/census/programs/gdev/g05_026.py', None),
    ('g07_016', 'lab/census/programs/gdev/g07_016.py', None),
    ('t223', 'lab/corpus/programs/glm-5.3-flash-free/t223.py', 'lab/corpus/tasks/t223'),
    ('t176', 'lab/census/programs/dev/t176.py', 'lab/corpus/tasks/t176'),
    ('t110', 'lab/census/programs/dev/t110.py', 'lab/corpus/tasks/t110'),
    ('g03_010', 'lab/census/programs/gdev/g03_010.py', None),
    ('g17_018', 'lab/census/programs/gdev/g17_018.py', None),
    ('t375', 'lab/corpus/programs/deepseek-v4.1-flash-free/t375.py', 'lab/corpus/tasks/t375'),
)
NEWLY_TYPED = ('g05_026',)
REFUSED_PROGRAMS = {'g17_018': 'duplicate AIL name: _'}

HISTOGRAM = '''from typing import List


def count_words_per_line(text: str) -> List[int]:
    return [len(line.split()) for line in text.splitlines()]


def build_histogram(counts: List[int], symbol: str = "*") -> List[str]:
    rows: List[str] = []
    for index, count in enumerate(counts, start=1):
        rows.append(f"Line {index:>2} | {symbol * count} ({count})")
    return rows


def main() -> None:
    text = "a b\\n\\nc d e\\n"
    counts = count_words_per_line(text)
    for row in build_histogram(counts):
        print(row)
    for row in build_histogram([0, 2], "#"):
        print(row)
    print(build_histogram([]))


main()
'''

DEFAULTS = '''def tag(name: str, sep: str = "-", prefix: str = "") -> str:
    return prefix + sep.join([name, name])


def empty(name: str, sep: str = "") -> str:
    return sep.join([name, "x"])


def unicode_mark(name: str, mark: str = "caf\\u00e9\\u2713") -> str:
    return name + mark


def byte_len(data: bytes = b"abc") -> int:
    return len(data)


def byte_first(data: bytes = b"") -> int:
    return len(data) * 10


def chained(n: int, text: str = "ab") -> int:
    return n + len(text) + byte_len()


def main() -> None:
    print(tag("a"))
    print(tag("a", "+"))
    print(tag("a", prefix="p"))
    print(empty("q"))
    print(unicode_mark("u"))
    print(unicode_mark("u", "!"))
    print(byte_len(), byte_len(b""), byte_len(bytes([0, 255])))
    print(byte_first(), byte_first(b"z"))
    print(chained(2), chained(2, ""))
    values = ["m", "n"]
    print(tag(values[0]), tag(values[1], "|"))
    d: dict[str, str] = {"s": "="}
    print(tag("k", d["s"]))


main()
'''

REFUSED_DEFAULTS = {
    'int_str': ('''def f(x: int = "a") -> int:
    return x + 1


def main() -> None:
    print(f())


main()
''', "the default for 'x' is a str but the parameter is int"),
    'str_bytes': ('''def f(x: str = b"a") -> str:
    return x


def main() -> None:
    print(f())


main()
''', "the default for 'x' is bytes but the parameter is str"),
    'bytes_str': ('''def f(x: bytes = "a") -> int:
    return len(x)


def main() -> None:
    print(f())


main()
''', "the default for 'x' is a str but the parameter is bytes"),
    'list_empty': ('''def f(x: list[int] = []) -> int:
    return len(x)


def main() -> None:
    print(f())


main()
''', 'the default for \'x\' must be a compile-time int, float, bool, str or bytes constant'),
    'str_none': ('''def f(x: str = None) -> str:
    return x


def main() -> None:
    print(f())


main()
''', 'the default for \'x\' must be a compile-time int, float, bool, str or bytes constant'),
    'method_default': ('''class C:
    def __init__(self) -> None:
        pass

    def m(self, x: str = "a") -> str:
        return x


def main() -> None:
    print(C().m())


main()
''', 'C.m must take plain positional arguments, no defaults'),
}


def run(cmd, cwd=None, stdin=b'', env=None):
    return subprocess.run(cmd, cwd=cwd, input=stdin, capture_output=True, env=env, timeout=900)


@unittest.skipUnless(HAVE_CC, 'needs a C compiler')
class TypedReach27(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ail-prog27-')
        self.env = dict(os.environ, AIL_NO_CACHE='1')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def build(self, src, name, strict=False, general=False):
        out = Path(self.tmp) / (name + ('.strict' if strict else '.general' if general else ''))
        env = dict(self.env)
        if general:
            env['AIL_UNIFIED_FORCE'] = '1'
        cmd = [sys.executable, '-B', CLI, 'compile']
        if strict:
            cmd.append('--strict')
        cmd += [str(src), '--syntax', 'python', '-o', str(out)]
        return run(cmd, Path(self.tmp), env=env), out

    def cases(self, task_dir):
        if task_dir is None:
            return [b'']
        base = REPO / task_dir
        return [(base / ('in%d.txt' % i)).read_bytes() for i in range(3)]

    def compare(self, src, exe, task_dir):
        for stdin in self.cases(task_dir):
            want = run([sys.executable, str(src)], Path(self.tmp), stdin=stdin)
            got = run([str(exe)], Path(self.tmp), stdin=stdin)
            self.assertEqual(got.returncode, want.returncode, stdin[:200])
            self.assertEqual(got.stdout, want.stdout, stdin[:200])

    def test_all_eight_match_cpython(self):
        for name, rel, task in PROGRAMS:
            src = REPO / rel
            built, exe = self.build(src, name)
            if name in REFUSED_PROGRAMS:
                output = (built.stdout + built.stderr).decode('utf-8', 'replace')
                self.assertNotEqual(built.returncode, 0, name + ': ' + output[-3000:])
                self.assertIn(REFUSED_PROGRAMS[name], output, name)
                continue
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.compare(src, exe, task)

    def test_newly_typed_program_builds_strict(self):
        for name, rel, task in PROGRAMS:
            if name not in NEWLY_TYPED:
                continue
            src = REPO / rel
            built, exe = self.build(src, name, strict=True)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.compare(src, exe, task)

    def test_newly_typed_functions_build_strict(self):
        src = Path(self.tmp) / 'histogram.py'
        src.write_text(HISTOGRAM, encoding='utf-8')
        built, exe = self.build(src, 'histogram', strict=True)
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        self.compare(src, exe, None)

    def test_string_and_bytes_defaults(self):
        src = Path(self.tmp) / 'defaults.py'
        src.write_text(DEFAULTS, encoding='utf-8')
        for general in (False, True):
            built, exe = self.build(src, 'defaults', strict=not general, general=general)
            self.assertEqual(built.returncode, 0, built.stderr[-3000:])
            self.compare(src, exe, None)

    def test_default_kind_mismatches_are_refused_by_name(self):
        for name, (text, needle) in REFUSED_DEFAULTS.items():
            src = Path(self.tmp) / ('refused_' + name + '.py')
            src.write_text(text, encoding='utf-8')
            built, _ = self.build(src, 'refused_' + name, strict=True)
            output = (built.stdout + built.stderr).decode('utf-8', 'replace')
            self.assertNotEqual(built.returncode, 0, name + ': ' + output[-3000:])
            self.assertIn(needle, output, name + ': ' + output[-3000:])


if __name__ == '__main__':
    unittest.main()
