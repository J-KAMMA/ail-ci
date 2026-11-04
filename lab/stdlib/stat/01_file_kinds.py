import stat


MODES = [0o40755, 0o100644, 0o120777, 0o20666, 0o60660, 0o140755, 0]


def main():
    for mode in MODES:
        print("mode", mode)
        print("  dir", stat.S_ISDIR(mode))
        print("  reg", stat.S_ISREG(mode))
        print("  lnk", stat.S_ISLNK(mode))
        print("  chr", stat.S_ISCHR(mode))
        print("  blk", stat.S_ISBLK(mode))
        print("  fifo", stat.S_ISFIFO(mode))
        print("  sock", stat.S_ISSOCK(mode))
        print("  mode string", stat.filemode(mode))
    print("done")


main()
