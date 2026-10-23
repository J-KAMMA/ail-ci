"""Field reads that used to copy a whole field read in place when nothing can change it meanwhile.

Three programs written for new tasks were 100-1000x slower than C on large inputs, each from one
copy per access of something only read:

* `let d = self.data` in a cursor method copied a multi-megabyte bytes field on every call
  (quadratic). A bytes field of a never-rebound struct PARAMETER is now read as a view when nothing
  the function runs -- its own statements and, transitively, everything it calls -- stores a field
  of that name on any object; values that outlive the call still copy as before.
* `r.stack[r.sp - 1]` snapshotted the whole list field because the index read another field. An
  int field of a held struct is now a pure index like a local int.
* `st.keys[id]` snapshotted every string of a `list[str]` field to read one; with a pure index it
  now copies only that element. Appending to a `list[str]` field repacked the whole field per
  append; it now repacks into a block with spare room (amortised constant copies per string).

Every case below runs against CPython, including the shapes where the view would be wrong.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCE = """
struct Rd { data: bytes; pos: int; }
impl Rd {
    fn next(self) -> int {
        let d = self.data;
        let p = self.pos;
        let n = len(d);
        while p < n and (d[p] < 48 or d[p] > 57) { p += 1; }
        let v = 0;
        while p < n and d[p] >= 48 and d[p] <= 57 { v = v * 10 + (d[p] - 48); p += 1; }
        self.pos = p;
        return v;
    }
    fn head(self) -> bytes { return self.data[0:3]; }
}

struct Box { data: bytes; tag: str; }
fn swap_in(b: Box, x: bytes) -> void { b.data = x; }
impl Box {
    fn replaced_by_call(self) -> bytes {
        let d = self.data;
        swap_in(self, b"zzzz");
        return d + self.data;
    }
    fn replaced_here(self) -> bytes {
        let d = self.data;
        self.data = b"yy";
        return d + self.data;
    }
    fn replaced_alias(self, other: Box) -> bytes {
        let d = self.data;
        other.data = b"ww";
        return d + self.data;
    }
    fn whole(self) -> bytes { return self.data; }
}
fn via_callback(b: Box, cb: Callable[[Box], int]) -> bytes {
    let d = b.data;
    cb(b);
    return d + b.data;
}
fn clobber(b: Box) -> int { b.data = b"cb"; return 0; }

struct Rt { stack: list[int]; sp: int; names: list[str]; }
fn top(r: Rt) -> int { return r.stack[r.sp - 1]; }
fn below(r: Rt) -> int { return r.stack[r.sp - 2] * 10 + r.stack[-r.sp]; }
fn name_at(r: Rt, i: int) -> str { return r.names[i]; }
fn keep_then_change(r: Rt) -> str {
    let k = r.names[r.sp - 1];
    r.names[r.sp - 1] = "changed";
    let j = r.names[0];
    r.names.clear();
    return k + "/" + j + "/" + str(len(r.names));
}

fn main() {
    let rd = Rd(b"12 x345,6 789", 0);
    let total = 0;
    for i in range(4) { total = total * 1000 + rd.next(); }
    print(total, rd.pos, rd.head().decode());

    let b = Box(b"abc", "t");
    print(b.replaced_by_call().decode());
    b = Box(b"abc", "t");
    print(b.replaced_here().decode());
    b = Box(b"abc", "t");
    print(b.replaced_alias(b).decode());
    b = Box(b"abc", "t");
    print(via_callback(b, clobber).decode());
    let w = b.whole();
    b.data = b"new";
    print(w.decode(), b.whole().decode());

    let r = Rt([4, 5, 6], 3, ["a", "", "ccc"]);
    print(top(r), below(r), name_at(r, 2), len(name_at(r, -2)));
    r.sp = 1;
    print(top(r), name_at(r, 0));
    try { r.sp = 5; print(top(r)); } except IndexError { print("index error"); }
    r.sp = 3;
    let names: list[str] = [];
    for i in range(300) {
        r.names.append("k" + str(i));
        if i % 7 == 0 { r.names.append(""); }
        if i % 50 == 0 { r.names.append(r.names[0] + r.names[i]); }
        if i % 97 == 0 { r.names.append("é中" + str(i)); }
        if i == 150 { r.names[3] = "three"; r.names.sort(); }
        if i == 200 { r.names.pop(); r.names.reverse(); }
    }
    let joined = "";
    for i in range(len(r.names)) { joined = joined + name_at(r, i) + ","; }
    print(len(r.names), len(joined), joined[0:60], joined[len(joined) - 60:len(joined)]);
    r.sp = 2;
    print(keep_then_change(r));
    for i in range(5) { r.names.append(str(i * i)); }
    print(name_at(r, 4), len(r.names));
}
"""

PYTHON = """
class Rd:
    def __init__(self, data, pos): self.data, self.pos = data, pos
    def next(self):
        d = self.data; p = self.pos; n = len(d)
        while p < n and (d[p] < 48 or d[p] > 57): p += 1
        v = 0
        while p < n and d[p] >= 48 and d[p] <= 57:
            v = v * 10 + (d[p] - 48); p += 1
        self.pos = p
        return v
    def head(self): return self.data[0:3]

