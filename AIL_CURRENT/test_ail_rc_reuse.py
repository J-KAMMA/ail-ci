"""rc4: Perceus reuse at a class-instance allocation site.

A second `Cls(...)` assigned to the same local place drops the old instance; when it is uniquely
held and the class has the same allocation size (it does -- same class), the IR emitter releases
its fields and parks the storage, and the constructor's `ail_obj_new` takes it back.  Two small
programs pin the reused shapes (a loop rebind and a straight rebind); three pin the refused ones
(across a call, a class with `__del__`, and an old instance still named).  Every program is checked
against CPython, and `ail_obj_reuse` must appear in `program.c` only where a reuse was emitted.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

BOX = """
class Box:
    def __init__(self, v: int):
        self.v = v
"""

LOOP = BOX + """
def main():
    b = Box(0)
    total = 0
    for i in range(5):
        b = Box(i)
        total = total + b.v
    print(total)

main()
"""

STRAIGHT = BOX + """
def main():
    b = Box(0)
    b = Box(1)
    print(b.v)

main()
"""

ACROSS = BOX + """
def make() -> int:
    return 7


def main():
    b = Box(0)
    b = Box(make())
    print(b.v)

main()
"""

NAMED = BOX + """
def main():
    p = Box(1)
    q = p
    p = Box(2)
    print(p.v + q.v)

main()
"""

FINALISER = """
class Box:
    def __init__(self, v: int):
        self.v = v
    def __del__(self):
        return


def main():
    b = Box(0)
    b = Box(1)
    print(b.v)

main()
"""


def build(directory, text, name, env=None):
    source = Path(directory, name + ".py")
    exe = Path(directory, name)
    debug = Path(directory, name + ".dbg")
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300, env=env)
    assert built.returncode == 0, built.stdout + built.stderr
    return exe, source, (debug / "program.c").read_text(encoding="utf-8")


class ReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.cases = {}
        for name, text in (("loop", LOOP), ("straight", STRAIGHT), ("across", ACROSS),
                           ("named", NAMED), ("finaliser", FINALISER)):
            cls.cases[name] = build(cls.directory.name, text, name)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def check(self, name):
        exe, source, program = self.cases[name]
        ran = subprocess.run([str(exe)], capture_output=True, timeout=60)
        expected = subprocess.run([sys.executable, str(source)], capture_output=True, timeout=60)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, expected.stdout)
        return program

    def test_loop_rebind_reuses_the_old_instance(self):
        self.assertIn("ail_obj_reuse(v_b, sizeof(ail_obj_Box))", self.check("loop"))

    def test_straight_rebind_reuses_the_old_instance(self):
        self.assertIn("ail_obj_reuse(v_b, sizeof(ail_obj_Box))", self.check("straight"))

    def test_across_a_call_is_refused(self):
        self.check("across")
        self.assertNotIn("ail_obj_reuse", self.cases["across"][2])

    def test_old_instance_still_named_is_refused(self):
        self.check("named")
        self.assertNotIn("ail_obj_reuse", self.cases["named"][2])

    def test_a_finaliser_class_is_refused(self):
        self.check("finaliser")
        self.assertNotIn("ail_obj_reuse", self.cases["finaliser"][2])

    def test_switch_is_the_escape_hatch(self):
        """`AIL_RC_REUSE=0` removes the helper and the fast path entirely."""
        text = Path(self.directory.name, "loop.py").read_text(encoding="utf-8")
        env = dict(os.environ, AIL_RC_REUSE="0")
        _exe, _source, program = build(self.directory.name, text, "off", env=env)
        self.assertNotIn("ail_obj_reuse", program)


if __name__ == "__main__":
    unittest.main()
