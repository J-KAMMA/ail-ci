# task: Write a script that replaces each element of a hardcoded list with the product of all other elements without using division and prints the result.
from typing import List


def product_except_self(nums: List[int]) -> List[int]:
    """Return a list where each element is the product of all other elements,
    computed without division using prefix and suffix products."""
    n = len(nums)
    result: List[int] = [1] * n

    prefix = 1
    for i in range(n):
        result[i] = prefix
        prefix *= nums[i]

    suffix = 1
    for i in range(n - 1, -1, -1):
        result[i] *= suffix
        suffix *= nums[i]

    return result


def main() -> None:
    values: List[int] = [1, 2, 3, 4, 5]
    output: List[int] = product_except_self(values)

    print(f"Input:  {values}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
