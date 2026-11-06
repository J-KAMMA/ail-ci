# task: Write a script that uses the nim-sum to find and print the winning move for the first player from Nim heaps [3, 4, 5].
from functools import reduce


def nim_sum(heaps: list[int]) -> int:
    """Return the XOR (nim-sum) of all heap sizes."""
    return reduce(lambda a, b: a ^ b, heaps, 0)


def winning_move(heaps: list[int]) -> tuple[int, int] | None:
    """
    Return (heap_index, stones_to_remove) for a winning move,
    or None if the position is a loss for the player to move.
    """
    total = nim_sum(heaps)
    if total == 0:
        return None
    for index, size in enumerate(heaps):
        target = size ^ total
        if target < size:
            return index, size - target
    return None


def main() -> None:
    heaps: list[int] = [3, 4, 5]
    print(f"Initial heaps: {heaps}")
    print(f"Nim-sum: {nim_sum(heaps)}")

    move = winning_move(heaps)
    if move is None:
        print("No winning move exists; the position is a loss for the first player.")
        return

    index, remove = move
    new_heaps = heaps.copy()
    new_heaps[index] -= remove
    print(f"Winning move: remove {remove} stone(s) from heap {index + 1} "
          f"(size {heaps[index]})")
    print(f"Heaps after move: {new_heaps}")
    print(f"Nim-sum after move: {nim_sum(new_heaps)}")


if __name__ == "__main__":
    main()
