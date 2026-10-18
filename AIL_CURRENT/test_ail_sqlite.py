"""G11: `import sqlite3` in a compiled program, compared with CPython 3.12's own sqlite3 module.

The compiled program links the system libsqlite3 (and only a program that imports sqlite3 does), CPython links
the same library, so every byte has to agree. The programs below are ordinary Python; CPython runs the very
same text as the oracle (`str(e)` of an error is built on the typed path).

* Scenario programs: the transaction rules of 3.12 (implicit BEGIN before insert / update / delete / replace,
  DDL and SELECT leave the transaction alone, rollback, `with conn:`), rowcount and lastrowid, the wording of
  every error and the exception class it gets, parameters (qmark, named, held in a variable), NULL, large
  integers, floats, unicode text and blobs, executemany / executescript, cursor reuse, classes holding
  connections.
* Randomised programs: a generator writes a program from a seed (random schema over INTEGER / REAL / TEXT /
  BLOB columns, NULLable or not, UNIQUE or not; random inserts through SQL text, qmark, named and executemany;
  updates, deletes, filters on NULL, aggregates, constraint violations, rollbacks and commits), the same text
  is run by CPython and by the compiled program, and the output must be identical.
* Files: a database on disk survives close and reopen; an unopenable path says why.
* The declared row shape is checked at run time (RuntimeError, a declared difference).
* Refusals by name for everything outside the built surface.
* A program that does not import sqlite3 carries nothing of it: no sqlite C, no -lsqlite3.

Typed programs are built with AIL_NO_GENERAL=1 (the typed path must take them).
The module skips with a reason where libsqlite3 (the header and the library) or CPython's _sqlite3 is missing.
"""
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLI = str(ROOT / "ail_chatgpt.py")
CC = os.environ.get("PIPE_CC") or shutil.which("cc") or shutil.which("gcc")


def missing_reason():
    """Why this module cannot run here, or None."""
    try:
        import sqlite3  # noqa: F401  (the oracle)
    except ImportError:
        return "CPython's sqlite3 module (the oracle) is not available"
    if not CC:
        return "no C compiler"
    probe = '#include <sqlite3.h>\nint main(void) { return sqlite3_libversion_number() > 0 ? 0 : 1; }\n'
    with tempfile.TemporaryDirectory(prefix="ail-sqlite-probe-") as tmp:
        source = Path(tmp) / "probe.c"
        source.write_text(probe)
        done = subprocess.run([CC, str(source), "-o", str(Path(tmp) / "probe"), "-lsqlite3"], capture_output=True, text=True)
        if done.returncode:
            return "libsqlite3 development files (sqlite3.h and -lsqlite3) are not installed for the C compiler"
        try:
            ran = subprocess.run([str(Path(tmp) / "probe")], capture_output=True, text=True, timeout=30)
        except OSError:
            return "a program linked with -lsqlite3 cannot run here"
        if ran.returncode:
            return "libsqlite3 does not initialise here"
    return None


def setUpModule():
    reason = missing_reason()
    if reason:
        raise unittest.SkipTest(reason)


def compile_program(directory, name, text, *flags, env_extra=None):
    path = Path(directory) / (name + ".py")
    path.write_text(text, encoding="utf8")
    out = Path(directory) / (name + ".out")
    if out.exists():
        out.unlink()
    env = dict(os.environ, AIL_NO_GENERAL="1")
    env.pop("PYTHONPATH", None)
    env.update(env_extra or {})
    done = subprocess.run([sys.executable, "-B", CLI, "compile", str(path), "-o", str(out), *flags], cwd=directory,
                          capture_output=True, text=True, timeout=900, env=env)
    return done, out


def oracle(directory, name, text, *args, cwd=None):
    """CPython running the same program."""
    path = Path(directory) / (name + "_cpy.py")
    path.write_text(text, encoding="utf8")
    env = dict(os.environ, PYTHONUTF8="1")
    env.pop("PYTHONPATH", None)
    return subprocess.run([sys.executable, "-B", str(path), *map(str, args)], cwd=cwd or directory,
                          capture_output=True, text=True, timeout=300, env=env)


def lit(value):
    """Python source for a value, with the int64 minimum written so that no literal leaves the int64 range."""
    if isinstance(value, bool):
        return repr(value)
    if isinstance(value, int) and value == -(1 << 63):
        return "(-9223372036854775807 - 1)"
    return repr(value)


# ---------------------------------------------------------------------------------------------
# Scenario programs

