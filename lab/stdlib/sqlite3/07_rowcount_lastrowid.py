import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("create table events(id integer primary key, kind text)")
    print("before", cur.rowcount, cur.lastrowid)
    ins = conn.execute("insert into events(kind) values (?)", ("start",))
    print("insert", ins.rowcount, ins.lastrowid)
    conn.execute("insert into events(kind) values (?)", ("tick",))
    upd = conn.execute("update events set kind = ? where id > ?", ("seen", 0))
    print("update", upd.rowcount, upd.lastrowid)
    dele = conn.execute("delete from events where kind = ?", ("seen",))
    print("delete", dele.rowcount, dele.lastrowid)
    conn.commit()
    print("total", conn.total_changes)
    conn.close()


main()
