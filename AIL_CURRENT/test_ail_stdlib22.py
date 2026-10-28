"""Library batch 22: struct integer formats, and the tempfile subset.

Programs below are compiled with the Python syntax on the default build and on the typed path
(AIL_NO_GENERAL=1), run on generated stdin, and must print the same bytes as CPython 3.12. The
refusals name the unsupported format or use; a program without a struct or tempfile import keeps
its text. tempfile names are random in both implementations, so the programs print the shape
(prefix, suffix, length, existence) rather than the random text.
"""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG = ROOT / "python" / "pkg-v12"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

PROGRAM = r"""import struct
import sys


def packed(n: int) -> bytes:
    return struct.pack(">I", n)


def main() -> None:
    vals = [int(t) for t in sys.stdin.read().split()]
    for n in vals:
        print(list(struct.pack(">I", n)))
        print(list(struct.pack("<q", -n)))
        print(list(struct.pack(">bBhHiIlLqQ", -n, n, -n, n, -n, n, -n, n, -n, n)))
        print(list(struct.pack(">3xI", n)))
        print(list(struct.pack("<2H", n, n + 1)))
        print(list(struct.pack(">H", n)), list(struct.pack("!I", n)))
        print(struct.calcsize(">Ihq"), struct.calcsize("<2H"), struct.calcsize(">3xI"), struct.calcsize(""))
        data = struct.pack(">Ihq", n, -n, n)
        result = struct.unpack(">Ihq", data)
        print(result)
        a, b, c = result
        print(a, b, c)
        print(struct.unpack("<2H", struct.pack("<2H", n, n + 1)))
        print(struct.unpack(">3xI", struct.pack(">3xI", n)))
        p = packed(n)
        print(list(p), list(struct.pack(">I", n)))
        try:
            struct.pack(">I", -1)
        except struct.error as e:
            print("pack", e)
        try:
            struct.pack(">I", 4294967296)
        except struct.error as e:
            print("pack", e)
        try:
            struct.unpack(">I", b"\x00\x00\x00")
        except struct.error as e:
            print("unpack", e)
    print(list(struct.pack(">b", -128)), list(struct.pack(">b", 127)))
    print(list(struct.pack(">B", 0)), list(struct.pack(">B", 255)))
    print(list(struct.pack(">h", -32768)), list(struct.pack(">h", 32767)))
    print(list(struct.pack(">H", 0)), list(struct.pack(">H", 65535)))
    print(list(struct.pack(">i", -2147483648)), list(struct.pack(">i", 2147483647)))
    print(list(struct.pack(">I", 0)), list(struct.pack(">I", 4294967295)))
    print(list(struct.pack(">l", -2147483648)), list(struct.pack(">l", 2147483647)))
    print(list(struct.pack(">L", 0)), list(struct.pack(">L", 4294967295)))
    print(list(struct.pack(">q", -9223372036854775807)), list(struct.pack(">q", 9223372036854775807)))
    print(list(struct.pack(">Q", 0)), list(struct.pack(">Q", 9223372036854775807)))
    print(list(struct.pack("")))


main()
"""

ALIASES = r"""import struct as st
from struct import pack as spack, unpack as sunpack, calcsize as ssize, error as Serror


def main() -> None:
    n = 42
    print(list(st.pack(">I", n)), list(spack("<h", -n)))
    print(ssize(">Ihq"), st.calcsize("<2H"))
    a, b = sunpack(">Ih", spack(">Ih", n, -n))
    print(a, b)
    try:
        spack(">I", -1)
    except Serror as e:
        print(e)


main()
"""

REFUSALS = {
    "float_format": ("import struct\n\nprint(struct.pack('>f', 1.5))\n", "'f' is not built"),
    "native_order": ("import struct\n\nprint(struct.pack('@I', 1))\n", "native alignment (@)"),
    "struct_class": ("import struct\n\ns = struct.Struct('>I')\nprint(s.size)\n", "struct.Struct"),
    "unpack_from": ("import struct\n\nprint(struct.unpack_from('>I', b'\\x00\\x00\\x00\\x01'))\n", "struct.unpack_from"),
    "runtime_format": ("import struct\n\nfmt = '>I'\nprint(struct.pack(fmt, 1))\n", "string literal"),
    "repeat_count": ("import struct\n\nprint(struct.calcsize('>5000I'))\n", "repeat count over 4096"),
    "empty_unpack": ("import struct\n\nprint(struct.unpack('', b''))\n", "empty result is not built"),
}


