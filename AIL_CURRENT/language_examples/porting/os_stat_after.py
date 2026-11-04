import os


def main() -> None:
    with open("data.txt", "w") as handle:
        handle.write("hello")
    print(os.path.getsize("data.txt"))


main()
