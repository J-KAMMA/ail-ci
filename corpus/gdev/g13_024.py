# task: Implement a JSONSerializable mixin with a serialize method and apply it to Book and Author classes, printing their serialized strings with json.
import json
from dataclasses import dataclass, field, asdict
from typing import Any


class JSONSerializable:
    """Mixin that provides a serialize method returning a JSON string."""

    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the instance."""
        return dict(vars(self))

    def serialize(self) -> str:
        """Return a deterministic JSON string representation of the instance."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)


@dataclass
class Author(JSONSerializable):
    name: str
    birth_year: int
    nationality: str = "Unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "birth_year": self.birth_year,
            "nationality": self.nationality,
        }


@dataclass
class Book(JSONSerializable):
    title: str
    year: int
    isbn: str
    author: Author
    genres: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "year": self.year,
            "isbn": self.isbn,
            "author": self.author.to_dict(),
            "genres": list(self.genres),
        }


def main() -> None:
    author = Author(name="Ursula K. Le Guin", birth_year=1929, nationality="American")
    book = Book(
        title="The Left Hand of Darkness",
        year=1969,
        isbn="978-0441478125",
        author=author,
        genres=["Science Fiction", "Novel"],
    )

    print(author.serialize())
    print(book.serialize())


if __name__ == "__main__":
    main()