def compile_python(directory, text, name, **env):
    source, exe = Path(directory, name + ".ail"), Path(directory, name)
    source.write_text(text, encoding="utf-8")
    built = subprocess.run([sys.executable, "-B", str(ROOT / "ail_chatgpt.py"), "compile", source.name,
                            "--syntax", "python", "-o", exe.name], cwd=directory, capture_output=True,
                           text=True, timeout=1800, env=dict(os.environ, **env))
    return built, source, exe


def values():
    out = []
    for seed in (2, 5, 9):
        rnd = random.Random(seed)
        out.append(" ".join(str(rnd.choice([0, 1, 7, 42, 100, 127])) for _ in range(8)) + "\n")
    out.append("0 1 127\n")
    return out



TEMPFILE_PROGRAM = r"""import os
import tempfile


class Holder:
    def __init__(self, prefix: str):
        self.prefix = prefix


def make(prefix: str, suffix: str, where: str) -> str:
    return tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=where)


def main() -> None:
    base = "tf-base"
    os.mkdir(base)
    print(tempfile.gettempprefix(), tempfile.gettempdirb().decode() == tempfile.gettempdir(),
          tempfile.gettempprefixb().decode(), tempfile.TMP_MAX)
    prefixes: list[str] = ["list-"]
    values: dict[str, str] = {"k": "dict-"}
    holder = Holder("attr-")
    names = []
    names.append((make("arg-", "-a", base), "arg-", "-a"))
    names.append((make(prefixes[0], "-l", base), "list-", "-l"))
    names.append((make(values["k"], "-d", base), "dict-", "-d"))
    names.append((make(holder.prefix, "-t", base), "attr-", "-t"))
    names.append((tempfile.mkdtemp("-p", "pos-", base), "pos-", "-p"))
    names.append((tempfile.mktemp(prefix="empty-", suffix="", dir=base), "empty-", ""))
    for name, prefix, suffix in names:
        base_name = os.path.basename(name)
        print(os.path.isdir(name), base_name.startswith(prefix),
              base_name.endswith(suffix) if suffix else True,
              len(base_name) == len(prefix) + 8 + len(suffix),
              os.path.dirname(name) == os.path.abspath(base))
    for name, _, _ in names[:5]:
        os.rmdir(name)
    td = tempfile.TemporaryDirectory(prefix="obj-", suffix="-s", dir=base)
    print(td.name.startswith(os.path.abspath(base) + "/obj-"), td.name.endswith("-s"),
          len(os.path.basename(td.name)) == 4 + 8 + 2, os.path.isdir(td.name))
    td.cleanup()
    td.cleanup()
    print(os.path.exists(td.name))
    with tempfile.TemporaryDirectory(prefix="with-", dir=base) as q:
        print(q.startswith(os.path.abspath(base) + "/with-"), os.path.isdir(q),
              len(os.path.basename(q)) == 5 + 8)
        os.mkdir(os.path.join(q, "nested"))
        with open(os.path.join(q, "nested", "x.txt"), "w") as f:
            f.write("x")
    print(os.path.exists(q))
    with tempfile.TemporaryDirectory(dir=base, delete=False) as kept:
        print(os.path.isdir(kept))
    print(os.path.isdir(kept))
    os.rmdir(kept)
    try:
        tempfile.mkdtemp(dir=os.path.join(base, "missing"))
    except FileNotFoundError as e:
        print(type(e).__name__)
    os.rmdir(base)


main()
"""


TEMPFILE_ALIASES = r"""import os
import tempfile as tf
from tempfile import TemporaryDirectory, mkdtemp, gettempdir, TMP_MAX


def main() -> None:
    base = "tf-alias"
    os.mkdir(base)
    p = mkdtemp(prefix="alias-", dir=base)
    print(os.path.isdir(p), os.path.basename(p).startswith("alias-"), len(os.path.basename(p)) == 6 + 8)
    q = tf.mkdtemp(prefix="mod-", dir=base)
    print(os.path.isdir(q), os.path.basename(q).startswith("mod-"), len(os.path.basename(q)) == 4 + 8)
    with TemporaryDirectory(prefix="ctx-", dir=base) as d:
        print(os.path.isdir(d), os.path.basename(d).startswith("ctx-"))
    print(os.path.exists(d), len(gettempdir()) > 0, TMP_MAX)
    os.rmdir(p)
    os.rmdir(q)
    os.rmdir(base)


main()
"""


