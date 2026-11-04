import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("create table sales(id integer primary key, region integer, amount integer)")
    data = [(i, i % 10, i + 1) for i in range(1000)]
    conn.executemany("insert into sales(region, amount) values (?, ?)",
                     [(region, amount) for _, region, amount in data])
    conn.commit()
    summary: list[tuple[int, int, float]] = conn.execute(
        "select region, sum(amount), avg(amount) from sales group by region order by region"
    ).fetchall()
    print(summary)
    total: tuple[int, float, int] = conn.execute(
        "select sum(amount), avg(amount), count(*) from sales").fetchone()
    print(total)
    top: list[tuple[int, int]] = conn.execute(
        "select region, sum(amount) as s from sales group by region order by s desc limit 3"
    ).fetchall()
    print(top)
    conn.close()


main()
