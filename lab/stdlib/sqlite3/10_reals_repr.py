import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("create table measures(id integer primary key, value real)")
    values = [0.1, -0.0, 1.5, 3.141592653589793, 1e300, 2.5e-300]
    conn.executemany("insert into measures(value) values (?)", [(v,) for v in values])
    conn.commit()
    rows: list[tuple[int, float]] = conn.execute(
        "select id, value from measures order by id").fetchall()
    for mid, value in rows:
        print(mid, repr(value))
    stats: tuple[float, float, float] = conn.execute(
        "select min(value), max(value), avg(value) from measures").fetchone()
    print(repr(stats[0]), repr(stats[1]), repr(stats[2]))
    conn.close()


main()
