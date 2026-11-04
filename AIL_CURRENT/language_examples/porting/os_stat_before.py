import os


def main() -> None:
    with open("data.txt", "w") as handle:
        handle.write("hello")
    info = os.stat("data.txt")
    print(info.st_size)


main()
