import stat


MODES = [0o40755, 0o100644, 0o120777, 0o20666, 0o60660, 0o10644,
         0o140755, 0]


def kind(mode):
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "regular"
    if stat.S_ISLNK(mode):
        return "symlink"
    if stat.S_ISCHR(mode):
        return "character"
    if stat.S_ISBLK(mode):
        return "block"
    if stat.S_ISFIFO(mode):
        return "fifo"
    if stat.S_ISSOCK(mode):
        return "socket"
    return "unknown"


def main():
    for mode in MODES:
        print(stat.filemode(mode), kind(mode))
    print("door", stat.S_ISDOOR(0o40755))
    print("port", stat.S_ISPORT(0o40755))
    print("whiteout", stat.S_ISWHT(0o40755))
    print("done")


main()