TRANSACTIONS = r'''
import sqlite3


def run(conn: sqlite3.Connection, sql: str) -> None:
    try:
        conn.execute(sql)
    except sqlite3.IntegrityError as e:
        print("IntegrityError", str(e))
    except sqlite3.OperationalError as e:
        print("OperationalError", str(e))
    except sqlite3.ProgrammingError as e:
        print("ProgrammingError", str(e))
    except sqlite3.Error as e:
        print("Error", str(e))


def main():
    conn = sqlite3.connect(":memory:")
    run(conn, "create table t(id integer primary key, a text not null unique, b integer check (b > 0))")
    print(conn.in_transaction)
    run(conn, "insert into t(a, b) values ('x', 1)")
    print(conn.in_transaction)
    run(conn, "insert into t(a, b) values ('x', 2)")
    run(conn, "insert into t(a, b) values (null, 2)")
    run(conn, "insert into t(a, b) values ('y', 0)")
    run(conn, "insert into nowhere values (1)")
    run(conn, "selec 1")
    run(conn, "select 1; select 2")
    run(conn, "create table t(x)")
    run(conn, "drop table nope")
    run(conn, "insert into t(id, a) values (1, 'z')")
    run(conn, "update t set a = 'x' where id = 99")
    run(conn, "select * from t where")
    run(conn, "insert into t(a, b) values ('long', 1) -- a comment")
    run(conn, "/* c */ insert into t(a, b) values ('long2', 1)")
    print(conn.in_transaction)
    conn.rollback()
    print(conn.in_transaction)
    run(conn, "create table u(x)")
    print(conn.in_transaction)
    run(conn, "select * from u")
    print(conn.in_transaction)
    run(conn, "replace into u values (1)")
    print(conn.in_transaction)
    conn.commit()
    run(conn, "with q as (select 1) insert into u select * from q")
    print(conn.in_transaction)
    conn.rollback()
    run(conn, "pragma user_version = 3")
    run(conn, "savepoint s1")
    print(conn.in_transaction)
    run(conn, "release s1")
    print(conn.in_transaction)
    run(conn, "begin")
    print(conn.in_transaction)
    run(conn, "insert into u values (2)")
    run(conn, "begin")
    run(conn, "rollback")
    print(conn.in_transaction)
    try:
        conn.execute("select ?", ())
    except sqlite3.ProgrammingError as e:
        print(str(e))
    try:
        conn.execute("select 1", (1, 2))
    except sqlite3.ProgrammingError as e:
        print(str(e))
    try:
        conn.execute("select :a, :b", {"a": 1})
    except sqlite3.ProgrammingError as e:
        print(str(e))
    try:
        conn.execute("select ?", {"a": 1})
    except sqlite3.ProgrammingError as e:
        print(str(e))
    try:
        conn.executemany("select ?", [(1,)])
    except sqlite3.ProgrammingError as e:
        print(str(e))
    try:
        conn.execute("insert into t(a, b) values (?, ?)", ("q",))
    except sqlite3.ProgrammingError as e:
        print(str(e))
    print(conn.in_transaction)
    conn.rollback()
    cur = conn.executescript("insert into t(a, b) values ('s1', 1); insert into t(a, b) values ('s2', 2);")
    print(conn.in_transaction, cur.rowcount)
    cur = conn.execute("update t set b = b + 1")
    print(cur.rowcount, cur.lastrowid, conn.in_transaction, conn.total_changes)
    conn.commit()
    rows: list[tuple[int, str, int]] = conn.execute("select id, a, b from t order by id").fetchall()
    print(rows)
    cur = conn.execute("select 1 where 0")
    print(cur.rowcount, cur.lastrowid)
    ins = conn.execute("insert into t(a, b) values ('w', 5)")
    print(ins.rowcount, ins.lastrowid)
    conn.commit()
    d = conn.execute("delete from t where b > ?", (2,))
    print(d.rowcount)
    conn.rollback()
    with conn:
        conn.execute("insert into t(a, b) values ('tx', 7)")
    print(conn.in_transaction)
    try:
        with conn:
            conn.execute("insert into t(a, b) values ('tx2', 8)")
            conn.execute("insert into t(a, b) values ('tx', 9)")
    except sqlite3.IntegrityError as e:
        print("rolled back", str(e))
    try:
        with conn:
            conn.execute("insert into t(a, b) values ('tx3', 8)")
            raise ValueError("stop")
    except ValueError:
        print("value error out of with")
    after: list[tuple[str]] = conn.execute("select a from t order by id").fetchall()
    print(after)
    conn.close()
    conn.close()
    try:
        conn.execute("select 1")
    except sqlite3.ProgrammingError as e:
        print(str(e))
    try:
        conn.commit()
    except sqlite3.ProgrammingError as e:
        print(str(e))


main()
'''

ISOLATION = r'''
import sqlite3


def main():
    for level in range(4):
        if level == 0:
            conn = sqlite3.connect(":memory:", isolation_level=None)
        elif level == 1:
            conn = sqlite3.connect(":memory:", isolation_level="")
        elif level == 2:
            conn = sqlite3.connect(":memory:", isolation_level="IMMEDIATE")
        else:
            conn = sqlite3.connect(database=":memory:", isolation_level="EXCLUSIVE")
        conn.execute("create table t(a)")
        conn.execute("insert into t values (1)")
        print(level, conn.in_transaction)
        conn.execute("update t set a = 2")
        print(level, conn.in_transaction)
        conn.rollback()
        print(level, conn.in_transaction)
        conn.execute("begin")
        print(level, conn.in_transaction)
        conn.commit()
        conn.executescript("insert into t values (3);")
        print(level, conn.in_transaction)
        got: list[tuple[int]] = conn.execute("select a from t order by a").fetchall()
        print(level, got)
        conn.close()


main()
'''

