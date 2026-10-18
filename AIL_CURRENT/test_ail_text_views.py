"""Short-style text programs without the copies they used to pay for, checked against CPython:

* `st.sold.add(f"{a}{b}")` / `.remove` / `.discard` on a set FIELD read the key as a view (the
  table copies a new key itself) -- it was copied into the arena first, then again by the table.
* `st.m[k] = v` on a str-valued dict field passes `v` as a view when neither the receiver nor the
  key runs a call (put copies it before freeing the value it replaces); with a call it still
  copies first, since the call could change what `v` shows.
* `kinds.get(k, "")` / `kinds[k]` on a str-valued dict PARAMETER returns a view of the dict's own
  text: parameters are read-only and outlive the call.
* `st.keys[i]` (an element of a list[str] field) is a view when its consumer proves nothing can
  change the list first: a lookup key, an argument the callee only reads while nothing else runs,
  a key column of a keyed sort whose key runs no user code. Before, each read was copied into the
  function's arena and kept until it returned (4 million sort keys and arguments: 160 MB).
* Runtime: str blocks come from the block cache (no calloc), `k == "literal"` compares a constant
  length, ASCII `isdigit`/`isalpha`/`isalnum` skip the property table, `s[i]`/`s[a:b]` on ASCII
  skip the cursor, `int(<one digit>)` is inline, a one-int-column keyed sort (and an int first
  column) compares without the column walk, small str-list vectors are recycled.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from ail_testenv import gnu_time

ROOT = Path(__file__).resolve().parent

SOURCE = r"""
struct St { sold: set[str]; m: dict[str, str]; keys: list[str]; score: list[int]; name: str; ix: dict[str, int]; }
fn bump(st: St) -> str { st.name = st.name + "!"; return "k"; }
fn show(k: str, v: int) -> void { print(f"{k}={v}"); }
fn clobber(st: St, k: str) -> void { st.keys[0] = "zzz"; print("clobber", k, st.keys[0]); }
fn pick(kinds: dict[str, str], k: str) -> str { return kinds.get(k, "none"); }
fn fields(kinds: dict[str, str], k: str) -> list[str] {
    let out: list[str] = [];
    for w in kinds.get(k, "").split() { out.append(w); }
    out.append(kinds[k] if k in kinds else "?");
    return out;
}
fn byid(names: dict[int, str], i: int) -> str { return names.get(i, "-") + names.get(i + 1, "-"); }
fn store(st: St, kinds: dict[str, str], k: str) -> void { st.m[k] = kinds.get(k, ""); st.keys.append(kinds[k]); st.score.append(9); }
fn syn(k: str, s: str) -> int {
    if k == "code" { return len(s) == 3 and s.isalpha() and s.isupper(); }
    if k == "cap" { return len(s) <= 6 and s.isdigit(); }
    if k == "event" { return len(s) == 6 and s.isdigit(); }
    if k == "seat" { return len(s) >= 2 and s[0].isupper() and s[1:].isdigit(); }
    if k == "buyer" { return len(s) >= 2 and s[0].islower() and s.isalnum(); }
    if k == "price" { return len(s) >= 4 and s[-3] == "." and (s[0:len(s) - 3] + s[len(s) - 2:]).isdigit(); }
    return 0;
}
fn ck(xs: list[int]) -> int { let t = 0; for x in xs { t = (t * 7 + x) % 1000003; } return t; }
fn digits(s: str) -> int {
    let t = 0;
    for i in range(len(s)) { t = t * 3 + int(s[i]); }
    return t;
}
fn main() {
    let kinds: dict[str, str] = {"V": "code cap", "S": "event seat buyer", "P": "price"};
    let names: dict[int, str] = {1: "one", 2: "two", 5: "five"};
    let st = St(set(), {}, [], [], "nm", {});
    let n = 0;
    for line in sys.stdin {
        n += 1;
        let f = line.strip().split("|");
        let ks = kinds.get(f[0], "").split();
        let ok = len(ks) == len(f) - 1;
        if ok { for j in range(len(ks)) { if not syn(ks[j], f[j + 1]) { ok = 0; } } }
        let seat = f"{f[0]}{f[len(f) - 1]}";
        if seat in st.sold { st.sold.remove(seat); } else { st.sold.add(seat); }
        st.sold.discard(f"x{n}");
        st.m[f[0]] = f[len(f) - 1];
        st.keys.append(f[len(f) - 1]);
        st.score.append((n * 7) % 5);
        st.ix[f[len(f) - 1]] = n;
        print(n, ok, len(ks), pick(kinds, f[0]), "|".join(fields(kinds, f[0])), byid(names, n % 6));
    }
    st.m[bump(st)] = st.name;
    print(st.name, st.m["k"]);
    store(st, kinds, "S");
    kinds["S"] = "changed";
    print(st.m["S"], st.keys[len(st.keys) - 1], kinds["S"]);
    for i in range(len(st.keys)) { show(st.keys[i], st.ix.get(st.keys[i], -1)); }
    clobber(st, st.keys[0]);
    let ix = [i for i in range(len(st.keys))];
    ix.sort(key=lambda i: (st.score[i], st.keys[i]));
    print("|".join([st.keys[i] for i in ix]));
    ix.sort(key=lambda i: (-st.score[i], st.keys[i]), reverse=True);
    print("|".join([st.keys[i] for i in ix]));
    ix.sort(key=lambda i: st.score[i]);
    print(ck(ix));
    ix.sort(key=lambda i: st.score[i], reverse=True);
    print(ck(ix));
    ix.sort(key=lambda i: (len(st.keys[i]), st.keys[i]));
    print(ck(ix));
    let held: list[str] = [];
    for i in range(len(st.keys)) { held.append(st.keys[i]); }
    st.keys.clear();
    st.keys.append("new");
    print("|".join(held), st.keys[0]);
    let sold = sorted(st.sold);
    print(len(sold), "|".join(sold));
    for s in ["123", "12a", "", "٣", "²", "é", "Ab9", "AB", "ab", "a_b", "x"] {
        print(s, s.isdigit(), s.isdecimal(), s.isnumeric(), s.isalpha(), s.isalnum());
    }
    print(digits("2101"), digits("0"), digits("99"));
    let w = "hello";
    print(w[0], w[-1], w[1:3], w[-3:], w[:-4], w[9:], w[2:1]);
    print(w[4], w[-5]);
    for k in ["code", "cap", "event", "seat", "buyer", "price", "zz", "codex", "co"] {
        print(k, syn(k, "ABC"), syn(k, "123456"), syn(k, "A12"), syn(k, "b0b"), syn(k, "12.35"));
    }
}
"""

PYTHON = r'''
import sys

class St:
    def __init__(self):
        self.sold, self.m, self.keys, self.score, self.name, self.ix = set(), {}, [], [], "nm", {}

def bump(st):
    st.name = st.name + "!"; return "k"
def show(k, v): print(f"{k}={v}")
def clobber(st, k):
    st.keys[0] = "zzz"; print("clobber", k, st.keys[0])
def pick(kinds, k): return kinds.get(k, "none")
def fields(kinds, k):
    out = [w for w in kinds.get(k, "").split()]
    out.append(kinds[k] if k in kinds else "?")
    return out
def byid(names, i): return names.get(i, "-") + names.get(i + 1, "-")
def store(st, kinds, k):
    st.m[k] = kinds.get(k, ""); st.keys.append(kinds[k]); st.score.append(9)
def syn(k, s):
    if k == "code": return int(len(s) == 3 and s.isalpha() and s.isupper())
    if k == "cap": return int(len(s) <= 6 and s.isdigit())
    if k == "event": return int(len(s) == 6 and s.isdigit())
    if k == "seat": return int(len(s) >= 2 and s[0].isupper() and s[1:].isdigit())
    if k == "buyer": return int(len(s) >= 2 and s[0].islower() and s.isalnum())
    if k == "price": return int(len(s) >= 4 and s[-3] == "." and (s[0:len(s) - 3] + s[len(s) - 2:]).isdigit())
    return 0
def ck(xs):
    t = 0
    for x in xs: t = (t * 7 + x) % 1000003
    return t
def digits(s):
    t = 0
    for i in range(len(s)): t = t * 3 + int(s[i])
    return t

def main():
    kinds = {"V": "code cap", "S": "event seat buyer", "P": "price"}
    names = {1: "one", 2: "two", 5: "five"}
    st = St()
    n = 0
    for line in sys.stdin:
        n += 1
        f = line.strip().split("|")
        ks = kinds.get(f[0], "").split()
        ok = int(len(ks) == len(f) - 1)
        if ok:
            for j in range(len(ks)):
                if not syn(ks[j], f[j + 1]): ok = 0
        seat = f"{f[0]}{f[len(f) - 1]}"
        if seat in st.sold: st.sold.remove(seat)
        else: st.sold.add(seat)
        st.sold.discard(f"x{n}")
        st.m[f[0]] = f[len(f) - 1]
        st.keys.append(f[len(f) - 1])
        st.score.append((n * 7) % 5)
        st.ix[f[len(f) - 1]] = n
        print(n, ok, len(ks), pick(kinds, f[0]), "|".join(fields(kinds, f[0])), byid(names, n % 6))
    st.m[bump(st)] = st.name
    print(st.name, st.m["k"])
    store(st, kinds, "S")
    kinds["S"] = "changed"
    print(st.m["S"], st.keys[len(st.keys) - 1], kinds["S"])
    for i in range(len(st.keys)): show(st.keys[i], st.ix.get(st.keys[i], -1))
    clobber(st, st.keys[0])
    ix = list(range(len(st.keys)))
    ix.sort(key=lambda i: (st.score[i], st.keys[i]))
    print("|".join([st.keys[i] for i in ix]))
    ix.sort(key=lambda i: (-st.score[i], st.keys[i]), reverse=True)
    print("|".join([st.keys[i] for i in ix]))
    ix.sort(key=lambda i: st.score[i])
    print(ck(ix))
    ix.sort(key=lambda i: st.score[i], reverse=True)
    print(ck(ix))
    ix.sort(key=lambda i: (len(st.keys[i]), st.keys[i]))
    print(ck(ix))
    held = [st.keys[i] for i in range(len(st.keys))]
    st.keys.clear()
    st.keys.append("new")
    print("|".join(held), st.keys[0])
    sold = sorted(st.sold)
    print(len(sold), "|".join(sold))
    for s in ["123", "12a", "", "٣", "²", "é", "Ab9", "AB", "ab", "a_b", "x"]:
        print(s, s.isdigit(), s.isdecimal(), s.isnumeric(), s.isalpha(), s.isalnum())
    print(digits("2101"), digits("0"), digits("99"))
    w = "hello"
    print(w[0], w[-1], w[1:3], w[-3:], w[:-4], w[9:], w[2:1])
    print(w[4], w[-5])
    for k in ["code", "cap", "event", "seat", "buyer", "price", "zz", "codex", "co"]:
        print(k, syn(k, "ABC"), syn(k, "123456"), syn(k, "A12"), syn(k, "b0b"), syn(k, "12.35"))

main()
'''

INPUT = ("V|ABC|120\nS|123456|A12|bob1\nS|123456|A12|bob1\nP|12.35\nV|abc|7\nS|12345|Z9|x\nQ|nothing\n"
         + "".join("S|%06d|R%d|u%d\n" % (i * 37 % 999999, i % 50, i % 9) for i in range(60))
         + "P|1.0\nV|XYZ|999999")

# A ranking loop: per document, sort indices by (-score, key) over a list[str] FIELD and pass
# keys to a reader. The keys were copied into main's arena on every read and never released.
RANK = r"""
struct Doc { keys: list[str]; total: list[int]; }
fn item(key: str, v: int) -> int { return len(key) + v; }
fn main() {
    let d = Doc([], []);
    for i in range(500) { d.keys.append(f"key{i * 7919 % 500:05d}"); d.total.append(i * 31 % 17); }
    let docs = int(sys.argv[1]);
    let used = 0;
    let check = 0;
    for doc in range(docs) {
        let ix = [i for i in range(len(d.keys))];
        ix.sort(key=lambda i: (-d.total[i], d.keys[i]));
        for j in range(len(ix)) { used += item(d.keys[ix[j]], j); }
        check = (check * 31 + ix[doc % len(ix)]) % 1000003;
    }
    print(check, used);
}
"""

RANK_PY = r'''
import sys
keys = [f"key{i * 7919 % 500:05d}" for i in range(500)]
total = [i * 31 % 17 for i in range(500)]
check = 0
used = 0
for doc in range(int(sys.argv[1])):
    ix = sorted(range(len(keys)), key=lambda i: (-total[i], keys[i]))
    check = (check * 31 + ix[doc % len(ix)]) % 1000003
    used += sum(len(keys[ix[j]]) + j for j in range(len(ix)))
print(check, used)
'''


def build(directory, text, name="p"):
    source, exe, debug = Path(directory, name + ".ail"), Path(directory, name), Path(directory, name + "-debug")
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, str(ROOT / "ail_chatgpt.py"), "compile", str(source),
                            "-o", str(exe), "--debug-dir", str(debug)],
                           capture_output=True, text=True, timeout=300)
    return built, exe, debug / "program.c"


def body_of(program, name):
    """The definition (not the prototype) of generated function `name`."""
    match = re.search(r"\n[\w *]+ %s\([^)]*\) \{\n" % name, program)
    assert match, name
    return program[match.end():program.index("\n}\n", match.end())]


def peak_rss_kb(argv):
    """Peak RSS of one run, from GNU time when present (None otherwise: macOS time has other flags)."""
    timer = gnu_time()
    if timer is None:
        return None
    ran = subprocess.run([timer, "-f", "%M", *argv], capture_output=True, text=True, timeout=120)
    return int(ran.stderr.strip().splitlines()[-1])


class TextViewsTests(unittest.TestCase):
    def test_views_match_cpython(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, SOURCE)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            oracle = Path(directory, "oracle.py")
            oracle.write_text(PYTHON, encoding="utf-8")
            data = INPUT.encode("utf-8")
            ran = subprocess.run([str(exe)], input=data, capture_output=True, timeout=60)
            expected = subprocess.run([sys.executable, "-X", "utf8", str(oracle)], input=data,
                                      capture_output=True, timeout=60)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout.decode("utf-8"), expected.stdout.decode("utf-8"))
            out = ran.stdout.decode("utf-8")
            for word in ("nm! nm\n", "clobber 120 zzz", "event seat buyer event seat buyer changed"):
                self.assertIn(word, out)
            program = c_file.read_text()
            main = body_of(program, "py_main")
            # set field element: no arena copy before the table's own
            self.assertRegex(main, r"ail_str _key = v_seat; ail_sset_add\(")
            self.assertRegex(main, r"ail_str _key = v_seat; ail_sset_remove\(")
            # the dict value put with no call in between is a view; with a call it is owned
            self.assertNotRegex(main, r"_value = ail_str_adopt\([^;]*ail_slist_get\(&v_f")
            self.assertRegex(main, r"_value = ail_str_adopt\(&v__sarena, ail_str_return_owned\([^;]*f_name\)+;[^}]*bump\(")
            # field elements: views for the lookup key, show()'s argument and the sort key columns
            views = re.findall(r"; ail_slist_get\(&\(v_st\)->f_keys, _index\); \}\)", main)
            self.assertGreaterEqual(len(views), 6, views)
            # ... but clobber() stores into keys, so its argument is still a copy
            self.assertRegex(main, r"ail_str_return_owned\(ail_slist_get\(&\(v_st\)->f_keys, _index\)\)\); \}\), clobber\(")
            for name in ("pick", "fields", "store"):
                self.assertNotIn("ail_smap_get(", body_of(program, name))
            self.assertIn("ail_smap_get_view(", body_of(program, "pick"))
            self.assertIn("ail_smap_need_view(", body_of(program, "store"))
            self.assertIn("ail_ismap_get_view(", body_of(program, "byid"))

    def test_ranking_loop_keeps_no_key_copies(self):
        with tempfile.TemporaryDirectory() as directory:
            built, exe, c_file = build(directory, RANK)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            oracle = Path(directory, "oracle.py")
            oracle.write_text(RANK_PY, encoding="utf-8")
            for docs in ("1", "13"):
                ran = subprocess.run([str(exe), docs], capture_output=True, timeout=60)
                expected = subprocess.run([sys.executable, str(oracle), docs], capture_output=True, timeout=60)
                self.assertEqual(ran.returncode, 0, ran.stderr)
                self.assertEqual(ran.stdout, expected.stdout)
            self.assertNotIn("ail_str_return_owned(ail_slist_get(", body_of(c_file.read_text(), "py_main"))
            small, large = peak_rss_kb([str(exe), "20"]), peak_rss_kb([str(exe), "4000"])
            if small is not None:
                # 4000 docs x 1000 key reads x ~32 bytes would be ~128 MB of copies
                self.assertLess(large - small, 16 * 1024, (small, large))


if __name__ == "__main__":
    unittest.main()
