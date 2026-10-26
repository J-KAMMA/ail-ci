"""Pre-206: a repeated grouping character in a format spec matches CPython's errors.

The review of job memsafe2 recorded a pre-existing difference: `format(1, '__d')` and
`format(1, ',,d')` said `Cannot specify both ',' and '_'.` where CPython raises
`ValueError: Invalid format specifier '__d' for object of type 'int'`.  CPython reads one
grouping character, then treats the second copy as the spec's type when it is the last
character (`format(1, ',,' )` -> `Cannot specify ',' with ','.`) and rejects the whole spec
when anything follows it.  Two different grouping characters keep the `both` message.
Other malformed specs now name the spec and the value's type, including non-ASCII,
long and NUL-bearing specs; a grouping character combined with a non-ASCII type gives
`Cannot specify '<group>' with '\\x..'`, as CPython does.

The cases below are direct calls and values reaching `format` through an argument, a list
item, an attribute, a dict value and an alias, over int, negative int, zero, bool, float,
negative zero and str values, with signs, zero padding and widths, on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")

PROGRAM = r'''class Box:
    def __init__(self, spec, value):
        self.spec = spec
        self.value = value


def show(label, fn):
    try:
        print(label, repr(fn()))
    except Exception as e:
        print(label, type(e).__name__, str(e))


def via(value, spec):
    return format(value, spec)


def via_sf(value, spec):
    return "{:{}}".format(value, spec)


def main():
    specs = ["__d", ",,d", "__", ",,", ",_d", "_,d", "___", ",,,", ",,,",
             "0__d", ">__d", "+__d", "__10d", ".__d", "__s", ",,s", "__n", ",,_"]
    values = [0, 1, -1234, 42, True, False, 1.5, -0.0, "x", ""]
    for spec in specs:
        for value in values:
            show("direct:" + repr(spec) + ":" + type(value).__name__,
                 lambda spec=spec, value=value: format(value, spec))

    box = Box("__d", 7)
    xs = [",,d", 9]
    d = {"spec": "__", "value": 3}
    alias = "__d"
    for spec in ["__d", ",,d", "__", ",,", ",_d", "_,d"]:
        show("arg:" + repr(spec), lambda spec=spec: via(7, spec))
        show("argsf:" + repr(spec), lambda spec=spec: via_sf(7, spec))
        show("list:" + repr(spec), lambda spec=spec: format(xs[1], spec))
        show("attr-spec:" + repr(spec), lambda spec=spec: format(7, box.spec))
        show("attr-value:" + repr(spec), lambda spec=spec: format(box.value, spec))
        show("dict-spec:" + repr(spec), lambda spec=spec: format(3, d["spec"]))
        show("dict-value:" + repr(spec), lambda spec=spec: format(d["value"], spec))
        show("alias:" + repr(spec), lambda spec=spec: format(7, alias))

    show("lit-comma", lambda: format(1, ",,d"))
    show("lit-under", lambda: format(1, "__d"))
    show("lit-comma-end", lambda: format(1, ",,"))
    show("lit-under-end", lambda: format(1, "__"))
    show("lit-both1", lambda: format(1, ",_d"))
    show("lit-both2", lambda: format(1, "_,d"))
    show("lit-fstr", lambda: f"{1:__d}")
    show("lit-strfmt", lambda: "{:,,d}".format(1))

    for spec in [",d", "_d", ",x", "_b", "_o", "_x", "_X", ",f", "_f",
                 ",e", "_e", ",g", "_g", ",%", "_%"]:
        show("valid:" + repr(spec) + ":int", lambda spec=spec: format(1234567, spec))
        show("valid:" + repr(spec) + ":float", lambda spec=spec: format(1234.5, spec))

    for spec in ["__é", ",é", ",中", ",q", ", ", "_q", "_i", ",\x01", ",\x7f",
                 ",\x80", ",\x00"]:
        for value in [0, -7, True, 1.5, "x"]:
            show("group-code:" + repr(spec) + ":" + type(value).__name__,
                 lambda spec=spec, value=value: format(value, spec))
        show("group-code-arg:" + repr(spec), lambda spec=spec: via(7, spec))
        show("group-code-attr:" + repr(spec), lambda spec=spec: format(box.value, spec))
        show("group-code-dict:" + repr(spec), lambda spec=spec: format(d["value"], spec))

    for spec in ["d" * 120, "d" * 300, "d\x00", "d中", ",d中", "é" * 100]:
        for value in [0, -7, True, 1.5, "x"]:
            show("whole:" + repr(spec) + ":" + type(value).__name__,
                 lambda spec=spec, value=value: format(value, spec))

    show("generic-trail", lambda: format(1, "d "))
    show("generic-long", lambda: format(1, "10q"))
    print("done")


main()
'''


def _cpython(directory, name, text):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], capture_output=True, timeout=120,
                          env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build_and_run(directory, name, text, general):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name + ('_g' if general else '_d'))
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    env.pop('AIL_NO_GENERAL', None)
    if general:
        env['AIL_UNIFIED_FORCE'] = '1'
    else:
        env.pop('AIL_UNIFIED_FORCE', None)
    built = subprocess.run([sys.executable, '-B', CLI, 'compile', src.name,
                            '--syntax', 'python', '-o', exe.name], cwd=directory,
                           capture_output=True, text=True, timeout=900, env=env)
    if built.returncode != 0:
        return None, (built.stdout + built.stderr)[-3000:]
    got = subprocess.run([str(exe)], capture_output=True, timeout=120, cwd=directory)
    return (got.stdout.replace(b'\r\n', b'\n'), got.returncode), got.stderr.decode('utf-8', 'replace')[-1500:]


class Pre206Tests(unittest.TestCase):
    def check(self, slug, text):
        with tempfile.TemporaryDirectory(prefix='ail-pre206-') as directory:
            want = _cpython(directory, slug, text)
            for general in (True, False):
                got, err = _build_and_run(directory, '%s_%s' % (slug, 'g' if general else 'd'),
                                          text, general)
                self.assertIsNotNone(got, '%s (general=%s)\n%s' % (slug, general, err))
                self.assertEqual(got, want, '%s (general=%s)\n%s' % (slug, general, err))

    def test_repeated_grouping(self):
        self.check('repeated_grouping', PROGRAM)


if __name__ == '__main__':
    unittest.main()
