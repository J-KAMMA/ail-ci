def main() -> None:
    a: int = 0
    b: int = 1
    for i in range(90):
        a, b = b, a + b
    print(a)
    print(b)
    for i in range(3):
        a, b = b, a + b
    print(a)


main()
