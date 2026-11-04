import stat


MODES = [0o100644, 0o40755, 0o120777, 0o20666, 0o60660, 0o10644,
         0o140755, 0o104755, 0o102755, 0o41777, 0]


def main():
    for mode in MODES:
        print("mode", mode)
        print("  ifmt", stat.S_IFMT(mode))
        print("  imode", stat.S_IMODE(mode))
    print("type constants", stat.S_IFDIR, stat.S_IFCHR, stat.S_IFBLK,
          stat.S_IFREG, stat.S_IFIFO, stat.S_IFLNK, stat.S_IFSOCK)
    print("portable fallbacks", stat.S_IFDOOR, stat.S_IFPORT, stat.S_IFWHT)
    print("done")


main()
