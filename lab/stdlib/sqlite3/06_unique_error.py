import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("create table accounts(email text unique not null, name text)")
    conn.execute("insert into accounts(email, name) values (?, ?)", ("a@example.com", "A"))
    try:
        conn.execute("insert into accounts(email, name) values (?, ?)",
                     ("a@example.com", "A again"))
    except sqlite3.IntegrityError as exc:
        print("IntegrityError:", exc)
    conn.rollback()
    rows: list[tuple[str, str]] = conn.execute(
        "select email, name from accounts").fetchall()
    print(rows)
    conn.close()


main()
