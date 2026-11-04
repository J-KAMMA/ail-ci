import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("create table people(id integer primary key, nickname text, city text)")
    conn.executemany("insert into people(nickname, city) values (?, ?)",
                     [("ada", "London"), (None, "Paris"), ("grace", None), (None, None)])
    conn.commit()
    rows: list[tuple[int, str | None, str | None]] = conn.execute(
        "select id, nickname, city from people order by id").fetchall()
    print(rows)
    for pid, nickname, city in rows:
        if nickname is None:
            print(pid, "no nickname", city)
        else:
            print(pid, nickname, city if city is not None else "unknown")
    count: tuple[int] = conn.execute(
        "select count(*) from people where nickname is null").fetchone()
    print("missing nicknames", count[0])
    conn.close()


main()