class Box:
    def __init__(self, data, tag): self.data, self.tag = data, tag
    def replaced_by_call(self):
        d = self.data; swap_in(self, b"zzzz"); return d + self.data
    def replaced_here(self):
        d = self.data; self.data = b"yy"; return d + self.data
    def replaced_alias(self, other):
        d = self.data; other.data = b"ww"; return d + self.data
    def whole(self): return self.data
def swap_in(b, x): b.data = x
def via_callback(b, cb):
    d = b.data; cb(b); return d + b.data
def clobber(b):
    b.data = b"cb"; return 0

class Rt:
    def __init__(self, stack, sp, names): self.stack, self.sp, self.names = stack, sp, names
def top(r): return r.stack[r.sp - 1]
def below(r): return r.stack[r.sp - 2] * 10 + r.stack[-r.sp]
def name_at(r, i): return r.names[i]
def keep_then_change(r):
    k = r.names[r.sp - 1]
    r.names[r.sp - 1] = "changed"
    j = r.names[0]
    r.names.clear()
    return k + "/" + j + "/" + str(len(r.names))

rd = Rd(b"12 x345,6 789", 0)
total = 0
for i in range(4): total = total * 1000 + rd.next()
print(total, rd.pos, rd.head().decode())
b = Box(b"abc", "t"); print(b.replaced_by_call().decode())
b = Box(b"abc", "t"); print(b.replaced_here().decode())
b = Box(b"abc", "t"); print(b.replaced_alias(b).decode())
b = Box(b"abc", "t"); print(via_callback(b, clobber).decode())
w = b.whole(); b.data = b"new"; print(w.decode(), b.whole().decode())
r = Rt([4, 5, 6], 3, ["a", "", "ccc"])
print(top(r), below(r), name_at(r, 2), len(name_at(r, -2)))
r.sp = 1
print(top(r), name_at(r, 0))
try:
    r.sp = 5; print(top(r))
except IndexError: print("index error")
r.sp = 3
for i in range(300):
    r.names.append("k" + str(i))
    if i % 7 == 0: r.names.append("")
    if i % 50 == 0: r.names.append(r.names[0] + r.names[i])
    if i % 97 == 0: r.names.append("\\u00e9\\u4e2d" + str(i))
    if i == 150: r.names[3] = "three"; r.names.sort()
    if i == 200: r.names.pop(); r.names.reverse()
joined = ""
for i in range(len(r.names)): joined = joined + name_at(r, i) + ","
print(len(r.names), len(joined), joined[0:60], joined[len(joined) - 60:len(joined)])
r.sp = 2
print(keep_then_change(r))
for i in range(5): r.names.append(str(i * i))
print(name_at(r, 4), len(r.names))
"""


def build(directory, text):
    source, exe, debug = Path(directory, "p.ail"), Path(directory, "p"), Path(directory, "debug")
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300)
    assert built.returncode == 0, built.stdout + built.stderr
    return exe, (debug / "program.c").read_text(encoding="utf-8")


def body_of(program, name):
    """The definition (not the prototype) of generated function `name`."""
    match = re.search(r"\n[\w *]+\b%s\([^)]*\) \{\n" % name, program)
    assert match, name
    return program[match.end():program.index("\n}\n", match.end())]


class FieldViewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.exe, cls.program = build(cls.directory.name, SOURCE)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_matches_cpython(self):
        ran = subprocess.run([str(self.exe)], capture_output=True, timeout=60)
        expected = subprocess.run([sys.executable, "-c", PYTHON], capture_output=True, timeout=60)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, expected.stdout)

    def test_bytes_field_view_only_where_never_replaced(self):
        copy = "ail_bytes_return_owned((v_self)->f_data)"
        self.assertIn("v_d = (v_self)->f_data;", body_of(self.program, "Rd__next"))
        self.assertNotIn(copy, body_of(self.program, "Rd__next"))
        for name in ("Box__replaced_by_call", "Box__replaced_here", "Box__replaced_alias"):
            self.assertIn(copy, body_of(self.program, name), name)
        self.assertIn("ail_bytes_return_owned((v_b)->f_data)", body_of(self.program, "via_callback"))

    def test_field_indexes_read_in_place(self):
        for name in ("top", "below"):
            self.assertNotIn("snapshot", body_of(self.program, name), name)
        self.assertNotIn("snapshot", body_of(self.program, "name_at"))
        self.assertIn("ail_pslist_get(&(v_r)->f_names", body_of(self.program, "name_at"))


# These tests pin the C text of the legacy emitter, the AIL_IR=0 opt-out (the IR is the default since
# 2026-10-19 and has its own text, pinned in test_ail_ir_*): the whole module builds with AIL_IR=0
# unless the caller set AIL_IR.
_SAVED_AIL_IR = []


def setUpModule():
    import os as _os
    _SAVED_AIL_IR.append(_os.environ.get('AIL_IR'))
    if _SAVED_AIL_IR[-1] is None:
        _os.environ['AIL_IR'] = '0'


def tearDownModule():
    import os as _os
    if _SAVED_AIL_IR.pop() is None:
        _os.environ.pop('AIL_IR', None)


if __name__ == "__main__":
    unittest.main()
