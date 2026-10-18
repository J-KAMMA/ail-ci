"""G10: pathlib.Path, compared with CPython 3.12.

Every program below is ordinary Python. CPython runs it as the oracle (in a temp directory), the compiled
program runs in another temp directory, and the two must print the same bytes and exit with the same
status -- or the spelling is refused by name at compile time ("write instead:"); there is no third outcome
in which a path is accepted and then behaves differently.

* Pure path arithmetic: random operation scripts (Path(a, b), `/`, joinpath, with_name / with_stem /
  with_suffix, ==, repr, sorted order, name / stem / suffix / suffixes / parent / parts / root / anchor)
  over awkward strings (empty, ".", "..", "//", trailing separators, dots, non-ASCII, quotes) are read
  from stdin by one compiled program and printed next to CPython's answers.
* glob / rglob: random patterns (sets with ranges, negation, ']' first, stray '[', '**', '..', hidden
  files, trailing '/') over a directory holding awkward names, checked against CPython's fnmatch-based
  selectors, including the patterns on which CPython raises.
* File-system operations: random sequences of mkdir (parents, exist_ok), write / read text and bytes,
  unlink (missing_ok), rmdir, rename, replace, exists / is_file / is_dir, iterdir, glob, rglob, resolve,
  open("a") ... on a small universe of names; every step prints its result or the class of its exception.
* Scenario programs: classes holding paths, functions taking and returning Path and list[Path], `with
  p.open()`, `os` and `os.path` called with paths, the `import pathlib` spellings, error messages
  (general path: `print(e)`), symbolic links (resolve, loops, glob, rglob), permission errors.
* Refusals by name: everything outside the built surface, a path whose type the program text does not
  show, a Windows target, the iterator forms used as values.
* A program that does not import pathlib carries nothing of it.

Typed programs are built with AIL_NO_GENERAL=1 (the typed path must take them, AIL_IR=0 and 1); programs
that only the general path accepts are built by default and by `pyc.py --general-only`.
"""
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
PYC = str(ROOT / "python" / "pkg-v12" / "pyc.py")


def setUpModule():
    if sys.platform == "win32":
        raise unittest.SkipTest("pathlib is built for POSIX targets only (a Windows target is refused by name)")


def case_insensitive_file_system():
    with tempfile.TemporaryDirectory(prefix="ail-pathlib-") as tmp:
        (Path(tmp) / "x").write_text("x")
        return (Path(tmp) / "X").exists()


