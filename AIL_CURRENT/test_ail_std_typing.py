"""The typing programs of lab/stdlib/typing: each passing program is compiled in the default mode and must
print what CPython prints (stdout and exit code).

The three follow-ups stay refused by name until their features are built: Protocol classes, the get_origin /
get_args introspection of typing objects, and get_type_hints.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAB = ROOT.parent / "lab" / "stdlib" / "typing"

PASSING = (
    "01_annotations.py",
    "02_typevars.py",
    "03_generic_class.py",
    "04_namedtuple.py",
    "05_typeddict.py",
    "06_typeddict_functional.py",
    "07_newtype.py",
    "08_cast.py",
    "09_literal_final.py",
    "13_errors.py",
)

REFUSED = {
    "10_protocol.py": "Protocol",
    "11_introspection.py": "get_origin",
    "12_get_type_hints.py": "get_type_hints",
}

BOUNDARIES = '''from typing import NewType, TypedDict, cast


class Empty(TypedDict):
    pass


class Partial(TypedDict, total=False):
    title: str
    year: int


Movie = TypedDict("Movie", {"title": str})
UserId = NewType("UserId", int)
Name = NewType("Name", str)
AdminId = NewType("AdminId", UserId)


class Token:
    def __init__(self, raw: str) -> None:
        self.raw = raw

    def show(self) -> str:
        return self.raw


TokenId = NewType("TokenId", Token)


def add(uid: UserId, n: int) -> UserId:
    return UserId(uid + n)


def main() -> None:
    e: Empty = {}
    print(e, len(e))
    p: Partial = {"title": "A"}
    print(p)
    p["year"] = 2000
    print(sorted(p.items()))
    m: Movie = {"title": "B"}
    print(m)
    u = UserId(5)
    print(add(u, 3), UserId(1) + UserId(2))
    n = Name("ada")
    print(n.upper(), len(Name("bob")), n.strip())
    t = Token("abc")
    marked = TokenId(t)
    print(marked is t, marked.show())
    alias = UserId
    print(alias(11))
    print(AdminId(7), type(AdminId(True)).__name__)
    try:
        UserId()
    except TypeError:
        print("missing")
    try:
        UserId(obj=5)
    except TypeError:
        print("keyword")
    val = cast(str, "7")
    print(val + "!")
    print(cast(int, 3) * 2)


main()
'''


def build_source(directory, name, text):
    Path(directory, name).write_text(text, encoding="utf-8")
    exe = name[:-3]
    env = dict(os.environ, AIL_NO_CACHE="1", AIL_SERVER="0")
    env.pop("AIL_NO_GENERAL", None)
    env.pop("AIL_UNIFIED_FORCE", None)
    built = subprocess.run(
        [sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", name, "--syntax", "python", "-o", exe],
        cwd=directory, capture_output=True, text=True, timeout=900, env=env,
    )
    return built, Path(directory, exe)


def compare_with_cpython(self, directory, name, text):
    built, exe = build_source(directory, name, text)
    self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
    ran = subprocess.run([str(exe)], capture_output=True, timeout=300)
    expected = subprocess.run([sys.executable, str(Path(directory, name))], capture_output=True, timeout=300)
    self.assertEqual(expected.returncode, 0, expected.stderr)
    self.assertEqual((ran.returncode, ran.stdout), (expected.returncode, expected.stdout),
                     ran.stderr[:500])


class TypingLabTests(unittest.TestCase):
    def test_passing_programs_match_cpython(self):
        for name in PASSING:
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                compare_with_cpython(self, directory, name, (LAB / name).read_text(encoding="utf-8"))

    def test_typeddict_newtype_cast_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            compare_with_cpython(self, directory, "boundaries.py", BOUNDARIES)

    def test_followups_are_refused_by_name(self):
        for name, wanted in REFUSED.items():
            with self.subTest(program=name), tempfile.TemporaryDirectory() as directory:
                built, exe = build_source(directory, name, (LAB / name).read_text(encoding="utf-8"))
                self.assertEqual(built.returncode, 3, built.stdout + built.stderr)
                self.assertIn(wanted, built.stderr)
                self.assertFalse(exe.exists())


if __name__ == "__main__":
    unittest.main()
