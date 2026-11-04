import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("create table tasks(id integer primary key, name text, done integer)")
    conn.executemany("insert into tasks(name, done) values (?, ?)",
                     [("write", 1), ("test", 1), ("ship", 0), ("rest", 0)])
    conn.commit()
    cur = conn.execute("select id, name, done from tasks order by id")
    row: tuple[int, str, int] | None = cur.fetchone()
    seen = 0
    while row is not None:
        print(row[0], row[1], bool(row[2]))
        seen += 1
        row = cur.fetchone()
    print("rows", seen)
    conn.close()


main()
