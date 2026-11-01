# task: Use a generator expression to compute the sum of the squares of odd numbers from 1 to 999 and print the result.
def main() -> None:
    total: int = sum(n * n for n in range(1, 1000, 2))
    print(total)


if __name__ == "__main__":
    main()