def oracle_env():
    env = dict(os.environ, PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    return env


def build(src, exe, ir, mode, extra=(), cwd=None):
    """mode: 'typed' (AIL_NO_GENERAL=1), 'default' (typed first, general fallback) or 'gonly' (pyc --general-only)."""
    env = dict(os.environ, AIL_IR=ir)
    env.pop("AIL_NO_GENERAL", None)
    env.pop("AIL_TARGET", None)
    if mode == "gonly":
        return subprocess.run([sys.executable, "-B", PYC, str(exe), "--file", str(src), "--general-only"], cwd=cwd,
                              capture_output=True, text=True, timeout=900, env=env)
    if mode == "typed":
        env["AIL_NO_GENERAL"] = "1"
    return subprocess.run([sys.executable, "-B", CLI, "compile", str(src), "-o", str(exe), *extra], cwd=cwd,
                          capture_output=True, text=True, timeout=900, env=env)


class Base(unittest.TestCase):
    def compare(self, name, text, mode="typed", irs=("0", "1"), inputs=(b"",), setup=None, rc=0):
        """CPython's stdout (and exit status) for the program equals the compiled program's, for every IR
        and every stdin in `inputs` (the program is built once per IR)."""
        with tempfile.TemporaryDirectory(prefix="ail-pathlib-") as tmp:
            src = Path(tmp) / (name + ".py")
            src.write_text(text, encoding="utf-8")
            wants = []
            for k, data in enumerate(inputs):
                work = Path(tmp) / ("oracle%d" % k) / "w"
                work.mkdir(parents=True)
                if setup:
                    setup(work)
                want = subprocess.run([sys.executable, str(src)], cwd=work, input=data, capture_output=True,
                                      timeout=300, env=oracle_env())
                self.assertEqual(want.returncode, rc, want.stderr.decode())
                wants.append(want)
            for ir in irs:
                exe = Path(tmp) / ("exe" + ir)
                built = build(src, exe, ir, mode, cwd=tmp)
                self.assertEqual(built.returncode, 0, "AIL_IR=%s: %s" % (ir, built.stderr[-3000:]))
                if mode == "default":
                    self.assertIn("general path", built.stderr)
                for k, data in enumerate(inputs):
                    work = Path(tmp) / ("run%s_%d" % (ir, k)) / "w"
                    work.mkdir(parents=True)
                    if setup:
                        setup(work)
                    got = subprocess.run([str(exe)], cwd=work, input=data, capture_output=True, timeout=300)
                    self.assertEqual(got.returncode, rc, got.stderr.decode())
                    want = wants[k]
                    if got.stdout != want.stdout:
                        a = want.stdout.decode("utf-8", "replace").split("\n")
                        b = got.stdout.decode("utf-8", "replace").split("\n")
                        for i in range(max(len(a), len(b))):
                            x = a[i] if i < len(a) else "<none>"
                            y = b[i] if i < len(b) else "<none>"
                            if x != y:
                                self.fail("%s AIL_IR=%s input %d line %d: CPython %r, AIL %r" % (mode, ir, k, i + 1, x[:300], y[:300]))
                    self.assertEqual(got.stdout, want.stdout)

    def refused(self, text, *needles, mode="typed", extra=()):
        with tempfile.TemporaryDirectory(prefix="ail-pathlib-") as tmp:
            src = Path(tmp) / "prog.py"
            src.write_text(text, encoding="utf-8")
            built = build(src, Path(tmp) / "exe", "1", mode, extra=extra, cwd=tmp)
            self.assertNotEqual(built.returncode, 0, built.stdout)
            self.assertFalse((Path(tmp) / "exe").exists())
            self.assertNotIn("Traceback", built.stderr)
            for needle in needles:
                self.assertIn(needle, built.stderr)
            return built.stderr


# ---------------------------------------------------------------------------------------- programs

SCENARIO = r'''from pathlib import Path


def show(p: Path) -> None:
    print(str(p), p.name, p.stem, p.suffix, p.parent, len(p.parts))


def walk_names(d: Path) -> list[str]:
    out: list[str] = []
    for q in sorted(d.iterdir()):
        out.append(q.name)
    return out


def lines(xs: list[str]) -> None:
    print("[" + "|".join(xs) + "]")


def main() -> None:
    root = Path("work")
    root.mkdir(parents=True, exist_ok=True)
    sub = root / "sub" / "deep"
    sub.mkdir(parents=True, exist_ok=True)
    f = root / "a.txt"
    n = f.write_text("héllo\nworld\n")
    print(n)
    print(f.read_text())
    (root / "b.bin").write_bytes(b"\x00\x01\xff")
    print(len((root / "b.bin").read_bytes()))
    show(f)
    show(Path("/"))
    show(Path("."))
    show(Path("a//b/./c/"))
    show(Path("/usr/lib/x.tar.gz"))
    show(Path("//x/y"))
    show(Path(".hidden"))
    show(Path("a.b.c"))
    print(f.exists(), f.is_file(), f.is_dir(), root.is_dir(), (root / "nope").exists())
    lines(walk_names(root))
    names: list[str] = []
    for p in root.glob("*.txt"):
        names.append(p.name)
    names.sort()
    lines(names)
    allf: list[str] = []
    for p in root.rglob("*"):
        allf.append(str(p))
    allf.sort()
    lines(allf)
    print(f.with_suffix(".md"), f.with_name("z.py"), f.with_stem("q"))
    print(Path("a/b") == Path("a//b/"), Path("a") != Path("b"))
    k = root
    k /= "x"
    k /= "y.txt"
    print(k)
    print(f"{k} and {k!r}")
    print(repr(k))
    lines(list(k.parts))
    for part in Path("/a/b/c").parts:
        print(part)
    print(Path("/a/b/c").parts[0], Path("a/b").parts[-1])
    print(Path("x").is_absolute(), Path("/x").is_absolute())
    g = root / "moved.txt"
    f.rename(g)
    print(f.exists(), g.exists())
    g.unlink()
    (root / "b.bin").unlink()
    try:
        g.unlink()
    except FileNotFoundError:
        print("fnf")
    g.unlink(missing_ok=True)
    try:
        (root / "nodir" / "x").write_text("x")
    except FileNotFoundError:
        print("fnf")
    try:
        sub.mkdir()
    except FileExistsError:
        print("exists")
    try:
        Path("zz/yy").mkdir()
    except FileNotFoundError:
        print("fnf")
    r = Path("work/../work/sub").resolve()
    print(r.name, r.is_absolute())
    names2: list[str] = []
    for p in Path("work").iterdir():
        names2.append(p.name)
    names2.sort()
    lines(names2)


main()
'''

MESSAGES = r'''import os
from pathlib import Path


def show(p: Path) -> None:
    print(str(p), p.name, p.stem, p.suffix, p.parent, len(p.parts))


def main() -> None:
    root = Path("work")
    root.mkdir(parents=True, exist_ok=True)
    sub = root / "sub" / "deep"
    sub.mkdir(parents=True, exist_ok=True)
    f = root / "a.txt"
    n = f.write_text("héllo\nworld\n")
    print(n)
    print(f.read_text())
    show(f)
    show(Path("/usr/lib/x.tar.gz"))
    names = sorted(p.name for p in root.glob("*"))
    print(names)
    allf = sorted([str(p) for p in root.rglob("*")])
    print(allf)
    print(sorted(root.iterdir()))
    print(f.with_suffix(".md"), f.with_name("z.py"), f.with_stem("q"))
    mixed = [1, "a", 2.5]
    print(mixed)
    try:
        (root / "nodir" / "x").write_text("x")
    except FileNotFoundError as e:
        print("fnf", e)
    try:
        sub.mkdir()
    except FileExistsError as e:
        print("exists", e)
    try:
        Path("zz/yy").mkdir()
    except FileNotFoundError as e:
        print("fnf", e)
    try:
        f.unlink()
        f.unlink()
    except FileNotFoundError as e:
        print("fnf", e)
    try:
        f.rename(root / "q" / "w")
    except FileNotFoundError as e:
        print("fnf", e)
    try:
        root.with_suffix("x")
    except ValueError as e:
        print("ve", e)
    try:
        Path("/").with_name("x")
    except ValueError as e:
        print("ve", e)
    try:
        root.with_name("a/b")
    except ValueError as e:
        print("ve", e)
    try:
        root.with_name("")
    except ValueError as e:
        print("ve", e)
    try:
        root.with_suffix("a/b")
    except ValueError as e:
        print("ve", e)
    try:
        Path("a").with_suffix(".")
    except ValueError as e:
        print("ve", e)
    try:
        root.read_text()
    except IsADirectoryError as e:
        print("isdir", e)
    (root / "plain").write_text("x")
    try:
        for q in (root / "plain").iterdir():
            print(q)
    except NotADirectoryError as e:
        print("notdir", e)
    try:
        (root / "plain" / "x").mkdir()
    except NotADirectoryError as e:
        print("notdir", e)
    try:
        (root / "plain").rmdir()
    except NotADirectoryError as e:
        print("notdir", e)
    try:
        root.rmdir()
    except OSError as e:
        print("oserr", e)
    try:
        root.unlink()
    except OSError as e:
        print("oserr", e)
    try:
        (root / "plain").write_text("again", encoding="ascii")
        (root / "plain").write_text("hé", encoding="ascii")
    except ValueError as e:
        print("ve", e)
    try:
        print(list(root.glob("")))
    except ValueError as e:
        print("ve", e)
    try:
        print(list(root.glob("/abs")))
    except RuntimeError as e:
        print("rt", e)
    try:
        print(list(root.glob("a**")))
    except ValueError as e:
        print("ve", e)
    try:
        print(list(root.glob(".")))
    except IndexError as e:
        print("ie", e)
    r = Path("work/../work/sub").resolve()
    print(r.name, r.is_absolute())
    print(os.path.exists(root), os.fspath(root / "a"))


main()
'''

CLASSES_TYPED = r'''import os
from pathlib import Path


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.count = 0

    def put(self, name: str, text: str) -> Path:
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        self.count += 1
        return target

    def listing(self) -> list[str]:
        out: list[str] = []
        for q in self.root.rglob("*"):
            if q.is_file():
                out.append(str(q))
        out.sort()
        return out


def make(base: Path, name: str) -> Path:
    return base / name / "leaf.txt"


def collect(base: Path) -> list[Path]:
    found: list[Path] = []
    for q in base.iterdir():
        if q.suffix == ".txt":
            found.append(q)
    return sorted(found)


def main() -> None:
    store = Store(Path("data"))
    a = store.put("one.txt", "1\n")
    b = store.put("sub/two.txt", "22\n")
    c = store.put("sub/deeper/three.log", "333\n")
    print(a, b, c)
    print(store.count)
    for line in store.listing():
        print(line)
    leaf = make(Path("data"), "x")
    print(leaf)
    leaf.parent.mkdir(parents=True)
    leaf.write_text("leaf")
    with leaf.open() as f:
        print(f.read())
    with (Path("data") / "log.txt").open("w") as g:
        g.write("hello\n")
        print("more", file=g)
    print((Path("data") / "log.txt").read_text())
    texts = collect(Path("data"))
    print(texts)
    print(len(texts), texts[0].name, texts[1].name)
    p = Path("data") / "sub"
    q = Path("data/sub")
    print(p == q, p != q, p is q)
    sizes = 0
    for t in collect(Path("data")):
        sizes += os.path.getsize(t)
        print(os.path.basename(t), os.path.exists(t))
    print(sizes)
    print(os.path.join(p, "z"))
    h = open(p / "two.txt")
    print(h.read())
    h.close()
    for line in (p / "two.txt").open():
        print(line, end="")
    cwd = Path.cwd()
    print(cwd.is_absolute(), cwd.name == os.path.basename(os.getcwd()))
    print(os.fspath(p))
    total = 0
    for ch in collect(Path("data")):
        total += len(ch.read_text())
    print(total)


main()
'''

CLASSES_GENERAL = r'''import os
from pathlib import Path


class Store:
    def __init__(self, root: Path):
        self.root = root
        self.count = 0

    def put(self, name: str, text: str) -> Path:
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        self.count += 1
        return target

    def listing(self) -> list[str]:
        return sorted(str(q) for q in self.root.rglob("*") if q.is_file())


def make(base: Path, name: str) -> Path:
    return base / name / "leaf.txt"


def collect(base: Path) -> list[Path]:
    return sorted([q for q in base.iterdir() if q.suffix == ".txt"])


def main() -> None:
    store = Store(Path("data"))
    a = store.put("one.txt", "1\n")
    b = store.put("sub/two.txt", "22\n")
    c = store.put("sub/deeper/three.log", "333\n")
    print(a, b, c)
    print(store.count, store.listing())
    leaf = make(Path("data"), "x")
    print(leaf)
    leaf.parent.mkdir(parents=True)
    leaf.write_text("leaf")
    with leaf.open() as f:
        print(f.read())
    with (Path("data") / "log.txt").open("w") as g:
        g.write("hello\n")
        print("more", file=g)
    print((Path("data") / "log.txt").read_text())
    texts = collect(Path("data"))
    print(texts)
    print(len(texts), texts[0].name, texts[1].name, [t.stem for t in texts])
    p = Path("data") / "sub"
    q = Path("data/sub")
    print(p == q, p != q, p is q)
    sizes = 0
    for t in collect(Path("data")):
        sizes += os.path.getsize(t)
        print(os.path.basename(t), os.path.exists(t))
    print(sizes)
    for root, dirs, files in os.walk(Path("data")):
        dirs.sort()
        print(root, sorted(files))
    print(os.path.join(p, "z"))
    h = open(p / "two.txt")
    print(h.read())
    h.close()
    cwd = Path.cwd()
    print(cwd.is_absolute(), cwd.name == os.path.basename(os.getcwd()))
    print(os.fspath(p), f"{p}", f"{texts}", f"{p!r}", str(texts))
    by_name = {t.name: len(t.read_text()) for t in texts}
    print(sorted(by_name.items()))
    print(any(t.suffix == ".txt" for t in texts), len([t for t in texts if t.exists()]))
    mixed = [1, "a", 2.5]
    print(mixed)


main()
'''

SPELLINGS = r'''import os
import pathlib
import pathlib as pl
from pathlib import Path as P


def tail(p: pathlib.Path) -> str:
    return p.name


def up(p: P) -> P:
    return p.parent


def main() -> None:
    a = pathlib.Path("x") / "y.txt"
    b = pl.Path("x", "y.txt")
    c = P("x/y.txt")
    print(a == b, b == c, a, tail(a), up(c))
    print(os.path.join(a, "z"))
    d = P("/") / "usr" / "lib"
    print(d, d.parts[-1], len(d.parts))
    paths: list[P] = []
    paths.append(a)
    paths.append(d)
    for q in paths:
        print(q.is_absolute(), q.suffix)
    print(paths)


main()
'''

PURE = r'''import sys
from pathlib import Path


def show(p: Path) -> None:
    print(str(p), "|", p.name, "|", p.stem, "|", p.suffix, "|", p.parent, "|", len(p.parts), "|", p.is_absolute(),
          "|", p.root, "|", p.anchor)
    for x in p.parts:
        print("[" + x + "]", end="")
    print()
    for s in p.suffixes:
        print("{" + s + "}", end="")
    print()


def main() -> None:
    data = sys.stdin.read()
    for line in data.split("\n"):
        if line == "":
            continue
        f = line.split("\t")
        op = f[0]
        if op == "new":
            show(Path(f[1]))
        elif op == "new2":
            show(Path(f[1], f[2]))
        elif op == "join":
            show(Path(f[1]) / f[2])
        elif op == "join3":
            show(Path(f[1]) / f[2] / f[3])
        elif op == "joinpath":
            show(Path(f[1]).joinpath(f[2], f[3]))
        elif op == "pjoin":
            show(Path(f[1]) / Path(f[2]))
        elif op == "with_name":
            try:
                show(Path(f[1]).with_name(f[2]))
            except ValueError:
                print("ValueError")
        elif op == "with_stem":
            try:
                show(Path(f[1]).with_stem(f[2]))
            except ValueError:
                print("ValueError")
        elif op == "with_suffix":
            try:
                show(Path(f[1]).with_suffix(f[2]))
            except ValueError:
                print("ValueError")
        elif op == "eq":
            a = Path(f[1])
            b = Path(f[2])
            print(a == b, a != b, a == Path(f[1]))
        elif op == "repr":
            a = Path(f[1])
            print(repr(a), f"{a!r}", f"{a}", a.as_posix())
        elif op == "sorted":
            ps: list[Path] = []
            for item in f[1:]:
                ps.append(Path(item))
            ordered = sorted(ps)
            for q in ordered:
                print(q, end=" ")
            print()
            back = sorted(ps, reverse=True)
            for q in back:
                print(q, end=" ")
            print()
            print(ordered)
            print(f"{back}")
        elif op == "absolute":
            print(Path(f[1]).is_absolute())


main()
'''

GLOB = r'''import sys
from pathlib import Path


def put(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")


def run(base: Path, pat: str, mode: int) -> None:
    out: list[str] = []
    try:
        if mode == 0:
            for q in base.glob(pat):
                out.append(str(q))
        else:
            for q in base.rglob(pat):
                out.append(str(q))
    except ValueError:
        print("ValueError")
        return
    except IndexError:
        print("IndexError")
        return
    out.sort()
    print(len(out), "|".join(out))


def main() -> None:
    base = Path("g")
    names = ["a", "ab", "abc", "b", "ba", "a.b", "a.txt", "b.txt", ".hidden", ".a.txt", "A", "B.TXT", "[x]",
             "a-b", "a]b", "a[b", "a?b", "a*b", "é", "éa", "x y", "-", "--", "!", "^", "\\", "d1/a.txt", "d1/b.py",
             "d1/sub/c.txt", "d1/sub/.d", "d2/a", "d2/ab/abc", ".dh/a", "e.d/z.txt", "a.b.c", "ab.", "a b c"]
    for n in names:
        put(base / n)
    data = sys.stdin.read()
    for pat in data.split("\n"):
        if pat == "":
            continue
        print("pattern", pat)
        run(base, pat, 0)
        run(base, pat, 1)
        run(base, "**/" + pat, 0)
        run(base, pat + "/", 0)
        run(base, "d1/" + pat, 0)


main()
'''

SYMLINKS = r'''from pathlib import Path


def rel(p: Path) -> str:
    return str(p).replace(str(Path.cwd()), "CWD")


def probe(name: str) -> None:
    p = Path(name)
    print(name, p.exists(), p.is_file(), p.is_dir())
    try:
        print("  ->", rel(p.resolve()))
    except RuntimeError:
        print("  -> loop")


def listing(ps: list[Path]) -> None:
    names: list[str] = []
    for q in ps:
        names.append(str(q))
    names.sort()
    print(len(names), "|".join(names))


def main() -> None:
    for name in ["real", "real/a.txt", "link_dir", "link_file", "broken", "loop1", "loop2", "abslink", "chain1",
                 "chain2", "link_dir/sub", "link_dir/sub/../a.txt", "real/../link_dir/a.txt", "nothing/at/all",
                 "link_file/x", "rel_up", "dirlink2"]:
        probe(name)
    listing(list(Path(".").glob("*")))
    listing(list(Path(".").rglob("*")))
    listing(list(Path(".").glob("**")))
    listing(list(Path(".").glob("**/a.txt")))
    listing(list(Path("link_dir").glob("*")))
    listing(list(Path("link_dir").rglob("*.txt")))
    listing(list(Path("real").glob("*/")))
    listing(list(Path(".").glob("*/")))
    listing(list(Path(".").iterdir()))
    print(Path("link_file").read_text(), Path("chain1").read_text())
    try:
        Path("broken").read_text()
    except FileNotFoundError:
        print("fnf")
    try:
        Path("loop1").read_text()
    except OSError:
        print("oserr")
    Path("link_file").unlink()
    print(Path("link_file").exists(), Path("real/a.txt").exists())


main()
'''


def symlink_setup(work):
    (work / "real" / "sub").mkdir(parents=True)
    (work / "real" / "a.txt").write_text("A\n")
    (work / "real" / "sub" / "b.txt").write_text("B\n")
    os.symlink("real", work / "link_dir")
    os.symlink("real/a.txt", work / "link_file")
    os.symlink("nowhere", work / "broken")
    os.symlink("loop2", work / "loop1")
    os.symlink("loop1", work / "loop2")
    os.symlink(str(work / "real"), work / "abslink")
    os.symlink("chain2", work / "chain1")
    os.symlink("real/sub/../a.txt", work / "chain2")
    os.symlink("link_dir/../real", work / "rel_up")
    os.symlink("abslink", work / "dirlink2")


TEXT_AND_BINARY = r'''from pathlib import Path


def show_lines(text: str) -> None:
    for part in text.split("\n"):
        print("<" + part + ">", end="")
    print()


def show_bytes(b: bytes) -> None:
    for x in b:
        print(x, end=" ")
    print()


def main() -> None:
    d = Path("io")
    d.mkdir()
    a = d / "a.txt"
    print(a.write_text("one\ntwo\r\nthree\rfour", newline="\r\n"))
    print(len(a.read_bytes()))
    show_lines(a.read_text())
    print(a.write_text("caf\u00e9 \u3042", encoding="latin-1", errors="replace"))
    show_bytes(a.read_bytes())
    print(a.read_text(encoding="latin-1"))
    print(a.write_text("caf\u00e9", encoding="ascii", errors="ignore"))
    show_bytes(a.read_bytes())
    b = d / "b.bin"
    buf = bytearray()
    for i in range(20000):
        buf.append(i % 251)
    data = bytes(buf)
    print(b.write_bytes(data))
    got = b.read_bytes()
    print(len(got), got == data, got[8191], got[8192])
    with b.open("rb") as f:
        head = f.read(5)
        show_bytes(head)
        print(f.tell())
    with b.open("ab") as f:
        f.write(b"tail")
    print(len(b.read_bytes()))
    try:
        b.read_text()
    except UnicodeDecodeError:
        print("decode error")
    try:
        with a.open("x") as f:
            f.write("no")
    except FileExistsError:
        print("exists")
    with a.open("w", encoding="utf-8") as f:
        f.write("line1\nline2\n")
        f.write("line3")
    for line in a.open():
        print(f"{line!r}")
    with a.open("r+") as f:
        print(f.read(3))
        f.seek(0)
        f.write("LINE")
    print(a.read_text())
    n = 0
    for chunk in a.read_text().splitlines():
        n += len(chunk)
    print(n)
    big = d / "big.txt"
    print(big.write_text("x" * 100000 + "\n" + "y" * 10))
    print(len(big.read_text()), len(big.read_text().split("\n")[0]))
    e = d / "empty"
    print(e.write_text(""), f"{e.read_text()!r}")


main()
'''


PERMISSIONS = r'''import os
from pathlib import Path


def main() -> None:
    d = Path("locked")
    d.mkdir()
    (d / "f.txt").write_text("x")
    os.chmod(d, 0)
    try:
        print((d / "f.txt").exists())
    except PermissionError:
        print("perm exists")
    try:
        print((d / "f.txt").is_file(), (d / "f.txt").is_dir())
    except PermissionError:
        print("perm is_file")
    try:
        for q in d.iterdir():
            print(q)
    except PermissionError:
        print("perm iterdir")
    try:
        print(len(list(d.glob("*"))))
    except PermissionError:
        print("perm glob")
    try:
        (d / "g.txt").write_text("y")
    except PermissionError:
        print("perm write")
    try:
        d.rmdir()
        print("removed")
    except OSError:
        print("oserr rmdir")
    os.chmod(d, 448)
    (d / "f.txt").unlink()
    d.rmdir()
    print(d.exists())
    ro = Path("ro.txt")
    ro.write_text("x")
    os.chmod(ro, 256)
    try:
        ro.write_text("y")
    except PermissionError:
        print("perm ro")
    print(ro.read_text())
    os.chmod(ro, 420)
    ro.unlink()


main()
'''


class ScenarioTests(Base):
    def test_scenario_typed(self):
        self.compare("scenario", SCENARIO)

    def test_classes_lists_and_os_typed(self):
        self.compare("classes", CLASSES_TYPED)

    def test_import_spellings_typed(self):
        self.compare("spellings", SPELLINGS, irs=("1",))

    def test_error_messages_and_comprehensions_general(self):
        self.compare("messages", MESSAGES, mode="default", irs=("1",))
        self.compare("messages_g", MESSAGES, mode="gonly", irs=("1",))

    def test_classes_lists_and_os_general(self):
        self.compare("classes_g", CLASSES_GENERAL, mode="default", irs=("1",))
        self.compare("classes_go", CLASSES_GENERAL, mode="gonly", irs=("1",))

    def test_text_and_binary_io_typed(self):
        self.compare("textio", TEXT_AND_BINARY)

    def test_symbolic_links_typed(self):
        self.compare("links", SYMLINKS, irs=("1",), setup=symlink_setup)

    def test_symbolic_links_general(self):
        self.compare("links_g", SYMLINKS, mode="gonly", irs=("1",), setup=symlink_setup)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores permission bits")
    def test_permission_errors(self):
        self.compare("perms", PERMISSIONS, irs=("1",))
        self.compare("perms_g", PERMISSIONS, mode="gonly", irs=("1",))


# ------------------------------------------------------------------------------------------ fuzz

PIECES = ["", ".", "..", "a", "b", "c.txt", "x.tar.gz", ".hidden", "...", "a.", ".b.", "é", "ü.py", "sp ace",
          "a-b", "z", "d.e.f", "[x]", "*", "q'q", 'q"q', "tab\\t"]
SEPS = ["/", "/", "/", "//", "/./", "///", "/"]


def pure_input(seed, count):
    rng = random.Random(seed)

    def rpath():
        k = rng.choice([0, 1, 1, 2, 2, 3, 4, 5])
        out = ""
        if rng.random() < 0.35:
            out = rng.choice(["/", "//", "///", "/"])
        parts = [rng.choice(PIECES) for _ in range(k)]
        for i, piece in enumerate(parts):
            out += piece
            if i < len(parts) - 1:
                out += rng.choice(SEPS)
        if rng.random() < 0.15:
            out += "/"
        return out

    def rname():
        return rng.choice(PIECES + ["x/y", "a/", "/", "", ".", "..", "n.m", "k.tar.gz", "ü"])

    def rsuffix():
        return rng.choice(["", ".", ".py", "py", ".txt", ".tar.gz", "a/b", "/", ".é", "..", ".a.b", "x", " "])

    lines = []
    for _ in range(count):
        op = rng.choice(["new", "new", "new", "new2", "join", "join3", "joinpath", "pjoin", "with_name", "with_stem",
                         "with_suffix", "eq", "repr", "sorted", "absolute"])
        if op == "new":
            lines.append("new\t" + rpath())
        elif op == "new2":
            lines.append("new2\t%s\t%s" % (rpath(), rpath()))
        elif op in ("join", "pjoin"):
            lines.append("%s\t%s\t%s" % (op, rpath(), rpath()))
        elif op in ("join3", "joinpath"):
            lines.append("%s\t%s\t%s\t%s" % (op, rpath(), rpath(), rpath()))
        elif op == "with_name":
            lines.append("with_name\t%s\t%s" % (rpath(), rname()))
        elif op == "with_stem":
            lines.append("with_stem\t%s\t%s" % (rpath(), rname()))
        elif op == "with_suffix":
            lines.append("with_suffix\t%s\t%s" % (rpath(), rsuffix()))
        elif op == "eq":
            a = rpath()
            lines.append("eq\t%s\t%s" % (a, a if rng.random() < 0.4 else rpath()))
        elif op == "repr":
            lines.append("repr\t" + rpath())
        elif op == "sorted":
            lines.append("sorted\t" + "\t".join(rpath() for _ in range(rng.randint(0, 6))))
        else:
            lines.append("absolute\t" + rpath())
    return ("\n".join(lines) + "\n").encode("utf-8")


GLOB_LIT = list("abcAB.-!^ x") + ["é", "]", "\\", "d", "1"]
GLOB_SETS = ["[ab]", "[!ab]", "[a-b]", "[^a]", "[]a]", "[!]a]", "[a-]", "[-a]", "[a-c-e]", "[b-a]", "[\\]", "[a\\]", "[!a-b]",
             "[ab-]", "[A-Za-z]", "[0-9]", "[.]", "[a-a]", "[]]", "[!]]", "[^]", "[!]", "[]", "[[]", "[[]x]", "[x]",
             "[a-bx-z]", "[é]", "[a-é]", "[-]", "[--a]", "[a--]", "[a-b-]", "[!-]", "[!--]"]


def glob_input(seed, count):
    rng = random.Random(seed)

    def tok():
        r = rng.random()
        if r < 0.35:
            return rng.choice(GLOB_LIT)
        if r < 0.55:
            return rng.choice(GLOB_SETS)
        if r < 0.8:
            return rng.choice(["*", "?"])
        if r < 0.85:
            return "["
        if r < 0.9:
            return "]"
        return rng.choice(GLOB_LIT)

    lines = set()
    while len(lines) < count:
        pat = "".join(tok() for _ in range(rng.randint(1, 5)))
        if rng.random() < 0.12:
            pat = rng.choice(["*", "d1", ".*", "d*", "**", "d1/*", "*/*", "*/sub", "..", "../g", "./*", "a/..", "*/.."]) + (
                "/" + pat if rng.random() < 0.5 else "")
        if "\n" in pat or pat.startswith("/") or all(c in ("", ".") for c in pat.split("/")):
            continue
        lines.add(pat)
    return ("\n".join(sorted(lines)) + "\n").encode("utf-8")


FS_DIRS = ["d1", "d2", "d1/x", "d1/x/y", "d2/z", "d3"]
FS_FILES = ["f1.txt", "d1/f2.txt", "d1/x/f3.py", "d2/f4.txt", "f5.bin", "d1/x/y/f6.txt", "d3/g.md", "d2/z/h.txt"]
FS_ALL = FS_DIRS + FS_FILES + ["", ".", "nope", "nope/deeper", "f1.txt/inner", "d1/../d2", "./d1//x/", "d9/q"]
FS_PATTERNS = ["*", "*.txt", "d*", "*/*", "**/*.txt", "**", "*/", "x*", "?", "f?.*", "[df]*", "**/*", "../*", "*.py", "**/y"]
FS_HEAD = '''import os
from pathlib import Path


def show_paths(ps: list[Path]) -> None:
    names: list[str] = []
    for q in ps:
        names.append(str(q))
    names.sort()
    print(len(names), "|".join(names))


'''
FS_HANDLERS = '''    except FileNotFoundError:
        print("FNF")
    except FileExistsError:
        print("EXISTS")
    except IsADirectoryError:
        print("ISDIR")
    except NotADirectoryError:
        print("NOTDIR")
    except OSError:
        print("OSERR")
    except ValueError:
        print("VALUE")
'''


def fs_program(seed, count, binary=True):
    """A random sequence of path operations, one small function each, printing the result or the exception class."""
    rng = random.Random(seed)
    ops = []

    def emit(tag, body):
        n = len(ops) + 1
        text = "def op%d() -> None:\n    print(\"%d %s\")\n    try:\n" % (n, n, tag)
        text += "".join("        %s\n" % line for line in body)
        text += FS_HANDLERS
        ops.append(text)

    def pth(name):
        return "Path(%r)" % name

    for i in range(count):
        op = rng.choice(["mkdir", "mkdir", "write", "write", "write_bytes", "read", "read_bytes", "unlink", "rmdir", "rename",
                         "replace", "exists", "list", "glob", "rglob", "iterdir", "resolve", "attrs", "append", "join"])
        name = rng.choice(FS_ALL)
        if not binary and op in ("write_bytes", "read_bytes"):
            op = "write"
        if op == "mkdir":
            parents = rng.choice(["", "parents=True", "exist_ok=True", "parents=True, exist_ok=True"])
            emit("mkdir", ["%s.mkdir(%s)" % (pth(name), parents), "print(\"ok\")"])
        elif op == "write":
            emit("write", ["n = %s.write_text(%r)" % (pth(name), "t%dé\n" % i), "print(n)"])
        elif op == "write_bytes":
            emit("write_bytes", ["n = %s.write_bytes(%r)" % (pth(name), bytes([i % 256, 0, 255])), "print(n)"])
        elif op == "read":
            emit("read", ["s = %s.read_text()" % pth(name), "print(len(s), s)"])
        elif op == "read_bytes":
            emit("read_bytes", ["b = %s.read_bytes()" % pth(name), "print(len(b))"])
        elif op == "unlink":
            emit("unlink", ["%s.unlink(%s)" % (pth(name), rng.choice(["", "missing_ok=True", "True"])), "print(\"ok\")"])
        elif op == "rmdir":
            emit("rmdir", ["%s.rmdir()" % pth(name), "print(\"ok\")"])
        elif op in ("rename", "replace"):
            target = rng.choice(FS_ALL)
            emit(op, ["r = %s.%s(%s)" % (pth(name), op, pth(target) if rng.random() < 0.6 else repr(target)), "print(r)"])
        elif op == "exists":
            emit("exists", ["p = %s" % pth(name), "print(p.exists(), p.is_file(), p.is_dir())"])
        elif op == "list":
            emit("iterdir", ["show_paths(list(%s.iterdir()))" % pth(name)])
        elif op == "iterdir":
            emit("iterdir_loop", ["c = 0", "for q in %s.iterdir():" % pth(name), "    c += len(q.name)", "print(c)"])
        elif op == "glob":
            emit("glob", ["show_paths(list(%s.glob(%r)))" % (pth(name), rng.choice(FS_PATTERNS))])
        elif op == "rglob":
            emit("rglob", ["show_paths(list(%s.rglob(%r)))" % (pth(name), rng.choice(FS_PATTERNS))])
        elif op == "resolve":
            emit("resolve", ["r = %s.resolve()" % pth(name), "print(str(r).replace(str(Path.cwd()), \"CWD\"))"])
        elif op == "attrs":
            emit("attrs", ["p = %s" % pth(name),
                           "print(p, p.name, p.stem, p.suffix, p.parent, p.parent.parent, p.with_suffix(\".q\"))"])
        elif op == "append":
            emit("append", ["with %s.open(\"a\") as f:" % pth(name), "    f.write(%r)" % ("a%d" % i), "print(\"ok\")"])
        else:
            emit("join", ["p = %s / %r / %s" % (pth(name), rng.choice(["x", "y.txt", "..", ".", ""]),
                                                 pth(rng.choice(["z", "w/v", "/abs"]))), "print(p)"])
    main = "def main() -> None:\n" + "".join("    op%d()\n" % (k + 1) for k in range(len(ops))) + "\n\nmain()\n"
    return FS_HEAD + "\n\n".join(ops) + "\n\n" + main


class FuzzTests(Base):
    def test_path_arithmetic_fuzz(self):
        inputs = [pure_input(seed, 400) for seed in (1, 2, 3, 4)]
        self.compare("pure", PURE, irs=("1",), inputs=inputs)

    def test_path_arithmetic_fuzz_ir0(self):
        self.compare("pure0", PURE, irs=("0",), inputs=[pure_input(5, 300)])

    def test_path_arithmetic_fuzz_general(self):
        self.compare("pure_g", PURE, mode="gonly", irs=("1",), inputs=[pure_input(6, 300)])

    @unittest.skipIf(case_insensitive_file_system(), "the glob names differ only in case")
    def test_glob_fuzz(self):
        inputs = [glob_input(seed, 250) for seed in (1, 2, 3)]
        self.compare("glob", GLOB, irs=("1",), inputs=inputs)

    @unittest.skipIf(case_insensitive_file_system(), "the glob names differ only in case")
    def test_glob_fuzz_general(self):
        self.compare("glob_g", GLOB, mode="gonly", irs=("1",), inputs=[glob_input(4, 150)])

    def test_file_system_operations_fuzz(self):
        for seed in (1, 2, 3):
            self.compare("fs%d" % seed, fs_program(seed, 45), irs=("1",))

    def test_file_system_operations_fuzz_ir0(self):
        self.compare("fs0", fs_program(9, 40), irs=("0",))

    def test_file_system_operations_fuzz_general(self):
        for seed in (4, 5):
            self.compare("fsg%d" % seed, fs_program(seed, 40, binary=False), mode="gonly", irs=("1",))


# ---------------------------------------------------------------------------------- refusals

class RefusalTests(Base):
    def one(self, body, *needles, mode="typed"):
        text = "from pathlib import Path\n\n\ndef main() -> None:\n    p = Path(\"a\")\n    q = Path(\"b\")\n" + \
            "".join("    " + line + "\n" for line in body.split("\n")) + "\n\nmain()\n"
        return self.refused(text, "write instead:", *needles, mode=mode)

    def test_methods_and_attributes_that_are_not_built(self):
        self.one("print(p.stat())", "Path.stat()", "os.path.getsize")
        self.one("p.touch()", "Path.touch()")
        self.one("print(p.parents)", "Path.parents")
        self.one("print(p.relative_to(q))", "relative_to")
        self.one("print(p.is_symlink())", "is_symlink")
        self.one("p.chmod(0o600)", "chmod")
        self.one("print(Path.home())", "home")
        self.one("print(p.samefile(q))", "samefile")
        self.one("print(p.expanduser())", "expanduser")
        self.one("print(p.readlink())", "readlink")
        self.one("print(p.as_uri())", "as_uri")
        self.one("print(p.match(\"*.py\"))", "match")
        self.one("print(p.owner())", "owner")

    def test_arguments_that_are_not_built(self):
        self.one("print(p.resolve(strict=True))", "strict=True")
        self.one("print(list(p.glob(\"*\", case_sensitive=False)))", "case_sensitive")
        self.one("print(p.exists(follow_symlinks=False))", "follow_symlinks")
        self.one("p.mkdir(0o755, True, True, 1)", "at most 3 arguments")
        self.one("print(p.read_text(\"utf-8\", \"strict\", 3))", "at most 2 arguments")
        self.one("print(p.with_suffix())", "missing required argument")

    def test_tuples_iterators_and_collections_of_paths(self):
        self.one("print(p.parts)", "p.parts is a tuple")
        self.one("print(tuple(p.parts))", "p.parts is a tuple")
        self.one("a, b = p.parts", "p.parts is a tuple")
        self.one("print(p.parts[0:1])", "slice of p.parts")
        self.one("it = p.iterdir()\nprint(next(it))", "is an iterator in CPython")
        self.one("it = p.glob(\"*\")", "is an iterator in CPython")
        self.one("print(p.iterdir())", "generator")
        self.one("print(max(p.iterdir()))", "max() of paths")
        self.one("d = {p: 1}", "")
        self.one("s = {p, q}", "")
        self.one("print(p < q)", "comparison of a path")
        self.one("print(p == \"a\")", "comparison of a path")
        self.one("print(p in [q])", "comparison of a path")
        self.one("print(\"%s\" % p)", "% formatting of a path")
        self.one("print(f\"{p:>10}\")", "format spec on a path")
        self.one("print(sorted([p, q], key=str))", "sorted(paths, key=")
        self.one("xs = [p, q]\nxs.sort()", "list.sort()")
        self.one("print(isinstance(p, Path))", "isinstance")
        self.one("x = Path", "class Path used as a value")

    def test_annotations_that_hold_paths_in_unsupported_ways(self):
        text = "from pathlib import Path\n\n\ndef f(d: dict[str, Path]) -> int:\n    return len(d)\n\n\nprint(f({}))\n"
        self.refused(text, "write instead:", "dict key, a set member or a tuple element")
        text = "from pathlib import Path\n\n\ndef f(d: tuple[Path, int]) -> int:\n    return 1\n\n\nprint(f((Path('a'), 1)))\n"
        self.refused(text, "write instead:")

    def test_imports_that_are_not_built(self):
        for name in ("PurePath", "PurePosixPath", "PureWindowsPath", "PosixPath", "WindowsPath"):
            self.refused("from pathlib import %s\n\nprint(1)\n" % name, "write instead: Path")
        self.refused("from pathlib import Path, PurePath\n\nprint(1)\n", "pathlib.PurePath is not built")
        self.refused("from pathlib import *\n\nprint(1)\n", "from pathlib import *")
        self.refused("import pathlib.foo\n\nprint(1)\n", "is not built")
        self.refused("def f() -> int:\n    from pathlib import Path\n    return 1\n\nprint(f())\n", "top of the file")

    def test_a_path_the_program_text_does_not_show_is_refused(self):
        text = "from pathlib import Path\n\n\ndef child(p, name):\n    return p / name\n\n\nprint(child(Path('a'), 'b'))\n"
        self.refused(text, "write instead: annotate it", "child(p: Path")
        text = "from pathlib import Path\n\n\ndef make(name: str):\n    return Path(name) / 'x'\n\n\nprint(make('a'))\n"
        self.refused(text, "write instead: def make(...) -> Path:")
        text = "from pathlib import Path\n\n\ndef make(name: str) -> list[Path]:\n    return [Path(name)]\n\n\nprint(len(make('a')))\n"
        self.compare_ok(text)
        text = "from pathlib import Path\n\n\ndef f(p: str) -> str:\n    return p\n\n\nprint(f(Path('a')))\n"
        self.refused(text, "write instead: annotate it")

    def compare_ok(self, text):
        self.compare("ok", text, irs=("1",))

    def test_windows_target(self):
        zig = os.environ.get("AIL_ZIG") or shutil.which("zig") or str(Path.home() / "tools" / "zig" / "zig")
        text = "from pathlib import Path\n\nprint(Path('a') / 'b')\n"
        env_target = dict(os.environ, AIL_TARGET="windows", AIL_NO_GENERAL="1")
        with tempfile.TemporaryDirectory(prefix="ail-pathlib-") as tmp:
            src = Path(tmp) / "w.py"
            src.write_text(text, encoding="utf-8")
            built = subprocess.run([sys.executable, "-B", CLI, "compile", str(src), "-o", str(Path(tmp) / "w.exe"),
                                    "--target", "windows"], capture_output=True, text=True, timeout=900, env=env_target)
            self.assertNotEqual(built.returncode, 0)
            self.assertIn("pathlib is built for POSIX targets only", built.stderr)
            self.assertIn("write instead: os.path", built.stderr)
            self.assertNotIn("Traceback", built.stderr)


# ------------------------------------------------------------------------------- isolation

class IsolationTests(Base):
    def c_of(self, text, mode="typed"):
        with tempfile.TemporaryDirectory(prefix="ail-pathlib-") as tmp:
            src = Path(tmp) / "prog.py"
            src.write_text(text, encoding="utf-8")
            dbg = Path(tmp) / "dbg"
            built = build(src, Path(tmp) / "exe", "1", mode, extra=("--debug-dir", str(dbg)), cwd=tmp)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            return (dbg / "program.c").read_text(encoding="utf-8")

    def test_a_program_without_pathlib_carries_none_of_it(self):
        for text in ("def main() -> None:\n    print(len(\"abc\"))\n\n\nmain()\n",
                     "import os\n\n\ndef main() -> None:\n    print(os.path.exists(\".\"), os.getcwd() != \"\")\n\n\nmain()\n"):
            c = self.c_of(text)
            for marker in ("AILPATH_CORE_H", "ailf_readlink", "ailt_pp_", "ailf_stat_errno", "_AilPath"):
                self.assertNotIn(marker, c)

    def test_a_pathlib_program_carries_the_path_core_only_when_it_reaches_it(self):
        plain = self.c_of("from pathlib import Path\n\n\ndef main() -> None:\n    print(Path(\"a/b.txt\").suffix)\n\n\nmain()\n")
        self.assertNotIn("AILPATH_CORE_H", plain)
        self.assertNotIn("AILPROC_CORE_H", plain)
        resolving = self.c_of("from pathlib import Path\n\n\ndef main() -> None:\n    print(Path(\"a\").resolve().is_absolute())\n\n\nmain()\n")
        self.assertIn("AILPATH_CORE_H", resolving)
        self.assertNotIn("AILPROC_CORE_H", resolving)

    def test_the_general_runtime_carries_the_path_core_only_when_it_reaches_it(self):
        text = "from pathlib import Path\n\n\ndef main() -> None:\n    print(Path(\"a/b.txt\").suffix)\n    print([1, \"a\"])\n\n\nmain()\n"
        with tempfile.TemporaryDirectory(prefix="ail-pathlib-") as tmp:
            src = Path(tmp) / "g.py"
            src.write_text(text, encoding="utf-8")
            built = build(src, Path(tmp) / "exe", "1", "gonly", cwd=tmp)
            self.assertEqual(built.returncode, 0, built.stderr[-2000:])
            got = subprocess.run([str(Path(tmp) / "exe")], capture_output=True, timeout=60)
            self.assertEqual(got.stdout.decode(), ".txt\n[1, 'a']\n")


if __name__ == "__main__":
    unittest.main()
