"""fz196: `re` sub with a callable whose kind is not a bare module-level def.

The real-program check found the corpus program `deepseek t196` (`re.sub` masking
emails and phones with callbacks annotated `re.Match[str]`).  The old tree sent a
callable replacement into the string-template helper, so it reflected the function
itself ("argument of type 'function' is not iterable") and exited 1 where CPython
prints the masked lines.  The t196 program itself now matches on both builds; the
same path is still wrong for an alias, a list item, a dict value, an argument or a
function result, and a negative `count`/`maxsplit` used to replace instead of
leaving the subject alone.  Unknown-kind replacements now dispatch between a
template and a callable at run time, an instance attribute is refused by name (the
instance would have to be bound first), a dynamic `subn` is refused by name, and
the count helpers follow CPython's negative-count rule.  Values through an
argument, a list item, a dict value, a class attribute, a local function and a
re-bound string match CPython on both builds.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODES = (
    ('default', {}),
    ('general', {'AIL_UNIFIED_FORCE': '1'}),
)

EXACT = r'''import re
import sys

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\d{3}-\d{3}-(\d{4})")


def mask_email(match: re.Match[str]) -> str:
    domain = match.group(0).rsplit("@", 1)[1]
    return "***@" + domain


def mask_phone(match: re.Match[str]) -> str:
    return "XXX-XXX-" + match.group(1)


def main() -> None:
    for line in sys.stdin:
        line = line.rstrip("\n")
        line = EMAIL_RE.sub(mask_email, line)
        line = PHONE_RE.sub(mask_phone, line)
        print(line)


if __name__ == "__main__":
    main()
'''

EXACT_INPUT = (b"732-118-3715 carol.erin@oscar.example.com kilo november whiskey november\n"
               b"grace.dave@papa.example.org tango tango banana 411-586-4308 foxtrot\n"
               b"mike frank.niaj@kilo.example.com quebec hotel foxtrot 424-513-4864 xray lima\n"
               b"a@example.com b@example.org 123-456-7890 999-888-7777\n"
               b"empty\n")

ROUTES = r'''import re

P = re.compile(r"(\d+)-([a-z]+)")


def bump(m: re.Match[str]) -> str:
    return "[" + m.group(1) + ":" + m.group(2) + "]"


alias = bump
lst = [bump]
d = {"f": bump}


class Box:
    f = bump


def call(fn) -> str:
    return P.sub(fn, "10-ab 20-cd")


def local():
    return bump


def main() -> None:
    print(P.sub(bump, "10-ab 20-cd"))
    print(P.sub(alias, "10-ab 20-cd"))
    print(P.sub(lst[0], "10-ab 20-cd"))
    print(P.sub(d["f"], "10-ab 20-cd"))
    print(call(bump))
    print(P.sub(local(), "10-ab 20-cd"))
    print(P.sub(Box.f, "10-ab 20-cd"))


main()
'''

COUNTS = r'''import re

PAT = re.compile(r"a")


def up(m: re.Match[str]) -> str:
    return "[" + m.group(0) + "]"


def main() -> None:
    for c in (-5, -2, -1, 0, 1, 2, 3):
        print(c, repr(re.sub("a", "X", "aaaa", count=c)), re.subn("a", "X", "aaaa", count=c))
        print(c, repr(PAT.sub(up, "aaaa", c)), PAT.subn(up, "aaaa", c))
        print(c, repr(PAT.sub("X", "aaaa", c)), PAT.subn("X", "aaaa", c))
    for m in (-2, -1, 0, 1, 2):
        print("split", m, re.split("a", "aaaa", maxsplit=m), PAT.split("aaaa", m))


main()
'''

NONE_AND_GROUPS = r'''import re

N = re.compile(r"(?P<user>[a-z]+)@(?P<host>[a-z.]+)")


def rep(m: re.Match[str]) -> str:
    return None


def odd(m: re.Match[str]) -> str:
    if m.group(0) in "ace":
        return None
    return "[" + m.group(0) + "]"


def mask(m: re.Match[str]) -> str:
    return m.group("user") + " at " + m.group(2)


def main() -> None:
    print(repr(re.sub(r"\w", rep, "abc")))
    print(re.sub(r"\w", odd, "abcdef"))
    print(re.subn(r"\w", odd, "abcdef", 2))
    print(N.sub(mask, "a@example.com b@example.org"))
    print(N.sub(mask, "a@example.com b@example.org", 1))


main()
'''

BYTES_AND_STRINGS = r'''import re

B = re.compile(rb"a")
P = re.compile(r"a")


def make():
    return b"Z"


def make_s():
    return "Z"


def main() -> None:
    repl = "X"
    print(P.sub(repl, "aaaa"))
    repl = "Y"
    print(P.sub(repl, "aaaa"))
    print(P.sub(make_s(), "aaaa"))
    print(B.sub([b"X"][0], b"aaaa"))
    print(B.sub({"r": b"Y"}["r"], b"aaaa"))
    print(B.sub(make(), b"aaaa"))
    brepl = b"Q"
    print(B.sub(brepl, b"aaaa"))


main()
'''

INSTANCE_ATTRIBUTE = r'''import re

P = re.compile(r"(\d+)-([a-z]+)")


def bump(m: re.Match[str]) -> str:
    return "[" + m.group(1) + ":" + m.group(2) + "]"


class Box:
    f = bump


b = Box()
print(P.sub(b.f, "10-ab"))
'''

SUBN_ALIAS = r'''import re

P = re.compile(r"a")


def up(m: re.Match[str]) -> str:
    return m.group(0).upper()


alias = up
print(P.subn(alias, "aaaa"))
'''


def _cpython(directory, name, text, stdin):
    src = Path(directory) / (name + '_cpython.py')
    src.write_text(text, encoding='utf-8')
    done = subprocess.run([sys.executable, '-B', str(src)], input=stdin, capture_output=True,
                          timeout=120, env=dict(os.environ, PYTHONUTF8='1'))
    return done.stdout.replace(b'\r\n', b'\n'), done.returncode


def _build(directory, name, text, extra):
    src = Path(directory) / (name + '.ail')
    src.write_text(text, encoding='utf-8')
    exe = Path(directory) / ('exe_' + name)
    exe.unlink(missing_ok=True)
    env = dict(os.environ, AIL_NO_CACHE='1', AIL_QUIET_FALLBACK='1')
    for key in ('AIL_NO_GENERAL', 'AIL_UNIFIED_FORCE', 'AIL_IR'):
        env.pop(key, None)
    env.update(extra)
    return exe, subprocess.run([sys.executable, '-B', str(ROOT / 'ail_chatgpt.py'), 'compile', src.name,
                                '--syntax', 'python', '-o', exe.name], cwd=directory,
                               capture_output=True, text=True, timeout=900, env=env)


class Fz196Tests(unittest.TestCase):
    def same_as_cpython(self, name, text, stdin=b''):
        with tempfile.TemporaryDirectory(prefix='ail-fz196-') as directory:
            want, want_rc = _cpython(directory, name, text, stdin)
            for mode, extra in MODES:
                exe, built = _build(directory, name, text, extra)
                self.assertEqual(built.returncode, 0, (name, mode, built.stdout + built.stderr))
                got = subprocess.run([str(exe)], input=stdin, capture_output=True, timeout=120, cwd=directory)
                self.assertEqual(got.stdout.replace(b'\r\n', b'\n'), want, (name, mode, got.stderr[-800:]))
                self.assertEqual(got.returncode, want_rc, (name, mode, got.stderr[-800:]))

    def refused_by_name(self, name, text, needle):
        with tempfile.TemporaryDirectory(prefix='ail-fz196-') as directory:
            for mode, extra in MODES:
                exe, built = _build(directory, name, text, extra)
                self.assertNotEqual(built.returncode, 0, (name, mode, built.stdout + built.stderr))
                self.assertIn(needle, built.stdout + built.stderr, (name, mode))

    def test_t196_email_and_phone_masking(self):
        self.same_as_cpython('exact', EXACT, EXACT_INPUT)

    def test_callable_replacement_routes(self):
        self.same_as_cpython('routes', ROUTES)

    def test_negative_count_and_split(self):
        self.same_as_cpython('counts', COUNTS)

    def test_none_result_and_named_groups(self):
        self.same_as_cpython('none_groups', NONE_AND_GROUPS)

    def test_run_time_template_and_bytes(self):
        self.same_as_cpython('bytes_strings', BYTES_AND_STRINGS)

    def test_instance_attribute_replacement_is_refused(self):
        self.refused_by_name('instance_attr', INSTANCE_ATTRIBUTE, 'replacement read through an attribute')

    def test_dynamic_subn_is_refused(self):
        self.refused_by_name('subn_alias', SUBN_ALIAS, 'subn with a replacement whose kind is not known')


if __name__ == '__main__':
    unittest.main()