PARAMETERS = r'''
import sqlite3


def main():
    conn = sqlite3.connect(":memory:")
    x = 5
    a: tuple[int, int, int] = conn.execute("select ?, ?, ?", (True, x > 3, False)).fetchone()
    print(a)
    nan = float("nan")
    inf = float("inf")
    b: tuple[float, float] = conn.execute("select ?, ?", (inf, -inf)).fetchone()
    print(b)
    r: list[tuple[int]] = conn.execute("select typeof(?) = 'null'", (nan,)).fetchall()
    print(r)
    s: tuple[str, str, int, int] = conn.execute("select ?, ?, length(?), length(?)", ("", "it's \"q\"", "", "a\x00b")).fetchone()
    print(s)
    bl: tuple[bytes, int] = conn.execute("select ?, length(?)", (b"", b"\x00\x00")).fetchone()
    print(bl[1], len(bl[0]))
    big = "ab" * 100000
    t: tuple[int] = conn.execute("select length(?)", (big,)).fetchone()
    print(t)
    u: tuple[str] = conn.execute("select upper(?)", ("straße 日本",)).fetchone()
    print(u)
    z = 0
    i1: tuple[int, float] = conn.execute("select ? + 1, ? * 1.5", (z - 9223372036854775807 - 1, z + 2)).fetchone()
    print(i1)
    named: tuple[int, str, int] = conn.execute("select :a, :b, :a", {"a": 7, "b": "bee"}).fetchone()
    print(named)
    extra: tuple[int] = conn.execute("select :a", {"a": 1, "unused": 2}).fetchone()
    print(extra)
    dollar: tuple[int, str] = conn.execute("select $a, @b", {"a": 1, "b": "x"}).fetchone()
    print(dollar)
    numbered: tuple[int, int, int] = conn.execute("select ?2, ?1, ?2", (10, 20)).fetchone()
    print(numbered)
    nul: tuple[int, int] = conn.execute("select ? is null, ? is null", (None, 1)).fetchone()
    print(nul)
    params = (3, "three")
    held: tuple[int, str] = conn.execute("select ?, ?", params).fetchone()
    print(held)
    plist = [4, 5]
    heldlist: tuple[int, int] = conn.execute("select ?, ?", plist).fetchone()
    print(heldlist)
    try:
        conn.execute("select ?, ?", [1])
    except sqlite3.ProgrammingError as e:
        print(str(e))
    try:
        conn.execute("select :a", {})
    except sqlite3.ProgrammingError as e:
        print(str(e))
    empty: tuple[int] = conn.execute("select 5", {}).fetchone()
    print(empty)
    conn.execute("create table t(a, b)")
    pairs = [(1, 2), (3, 4), (5, 6)]
    conn.executemany("insert into t values (?, ?)", pairs)
    nested = [10, 20]
    conn.executemany("insert into t values (?, 0)", [(v,) for v in nested])
    conn.executemany("insert into t values (?, ?)", ((i, i * i) for i in range(3)))
    out: list[tuple[int, int]] = conn.execute("select a, b from t order by rowid").fetchall()
    print(out)
    conn.close()


main()
'''

NULLS_AND_BLOBS = r'''
import sqlite3
from typing import Optional


def show(rows: list[tuple[int, Optional[str], Optional[float], bytes]]) -> None:
    for r in rows:
        print(r[0], r[1], r[2], r[3])


def main():
    conn = sqlite3.connect(":memory:")
    conn.execute("create table t(id integer primary key, s text, f real, b blob not null)")
    conn.executemany("insert into t values (?, ?, ?, ?)", [(1, "héllo", 1.5, b"\x00\x01"), (2, None, None, b""), (3, "日本語😀", -0.0, b"a'b")])
    conn.commit()
    rows: list[tuple[int, Optional[str], Optional[float], bytes]] = conn.execute("select id, s, f, b from t order by id").fetchall()
    print(rows)
    show(rows)
    for r in rows:
        if r[1] is None:
            print("null s at", r[0])
        a, b, c, d = r
        print(a, b, c, len(d))
    print(len(rows), rows[0][3], rows[1][1] is None, rows[1][2] is not None)
    row: Optional[tuple[int, Optional[str], Optional[float], bytes]] = conn.execute("select id, s, f, b from t where id = 2").fetchone()
    if row is not None:
        print(row)
        print(f"{row} {row[1]} {row[2]} {row[0]}")
    one: Optional[tuple[int, Optional[str], Optional[float], bytes]] = conn.execute("select id, s, f, b from t where id = 99").fetchone()
    print(one is None, one)
    pk: int
    name: Optional[str]
    blob: bytes
    for pk, name, blob in conn.execute("select id, s, b from t"):
        print(pk, name, len(blob))
    big = 9223372036854775807
    conn.execute("create table n(v integer)")
    conn.execute("insert into n values (?)", (big,))
    conn.execute("insert into n values (?)", (-big - 1,))
    x: list[tuple[int]] = conn.execute("select v from n").fetchall()
    print(x)
    y: list[tuple[int, int]] = conn.execute("select v, v + 0 from n order by v").fetchall()
    print(y)
    summed: tuple[Optional[int]] = conn.execute("select sum(v) from n where v > 0").fetchone()
    print(summed)
    try:
        over: tuple[Optional[int]] = conn.execute("select sum(v) from (select 9223372036854775807 as v union all select 9223372036854775807)").fetchone()
        print(over)
    except sqlite3.OperationalError as e:
        print(str(e))
    empty: tuple[Optional[int], Optional[float], int, float] = conn.execute("select max(v), avg(v), count(v), total(v) from n where v is null").fetchone()
    print(empty)
    conn.close()


main()
'''

STORE_CLASS = r'''
import sqlite3


class Store:
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)

    def setup(self) -> None:
        self.conn.execute("create table if not exists kv(k text primary key, v integer)")
        self.conn.commit()

    def put(self, k: str, v: int) -> None:
        self.conn.execute("insert or replace into kv values (?, ?)", (k, v))

    def get(self, k: str) -> int:
        row: tuple[int] | None = self.conn.execute("select v from kv where k = ?", (k,)).fetchone()
        if row is None:
            return -1
        return row[0]

    def all(self) -> list[tuple[str, int]]:
        rows: list[tuple[str, int]] = self.conn.execute("select k, v from kv order by k").fetchall()
        return rows

    def close(self) -> None:
        self.conn.commit()
        self.conn.close()


def load(conn: sqlite3.Connection, pairs: list[tuple[str, int]]) -> int:
    conn.executemany("insert or replace into kv values (?, ?)", pairs)
    return len(pairs)


def total(cur: sqlite3.Cursor) -> int:
    cur.execute("select sum(v) from kv")
    t: tuple[int] = cur.fetchone()
    return t[0]


def main():
    s = Store(":memory:")
    s.setup()
    s.put("a", 1)
    s.put("b", 2)
    print(s.get("a"), s.get("zz"))
    print(s.all())
    n = load(s.conn, [("c", 3), ("d", 4)])
    print(n)
    params = ("e", 5)
    s.conn.execute("insert into kv values (?, ?)", params)
    plist = [6]
    s.conn.execute("insert into kv values ('f', ?)", plist)
    s.conn.execute("insert into kv values (:key, :val)", {"key": "g", "val": 7})
    cur = s.conn.cursor()
    print(total(cur))
    row: tuple[str, int] | None
    cur.execute("select k, v from kv order by v")
    row = cur.fetchone()
    while row is not None:
        print(row[0], row[1])
        row = cur.fetchone()
    k: str
    v: int
    for k, v in cur.execute("select k, v from kv where v > ? order by v desc", (5,)):
        print(k, v)
    cur.execute("select k from kv where v = 99")
    x: tuple[str] | None = cur.fetchone()
    print(x)
    sql = "select count(*) from kv"
    c: tuple[int] = s.conn.execute(sql).fetchone()
    print(c[0], c)
    c2 = cur.execute("select 1")
    print(c2.rowcount)
    s.close()


main()
'''

