# task: Use backtracking to find a 3-coloring of the Australian states and territories adjacency map and print the assignment.
from typing import Optional

ADJACENCY: dict[str, frozenset[str]] = {
    "ACT": frozenset({"NSW"}),
    "NSW": frozenset({"ACT", "QLD", "SA", "VIC"}),
    "NT": frozenset({"QLD", "SA", "WA"}),
    "QLD": frozenset({"NSW", "NT", "SA"}),
    "SA": frozenset({"NSW", "NT", "QLD", "VIC", "WA"}),
    "TAS": frozenset(),
    "VIC": frozenset({"NSW", "SA"}),
    "WA": frozenset({"NT", "SA"}),
}

COLORS: tuple[str, ...] = ("red", "green", "blue")


def is_safe(region: str, color: str, assignment: dict[str, str]) -> bool:
    """Return True if no neighbour of `region` already uses `color`."""
    return all(assignment.get(neighbour) != color for neighbour in ADJACENCY[region])


def backtrack(
    regions: list[str], index: int, assignment: dict[str, str]
) -> Optional[dict[str, str]]:
    """Assign colours to regions[index:] via depth-first backtracking."""
    if index == len(regions):
        return dict(assignment)

    region = regions[index]
    for color in COLORS:
        if is_safe(region, color, assignment):
            assignment[region] = color
            result = backtrack(regions, index + 1, assignment)
            if result is not None:
                return result
            del assignment[region]
    return None


def main() -> None:
    regions: list[str] = sorted(ADJACENCY)
    solution: Optional[dict[str, str]] = backtrack(regions, 0, {})

    if solution is None:
        print("No 3-coloring exists.")
        return

    print("3-coloring of Australian states and territories:")
    for region in sorted(solution):
        print(f"{region}: {solution[region]}")


if __name__ == "__main__":
    main()
