def main() -> None:
    x: int = 1
    for i in range(10):
        x <<= 1
    print(x)
    for i in range(52):
        x <<= 1
    print(x)
    x <<= 1
    print(x)


main()
