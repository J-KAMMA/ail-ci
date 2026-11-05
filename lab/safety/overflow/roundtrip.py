def main() -> None:
    x: int = 1
    for i in range(62):
        x <<= 1
    print((x // 4) * 4)
    print((x // 2) + 3)
    print((x * 4) // 4)


main()
