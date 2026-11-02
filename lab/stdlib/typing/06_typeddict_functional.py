import typing
from typing import TypedDict

Movie = TypedDict("Movie", {"title": str, "year": int})
Config = typing.TypedDict("Config", {"name": str, "debug": bool})


def describe(m: Movie) -> str:
    tag = "on" if m["year"] >= 2000 else "old"
    return m["title"] + " " + tag


def main() -> None:
    m: Movie = {"title": "Arrival", "year": 2016}
    print(describe(m))
    c: Config = Config(name="app", debug=True)
    print(c["name"], c["debug"])
    print(c == {"name": "app", "debug": True})
    c["debug"] = False
    print(c)
    print(list(m.keys()))
    print(m.get("year"))


main()
