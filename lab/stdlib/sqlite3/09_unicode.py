import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("create table words(id integer primary key, text text)")
    data = ["café", "naïve", "日本語", "Привет", "emoji 😀", "Ω≈ç√∫"]
    conn.executemany("insert into words(text) values (?)", [(w,) for w in data])
    conn.commit()
    rows: list[tuple[int, str]] = conn.execute(
        "select id, text from words order by id").fetchall()
    for wid, text in rows:
        print(wid, text, len(text))
    longest: tuple[str, int] = conn.execute(
        "select text, length(text) from words order by length(text) desc, id limit 1").fetchone()
    print(longest)
    upper: list[tuple[str]] = conn.execute(
        "select upper(text) from words where id <= ?", (2,)).fetchall()
    print(upper)
    conn.close()


main()
