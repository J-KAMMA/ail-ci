"""The `--json` machine form of a compiler diagnostic (docs/design/AGENT_ERRORS.md, step 1).

One program per message family from `lab/err/triggers/` is compiled with `--json`.  The build
report carries `agent_diagnostics`, one object per known family:

    {"code","severity","file","line","col","cause","message","fix":{"replace_range","with"}}

`message` is the human note byte for byte.  The literal `fix` is applied to the source (whole
lines, 1-based inclusive) and the result must build; for every family but the compiler-internal
row-arity note (AIL0102, implementation step 2) the family's message must be gone.  Every fixed
program also prints what CPython prints.

The variants below are the shapes the first version got wrong: a renamed variable, a prelude line
inside the file, a second function that also returns a number, two identical bad comparisons, a
renamed `.get` receiver, an edit range that spanned lines its `with` did not reproduce, a branch the
edit flipped, and a `.get` default that replaced a real `None`.  A failed build (refusal) and
`--strict --json` carry the field too, with `severity:"error"`.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CLI = ROOT / 'ail_chatgpt.py'
TRIGGERS = REPO / 'lab' / 'err' / 'triggers'
ORIGINAL = REPO / 'lab' / 'err' / 'messages_original.json'
REWRITTEN = REPO / 'lab' / 'err' / 'messages_rewritten.json'

CODES = {
    '01_stdin_buffer': 'AIL0101', '02_poprow_arity': 'AIL0102', '03_str_number': 'AIL0103',
    '04_dict_get_optional': 'AIL0104', '05_dict_of_containers': 'AIL0105',
    '06_class_list_comp': 'AIL0106', '07_bool_number_mix': 'AIL0107',
    '08_bytes_number_return': 'AIL0108', '09_while_else': 'AIL0109',
    '10_nested_annotation': 'AIL0110', '11_fraction_dunder': 'AIL0111',
    '12_decimal_format': 'AIL0112', '13_yield': 'AIL0113',
    '14_tuple_single_value': 'AIL0114', '15_list_param_readonly': 'AIL0115',
}

# name -> (source, code, line the diagnostic must name)
VARIANTS = {
    'fraction_renamed': ("""from fractions import Fraction
y = Fraction(2, 3)
print(float(y))
""", 'AIL0111', 3),
    'decimal_shifted': ("""from decimal import Decimal
x = Decimal("1.234")
y = x * 2
print(f"{y:.2f}")
""", 'AIL0112', 4),
    'class_comp_renamed': ("""class Q:
    def __init__(self, x: int) -> None:
        self.x = x

def build(zs: list[int]) -> list[Q]:
    return [Q(z) for z in zs]

print(build([3, 4])[0].x)
""", 'AIL0106', 6),
    'bytes_second_function': ("""def zero() -> int:
    return 0

def term(tok: bytes):
    t = tok.replace(b"'", b"")
    if len(t) > 0:
        return b"#" + str(len(t)).encode()
    return 0

print(zero(), term(b"x"))
""", 'AIL0108', 8),
    'get_renamed': ("""m = {1: 10, 2: 20}
k = 1
v = m.get(k)
print(v)
""", 'AIL0104', 3),
    'duplicate_comparison': ("""s = "abc"
if s == 1:
    print("one")
print("mid")
if s == 1:
    print("two")
print("end")
""", 'AIL0103', 2),
    # implementation step 2: the same user name popped from heaps of two widths, renamed.  The
    # diagnostic must name `job` and its first pop site, never the compiler's `_ail_l1l`.
    'poprow_renamed': ((TRIGGERS / '02_poprow_arity.py').read_text(encoding='utf-8')
                       .replace('entry', 'job'), 'AIL0102', 78),
}

ASYNC = """import asyncio

async def main() -> int:
    return 5

print(asyncio.run(main()))
"""

# The shapes where an earlier version published an edit that changed the program: an edit range that
# spanned lines its `with` did not reproduce (AIL0111/AIL0101), a branch that the edit flipped
# (AIL0103), and a `.get` default that replaced a real `None` (AIL0104).  The last field is the
# number of source lines inside the range that the replacement deliberately drops.
UNSAFE = {
    'fraction_line_between': ("""from fractions import Fraction
