"""pre315: a statically known out-of-int64 int() through a variable, item or attribute.

The reviewer of rbrbpre9 recorded that an out-of-range ``int()`` still stopped at run time with
``integer overflow`` when the text or float reached it through a module/function variable, a
list/dict item, an instance attribute or a class attribute, where CPython prints the big
integer.  The static int() pass now follows those routes (and a wrapper argument) and refuses
the call by name with the existing wording.  A container changed before the call (including
through an alias), an attribute overwritten on the instance or by a method, unreachable
conversions, in-range values and dynamic values keep their previous behaviour.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

REFUSED = {
    'module_variable': '''TEXT = "9223372036854775808"
print(int(TEXT))
''',
    'list_item': '''TEXT = ["9223372036854775808"]
print(int(TEXT[0]))
''',
    'dict_value': '''TABLE = {"text": "9223372036854775808"}
print(int(TABLE["text"]))
''',
    'instance_attribute': '''class Box:
    pass


box = Box()
box.text = "9223372036854775808"
print(int(box.text))
''',
    'init_attribute': '''class Box:
    def __init__(self, text):
        self.text = text


box = Box("9223372036854775808")
print(int(box.text))
''',
    'class_attribute': '''class Box:
    text = "9223372036854775808"


print(int(Box.text))
''',
    'local_variable': '''def main():
    text = "9223372036854775808"
    print(int(text))


main()
''',
    'local_list': '''def main():
    texts = ["9223372036854775808"]
    print(int(texts[0]))


main()
''',
    'argument': '''def show(value):
    print(int(value))


show("9223372036854775808")
''',
    'list_float': '''VALUES = [1e30]
print(int(VALUES[0]))
''',
    'dict_float': '''VALUES = {"value": 1e30}
print(int(VALUES["value"]))
''',
    'instance_attribute_float': '''class Box:
    pass


box = Box()
box.value = 1e30
print(int(box.value))
''',
    'class_attribute_float': '''class Box:
    value = 1e30


print(int(Box.value))
''',
    'attribute_base': '''class Box:
    text = "ffffffffffffffff"


print(int(Box.text, 16))
''',
}

MATCHES = r'''class Box:
    text = "45"

    def __init__(self, text):
        self.text = text


box = Box("46")
text = "42"
texts = [43]
table = {"text": "44"}


def local():
    text = "47"
    return int(text)


def show(value):
    return int(value)


def changed_list():
    values = ["9223372036854775808"]
    values[0] = "48"
    return int(values[0])


def changed_dict():
    values = {"text": "9223372036854775808"}
    values["text"] = "49"
    return int(values["text"])


def aliased_list():
    values = ["9223372036854775808"]
    alias = values
    alias[0] = "50"
    return int(values[0])


print(int(text), int(texts[0]), int(table["text"]), int(Box.text), int(box.text))
print(local(), show("51"), changed_list(), changed_dict(), aliased_list())


class Other:
    pass


other = Other()
other.text = "9223372036854775808"
other.text = "52"
print(int(other.text))


class AliasBox:
    pass


alias_box = AliasBox()
alias_box.text = "9223372036854775808"
same_box = alias_box
same_box.text = "53"
print(int(alias_box.text))


class ResetBox:
    def __init__(self):
        self.text = "9223372036854775808"

    def reset(self):
        self.text = "54"


reset_box = ResetBox()
reset_box.reset()
print(int(reset_box.text))

nested = [["9223372036854775808"]]
nested_inner = nested[0]
nested_inner[0] = "55"
print(int(nested[0][0]))


def unreachable_show(value):
    if True:
        return 56
    return int(value)


print(unreachable_show("9223372036854775808"))


class DirectResetBox:
    def touch(self):
        self.value = "57"


direct_reset = DirectResetBox()
direct_reset.value = "9223372036854775808"
direct_reset.touch()
print(int(direct_reset.value))


class ExternalResetBox:
    def __init__(self):
        self.label = "9223372036854775808"


def reset_label(target):
    target.label = "58"


external_reset = ExternalResetBox()
reset_label(external_reset)
print(int(external_reset.label))
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode, done.stderr


def _build(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    return built, exe


def _run(directory, name, text, general):
    built, exe = _build(directory, name, text, general)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre315Tests(unittest.TestCase):
    def refused(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre315-') as directory:
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                built, exe = _build(directory, name, text, general)
                output = built.stdout + built.stderr
                self.assertEqual(built.returncode, 2, '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertFalse(exe.exists(), '%s (general=%s) built an executable' % (slug, general))
                self.assertTrue('int64 constant expression out of range' in output
                                or 'int() of a float outside int64' in output,
                                '%s (general=%s)\n%s' % (slug, general, output[-3000:]))
                self.assertNotIn('integer overflow', output,
                                 '%s (general=%s)\n%s' % (slug, general, output[-3000:]))

    def matches(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre315-') as directory:
            want, want_rc, err = _cpython(directory, slug, text)
            self.assertEqual(want_rc, 0, err)
            for general in (True, False):
                name = '%s_%s' % (slug, 'g' if general else 'd')
                got, build_err = _run(directory, name, text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s'
                                     % (slug, general, build_err))
                self.assertEqual(got, (want, want_rc),
                                 '%s (general=%s)\n%s' % (slug, general, build_err))

    def test_out_of_int64_int_through_routes_is_refused(self):
        for slug, text in REFUSED.items():
            with self.subTest(case=slug):
                self.refused(slug, text)

    def test_in_range_mutated_and_dynamic_routes_match_cpython(self):
        self.matches('matches', MATCHES)


if __name__ == '__main__':
    unittest.main()
