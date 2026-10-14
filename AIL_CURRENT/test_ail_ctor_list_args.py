"""A list[str] passed to a constructor by plain name is copied by the constructor, not staged.

The object must still own an independent copy: later changes to the local, a pop in an earlier
argument, and views into a string that dies with its function all have to leave it unchanged.
"""
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = r'''struct Row { number: int; fields: list[str]; tag: str; }
fn make(text: str) -> Row {
    let local: str = text + "|" + str(42);
    let parts: list[str] = local.split("|");
    let tag: str = "t";
    return Row(len(parts), parts, tag);
}
fn main() -> int {
    let fields: list[str] = ["a", "b", "c"];
    let r = Row(1, fields, "x");
    fields.append("d"); fields[0] = "z";
    let s = Row(fields.pop() == "d", fields, "y");
    fields.clear();
    let m = make("é,😀");
    print(len(r.fields), r.fields[0], len(s.fields), s.number, s.fields[0], len(fields));
    print(m.number, "/".join(m.fields), m.tag);
    return 0;
}'''


class ConstructorListArgumentTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_constructor_owns_its_list(self):
        program = build(self, 'ctor_list_args', SOURCE)
        result = subprocess.run([str(program)], capture_output=True, timeout=30)
        self.assertEqual((result.returncode, result.stdout.decode()),
                         (0, '3 a 3 1 z 0\n2 é,😀/42 t\n'), result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