x = Fraction(1, 2)
print("side")
print(float(x))
""", 'AIL0111', 'side\n0.5\n', 2),
    'fraction_multiline_call': ("""from fractions import Fraction
x = Fraction(
    1, 2)
print(float(x))
""", 'AIL0111', '0.5\n', 3),
    'fraction_in_larger_expression': ("""from fractions import Fraction
x = Fraction(1, 2)
print(2 / float(x))
""", 'AIL0111', '4.0\n', 2),
    'stdin_line_between': ("""import sys
read = sys.stdin.buffer.readline
print("mid")
print(read().decode().strip())
""", 'AIL0101', 'mid\nhello\n', 1),
    'stdin_saved_twice': ("""import sys
r1 = sys.stdin.buffer.readline
r2 = sys.stdin.buffer.readline
print(r1().decode().strip())
""", 'AIL0101', 'hello\n', 2),
    'str_equals_literal': ("""s = "1"
if s == 1:
    print("one")
else:
    print("not one")
""", 'AIL0103', 'not one\n', 0),
    'str_not_equals_literal': ("""s = "1"
if s != 1:
    print("taken")
else:
    print("not")
""", 'AIL0103', 'taken\n', 0),
    'str_two_comparisons_on_one_line': ("""s = "1"
print(s == 1, s == 1)
""", 'AIL0103', 'False False\n', 0),
    'str_two_names_on_one_line': ("""s = "1"
t = "2"
print(s == 1, t == 1)
""", 'AIL0103', 'False False\n', 0),
}


# The saved method or the `float(...)` call need not sit on the statement's first line: `print(`
# on one line and the call on the next, or the call itself split across lines.  An earlier version
# keyed the edit to `statement.lineno` / `call.lineno` while the columns belonged to the argument, so
# `with` glued `prin` to the replacement and dropped the call.  The edit now replaces the whole span
# of the argument/call, and the range may drop only the lines the replacement covers.
SPLIT = {
    'stdin_print_then_call': ("""import sys
read = sys.stdin.buffer.readline
print(
    read().decode().strip())
""", 'AIL0101', 'hello\n', 1),
    'stdin_call_split_before_decode': ("""import sys
read = sys.stdin.buffer.readline
print(read()
      .decode().strip())
""", 'AIL0101', 'hello\n', 2),
    'stdin_chain_one_per_line': ("""import sys
read = sys.stdin.buffer.readline
print(
    read()
    .decode()
    .strip()
)
""", 'AIL0101', 'hello\n', 3),
    'fraction_print_then_call': ("""from fractions import Fraction
x = Fraction(1, 2)
print(float(
    x))
""", 'AIL0111', '0.5\n', 3),
    'fraction_call_split_before_close': ("""from fractions import Fraction
x = Fraction(1, 2)
print(float(x
            ))
