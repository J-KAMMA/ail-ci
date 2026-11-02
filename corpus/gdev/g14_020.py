# task: Implement a dataclass with hash enabled via unsafe_hash=True and use instances as dictionary keys.
from dataclasses import dataclass


@dataclass(unsafe_hash=True)
class Point:
    x: int
    y: int
    label: str = ""


def main() -> None:
    # Instances with equal field values hash equally and compare equal,
    # so they can be used interchangeably as dictionary keys.
    p1 = Point(1, 2, "origin-ish")
    p2 = Point(1, 2, "origin-ish")
    p3 = Point(3, 4, "far")

    print("p1 == p2:", p1 == p2)
    print("hash(p1) == hash(p2):", hash(p1) == hash(p2))
    print("p1 is p2:", p1 is p2)

    grid: dict[Point, str] = {}
    grid[p1] = "first"
    grid[p3] = "second"

    # Overwrite using an equal but distinct instance.
    grid[p2] = "updated via equal key"

    print("number of keys:", len(grid))
    for key in sorted(grid, key=lambda p: (p.x, p.y, p.label)):
        print(f"{key} -> {grid[key]!r}")

    # Lookup with a freshly constructed equal instance.
    lookup = Point(3, 4, "far")
    print("lookup found:", grid.get(lookup))

    # Membership in a set of instances.
    unique_points = {Point(0, 0), Point(0, 0), Point(1, 1)}
    print("unique points:", len(unique_points))


if __name__ == "__main__":
    main()
