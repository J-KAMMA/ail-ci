"""Dict fields keep value semantics when the compiler moves instead of copying.

`let d = obj.field` copies once straight out of the field, and `obj.field = d` moves `d` when it is
a top-level statement and the last mention of `d`. Every case here would print a different answer
if a move leaked into a place where the local or the field can still be observed.
"""
import subprocess
import unittest
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = r'''struct Box { counts: dict[str,int]; }
fn pick(b: Box, d: dict[str,int]) -> Box { return b; }
fn last_use(b: Box) -> void {
    let d: dict[str,int] = b.counts;
    d["moved"] = 1;
    b.counts = d;
}
fn used_after(b: Box) -> int {
    let d: dict[str,int] = b.counts;
    d["kept"] = 2;
    b.counts = d;
    d["after"] = 3;
    return len(d);
}
fn in_loop(b: Box) -> int {
    let d: dict[str,int] = {};
    for i in range(3) {
        d[str(i)] = i;
        b.counts = d;
    }
    return len(d);
}
fn rebound(b: Box) -> int {
    let d: dict[str,int] = {"a": 1};
    b.counts = d;
    d = {"z": 9};
    return len(d);
}
fn through_receiver(b: Box) -> void {
    let d: dict[str,int] = {"r": 5};
    pick(b, d).counts = d;
}
fn main() -> int {
    let b = Box({"start": 0});
    let alias = b;
    let snapshot: dict[str,int] = b.counts;
    snapshot["local"] = 7;
    if "local" in b.counts { return 1; }
    last_use(b);
    if len(alias.counts) != 2 or alias.counts["moved"] != 1 { return 2; }
    if "local" in alias.counts { return 3; }
    if used_after(b) != 4 { return 4; }
    if len(b.counts) != 3 or "after" in b.counts { return 5; }
    if in_loop(b) != 3 or len(b.counts) != 3 or b.counts["2"] != 2 { return 6; }
    if rebound(b) != 1 or len(b.counts) != 1 or b.counts["a"] != 1 { return 7; }
    through_receiver(b);
    if len(b.counts) != 1 or b.counts["r"] != 5 { return 8; }
    let other = Box({"x": 1});
    other.counts = b.counts;
    b.counts["r"] = 6;
    if other.counts["r"] != 5 { return 9; }
    print("ok");
    return 0;
}'''


class MapFieldMoveTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_moves_keep_value_semantics(self):
        program = build(self, 'map_field_moves', SOURCE)
        result = subprocess.run([str(program)], capture_output=True, timeout=30)
        self.assertEqual((result.returncode, result.stdout), (0, b'ok\n'), result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
