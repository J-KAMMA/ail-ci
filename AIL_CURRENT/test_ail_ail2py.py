"""The brace-to-Python converter: readable annotated Python with its comments kept.

Five small brace programs cover a struct with impl methods, ``let`` with ``list[float]``, a
``-> void`` function, a top-level ``const`` and try/except.  Two of them are rebuilt through
``--check`` and must produce the same C as the brace source; the other three run as Python and
must print what the AOT binary prints.
"""
import ast
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
TOOL = str(REPO / 'tools' / 'ail2py.py')
HAVE_CC = shutil.which(os.environ.get('PIPE_CC') or 'gcc') is not None

STRUCT_IMPL = '''
struct Box {
    value: int;
}

impl Box {
    fn bump(self, n: int) -> void {
        # start: increase by n
        self.value += n; # end: keep it in the box
    }

    fn get(self) -> int {
        return self.value;
    }
}

fn main() -> int {
    let box = Box(10);
    box.bump(5);
    print(box.get());
    return 0;
}
'''

FLOAT_LIST = '''
fn main() -> int {
    let values: list[float] = [1.5, 2.5];
    let total: float = 0.0;
    for value in values {
        total += value;
    }
    # start: total after the loop
    print(int(total)); # end: the sum
    return 0;
}
'''

VOID_FUNCTION = '''
const LIMIT = 3;

fn show(n: int) -> void {
    # start: print once
    print(n); # end: the value
}

fn main() -> int {
    let i = 0;
    while i < LIMIT {
        show(i);
        i += 1;
    }
    return 0;
}
'''

TRY_EXCEPT = '''
fn main() -> int {
    # start: try path
    try {
        let n = int("12"); # end: parses
        print(n);
    } except ValueError {
        print("bad");
    }
    return 0;
}
'''

STRUCT_LIST = '''
struct Pair {
    a: int;
    b: int;
}

impl Pair {
    fn total(self) -> int {
        return self.a + self.b;
    }
}

fn main() -> int {
    let pair = Pair(4, 5);
    let values: list[float] = [1.0, 2.0, 3.0];
    # start: sum and float count
    print(pair.total(), len(values)); # end: done
    return 0;
}
'''

MULTILINE_COMMENT = '''
fn main() -> int {
    let x = add(
        1,
        2); # end: the sum
    print(x);
    return 0;
}
'''

STRUCT_COMMENT = '''
# file head: before the struct
struct Box {
    # field note: value
    value: int;
}
impl Box {
    # method note: bump
    fn bump(self, n: int) -> void { self.value += n; # end: inline note
    }
}
'''

CLOSE_COMMENT = '''
struct Box {
    value: int;
} # after struct
fn main() -> int {
    if true {
        print(1);
    } # after if
    print(2);
    return 0;
} # after main
'''

USE_AFTER_STRUCT = '''
# top
struct A {
    # field note
    a: int;
}
use block_math;
# before main
fn main() -> int {
    print(1);
    return 0;
}
'''

PROGRAMS = {
    'struct_impl': STRUCT_IMPL,
    'float_list': FLOAT_LIST,
    'void_function': VOID_FUNCTION,
    'try_except': TRY_EXCEPT,
    'struct_list': STRUCT_LIST,
}
CHECKED = ('struct_impl', 'void_function')
RUNTIME = ('float_list', 'try_except', 'struct_list')


def run(command, cwd=None):
    return subprocess.run(command, cwd=cwd, input=b'', capture_output=True, timeout=1800)


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='ail-ail2py-')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def convert(self, name, text):
        source = Path(self.tmp) / (name + '.ail')
        source.write_text(text, encoding='utf-8')
        output = Path(self.tmp) / (name + '.py')
        built = run([sys.executable, '-B', TOOL, str(source), '-o', str(output)])
        self.assertEqual(built.returncode, 0, built.stderr[-3000:])
        return source, output, output.read_text(encoding='utf-8')

    def test_each_output_parses_and_keeps_both_comments(self):
        for name, text in PROGRAMS.items():
            with self.subTest(name):
                _, _, converted = self.convert(name, text)
                ast.parse(converted)
                self.assertNotIn('__ail_', converted)
                self.assertIn('start:', converted)
                self.assertIn('end:', converted)

    def test_comments_precede_the_statement_they_annotate(self):
        _, _, converted = self.convert('multiline', MULTILINE_COMMENT)
        self.assertIn('    # end: the sum\n    x = add(1, 2)', converted)
        _, _, converted = self.convert('struct_comment', STRUCT_COMMENT)
        self.assertTrue(converted.startswith('# file head: before the struct\nclass Box:'))
        self.assertLess(converted.index('# field note: value'), converted.index('self.value = value'))
        self.assertIn('    # method note: bump\n    def bump', converted)
        self.assertIn('        # end: inline note\n        self.value += n', converted)

    def test_closing_brace_comment_belongs_to_its_block(self):
        _, _, converted = self.convert('close_comment', CLOSE_COMMENT)
        self.assertIn('# after struct\nclass Box:', converted)
        self.assertIn('    # after if\n    if True:', converted)
        self.assertIn('# after main\ndef main', converted)
        self.assertNotIn('        # after struct', converted)
        self.assertNotIn('        # after if', converted)
        self.assertNotIn('    # after main', converted)

    def test_field_comment_before_a_later_use_stays_on_the_field(self):
        _, _, converted = self.convert('use_after_struct', USE_AFTER_STRUCT)
        self.assertIn('        # field note\n        self.a = a', converted)
        self.assertLess(converted.index('# field note'), converted.index('# before main'))

    @unittest.skipUnless(HAVE_CC, 'needs a C compiler')
    def test_two_check_identical(self):
        for name in CHECKED:
            with self.subTest(name):
                source = Path(self.tmp) / (name + '.ail')
                source.write_text(PROGRAMS[name], encoding='utf-8')
                checked = run([sys.executable, '-B', TOOL, str(source), '--check',
                               '--flags', '--strict'])
                self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
                self.assertEqual(checked.stdout.strip(), b'identical')

    @unittest.skipUnless(HAVE_CC, 'needs a C compiler')
    def test_three_run_like_the_binary(self):
        for name in RUNTIME:
            with self.subTest(name):
                source, output, _ = self.convert(name, PROGRAMS[name])
                binary = Path(self.tmp) / (name + '.bin')
                built = run([sys.executable, '-B', CLI, 'compile', str(source), '-o', str(binary)])
                self.assertEqual(built.returncode, 0, built.stderr[-3000:])
                wanted = run([str(binary)])
                got = run([sys.executable, str(output)])
                self.assertEqual(got.returncode, wanted.returncode)
                self.assertEqual(got.stdout, wanted.stdout)


if __name__ == '__main__':
    unittest.main()
