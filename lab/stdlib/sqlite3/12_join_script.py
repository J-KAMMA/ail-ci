import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        "create table authors(id integer primary key, name text);"
        "create table books(id integer primary key, author_id integer, title text);"
    )
    conn.executemany("insert into authors(name) values (?)",
                     [("Ursula",), ("Octavia",), ("Ted",)])
    conn.executemany("insert into books(author_id, title) values (?, ?)",
                     [(1, "The Dispossessed"), (1, "Earthsea"), (2, "Kindred"),
                      (3, "Story of Your Life")])
    conn.commit()
    rows: list[tuple[str, str]] = conn.execute(
        "select authors.name, books.title from authors join books on books.author_id = authors.id "
        "order by authors.name, books.title").fetchall()
    for author, title in rows:
        print(author, "-", title)
    counts: list[tuple[str, int]] = conn.execute(
        "select authors.name, count(*) from authors join books on books.author_id = authors.id "
        "group by authors.name order by authors.name").fetchall()
    print(counts)
    conn.close()


main()
