# task: Use depth-first backtracking to solve the water jug problem of measuring exactly 2 liters with 4-liter and 3-liter jugs and print the steps.
from typing import Optional

CAP_A: int = 4  # 4-liter jug capacity
CAP_B: int = 3  # 3-liter jug capacity
TARGET: int = 2  # amount to measure

State = tuple[int, int]
Move = tuple[str, State]


def successors(state: State) -> list[Move]:
    """Return all legal next states in a fixed, deterministic order."""
    a, b = state
    pour_ab: int = min(a, CAP_B - b)  # pour from A into B
    pour_ba: int = min(b, CAP_A - a)  # pour from B into A
    return [
        ("Fill the 4-liter jug", (CAP_A, b)),
        ("Fill the 3-liter jug", (a, CAP_B)),
        ("Empty the 4-liter jug", (0, b)),
        ("Empty the 3-liter jug", (a, 0)),
        ("Pour the 4-liter jug into the 3-liter jug", (a - pour_ab, b + pour_ab)),
        ("Pour the 3-liter jug into the 4-liter jug", (a + pour_ba, b - pour_ba)),
    ]


def is_goal(state: State) -> bool:
    """Goal: exactly TARGET liters in either jug."""
    return state[0] == TARGET or state[1] == TARGET


def dfs(
    state: State,
    path: list[Move],
    visited: set[State],
) -> bool:
    """Depth-first backtracking search. Returns True when the goal is reached."""
    if is_goal(state):
        return True
    for description, nxt in successors(state):
        if nxt in visited:
            continue
        visited.add(nxt)
        path.append((description, nxt))
        if dfs(nxt, path, visited):
            return True
        # Backtrack: undo this move and try the next alternative.
        path.pop()
    return False


def solve() -> Optional[list[Move]]:
    """Run the DFS from the empty state and return the move path, or None."""
    start: State = (0, 0)
    path: list[Move] = []
    visited: set[State] = {start}
    if dfs(start, path, visited):
        return path
    return None


def main() -> None:
    print(
        f"Goal: measure exactly {TARGET} liters using a {CAP_A}-liter jug "
        f"and a {CAP_B}-liter jug."
    )
    print("Start: both jugs empty  (4L, 3L) = (0, 0)")
    print()

    result: Optional[list[Move]] = solve()
    if result is None:
        print("No solution found.")
        return

    state: State = (0, 0)
    for step, (description, state) in enumerate(result, start=1):
        print(f"Step {step}: {description:<44} -> (4L, 3L) = {state}")

    print()
    a, b = state
    which: str = "4-liter jug" if a == TARGET else "3-liter jug"
    print(f"Solved in {len(result)} steps: {TARGET} liters remain in the {which}.")


if __name__ == "__main__":
    main()
