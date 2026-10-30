# task: Compute C(100, 50) with math.comb and verify it against a Pascal's triangle computation, printing both results.
import math


def pascal_binomial(n: int, k: int) -> int:
    """Compute C(n, k) by building Pascal's triangle row by row up to row n."""
    row: list[int] = [1]
    for _ in range(n):
        next_row: list[int] = [1]
        for j in range(1, len(row)):
            next_row.append(row[j - 1] + row[j])
        next_row.append(1)
        row = next_row
    return row[k]


def main() -> None:
    n: int = 100
    k: int = 50

    comb_result: int = math.comb(n, k)
    pascal_result: int = pascal_binomial(n, k)

    print(f"math.comb({n}, {k}) = {comb_result}")
    print(f"Pascal's triangle C({n}, {k}) = {pascal_result}")
    if comb_result == pascal_result:
        print("Verification: PASSED (results match)")
    else:
        print("Verification: FAILED (results differ)")


if __name__ == "__main__":
    main()
