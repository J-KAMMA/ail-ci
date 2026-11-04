import sqlite3


def main() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute("create table users(id integer primary key, name text, score real)")
    users = [
        ("alice", 91.5),
        ("bob", 78.0),
        ("carol", 84.25),
    ]
    for name, score in users:
        conn.execute(
            "insert into users(name, score) values (:name, :score)",
            {"name": name, "score": score},
        )
    conn.commit()
    row: tuple[int, str, float] = conn.execute(
        "select id, name, score from users where name = :name", {"name": "bob"}).fetchone()
    print(row)
    count: tuple[int] = conn.execute(
        "select count(*) from users where score >= :min", {"min": 80.0}).fetchone()
    print(count[0])
    conn.close()


main()
