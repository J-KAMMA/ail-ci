import fnmatch


def main():
    files = ["a.py", "b.txt", "c.py", "data.csv", "Makefile", "test_a.py"]
    print(fnmatch.filter(files, "*.py"))
    print(fnmatch.filter(files, "test_*"))
    print(fnmatch.filter(files, "*"))
    print(fnmatch.filter(files, "*.c"))
    data = [b"one.bin", b"two.txt", b"three.bin"]
    print(fnmatch.filter(data, b"*.bin"))
    print(fnmatch.fnmatch(b"name.txt", b"*.txt"))


main()
