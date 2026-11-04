import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("create table big(id integer primary key, value integer)")
    numbers = [0, 2147483647, 2147483648, -2147483649, 9223372036854775807,
               -9223372036854775807 - 1]
    conn.executemany("insert into big(value) values (?)", [(n,) for n in numbers])
    conn.commit()
    rows: list[tuple[int, int]] = conn.execute(
        "select id, value from big order by id").fetchall()
    for bid, value in rows:
        print(bid, value)
    high: tuple[int] = conn.execute(
        "select value from big where value > ?", (2 ** 31 - 1,)).fetchone()
    print("high", high[0])
    low: tuple[int] = conn.execute("select min(value) from big").fetchone()
    print("low", low[0])
    conn.close()


main()