CURSORS = r'''
import sqlite3


def main():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    nothing: list[tuple[int]] = cur.fetchall()
    print(cur.rowcount, cur.lastrowid, nothing)
    cur.execute("create table t(a integer, b text)")
    cur.executemany("insert into t values (?, ?)", [(1, "one"), (2, "two"), (3, "three")])
    print(cur.rowcount)
    other = conn.cursor()
    other.execute("select a, b from t order by a")
    first: tuple[int, str] | None = other.fetchone()
    print(first)
    cur.execute("update t set b = upper(b) where a > 1")
    print(cur.rowcount)
    rest: list[tuple[int, str]] = other.fetchall()
    print(rest)
    again: list[tuple[int, str]] = other.fetchall()
    print(again)
    none: tuple[int, str] | None = other.fetchone()
    print(none)
    n = 0
    k: int
    s: str
    for k, s in cur.execute("select a, b from t order by a desc"):
        n += k
        print(k, s)
        if k == 2:
            break
    print(n, cur.rowcount)
    pair: tuple[int, str]
    for pair in conn.execute("select a, b from t where a >= ? order by a", (2,)):
        print(pair)
    by_name: list[tuple[str]] = conn.execute("select b from t where a = :n", {"n": 3}).fetchall()
    print(by_name)
    cur.close()
    try:
        cur.execute("select 1")
    except sqlite3.ProgrammingError as e:
        print(str(e))
    conn.close()


main()
'''

PERSIST = r'''
import sqlite3
import sys


def main():
    path = sys.argv[1]
    mode = int(sys.argv[2])
    if mode == 0:
        conn = sqlite3.connect(path)
        conn.execute("create table t(a integer, b text)")
        conn.executemany("insert into t values (?, ?)", [(1, "x"), (2, "y")])
        conn.commit()
        conn.execute("insert into t values (3, 'uncommitted')")
        conn.close()
    elif mode == 1:
        conn = sqlite3.connect(path)
        rows: list[tuple[int, str]] = conn.execute("select a, b from t order by a").fetchall()
        print(rows)
        with conn:
            conn.execute("delete from t where a = 1")
        n: tuple[int] = conn.execute("select count(*) from t").fetchone()
        print(n)
        conn.close()
    elif mode == 2:
        a = sqlite3.connect(path)
        b = sqlite3.connect(path)
        a.execute("insert into t values (9, 'a')")
        print(a.in_transaction)
        a.commit()
        seen: list[tuple[int, str]] = b.execute("select a, b from t order by a").fetchall()
        print(seen)
        a.close()
        b.close()
    else:
        try:
            sqlite3.connect(path)
        except sqlite3.OperationalError as e:
            print(str(e))


main()
'''

SHAPE_MISMATCH = r'''
import sqlite3
import sys


def main():
    conn = sqlite3.connect(":memory:")
    conn.execute("create table t(a, b)")
    conn.execute("insert into t values (1, 'x')")
    case = int(sys.argv[1])
    try:
        if case == 0:
            r0: list[tuple[int, str]] = conn.execute("select a, b from t").fetchall()
            print(r0)
        elif case == 1:
            r1: list[tuple[str, str]] = conn.execute("select a, b from t").fetchall()
            print(len(r1))
        elif case == 2:
            r2: list[tuple[int]] = conn.execute("select a, b from t").fetchall()
            print(len(r2))
        elif case == 3:
            conn.execute("insert into t values (null, null)")
            r3: list[tuple[int, str]] = conn.execute("select a, b from t order by rowid").fetchall()
            print(len(r3))
        else:
            conn.execute("insert into t values (null, null)")
            r4: list[tuple[Optional[int], Optional[str]]] = conn.execute("select a, b from t order by rowid").fetchall()
            print(r4)
    except RuntimeError:
        print("RuntimeError")


main()
'''

# ---------------------------------------------------------------------------------------------
# Randomised programs

INTS = [0, 1, -1, 7, 255, 256, 65535, 2 ** 31 - 1, -2 ** 31, 2 ** 32, 2 ** 53, 2 ** 53 + 1, 2 ** 62, 2 ** 63 - 1, -2 ** 63, 12345678901]
FLOATS = [0.0, -0.0, 1.0, -1.5, 0.1, 0.5, 1e-9, 1e15, 1e16, 1e22, 1e300, -1e300, 2.5e-300, 3.141592653589793, 123456.789, 1 / 3]
TEXTS = ["", "a", "hello world", "it's", 'say "hi"', "héllo", "日本語", "😀", "mixed 日本 and ascii", "line\nbreak",
         "tab\there", " padded ", "back\\slash", "100%", "x" * 300, "a\x00b", "ÅÄÖ", "ß", "\U0001f600\U0001f4a9"]
BLOBS = [b"", b"\x00", b"\xff\x00\xfe", bytes(range(256)), b"abc", b"a'b", b"\x80\x81 bad utf8", b"\x00" * 40]
SQLTYPE = {"i": "integer", "f": "real", "s": "text", "b": "blob"}
PYTYPE = {"i": "int", "f": "float", "s": "str", "b": "bytes"}


