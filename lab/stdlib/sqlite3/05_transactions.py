import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("create table ledger(id integer primary key, memo text, amount integer)")
    conn.commit()

    with conn:
        conn.execute("insert into ledger(memo, amount) values (?, ?)", ("opening", 100))
        conn.execute("insert into ledger(memo, amount) values (?, ?)", ("coffee", -3))

    try:
        with conn:
            conn.execute("insert into ledger(memo, amount) values (?, ?)", ("refund", 50))
            raise ValueError("posting failed")
    except ValueError as exc:
        print("rolled back:", exc)

    rows: list[tuple[str, int]] = conn.execute(
        "select memo, amount from ledger order by id").fetchall()
    print(rows)
    print("in transaction", conn.in_transaction)
    conn.close()


main()
