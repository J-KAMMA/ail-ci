from typing import NewType, TypedDict

UserId = NewType("UserId", int)
Email = NewType("Email", str)


class Movie(TypedDict):
    title: str
    year: int


def report(label, fn):
    try:
        print(label, fn())
    except Exception as exc:
        print(label, type(exc).__name__, exc)


def main():
    report("zero", lambda: UserId())
    report("two", lambda: UserId(1, 2))
    report("three", lambda: UserId(1, 2, 3))
    report("keyword", lambda: UserId(value=1))
    report("pos-keyword", lambda: UserId(1, value=2))
    report("star-empty", lambda: UserId(*[]))
    report("star-two", lambda: UserId(*[1, 2]))
    report("star-one", lambda: UserId(*[5]))

    movie: Movie = {"title": "Up", "year": 2009}
    report("missing-key", lambda: movie["director"])
    report("bad-lookup", lambda: movie.get("director", "none"))
    report("normal", lambda: UserId(7) + 1)
    print(type(UserId(1)).__name__, type(Email("ada")).__name__)


main()