class Column:
    def __init__(self, kind, nullable, unique):
        self.kind, self.nullable, self.unique = kind, nullable, unique

    def pool(self):
        return {"i": INTS, "f": FLOATS, "s": TEXTS, "b": BLOBS}[self.kind]

    def annotation(self):
        t = PYTYPE[self.kind]
        return "Optional[%s]" % t if self.nullable else t


class Generator:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.cols = []
        self.lines = []
        self.n = 0
        self.ids = 0

    def name(self, prefix):
        self.n += 1
        return "%s%d" % (prefix, self.n)

    def value(self, col, allow_null=True):
        if col.nullable and allow_null and self.rng.random() < 0.3:
            return None
        v = self.rng.choice(col.pool())
        return v

    def sql_literal(self, col, v):
        """A SQL literal for v (text with a NUL cannot be written into SQL text: the caller uses parameters)."""
        if v is None:
            return "null"
        if col.kind == "b":
            return "x'%s'" % v.hex()
        if col.kind == "s":
            return "'%s'" % v.replace("'", "''")
        return repr(v)

    def shape(self, cols, with_id=True):
        parts = (["int"] if with_id else []) + [c.annotation() for c in cols]
        return "tuple[%s]" % ", ".join(parts)

    def uses_optional(self):
        return any(c.nullable for c in self.cols)

    def emit(self, line):
        self.lines.append("    " + line)

    def build(self):
        r = self.rng
        for _ in range(r.randint(1, 4)):
            self.cols.append(Column(r.choice("ifsb"), r.random() < 0.5, r.random() < 0.15))
        defs = ["id integer primary key"]
        for k, c in enumerate(self.cols):
            d = "c%d %s" % (k, SQLTYPE[c.kind])
            if not c.nullable:
                d += " not null"
            if c.unique:
                d += " unique"
            defs.append(d)
        self.emit("conn = sqlite3.connect(\":memory:\")")
        self.emit("conn.execute(%r)" % ("create table t(%s)" % ", ".join(defs)))
        for _ in range(r.randint(6, 14)):
            self.step()
        self.select_all()
        self.emit("conn.close()")
        header = "import sqlite3\nfrom typing import Optional\n\n\ndef main():\n"
        return header + "\n".join(self.lines) + "\n\n\nmain()\n"

    # ---- steps -------------------------------------------------------------------------
    def step(self):
        self.rng.choice([self.insert_text, self.insert_qmark, self.insert_named, self.insert_many, self.insert_many,
                         self.update, self.delete, self.select_all, self.select_filter, self.select_filter, self.aggregate,
                         self.violation, self.transaction, self.transaction, self.fetch_loop, self.cursor_loop])()

    def row_values(self, allow_null=True):
        return [self.value(c, allow_null) for c in self.cols]

    def insert_text(self):
        vals = self.row_values()
        if any(isinstance(v, str) and "\x00" in v for v in vals):
            return self.insert_qmark()
        lits = ", ".join(self.sql_literal(c, v) for c, v in zip(self.cols, vals))
        names = ", ".join("c%d" % k for k in range(len(self.cols)))
        self.try_exec("insert into t(%s) values (%s)" % (names, lits), None)
        self.report("conn")

    def try_exec(self, sql, params, verb="exec"):
        args = ""
        if params is not None:
            args = ", " + params
        self.emit("try:")
        self.emit("    cur = conn.execute(%r%s)" % (sql, args))
        self.emit("    print(%r, cur.rowcount, cur.lastrowid, conn.in_transaction)" % verb)
        self.emit("except sqlite3.IntegrityError as e:")
        self.emit("    print('IntegrityError', str(e))")
        self.emit("except sqlite3.OperationalError as e:")
        self.emit("    print('OperationalError', str(e))")
        self.emit("except sqlite3.Error as e:")
        self.emit("    print('Error', str(e))")

    def report(self, _):
        pass

    def tuple_src(self, vals):
        return "(%s,)" % ", ".join(lit(v) for v in vals) if len(vals) == 1 else "(%s)" % ", ".join(lit(v) for v in vals)

    def insert_qmark(self):
        vals = self.row_values()
        names = ", ".join("c%d" % k for k in range(len(self.cols)))
        marks = ", ".join("?" for _ in self.cols)
        self.try_exec("insert into t(%s) values (%s)" % (names, marks), self.tuple_src(vals), "qmark")

    def insert_named(self):
        vals = self.row_values()
        names = ", ".join("c%d" % k for k in range(len(self.cols)))
        marks = ", ".join(":v%d" % k for k in range(len(self.cols)))
        d = "{%s}" % ", ".join("%r: %s" % ("v%d" % k, lit(v)) for k, v in enumerate(vals))
        self.try_exec("insert into t(%s) values (%s)" % (names, marks), d, "named")

    def insert_many(self):
        rows = [self.row_values() for _ in range(self.rng.randint(0, 4))]
        names = ", ".join("c%d" % k for k in range(len(self.cols)))
        marks = ", ".join("?" for _ in self.cols)
        sql = "insert into t(%s) values (%s)" % (names, marks)
        self.emit("try:")
        self.emit("    cur = conn.executemany(%r, [%s])" % (sql, ", ".join(self.tuple_src(r) for r in rows)))
        self.emit("    print('many', cur.rowcount, cur.lastrowid, conn.in_transaction)")
        self.emit("except sqlite3.IntegrityError as e:")
        self.emit("    print('IntegrityError', str(e))")
        self.emit("except sqlite3.Error as e:")
        self.emit("    print('Error', str(e))")
        self.emit("print(conn.total_changes)")

    def update(self):
        k = self.rng.randrange(len(self.cols))
        c = self.cols[k]
        v = self.value(c)
        self.try_exec("update t set c%d = ? where id %% 2 = ?" % k, "(%s, %d)" % (lit(v), self.rng.randint(0, 1)), "update")

    def delete(self):
        self.try_exec("delete from t where id %% %d = ?" % self.rng.randint(2, 4), "(%d,)" % self.rng.randint(0, 1), "delete")

    def select_all(self):
        name = self.name("rows")
        self.emit("%s: list[%s] = conn.execute('select * from t order by id').fetchall()" % (name, self.shape(self.cols)))
        self.emit("print(len(%s))" % name)
        self.emit("print(%s)" % name)

    def select_filter(self):
        k = self.rng.randrange(len(self.cols))
        c = self.cols[k]
        name = self.name("sel")
        kind = self.rng.choice(["null", "notnull", "eq", "eq", "lt"])
        shape = self.shape(self.cols)
        if kind == "null":
            sql, params = "select * from t where c%d is null order by id" % k, ""
        elif kind == "notnull":
            sql, params = "select * from t where c%d is not null order by id" % k, ""
        elif kind == "eq":
            sql, params = "select * from t where c%d = ? order by id" % k, ", (%s,)" % lit(self.value(c, False))
        else:
            sql, params = "select * from t where c%d < ? order by id" % k, ", (%s,)" % lit(self.value(c, False))
        self.emit("%s: list[%s] = conn.execute(%r%s).fetchall()" % (name, shape, sql, params))
        self.emit("print(%r, %s)" % (kind, name))

    def aggregate(self):
        k = self.rng.randrange(len(self.cols))
        c = self.cols[k]
        name = self.name("agg")
        parts = [("count(*)", "int"), ("count(c%d)" % k, "int"), ("min(c%d)" % k, "Optional[%s]" % PYTYPE[c.kind]),
                 ("max(c%d)" % k, "Optional[%s]" % PYTYPE[c.kind])]
        if c.kind in "if":
            parts.append(("total(c%d)" % k, "float"))
            parts.append(("avg(c%d)" % k, "Optional[float]"))
        sql = "select %s from t" % ", ".join(p[0] for p in parts)
        shape = "tuple[%s]" % ", ".join(p[1] for p in parts)
        self.emit("try:")
        self.emit("    %s: %s = conn.execute(%r).fetchone()" % (name, shape, sql))
        self.emit("    print(%s)" % name)
        self.emit("except sqlite3.OperationalError as e:")
        self.emit("    print('OperationalError', str(e))")
        if c.kind == "i":
            n2 = self.name("sum")
            self.emit("try:")
            self.emit("    %s: tuple[Optional[int]] = conn.execute('select sum(c%d) from t').fetchone()" % (n2, k))
            self.emit("    print(%s)" % n2)
            self.emit("except sqlite3.OperationalError as e:")
            self.emit("    print('OperationalError', str(e))")

    def violation(self):
        what = self.rng.choice(["dupid", "null", "badcol", "badtable", "syntax", "count"])
        if what == "dupid":
            self.try_exec("insert into t(id) values (?)", "(%d,)" % self.rng.randint(1, 3), "dupid")
        elif what == "null":
            nn = [k for k, c in enumerate(self.cols) if not c.nullable]
            if not nn:
                return self.try_exec("insert into t(c0) values (null)", None, "null")
            self.try_exec("insert into t(c%d) values (?)" % nn[0], "(None,)", "null")
        elif what == "badcol":
            self.try_exec("select nosuchcolumn from t", None, "badcol")
        elif what == "badtable":
            self.try_exec("insert into nosuchtable values (?)", "(1,)", "badtable")
        elif what == "syntax":
            self.try_exec("selct * from t", None, "syntax")
        else:
            self.try_exec("insert into t(c0) values (?)", "(%s, %s)" % (lit(1), lit(2)), "count")

    def transaction(self):
        what = self.rng.choice(["commit", "rollback", "with_ok", "with_fail", "script"])
        if what == "commit":
            self.emit("conn.commit()")
            self.emit("print('commit', conn.in_transaction)")
        elif what == "rollback":
            self.emit("conn.rollback()")
            self.emit("print('rollback', conn.in_transaction)")
        elif what == "with_ok":
            vals = self.row_values()
            names = ", ".join("c%d" % k for k in range(len(self.cols)))
            marks = ", ".join("?" for _ in self.cols)
            self.emit("try:")
            self.emit("    with conn:")
            self.emit("        conn.execute(%r, %s)" % ("insert into t(%s) values (%s)" % (names, marks), self.tuple_src(vals)))
            self.emit("    print('with ok', conn.in_transaction)")
            self.emit("except sqlite3.Error as e:")
            self.emit("    print('with error', str(e), conn.in_transaction)")
        elif what == "with_fail":
            vals = self.row_values()
            names = ", ".join("c%d" % k for k in range(len(self.cols)))
            marks = ", ".join("?" for _ in self.cols)
            self.emit("try:")
            self.emit("    with conn:")
            self.emit("        conn.execute(%r, %s)" % ("insert into t(%s) values (%s)" % (names, marks), self.tuple_src(vals)))
            self.emit("        raise ValueError('boom')")
            self.emit("except ValueError:")
            self.emit("    print('with raised', conn.in_transaction)")
            self.emit("except sqlite3.Error as e:")
            self.emit("    print('with error', str(e), conn.in_transaction)")
        else:
            self.emit("try:")
            self.emit("    conn.executescript('insert into t(id) values (%d); delete from t where id = %d;')" % (
                1000 + self.rng.randint(0, 5), 1000 + self.rng.randint(0, 5)))
            self.emit("    print('script', conn.in_transaction)")
            self.emit("except sqlite3.Error as e:")
            self.emit("    print('script error', str(e))")

    def fetch_loop(self):
        name = self.name("row")
        self.emit("cur = conn.execute('select * from t order by id')")
        self.emit("%s: %s | None = cur.fetchone()" % (name, self.shape(self.cols)))
        self.emit("count = 0")
        self.emit("while %s is not None and count < 4:" % name)
        self.emit("    print(%s)" % name)
        self.emit("    count += 1")
        self.emit("    %s = cur.fetchone()" % name)
        self.emit("print(count, %s is None)" % name)

    def cursor_loop(self):
        k = self.rng.randrange(len(self.cols))
        c = self.cols[k]
        if c.kind == "b" and c.nullable:
            return self.fetch_loop()                # a nullable bytes column cannot be held in a variable (refused by name)
        a, b = self.name("pk"), self.name("val")
        self.emit("%s: int" % a)
        self.emit("%s: %s" % (b, c.annotation()))
        self.emit("for %s, %s in conn.execute('select id, c%d from t order by id'):" % (a, b, k))
        self.emit("    print(%s, %s)" % (a, b if c.kind != "b" else "len(%s)" % b if not c.nullable else "%s is None" % b))


