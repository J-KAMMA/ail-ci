import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("create table books(id integer primary key, title text, year integer)")
    conn.execute("insert into books(title, year) values (?, ?)", ("Dune", 1965))
    conn.execute("insert into books(title, year) values (?, ?)", ("Neuromancer", 1984))
    conn.execute("insert into books(title, year) values (?, ?)", ("Snow Crash", 1992))
    conn.commit()
    rows: list[tuple[int, str, int]] = conn.execute(
        "select id, title, year from books order by id").fetchall()
    for book_id, title, year in rows:
        print(book_id, title, year)
    old: list[tuple[str]] = conn.execute(
        "select title from books where year < ? order by year", (1980,)).fetchall()
    print(old)
    conn.close()


main()
