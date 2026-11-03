from ail_ffi import *

link("sqlite3")

Db = Handle("sqlite3", free="sqlite3_close")
Stmt = Handle("sqlite3_stmt", free="sqlite3_finalize")

@extern(header="sqlite3.h", trust=True)
def sqlite3_open(path: c_char_p, out: ptr(c_void_p)) -> c_int: ...

@extern(header="sqlite3.h", trust=True)
def sqlite3_exec(db: Db, sql: c_char_p, cb: c_void_p, arg: c_void_p,
                 err: c_void_p) -> c_int: ...

@extern(header="sqlite3.h", trust=True)
def sqlite3_prepare_v2(db: Db, sql: c_char_p, n: c_int, out: ptr(c_void_p),
                       tail: ptr(c_void_p)) -> c_int: ...

@extern(header="sqlite3.h", trust=True)
def sqlite3_step(stmt: Stmt) -> c_int: ...

@extern(header="sqlite3.h", trust=True)
def sqlite3_column_int64(stmt: Stmt, i: c_int) -> c_longlong: ...

ROW = 100


def open_memory() -> Db:
    out = bytearray(8)
    sqlite3_open(":memory:", out)
    return Db.adopt(out)


def main():
    db = open_memory()
    sqlite3_exec(db, "create table item(id integer primary key, v integer)", 0, 0, 0)
    sql = "begin;"
    for i in range(1, 1001):
        sql = sql + "insert into item(v) values(" + str(i) + ");"
    sql = sql + "commit;"
    sqlite3_exec(db, sql, 0, 0, 0)
    out = bytearray(8)
    tail = bytearray(8)
    sqlite3_prepare_v2(db, "select count(*), sum(v) from item", -1, out, tail)
    stmt = Stmt.adopt(out)
    if sqlite3_step(stmt) == ROW:
        print(sqlite3_column_int64(stmt, 0), sqlite3_column_int64(stmt, 1))
    stmt.close()
    db.close()


main()
