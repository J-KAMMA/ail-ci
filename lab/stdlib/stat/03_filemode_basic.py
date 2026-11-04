import stat


MODES = [0o100644, 0o40755, 0o120777, 0]


def main():
    for mode in MODES:
        print(mode, stat.filemode(mode))
    print("zero", stat.filemode(0))
    print("plain regular", stat.filemode(0o100000))
    print("plain directory", stat.filemode(0o40000))
    print("empty permission", stat.filemode(0o100000))
    print("all permissions", stat.filemode(0o100777))
    print("done")


main()
