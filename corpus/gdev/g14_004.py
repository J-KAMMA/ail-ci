# task: Define a dataclass with a default_factory list field and demonstrate that each instance gets its own independent list.
from dataclasses import dataclass, field


@dataclass
class Playlist:
    name: str
    songs: list[str] = field(default_factory=list)

    def add(self, song: str) -> None:
        self.songs.append(song)


def main() -> None:
    a = Playlist("Morning")
    b = Playlist("Evening")

    a.add("Sunrise Song")
    a.add("Coffee Blues")
    b.add("Night Drive")

    print(f"{a.name}: {a.songs}")
    print(f"{b.name}: {b.songs}")
    print(f"Same list object? {a.songs is b.songs}")

    c = Playlist("Empty", [])
    print(f"{c.name}: {c.songs}")
    print(f"Default lists independent? {a.songs is not b.songs}")


if __name__ == "__main__":
    main()
