"""Idioms the rep5 AIL sessions hit (an audit program, a tree-folding program, a ranking program, a packing program, a tally program).

Accepted programs are ordinary Python: CPython runs each as the oracle and the compiled program (the typed
path only, AIL_NO_GENERAL=1) must print the same bytes.

* two loops over two different index lists may reuse one loop variable (`for i in vi:` ... `for i in ei:`);
* `ba[a:b].decode()` on a bytearray, also as the argument of `list[str].append`;
* `ids: dict[bytes, int] = {}` / `seen: set[bytes] = set()` as locals;

Refused with a message that names the construct and the rewrite:
* a tuple holding a bytearray, an unannotated dict literal passed to a constructor, a module-level set /
  dict, a `set[bytes]` parameter, a bytes element used as a sort key, a bytes appended to a
  `list[int]`.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def compile_python(directory, text, name):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, AIL_NO_GENERAL="1"))
    return built, exe


ACCEPTED = {
    "index_lists_share_loop_variable": ("", """
import sys

def main() -> int:
    w = [3, 1, 2]
    names = ["a", "b", "c"]
    vi = list(range(3))
    vi.sort(key=lambda i: w[i])
    ei = list(range(3))
    ei.sort(key=lambda i: (-w[i], names[i]))
    total = 0
    for i in vi:
        total += w[i] * 10 + i
    for i in ei:
        total += i
    for i in vi:
        total += 1
    print(total)
    return 0

sys.exit(main())
"""),
    "record_list_and_index_list_share_loop_variable": ("", """
import sys

def main() -> int:
    ps = []
    ps.append((3, 1))
    ps.append((1, 2))
    vi = list(range(2))
    t = 0
    for i in vi:
        t += i * 10
    for i in ps:
        t += i[0] * 100 + i[1]
    for i in vi:
        t += i
    print(t)
    return 0

sys.exit(main())
"""),
    "bytearray_slice_decode": ("", """
import sys
from dataclasses import dataclass

@dataclass
class T:
    pool: bytearray
    ns: list[int]
    nl: list[int]

def main() -> int:
    t = T(bytearray(b"abcdef"), [0, 2], [2, 3])
    ba = bytearray(b"xyz\\xc3")
    ks: list[str] = []
    for j in range(2):
        ks.append(t.pool[t.ns[j]:t.ns[j] + t.nl[j]].decode())
    ks.append(ba[1:3].decode())
    s = ba[0:2].decode()
    print(",".join(ks), s, len(ks))
    try:
        print(ba[3:4].decode())
    except ValueError:
        print("bad utf8")
    return 0

sys.exit(main())
"""),
    "bytes_keyed_locals": ("the cat an ox cat the dog\n", """
import sys

def main() -> int:
    ids: dict[bytes, int] = {}
    seen: set[bytes] = set()
    stop = {b"an", b"the"}
    terms = []
    for w in sys.stdin.buffer.read().split():
        t = bytes(w)
        if t in stop:
            continue
        seen.add(t)
        if t not in ids:
            ids[t] = len(terms)
            terms.append(t)
    order = list(range(len(terms)))
    order.sort(key=lambda i: terms[i].hex())
    print(len(terms), len(seen), order[0], order[1], order[2], ids[b"ox"])
    return 0

sys.exit(main())
"""),
}

REFUSED = {
    "tuple_with_bytearray": ("""
import sys

def unpack(d: bytes) -> tuple[int, bytearray]:
    out = bytearray()
    out.append(d[0])
    return 0, out

def main() -> int:
    code, res = unpack(b"ab")
    print(code, len(res))
    return 0

sys.exit(main())
""", ["a tuple cannot hold a bytearray", "pass the bytearray in as a parameter"]),
    "unannotated_dict_literal_into_constructor": ("""
import sys
from dataclasses import dataclass

@dataclass
class S:
    n: int
    kw: dict[str, int]

def main() -> int:
    kw = {"set": 10, "out": 11}
    p = S(0, kw)
    print(p.kw["set"])
    return 0

sys.exit(main())
""", ["'kw' is an unannotated dict literal", "annotate it `kw: dict[str, int] = {...}`"]),
    "module_level_set": ("""
import sys

STOP = {"an", "and", 1}

def f(t: str) -> int:
    return 1 if t in STOP else 0

def main() -> int:
    print(f("an"))
    return 0

sys.exit(main())
""", ["'STOP' is a module-level set", "build it in main() (`stop: set[str] = {...}`)"]),
    "bytes_set_parameter": ("""
import sys

def f(t: bytes, stop: set[bytes]) -> int:
    return 1 if t in stop else 0

def main() -> int:
    stop = {b"an"}
    print(f(b"an", stop))
    return 0

sys.exit(main())
""", ["'stop' is annotated set[bytes]", "a bytes-keyed set or dict is a local"]),
    "bytes_sort_key": ("""
import sys

def main() -> int:
    terms = []
    terms.append(b"bb")
    terms.append(b"aa")
    order = list(range(len(terms)))
    order.sort(key=lambda x: terms[x])
    print(order[0])
    return 0

sys.exit(main())
""", ["'terms'[...] is a bytes element, not a number", "terms[i].hex()"]),
    "bytes_appended_to_int_list": ("""
import sys

def main() -> int:
    r: list[int] = []
    r.append(b"ab")
    print(len(r))
    return 0

sys.exit(main())
""", ["a declared list[int] accepts only int elements, not bytes"]),
}


class Rep5Idioms(unittest.TestCase):
    def test_accepted_programs_match_cpython(self):
        for name, (stdin, text) in ACCEPTED.items():
            with self.subTest(name), tempfile.TemporaryDirectory(prefix="rep5_") as directory:
                built, exe = compile_python(directory, text, name)
                self.assertEqual(built.returncode, 0, name + ": " + (built.stdout + built.stderr)[-3000:])
                got = subprocess.run([str(exe)], cwd=directory, input=stdin.encode(), capture_output=True, timeout=300)
                want = subprocess.run([sys.executable, "-c", text], input=stdin.encode(), capture_output=True, timeout=300)
                self.assertEqual(want.returncode, 0, want.stderr)
                self.assertEqual(got.stdout, want.stdout, name)
                self.assertEqual(got.returncode, want.returncode, name)

    def test_refused_programs_say_what_to_write(self):
        for name, (text, phrases) in REFUSED.items():
            with self.subTest(name), tempfile.TemporaryDirectory(prefix="rep5_") as directory:
                built, _ = compile_python(directory, text, name)
                self.assertEqual(built.returncode, 3, name + ": " + (built.stdout + built.stderr)[-3000:])
                for phrase in phrases:
                    self.assertIn(phrase, built.stderr, name)


if __name__ == "__main__":
    unittest.main()
