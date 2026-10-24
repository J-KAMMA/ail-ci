# task: Write a script that finds the common characters between two hardcoded strings using set intersection and prints them sorted.
def main() -> None:
    first: str = "programming language"
    second: str = "python interpreter"

    common: set[str] = set(first) & set(second)
    for char in sorted(common):
        print(char)


if __name__ == "__main__":
    main()
