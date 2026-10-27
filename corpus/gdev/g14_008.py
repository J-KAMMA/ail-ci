# task: Use dataclasses.replace to produce modified copies of an immutable Config dataclass and print both versions.
from dataclasses import dataclass, replace, asdict


@dataclass(frozen=True)
class Config:
    app_name: str = "demo"
    version: int = 1
    debug: bool = False
    max_connections: int = 10
    tags: tuple[str, ...] = ("alpha", "beta")


def describe(label: str, cfg: Config) -> None:
    print(f"{label}:")
    for key, value in asdict(cfg).items():
        print(f"  {key} = {value!r}")


def main() -> None:
    original = Config()

    # dataclasses.replace returns a new instance with the given fields changed;
    # the original instance is left untouched because Config is frozen.
    modified = replace(original, debug=True, max_connections=50, version=2)

    # Replacing a tuple field also creates a fresh copy rather than mutating.
    extended = replace(modified, tags=modified.tags + ("gamma",))

    describe("Original config", original)
    print()
    describe("Modified config", modified)
    print()
    describe("Extended config", extended)
    print()

    print(f"original is modified: {original is modified}")
    print(f"original == modified: {original == modified}")
    print(f"modified == extended: {modified == extended}")


if __name__ == "__main__":
    main()
