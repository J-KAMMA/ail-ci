def main() -> None:
    values = [1, 3]
    for i in range(4):
        values[0] += values[0]
    print(values[0], values[1])
    for i in range(58):
        values[0] += values[0]
    print(values[0])
    values[0] += values[0]
    print(values[0])


main()