TEMPFILE_REFUSALS = {
    "named_file": ("import tempfile\n\nprint(tempfile.NamedTemporaryFile().name)\n", "NamedTemporaryFile"),
    "mkstemp": ("from tempfile import mkstemp\n\nprint(mkstemp())\n", "mkstemp"),
    "temporary_file": ("import tempfile\n\nprint(tempfile.TemporaryFile())\n", "TemporaryFile"),
    "tempdir_value": ("import tempfile\n\nprint(tempfile.tempdir)\n", "tempfile.tempdir"),
}


class CompiledPrograms(unittest.TestCase):
    def check(self, name, text, inputs, ir, **env):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(env, AIL_IR="1" if ir else "0")
            built, source, exe = compile_python(directory, text, "p_" + name, **env)
            self.assertEqual(built.returncode, 0, "%s (AIL_IR=%s)\n%s%s" % (name, env["AIL_IR"], built.stdout, built.stderr))
            Path(directory, "oracle.py").write_text(text, encoding="utf-8")
            for k, stdin in enumerate(inputs):
                want = subprocess.run([sys.executable, "-X", "utf8", str(Path(directory, "oracle.py"))], input=stdin.encode(),
                                      capture_output=True, timeout=300)
                got = subprocess.run([str(exe)], input=stdin.encode(), capture_output=True, timeout=300)
                self.assertEqual(got.returncode, want.returncode, "%s input %d: %s" % (name, k, got.stderr[-300:]))
                self.assertEqual(got.stdout, want.stdout, "%s input %d (AIL_IR=%s)" % (name, k, env["AIL_IR"]))

    def test_struct_program_matches_cpython(self):
        for ir in (False, True):
            with self.subTest(path="default", ir=ir):
                self.check("struct", PROGRAM, values(), ir)
            with self.subTest(path="typed", ir=ir):
                self.check("struct_typed", PROGRAM, values(), ir, AIL_NO_GENERAL="1")

    def test_aliases_match_cpython(self):
        for ir in (False, True):
            with self.subTest(path="default", ir=ir):
                self.check("aliases", ALIASES, [""], ir)
            with self.subTest(path="typed", ir=ir):
                self.check("aliases_typed", ALIASES, [""], ir, AIL_NO_GENERAL="1")


    def test_tempfile_program_matches_cpython(self):
        for ir in (False, True):
            with self.subTest(path="default", ir=ir):
                self.check("tempfile", TEMPFILE_PROGRAM, [""], ir)
            with self.subTest(path="typed", ir=ir):
                self.check("tempfile_typed", TEMPFILE_PROGRAM, [""], ir, AIL_NO_GENERAL="1")

    def test_tempfile_aliases_match_cpython(self):
        for ir in (False, True):
            with self.subTest(path="default", ir=ir):
                self.check("tempfile_aliases", TEMPFILE_ALIASES, [""], ir)
            with self.subTest(path="typed", ir=ir):
                self.check("tempfile_aliases_typed", TEMPFILE_ALIASES, [""], ir, AIL_NO_GENERAL="1")


class Refusals(unittest.TestCase):
    def refused(self, text, wanted):
        with tempfile.TemporaryDirectory() as directory:
            built, _, exe = compile_python(directory, text, "refused")
            self.assertNotEqual(built.returncode, 0, "compiled but should be refused: " + wanted)
            self.assertIn(wanted, built.stdout + built.stderr)
            self.assertFalse(exe.exists())

    def test_refusals_name_the_use(self):
        for name, (text, wanted) in REFUSALS.items():
            with self.subTest(name):
                self.refused(text, wanted)

    def test_tempfile_refusals_name_the_use(self):
        for name, (text, wanted) in TEMPFILE_REFUSALS.items():
            with self.subTest(name):
                self.refused(text, wanted)


class UnchangedPrograms(unittest.TestCase):
    PLAIN = [
        "import sys\n\nprint(sys.stdin.read().strip())\n",
        "# a comment mentions struct and struct.pack only\nprint(1)\n",
        "structure = {'pack': 1}\nprint(structure['pack'])\n",
    ]

    def test_other_programs_keep_their_text(self):
        import structlib
        import tempfilelib
        for text in self.PLAIN:
            with self.subTest(text[:30]):
                notes = []
                self.assertEqual(structlib.rewrite_text(text, notes), text)
                self.assertEqual(notes, [])
        for text in self.PLAIN + ["# tempfile is only mentioned here\nprint(1)\n"]:
            with self.subTest(tempfile=text[:30]):
                notes = []
                self.assertEqual(tempfilelib.rewrite_text(text, notes), text)
                self.assertEqual(notes, [])


if __name__ == "__main__":
    unittest.main()
