"""`a + b` returns the wider view when b starts where a ends (the `field += ch` idiom).

The views built here outlive the text they point into only through a return, a struct field, a
list or a dict key, and each of those must still own its bytes.
"""
import subprocess
import unittest
from pathlib import Path
import test_ail_c_objects as support
from test_ail_map_fields import build


SOURCE = r'''struct Holder { text: str; parts: list[str]; }

fn built_here() -> str {
    let t: str = str(12345) + "abcé日😀";
    let s: str = "";
    for ch in t { s += ch; }
    return s;
}

fn pieces(text: str) -> list[str] {
    let out: list[str] = [];
    let field: str = "";
    for ch in text {
        if ch == "," { out.append(field); field = ""; }
        else { field += ch; }
    }
    out.append(field);
    return out;
}

fn local_pieces() -> list[str] {
    let t: str = "x" + str(987) + ",yé,,z😀z";
    return pieces(t);
}

fn fill(h: Holder) -> void {
    let t: str = str(55) + "-tail";
    let s: str = "";
    for ch in t { s += ch; }
    h.text = s;
    h.parts = pieces(t + ",q");
}

fn main() -> int {
    let a: str = built_here();
    let b: list[str] = local_pieces();
    let h = Holder("", []);
    fill(h);
    let counts: dict[str, int] = {};
    for i in range(50) {
        let t: str = str(i % 7) + "k";
        let key: str = "";
        for ch in t { key += ch; }
        counts[key] = counts.get(key, 0) + 1;
    }
    let s: str = "ab";
    let u: str = s[0:1] + s[1:2];
    let w: str = s + s;
    let v: str = s[1:2] + s[0:1];
    print(a);
    print("|".join(b));
    print(h.text + " " + "|".join(h.parts));
    print(len(counts), counts["3k"]);
    print(u, w, v, u == s);
    return 0;
}
'''
EXPECTED = '12345abcé日😀\nx987|yé||z😀z\n55-tail 55-tail|q\n7 7\nab abab ba True\n'


class AdjacentCatTests(unittest.TestCase):
    setUp = support.CObjectTests.setUp
    write = support.CObjectTests.write
    command = support.CObjectTests.command

    def test_adjacent_views_keep_their_bytes(self):
        program = build(self, 'adjacent_cat', SOURCE)
        result = subprocess.run([str(program)], capture_output=True, timeout=30)
        self.assertEqual((result.returncode, result.stdout.decode()), (0, EXPECTED),
                         result.stderr.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