# ---------------------------------------------------------------------------------------------

class SqliteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="ail-sqlite-test-")
        cls.dir = Path(cls.temp.name)
        cls.exe = {}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def build(self, name, text, **kw):
        key = (name, tuple(sorted(kw.get("env_extra", {}).items())))
        if key not in self.exe:
            done, out = compile_program(self.dir, name, text, **kw)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertNotIn("general path", done.stderr)
            self.exe[key] = out
        return self.exe[key]

    def compare(self, name, text, *args, **kw):
        exe = self.build(name, text, **kw)
        expected = oracle(self.dir, name, text, *args)
        self.assertEqual(expected.returncode, 0, expected.stderr)
        ran = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True, timeout=300, cwd=self.dir)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(ran.stdout, expected.stdout)
        return ran.stdout

    # ---- scenarios ------------------------------------------------------------------------
    def test_transactions_errors_rowcount_lastrowid(self):
        out = self.compare("transactions", TRANSACTIONS)
        for needle in ("IntegrityError UNIQUE constraint failed: t.a", "IntegrityError NOT NULL constraint failed: t.a",
                       "IntegrityError CHECK constraint failed", "OperationalError no such table: nowhere",
                       "ProgrammingError You can only execute one statement at a time.",
                       "Incorrect number of bindings supplied. The current statement uses 1, and there are 0 supplied.",
                       "You did not supply a value for binding parameter :b.",
                       "Binding 1 has no name, but you supplied a dictionary (which has only names).",
                       "executemany() can only execute DML statements.", "Cannot operate on a closed database.",
                       "rolled back UNIQUE constraint failed: t.a", "value error out of with"):
            self.assertIn(needle, out)

    def test_transactions_with_the_ir(self):
        self.compare("transactions_ir", TRANSACTIONS, env_extra={"AIL_IR": "1"})

    def test_isolation_levels(self):
        out = self.compare("isolation", ISOLATION)
        self.assertIn("0 False\n0 False", out)          # isolation_level=None: no implicit BEGIN
        self.assertIn("1 True", out)

    def test_parameters(self):
        out = self.compare("parameters", PARAMETERS)
        self.assertIn("(7, 'bee', 7)", out)
        self.assertIn("(20, 10, 20)", out)

    def test_nulls_blobs_unicode_and_large_integers(self):
        out = self.compare("nulls", NULLS_AND_BLOBS)
        self.assertIn("9223372036854775807", out)
        self.assertIn("日本語😀", out)
        self.assertIn("integer overflow", out)

    def test_a_class_holding_a_connection(self):
        self.compare("store", STORE_CLASS)

    def test_cursors(self):
        out = self.compare("cursors", CURSORS)
        self.assertIn("Cannot operate on a closed cursor.", out)

    def test_database_files(self):
        path = str(self.dir / "persist.db")
        wpath = str(self.dir / "persist_cpy.db")
        text = PERSIST
        exe = self.build("persist", text)
        for mode in (0, 1, 2):
            expected = oracle(self.dir, "persist", text, wpath, mode)
            self.assertEqual(expected.returncode, 0, expected.stderr)
            ran = subprocess.run([str(exe), path, str(mode)], capture_output=True, text=True, timeout=120)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout, expected.stdout, "mode %d" % mode)
        missing = str(self.dir / "no" / "such" / "dir" / "x.db")
        expected = oracle(self.dir, "persist", text, missing, 3)
        ran = subprocess.run([str(exe), missing, "3"], capture_output=True, text=True, timeout=120)
        self.assertEqual(ran.stdout, expected.stdout)
        self.assertIn("unable to open database file", ran.stdout)

    def test_the_declared_row_shape_is_checked(self):
        text = SHAPE_MISMATCH.replace("import sys\n", "import sys\nfrom typing import Optional\n", 1)
        exe = self.build("shape", text)
        want = ["[(1, 'x')]", "RuntimeError", "RuntimeError", "RuntimeError", "[(1, 'x'), (None, None)]"]
        for case, expected in enumerate(want):
            ran = subprocess.run([str(exe), str(case)], capture_output=True, text=True, timeout=60)
            self.assertEqual(ran.returncode, 0, ran.stderr)
            self.assertEqual(ran.stdout.strip(), expected, "case %d" % case)

    # ---- randomised programs --------------------------------------------------------------
    def test_random_programs(self):
        seen_kinds = set()
        for seed in range(1, 25):
            with self.subTest(seed=seed):
                text = Generator(seed * 7919).build()
                out = self.compare("random%d" % seed, text)
                self.assertTrue(out)
                seen_kinds.update(re.findall(r"^(IntegrityError|OperationalError|Error|exec|qmark|named|many|update|delete) ", out, re.M))
        self.assertTrue({"IntegrityError", "qmark", "named", "many"} <= seen_kinds, seen_kinds)

    # ---- what a program that does not import sqlite3 carries ---------------------------------
    def test_a_program_without_sqlite3_is_untouched_and_unlinked(self):
        sys.path.insert(0, str(ROOT / "python" / "pkg-v12"))
        sys.path.insert(0, str(ROOT))
        try:
            import ail_syntax
            import pyfunc
            plain = "def main():\n    xs = [1, 2, 3]\n    print(sum(xs))\n    d = {'a': 1}\n    print(d['a'])\n\nmain()\n"
            self.assertIs(ail_syntax._sqllower().rewrite_text(plain), plain)
            c = pyfunc.to_c(ail_syntax.python_surface(plain), name="run", strict=True)
            self.assertNotIn("sqlite", c)
            self.assertNotIn("ails_", c)
            mention = "def main():\n    print('sqlite3 is a database')\n\nmain()\n"
            self.assertIs(ail_syntax._sqllower().rewrite_text(mention), mention)
        finally:
            sys.path.remove(str(ROOT))
            sys.path.remove(str(ROOT / "python" / "pkg-v12"))
        done, out = compile_program(self.dir, "plain", "def main():\n    print(sum([1, 2, 3]))\n\nmain()\n")
        self.assertEqual(done.returncode, 0, done.stderr)
        if sys.platform.startswith("linux") and shutil.which("ldd"):
            needed = subprocess.run(["ldd", str(out)], capture_output=True, text=True).stdout
            self.assertNotIn("sqlite", needed)
            with_sqlite = self.build("scenario_link", CURSORS)
            needed = subprocess.run(["ldd", str(with_sqlite)], capture_output=True, text=True).stdout
            self.assertIn("libsqlite3", needed)

    # ---- refusals -------------------------------------------------------------------------
    def refused(self, body, needle, header="import sqlite3\n"):
        text = header + "\n\ndef main():\n    conn = sqlite3.connect(':memory:')\n" + "".join(
            "    " + line + "\n" for line in body.strip("\n").split("\n")) + "\n\nmain()\n"
        done, out = compile_program(self.dir, "refused", text)
        self.assertNotEqual(done.returncode, 0, "accepted: " + body)
        self.assertIn(needle, done.stderr, body)
        self.assertIn("write instead:", done.stderr, body)

    def test_everything_else_is_refused_by_name(self):
        self.refused("conn.row_factory = sqlite3.Row", "row_factory is not built")
        self.refused("print(conn.row_factory)", "row_factory is not built")
        self.refused("conn.create_function('f', 1, abs)", "user-defined SQL functions")
        self.refused("conn.create_aggregate('f', 1, abs)", "user-defined aggregates")
        self.refused("sqlite3.register_adapter(int, str)", "adapters are not built")
        self.refused("sqlite3.register_converter('x', str)", "converters are not built")
        self.refused("c = sqlite3.connect(':memory:', detect_types=1)", "detect_types")
        self.refused("c = sqlite3.connect(':memory:', timeout=1.0)", "timeout=")
        self.refused("c = sqlite3.connect(':memory:', check_same_thread=False)", "check_same_thread")
        self.refused("c = sqlite3.connect(':memory:', isolation_level='x')", "isolation_level must be")
        self.refused("cur = conn.execute('select 1')\nprint(cur.description)", "cursor.description")
        self.refused("cur = conn.execute('select 1')\nr = cur.fetchmany(2)", "fetchmany")
        self.refused("conn.execute('select 1').fetchone()", "needs the shape of the rows")
        self.refused("rows = conn.execute('select 1').fetchall()", "needs the shape of the rows")
        self.refused("for r in conn.execute('select 1'):\n    print(r)", "needs the shape of the rows")
        self.refused("cur = conn.execute('select 1')\nr: tuple[int] = cur.fetchall()", "fetchall() gives a list of rows")
        self.refused("cur = conn.execute('select 1')\nr: list[tuple[int]] = cur.fetchone()", "fetchone() gives one row")
        self.refused("conn.execute('select ?', make())", "parameters must be")
        self.refused("conn.execute('select ?', (*[1],))", "*args in the parameters")
        self.refused("sql = 'select ?'\nconn.execute(sql, [1][0:1])", "parameters")
        self.refused("n = 1\nconn.executemany('insert into t values (:a)', [{'a': 1}])", "named parameters is not built")
        self.refused("x = conn.executemany('insert into t values (?)', [(1,)]).rowcount", "executemany is built as a statement")
        self.refused("conn.iterdump()", "iterdump")
        self.refused("conn.backup(conn)", "backup")
        self.refused("print(sqlite3.version)", "sqlite3.version")
        self.refused("print(sqlite3.PARSE_DECLTYPES)", "detect_types")
        self.refused("conn.enable_load_extension(True)", "extensions")
        self.refused("conn.isolation_level = None", "isolation_level can only be given to connect()")
        self.refused("with conn:\n    return", "return inside `with conn:`")
        self.refused("for i in range(3):\n    with conn:\n        break", "break inside `with conn:`")
        self.refused("def inner():\n    import sqlite3", "at the top of the file", header="")

    def test_row_shape_errors_need_a_declaration_with_a_nullable_or_bytes_column(self):
        self.refused("rows: list[tuple[int, Optional[str]]] = conn.execute('select 1, 2').fetchall()\nprint(rows[0][x])",
                     "indexed with a constant", header="import sqlite3\nfrom typing import Optional\n")

    def test_a_cross_build_is_refused(self):
        zig = os.environ.get("AIL_ZIG") or shutil.which("zig") or str(Path.home() / "tools" / "zig" / "zig")
        if not os.path.isfile(zig):
            self.skipTest("--target needs zig, which is not installed here")
        text = "import sqlite3\n\n\ndef main():\n    conn = sqlite3.connect(':memory:')\n    conn.close()\n\n\nmain()\n"
        done, _ = compile_program(self.dir, "cross", text, "--target", "windows")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("cross", done.stderr)
        self.assertIn("write instead:", done.stderr)


if __name__ == "__main__":
    unittest.main()