""", 'AIL0111', '0.5\n', 3),
}


class AgentErrors(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='ail-agent-errors-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.original = json.loads(ORIGINAL.read_text(encoding='utf-8'))
        self.rewritten = json.loads(REWRITTEN.read_text(encoding='utf-8'))

    def compile(self, source, name, as_json=True, extra=()):
        command = [sys.executable, '-B', str(CLI), 'compile', str(source), '--syntax', 'python',
                   '-o', str(self.tmp / name)] + list(extra) + (['--json'] if as_json else [])
        environment = {key: value for key, value in os.environ.items()
                       if key not in ('AIL_NO_GENERAL', 'AIL_QUIET_FALLBACK', 'AIL_STRICT')}
        return subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=900,
                              env=environment)

    def apply(self, source, item, name):
        """Write the source with `item['fix']` applied; return its path."""
        lines = source.read_text(encoding='utf-8').split('\n')
        first, last = item['fix']['replace_range']
        fixed = '\n'.join(lines[:first - 1] + item['fix']['with'].split('\n') + lines[last:])
        path = self.tmp / (name + '.py')
        path.write_text(fixed, encoding='utf-8')
        return path

    def check_fix(self, source, item, code, name):
        self.assertIn('fix', item, (code, item))
        fix = item['fix']
        self.assertEqual(len(fix['replace_range']), 2)
        self.assertLessEqual(fix['replace_range'][0], fix['replace_range'][1])
        self.assertTrue(fix['with'])
        fixed_path = self.apply(source, item, name)
        rebuilt = self.compile(fixed_path, name + '_fixed')
        self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
        after = [entry['code'] for entry in json.loads(rebuilt.stdout).get('agent_diagnostics', [])]
        self.assertNotIn(code, after, after)
        native = subprocess.run([str(self.tmp / (name + '_fixed'))], capture_output=True, timeout=120)
        cpython = subprocess.run([sys.executable, str(fixed_path)], capture_output=True, timeout=120)
        self.assertEqual((native.returncode, native.stdout), (cpython.returncode, cpython.stdout))

    def test_one_program_per_family(self):
        for stem, code in CODES.items():
            with self.subTest(stem=stem):
                source = Path('lab') / 'err' / 'triggers' / (stem + '.py')
                built = self.compile(source, stem)
                self.assertEqual(built.returncode, 0, built.stderr)
                report = json.loads(built.stdout)
                found = [item for item in report.get('agent_diagnostics', []) if item['code'] == code]
                self.assertEqual(len(found), 1, (code, report.get('agent_diagnostics')))
                item = found[0]
                self.assertEqual(item['severity'], 'note')
                self.assertEqual(item['file'], source.as_posix())
                self.assertIsInstance(item['line'], int)
                self.assertIsInstance(item['col'], int)
                self.assertTrue(item['cause'])
                self.assertNotIn('_ail_', item['cause'])
                # The agent format: the position is in the user's file, the cause names only the
                # user's identifiers, and the message carries the literal `Replace:`/`With:` edit.
                self.assertNotIn('_ail_', item['message'])
                head = '%s:%d:%d: %s: ' % (source.as_posix(), item['line'], item['col'], code)
                self.assertTrue(item['message'].startswith(head), item['message'])
                self.assertIn('\nReplace:\n', item['message'])
                self.assertIn('\nWith:\n', item['message'])
                if code not in ('AIL0102', 'AIL0111'):
                    self.assertEqual(item['message'], self.rewritten[stem], item['message'])
                if code == 'AIL0102':
                    # implementation step 2: the row-arity note no longer names a compiler
                    # temporary; it names the user's row variable and every heap it was popped from.
                    self.assertNotEqual(item['message'], self.original[stem])
                    self.assertIn("'entry'", item['message'])
                    for heap in ('departures', 'wait1', 'wait2', 'wait3'):
                        self.assertIn(heap, item['message'])
                elif code == 'AIL0111':
                    # step 2: a note raised inside a shipped prelude now points at the user's call
                    # and says which module it came from instead of the prelude's line 235.
                    self.assertNotEqual(item['message'], self.original[stem])
                    self.assertIn('fractions', item['message'])
                    self.assertNotIn(':235:', item['message'])
                    self.assertEqual(item['line'], 3, item)
                elif code == 'AIL0112':
                    # step 2 moved the note to the user's call; the agent message names the old
                    # prelude line in its cause (the design's exact rewrite).
                    self.assertNotIn(':1687:1: built on the general path', item['message'])
                    self.assertEqual(item['line'], 3, item)

                text = (REPO / source).read_text(encoding='utf-8')
                lines = text.split('\n')
                self.assertGreaterEqual(item['line'], 1, (code, item['line']))
                self.assertLessEqual(item['line'], len(lines), (code, item['line']))
                fix = item['fix']
                self.assertEqual(len(fix['replace_range']), 2)
                self.assertLessEqual(fix['replace_range'][0], fix['replace_range'][1])
                self.assertTrue(fix['with'])

                first, last = fix['replace_range']
                fixed = '\n'.join(lines[:first - 1] + fix['with'].split('\n') + lines[last:])
                fixed_path = self.tmp / (stem + '_fixed.py')
                fixed_path.write_text(fixed, encoding='utf-8')
                rebuilt = self.compile(fixed_path, stem + '_fixed')
                self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
                after = [entry['code'] for entry in json.loads(rebuilt.stdout).get('agent_diagnostics', [])]
                self.assertNotIn(code, after, after)

    def test_fixed_program_prints_what_cpython_prints(self):
        for stem in CODES:
            with self.subTest(stem=stem):
                source = REPO / 'lab' / 'err' / 'triggers' / (stem + '.py')
                built = self.compile(source, stem + '_run')
                self.assertEqual(built.returncode, 0, built.stderr)
                item = next(item for item in json.loads(built.stdout)['agent_diagnostics']
                            if item['code'] == CODES[stem])
                fixed_path = self.apply(source, item, stem + '_run')
                rebuilt = self.compile(fixed_path, stem + '_run_fixed')
                self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
                stdin = source.with_suffix('.in')
                data = stdin.read_bytes() if stdin.is_file() else b''
                native = subprocess.run([str(self.tmp / (stem + '_run_fixed'))], input=data,
                                        capture_output=True, timeout=120)
                cpython = subprocess.run([sys.executable, str(fixed_path)], input=data,
                                         capture_output=True, timeout=120)
                self.assertEqual((native.returncode, native.stdout), (cpython.returncode, cpython.stdout))

    def test_variants_locate_the_users_code(self):
        for name, (text, code, line) in VARIANTS.items():
            with self.subTest(name=name):
                source = self.tmp / (name + '.py')
                source.write_text(text, encoding='utf-8')
                built = self.compile(source, name)
                self.assertEqual(built.returncode, 0, built.stderr)
                report = json.loads(built.stdout)
                found = [item for item in report.get('agent_diagnostics', []) if item['code'] == code]
                self.assertEqual(len(found), 1, (code, report.get('agent_diagnostics')))
                item = found[0]
                self.assertEqual(item['severity'], 'note')
                self.assertEqual(item['file'], str(source))
                self.assertEqual(item['line'], line, item)
                self.assertIn('fix', item, item)
                self.check_fix(source, item, code, name)

    def test_prelude_notes_point_at_the_users_call(self):
        # A refusal raised while loading a shipped prelude is reported on the merged text, so the
        # compiler used to name a line of the prelude (235 in `fractions`, 1687 in `decimal`).
        # The note now names the user's call and says which module it came from.
        cases = (
            ('fraction_call', 'from fractions import Fraction\nx = Fraction(1, 2)\nprint(float(x))\n',
             'fractions', 'dunder'),
            ('decimal_format', 'from decimal import Decimal\nd = Decimal("1.234")\nprint(f"{d:.2f}")\n',
             'decimal', 'format spec'),
            # a later call of the same builtin on a value that is not the prelude type must not
            # move the note: the failing expression is the one that reaches the prelude.
            ('fraction_call_then_literal',
             'from fractions import Fraction\na = Fraction(1, 2)\nprint(float(a))\nprint(float(3))\n',
             'fractions', 'dunder'),
            ('decimal_format_then_literal',
             'from decimal import Decimal\nd = Decimal("2.5")\nprint(f"{d:.1f}")\nprint(f"{1.5:.1f}")\n',
             'decimal', 'format spec'),
        )
        for name, text, module, marker in cases:
            with self.subTest(name=name):
                source = self.tmp / (name + '.py')
                source.write_text(text, encoding='utf-8')
                built = self.compile(source, name, as_json=False)
                self.assertEqual(built.returncode, 0, built.stderr)
                note = next(line for line in built.stderr.splitlines()
                            if marker in line and 'built on the general path' in line)
                self.assertIn("standard library's %s module" % module, note)
                where = re.search(r':(\d+):(\d+): built on the general path', note)
                self.assertIsNotNone(where, note)
                self.assertEqual(int(where.group(1)), 3, note)
                self.assertNotIn(':235:', note)
                self.assertNotIn(':1687:', note)

    def test_prelude_note_without_the_unit_name_points_at_the_users_call(self):
        # `_dec_cmp_parts` is a definition the decimal prelude adds; the reason does not contain
        # the word `Decimal`, so the note used to stay at prelude line 318.  It now names the
        # user's first use and says which module it came from.
        source = self.tmp / 'decimal_plain.py'
        source.write_text('from decimal import Decimal\nd = Decimal("2.5")\nprint(d + d)\n',
                          encoding='utf-8')
        built = self.compile(source, 'decimal_plain', as_json=False)
        self.assertEqual(built.returncode, 0, built.stderr)
        note = next(line for line in built.stderr.splitlines()
                    if 'built on the general path' in line)
        self.assertIn("standard library's decimal module", note)
        where = re.search(r':(\d+):(\d+): built on the general path', note)
        self.assertIsNotNone(where, note)
        self.assertEqual(int(where.group(1)), 3, note)
        self.assertNotIn(':318:', note)

    def assert_applied_output(self, name, text, code, expected, dropped):
        source = self.tmp / (name + '.py')
        source.write_text(text, encoding='utf-8')
        built = self.compile(source, name)
        self.assertEqual(built.returncode, 0, built.stderr)
        found = [item for item in json.loads(built.stdout).get('agent_diagnostics', [])
                 if item['code'] == code]
        self.assertEqual(len(found), 1, found)
        item = found[0]
        self.assertIn('fix', item, item)
        first, last = item['fix']['replace_range']
        lines = text.split('\n')
        self.assertTrue(1 <= first <= last <= len(lines), item['fix'])
        # The range may drop only the lines the replacement text itself covers: the
        # `fractions` import and every line of the `Fraction(...)` assignment (AIL0111), the
        # saved `readline` lines (AIL0101).  Every other line of the range is reproduced.
        self.assertEqual(len(item['fix']['with'].split('\n')),
                         (last - first + 1) - dropped, item['fix'])
        fixed_path = self.apply(source, item, name)
        rebuilt = self.compile(fixed_path, name + '_fixed')
        self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
        after = [entry['code'] for entry in json.loads(rebuilt.stdout).get('agent_diagnostics', [])]
        self.assertNotIn(code, after, after)
        data = b'hello\n' if code == 'AIL0101' else b''
        native = subprocess.run([str(self.tmp / (name + '_fixed'))], input=data,
                                capture_output=True, timeout=120)
        cpython = subprocess.run([sys.executable, str(fixed_path)], input=data,
                                 capture_output=True, timeout=120)
        self.assertEqual((native.returncode, native.stdout), (cpython.returncode, cpython.stdout))
        self.assertEqual(native.stdout.decode(), expected)

    def test_unsafe_shapes_keep_the_output(self):
        for name, (text, code, expected, dropped) in UNSAFE.items():
            with self.subTest(name=name):
                self.assert_applied_output(name, text, code, expected, dropped)

    def test_split_call_shapes_keep_the_output(self):
        for name, (text, code, expected, dropped) in SPLIT.items():
            with self.subTest(name=name):
                self.assert_applied_output(name, text, code, expected, dropped)

    def test_no_edit_when_the_values_are_not_provable(self):
        # `d.get(k, -1)` prints `-1` where CPython prints `None`, and `s == "1"` takes a branch
        # CPython does not when `s` turns out to be `"1"`: neither edit may be published unless the
        # source proves the value.  The diagnostic still carries its position and cause.
        for name, text, code in (
                ('absent_key', 'd = {"a": 1, "b": 2}\nk = "c"\nprint(d.get(k))\n', 'AIL0104'),
                ('literal_absent_key', 'd = {"a": 1, "b": 2}\nprint(d.get("c"))\n', 'AIL0104'),
                ('stored_key', 'd = {"a": 1, "b": 2}\nd["b"] = 5\nk = "b"\nprint(d.get(k))\n',
                 'AIL0104'),
                ('unknown_str', 's = input()\nif s == 1:\n    print("one")\nelse:\n    print("no")\n',
                 'AIL0103')):
            with self.subTest(name=name):
                source = self.tmp / (name + '.py')
                source.write_text(text, encoding='utf-8')
                built = self.compile(source, name)
                self.assertEqual(built.returncode, 0, built.stderr)
                found = [item for item in json.loads(built.stdout).get('agent_diagnostics', [])
                         if item['code'] == code]
                self.assertEqual(len(found), 1, found)
                self.assertNotIn('fix', found[0], found[0])
                self.assertIsInstance(found[0]['line'], int)
                self.assertIsInstance(found[0]['col'], int)
                self.assertTrue(found[0]['cause'])

    def test_empty_file_refusal_has_a_position(self):
        source = self.tmp / 'empty.py'
        source.write_text('', encoding='utf-8')
        built = self.compile(source, 'empty')
        self.assertEqual(built.returncode, 3, built.stderr)
        diagnostics = json.loads(built.stdout).get('agent_diagnostics') or []
        self.assertEqual(len(diagnostics), 1, diagnostics)
        self.assertEqual(diagnostics[0]['code'], 'AIL0000')
        self.assertEqual((diagnostics[0]['line'], diagnostics[0]['col']), (1, 1), diagnostics[0])

    def test_refusal_carries_an_error_diagnostic(self):
        source = self.tmp / 'async_refusal.py'
        source.write_text(ASYNC, encoding='utf-8')
        built = self.compile(source, 'async_refusal')
        self.assertEqual(built.returncode, 3, built.stderr)
        report = json.loads(built.stdout)
        self.assertEqual(report['status'], 'failed')
        diagnostics = report.get('agent_diagnostics') or []
        self.assertEqual(len(diagnostics), 1, diagnostics)
        item = diagnostics[0]
        self.assertEqual(item['severity'], 'error')
        self.assertEqual(item['code'], 'AIL0000')
        self.assertIsInstance(item['line'], int)
        self.assertEqual(item['line'], 3, item)
        self.assertTrue(item['cause'])

    def test_strict_json_carries_the_same_field(self):
        source = Path('lab') / 'err' / 'triggers' / '13_yield.py'
        built = self.compile(source, 'strict_yield', extra=['--strict'])
        self.assertEqual(built.returncode, 3, built.stderr)
        report = json.loads(built.stdout)
        self.assertEqual(report['schema'], 'ail.strict/1')
        diagnostics = report.get('agent_diagnostics') or []
        found = [item for item in diagnostics if item['code'] == 'AIL0113']
        self.assertEqual(len(found), 1, diagnostics)
        self.assertEqual(found[0]['severity'], 'error')
        self.assertEqual(found[0]['line'], 3)

    def test_while_else_with_break_is_break_aware(self):
        # The table's cause says "the loop has no `break`, so the `else` body always runs" and
        # offers to move the `else` after the loop.  Both are false when the loop breaks, and the
        # move would change the output, so the locator must report the break and publish no edit.
        text = """i = 0
while i < 3:
    if i == 1:
        break
    i += 1
else:
    print("else")
print("after", i)
"""
        source = self.tmp / 'while_break.py'
        source.write_text(text, encoding='utf-8')
        built = self.compile(source, 'while_break')
        self.assertEqual(built.returncode, 0, built.stderr)
        found = [item for item in json.loads(built.stdout).get('agent_diagnostics', [])
                 if item['code'] == 'AIL0109']
        self.assertEqual(len(found), 1, found)
        item = found[0]
        self.assertEqual((item['line'], item['col']), (2, 1), item)
        self.assertIn('has a `break`', item['cause'], item)
        self.assertNotIn('no `break`', item['cause'], item)
        self.assertNotIn('fix', item, item)
        self.assertNotIn('\nReplace:\n', item['message'])
        self.assertNotIn('move after the loop', item['message'])
        native = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=120)
        self.assertEqual(native.stdout.decode(), 'after 1\n')


if __name__ == '__main__':
    unittest.main()
