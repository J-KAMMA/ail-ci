from typing import TypedDict


class Movie(TypedDict):
    title: str
    year: int


class Book(TypedDict):
    title: str
    pages: int


def summary(m: Movie) -> str:
    return m["title"] + " (" + str(m["year"]) + ")"


def main() -> None:
    m: Movie = {"title": "Alien", "year": 1979}
    print(summary(m))
    print(m["title"], m["year"])
    print(len(m))
    print(sorted(m))
    m["year"] = 1986
    print(m)
    b: Book = {"title": "Dune", "pages": 412}
    print(b["title"], b["pages"])
    made = Movie(title="Up", year=2009)
    print(made["title"], made["year"])
    data = {"title": "Heat", "year": 1995}
    other = Movie(**data)
    print(other)


main()
