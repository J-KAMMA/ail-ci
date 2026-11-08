def push(values: list[int]) -> int:
    values.append(9)
    return len(values)


def main() -> None:
    values = [1, 2]
    print(push(values), values)


main()
