"""Three silent differences found by differential fuzzing (lab/fuzz), each compared with CPython.

1. `s[i]` out of range on a str raises a catchable IndexError (it stopped the program).
2. `xs == ys` / `xs != ys` on two `list[int]` compares element by element (it was a C compile error).
3. A def-syntax file that binds a second name to a list/dict/set/bytearray and writes through one name
   while reading the other is refused by name where only the copying emitter could take it (CPython
   shares the object); block-syntax files keep their value semantics.
4. (round 2) alias shapes the fuzzer built (try/else, augmented ops, list == beside a lambda sort key)
   are CPython-identical or refused by name, never a silent difference or a C error; `.lower()` /
   `.upper()` on a non-ASCII str literal is folded at compile time instead of trapping at run time.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STR_INDEX = '''
def main() -> None:
    s: str = "a\\u00f1c"
    for i in [3, -4, 1, -1, 0, 100]:
        try:
            c: str = s[i]
            print(c)
        except IndexError:
            print("caught", i)
    t: str = "abc"
    try:
        print(t[3])
    except IndexError:
        print("caught")
    b: bytes = b"ab"
    try:
        print(b[5])
    except IndexError:
        print("caught bytes")
    print(t[7])


main()
'''

LIST_EQ = '''
def main() -> None:
    a: list[int] = [1, 2]
    b: list[int] = [1, 2]
    c: list[int] = [1]
    e: list[int] = []
    f: list[int] = [1, 3]
    print(a == b, a != b, a == c, a != c, e == [], c == [1], a == f, a != f)
    print(a == [1, 2], [2, 1] == a, e != c)
    if a == b:
        print("same")
    if a != f:
        print("different")
    a.append(5)
    print(a == b, a == [1, 2, 5])


main()
'''

LIST_OTHER = '''
def main() -> None:
    a: list[float] = [0.0, 1.5]
    b: list[float] = [-0.0, 1.5]
    print(a == b, a != b)
    s: list[str] = ["a", "b"]
    t: list[str] = ["a", "b"]
    print(s == t)
    n: list[int] = [1, 2]
    m: list[int] = [1, 3]
    print(n < m, n >= m)


main()
'''

ALIAS = {
    'list': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs\n'
             '    ys.append(3)\n    print(len(xs), len(ys))\n\n\nmain()\n'),
    'list_store': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs\n'
                   '    ys[0] = 9\n    print(xs[0], ys[0])\n\n\nmain()\n'),
    'list_aug': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs\n'
                 '    xs += [3]\n    print(len(xs), len(ys))\n\n\nmain()\n'),
    'list_loop': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs\n'
                  '    for i in range(3):\n        print(len(ys))\n        xs.append(i)\n\n\nmain()\n'),
    'dict': ('def main() -> None:\n    d: dict[int, int] = {1: 2}\n    e: dict[int, int] = d\n'
             '    e[5] = 6\n    print(len(d), len(e))\n\n\nmain()\n'),
    'set': ('def main() -> None:\n    s: set[int] = {1, 2}\n    t: set[int] = s\n'
            '    t.add(7)\n    print(len(s), len(t))\n\n\nmain()\n'),
    'bytearray': ('def main() -> None:\n    b: bytearray = bytearray(b"ab")\n    c: bytearray = b\n'
                  '    c.append(99)\n    print(len(b), len(c))\n\n\nmain()\n'),
}

# aliasing that does not differ, or a copy made on purpose: compiles on the copying emitter
ALIAS_FINE = {
    'copy': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs.copy()\n'
             '    ys.append(3)\n    print(len(xs), len(ys))\n\n\nmain()\n'),
    'list_call': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = list(xs)\n'
                  '    ys.append(3)\n    print(len(xs), len(ys))\n\n\nmain()\n'),
    'only_alias_read': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs\n'
                        '    print(len(xs), len(ys))\n\n\nmain()\n'),
    'only_dst_used': ('def main() -> None:\n    xs: list[int] = [1, 2]\n    ys: list[int] = xs\n'
                      '    ys.append(3)\n    print(len(ys))\n\n\nmain()\n'),
    'sorted_copy': ('def main() -> None:\n    xs: list[int] = [3, 1]\n    ys: list[int] = sorted(xs)\n'
                    '    ys.append(0)\n    print(len(xs), len(ys))\n\n\nmain()\n'),
}

# the alias sends these to the general (boxed) path; its `+=`/`|=` change the object in place and its
# str format specs pad by code points
GENERAL = '''
def main() -> None:
    xs: list[int] = [1, 2]
    ys: list[int] = xs
    xs += [3]
    xs += xs
    print(len(xs), len(ys))
    s: set[int] = {1}
    t: set[int] = s
    s |= {2, 3}
    print(len(s), len(t))
    n: int = 5
    n += 2
    z: str = "a"
    z += "b"
    print(n, z)
    u: str = "日本"
    print(f"{u:<6}|{u:^7}|{u:>5}|{u:*^8.1}|{u:.1}|")
    print(f"{'日本':<6}{5:3d}")


main()
'''

# a `return` whose C expression has a multi-line set-up (seed 2074200013): the cleanup rewrite of
# `return e;` cut it in the middle and gcc saw an unterminated function
RETURN_SETUP = '''
def h0(text: str) -> int:
    return text.find("-".join(text.split(",")))


def h1(text: str, other: str) -> int:
    return len(other.join(text.split(","))) + text.find(",".join(other.split("x")))


print(h0("a,b"), h0("a-b,b"), h1("a,b", "zxz"))
'''

# round 2: shapes from the fuzz run (try/else alias with `+=`; list == beside a lambda sort key)
ROUND2 = {
    'try_else_alias': '''
def main() -> int:
    v1: list[int] = [5, 3, 1]
    try:
        print(len(v1))
    except KeyError:
        v6: int = 2
    else:
        al7: list[int] = v1
        al7 += [7]
        print(len(v1), len(al7), sum(v1) - sum(al7))
    finally:
        print(238)
    return 0


main()
''',
    'alias_eq_sortkey': '''
def main() -> int:
    v7: list[int] = [1, 2, 3]
    v9: list[int] = [3, 1, 2]
    v9.sort(key=lambda q: (-q, q))
    al21: list[int] = v7
    al21.append(8)
    print(len(v7), len(al21), sum(v7) - sum(al21))
    print(v7 == al21)
    print(v9)
    return 0


main()
''',
    'aug_ops_alias': '''
def main() -> int:
    xs: list[int] = [1, 2, 3]
    ys: list[int] = xs
    ys *= 2
    s: set[int] = {1, 2, 3}
    t: set[int] = s
    t -= {1}
    t &= {2, 5}
    t ^= {9}
    print(len(xs), len(ys), sorted(s), sorted(t))
    return 0


main()
''',
}

NONASCII_CASE = '''
def h(a: int) -> str:
    v2: str = "-".join("caf\\u00e9 \\u00d1".lower().split(","))
    return v2 + "stra\\u00dfe".upper()


print(h(1))
print("\\u00c9t\\u00e9".upper(), "\\u00c9t\\u00e9".lower())
'''

BRACE_ALIAS = '''fn main() {
    let xs = [1, 2];
    let ys = xs;
    ys.append(3);
    print(len(xs), len(ys));
}
'''


def compile_source(directory, text, name, syntax='python', env=None):
    source, exe = Path(directory, name + '.ail'), Path(directory, name)
    source.write_text(text, encoding='utf-8')
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', source.name,
                            '--syntax', syntax, '-o', exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=600, env=dict(os.environ, **(env or {})))
    return built, source, exe


def run_both(directory, text, name, env=None):
    """(compile result, AIL run, CPython run) of one def-syntax program."""
    built, source, exe = compile_source(directory, text, name, env=env)
    expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
    if built.returncode != 0:
        return built, None, expected
    return built, subprocess.run([str(exe)], capture_output=True, timeout=60), expected


class FuzzFindings(unittest.TestCase):
    def same_as_cpython(self, text, name, env=None):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = run_both(directory, text, name, env)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)
            if expected.returncode:
                self.assertIn(b'IndexError: ', expected.stderr)
                self.assertIn(b'string index out of range', ran.stderr)

    def test_str_index_error_is_catchable(self):
        self.same_as_cpython(STR_INDEX, 'stridx')

    def test_str_index_error_is_catchable_ir(self):
        self.same_as_cpython(STR_INDEX, 'stridx_ir', {'AIL_IR': '1'})

    def test_list_int_equality(self):
        self.same_as_cpython(LIST_EQ, 'listeq')
        self.same_as_cpython(LIST_EQ, 'listeq_ir', {'AIL_IR': '1'})

    def test_other_list_comparisons_never_reach_the_c_compiler(self):
        # element kinds the whole-list compare is not built for are answered by another path or
        # refused by name -- never a C compile error (exit 4)
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = run_both(directory, LIST_OTHER, 'listother', {'AIL_NO_GENERAL': '1'})
            self.assertIn(built.returncode, (0, 3), built.stdout + built.stderr)
            if built.returncode == 0:
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout))
        self.same_as_cpython(LIST_OTHER, 'listother_general')

    def test_alias_is_refused_by_name_where_only_value_semantics_exist(self):
        for name, text in ALIAS.items():
            with self.subTest(name):
                with tempfile.TemporaryDirectory() as directory:
                    built, _, _ = run_both(directory, text, name, {'AIL_NO_GENERAL': '1'})
                    self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                    message = built.stdout + built.stderr
                    self.assertIn('makes a second name for the same container', message)
                    self.assertIn('.copy()', message)

    def test_alias_is_cpython_where_a_sharing_path_takes_it(self):
        for name, text in ALIAS.items():
            if name == 'bytearray':
                continue                 # the general path cannot build it: the refusal above stands
            with self.subTest(name):
                self.same_as_cpython(text, name + '_general')
                self.same_as_cpython(text, name + '_general_ir', {'AIL_IR': '1'})

    def test_copies_and_harmless_aliases_still_compile_fast(self):
        for name, text in ALIAS_FINE.items():
            with self.subTest(name):
                self.same_as_cpython(text, name, {'AIL_NO_GENERAL': '1'})

    def test_general_path_in_place_operators_and_unicode_format_specs(self):
        self.same_as_cpython(GENERAL, 'general')
        self.same_as_cpython(GENERAL, 'general_ir', {'AIL_IR': '1'})

    def test_return_with_a_multi_line_setup_is_one_statement(self):
        self.same_as_cpython(RETURN_SETUP, 'retsetup')
        self.same_as_cpython(RETURN_SETUP, 'retsetup_ir', {'AIL_IR': '1'})

    def same_or_named_refusal(self, text, name, env=None):
        with tempfile.TemporaryDirectory() as directory:
            built, ran, expected = run_both(directory, text, name, env)
            self.assertIn(built.returncode, (0, 3), built.stdout + built.stderr)
            if built.returncode == 3:
                self.assertIn('not in the subset', built.stdout + built.stderr)
            else:
                self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout), ran.stderr)

    def test_round2_alias_shapes_never_differ_silently(self):
        for name, text in ROUND2.items():
            with self.subTest(name):
                self.same_or_named_refusal(text, name)
                self.same_or_named_refusal(text, name + '_ir', {'AIL_IR': '1'})

    def test_case_mapping_of_non_ascii_literals_is_folded(self):
        self.same_as_cpython(NONASCII_CASE, 'nonascii_case')
        self.same_as_cpython(NONASCII_CASE, 'nonascii_case_ir', {'AIL_IR': '1'})

    def test_check_names_the_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory, 'alias.ail')
            source.write_text(ALIAS['list'], encoding='utf-8')
            checked = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'check', source.name,
                                      '--syntax', 'python'], cwd=directory, capture_output=True, text=True,
                                     timeout=120)
            self.assertIn('makes a second name for the same container', checked.stdout)
            self.assertIn('line 3', checked.stdout)

    def test_block_syntax_keeps_value_semantics(self):
        with tempfile.TemporaryDirectory() as directory:
            built, source, exe = compile_source(directory, BRACE_ALIAS, 'brace', syntax='ail',
                                                env={'AIL_NO_GENERAL': '1'})
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
            self.assertEqual(ran.stdout, b'2 3\n')


if __name__ == '__main__':
    unittest.main()
