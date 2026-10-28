"""Pre405: int() of a literal bytearray text outside int64 is refused by name.

A reviewer of pre392 recorded that ``int(bytearray(b"9999999999999999999"))`` (directly and
through a wrapper) compiled on both builds and then stopped at run time with
``integer overflow``, while CPython prints the exact big integer.  The static int() checker
now treats a bytearray built from a bytes literal like the same bytes, so the out-of-int64
conversion is refused at compile time with ``int64 constant expression out of range``.
In-range text, invalid text, mutated bytearrays, and values that only reach int() at run time
keep CPython's behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHATGPT = str(ROOT / 'ail_chatgpt.py')

BIG = '9999999999999999999'


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
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    return exe, subprocess.run([sys.executable, '-B', CHATGPT, 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


def check_refused(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre405-') as directory:
        for general in (True, False):
            exe, built = build(directory, name + ('g' if general else 'd'), text, general)
            output = built.stdout + built.stderr
            test.assertNotEqual(built.returncode, 0, (name, general, output[-1200:]))
            test.assertFalse(exe.exists(), (name, general))
            test.assertIn('int64 constant expression out of range', output,
                          (name, general, output[-1200:]))
            test.assertNotIn('integer overflow', output, (name, general, output[-1200:]))


def check_program(test, name, text):
    with tempfile.TemporaryDirectory(prefix='ail-pre405-') as directory:
        want = cpython(directory, name, text)
        for general in (True, False):
            exe, built = build(directory, name, text, general)
            test.assertEqual(built.returncode, 0, (name, general, built.stdout + built.stderr))
            got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
            test.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want[0],
                             (name, general, got.stderr[-800:]))
            test.assertEqual(got.returncode, want[1], (name, general, got.stderr[-800:]))


REFUSED = {
    'direct': 'print(int(bytearray(b"%s")))\n' % BIG,
    'wrapped': '''def take(value):
    return int(value)


print(take(bytearray(b"%s")))
''' % BIG,
    'wrapped_keyword': '''def take(value):
    return int(value)


print(take(value=bytearray(b"%s")))
''' % BIG,
    'wrapped_readonly_helper': '''def ident(value):
    return value


def take(value):
    return int(ident(value))


print(take(bytearray(b"%s")))
''' % BIG,
    'negative': 'print(int(bytearray(b"-%s")))\n' % BIG,
    'whitespace_underscores': 'print(int(bytearray(b"  +9_999_999_999_999_999_999  ")))\n',
    'max_plus_one': 'print(int(bytearray(b"9223372036854775808")))\n',
    'min_minus_one': 'print(int(bytearray(b"-9223372036854775809")))\n',
    'list_item': 'print(int([bytearray(b"%s")][0]))\n' % BIG,
    'tuple_item': 'print(int((bytearray(b"%s"),)[0]))\n' % BIG,
    'dict_value': 'print(int({"k": bytearray(b"%s")}["k"]))\n' % BIG,
    'class_attribute': '''class Box:
    value = bytearray(b"%s")


print(int(Box.value))
''' % BIG,
    'instance_attribute': '''class Box:
    def __init__(self):
        self.value = bytearray(b"%s")


print(int(Box().value))
''' % BIG,
    'alias': '''b = bytearray(b"%s")
alias = b
print(int(alias))
''' % BIG,
    'module_constant': '''TEXT = bytearray(b"%s")


def main():
    print(int(TEXT))


main()
''' % BIG,
}

MATCH = {
    'in_range': '''def main():
    print(int(bytearray(b"42")), int(bytearray(b"  -7 ")), int(bytearray(b"1_0")))
    print(int(bytearray(b"9223372036854775807")), int(bytearray(b"-9223372036854775808")))


main()
''',
    'empty_and_invalid': '''def show(value):
    try:
        print(int(value))
    except ValueError as error:
        print(type(error).__name__, error)


def main():
    show(bytearray(b""))
    show(bytearray(b"12x"))
    show(bytearray(b"0x10"))


main()
''',
    'routes_in_range': '''class Box:
    value = bytearray(b"45")

    def __init__(self):
        self.other = bytearray(b" 8 ")


def take(value):
    return int(value)


def main():
    print(int([bytearray(b"1")][0]))
    print(int({"k": bytearray(b"2")}["k"]))
    print(int((bytearray(b"3"),)[0]))
    print(int(Box.value), int(Box().other))
    print(take(bytearray(b"46")), take(value=bytearray(b"47")))


main()
''',
    'named_and_alias': '''def main():
    b = bytearray(b"45")
    alias = b
    print(int(b), int(alias))


main()
''',
    'mutated_alias': '''def main():
    b = bytearray(b"9999999999999999999")
    alias = b
    alias[:] = b"1"
    print(int(b), int(alias))


main()
''',
    'mutated_class_attribute': '''class Box:
    value = bytearray(b"9999999999999999999")


def main():
    Box.value[:] = b"1"
    print(int(Box.value))


main()
''',
    'mutated_instance_attribute': '''class Box:
    def __init__(self):
        self.value = bytearray(b"9999999999999999999")


def main():
    box = Box()
    box.value[:] = b"1"
    print(int(box.value))


main()
''',
    'bytes_and_str_controls': '''def main():
    print(int(b"42"), int("43"), int(b"9223372036854775807"))


main()
''',
    'mutated_wrapper_subscript': '''def take(value):
    value[:] = b"1"
    return int(value)


print(take(bytearray(b"9999999999999999999")))
''',
    'mutated_wrapper_method': '''def take(value):
    value.clear()
    value.extend(b"2")
    return int(value)


print(take(bytearray(b"9999999999999999999")))
''',
    'mutated_wrapper_helper': '''def reset(value):
    value[:] = b"3"


def take(value):
    reset(value)
    return int(value)


print(take(bytearray(b"9999999999999999999")))
''',
    'mutated_wrapper_nested_helper': '''def reset(value):
    value[:] = b"8"


def middle(value):
    reset(value)


def take(value):
    middle(value)
    return int(value)


print(take(bytearray(b"9999999999999999999")))
''',
    'mutated_wrapper_alias': '''def take(value):
    alias = value
    alias[:] = b"5"
    return int(value)


print(take(bytearray(b"9999999999999999999")))
''',
    'mutated_wrapper_negative_and_boundary': '''def take(value):
    value[:] = b"-7"
    return int(value)


def edge(value):
    value[:] = b"9223372036854775807"
    return int(value)


print(take(bytearray(b"9999999999999999999")))
print(edge(bytearray(b"9999999999999999999")))
''',
    'mutated_wrapper_empty_and_invalid': '''def take(value):
    value.clear()
    try:
        print(int(value))
    except ValueError as error:
        print(type(error).__name__, error)


take(bytearray(b"9999999999999999999"))
''',
    'mutated_wrapper_container_items': '''def take_dict(value):
    value["k"][:] = b"7"
    return int(value["k"])


def take_list(value):
    value[0][:] = b"4"
    return int(value[0])


print(take_dict({"k": bytearray(b"9999999999999999999")}))
print(take_list([bytearray(b"9999999999999999999")]))
''',
}


class Pre405Tests(unittest.TestCase):
    def test_out_of_int64_bytearray_text_is_refused(self):
        for name, text in REFUSED.items():
            with self.subTest(case=name):
                check_refused(self, name, text)

    def test_in_range_invalid_and_mutated_routes_match_cpython(self):
        for name, text in MATCH.items():
            with self.subTest(case=name):
                check_program(self, name, text)


if __name__ == '__main__':
    unittest.main()
