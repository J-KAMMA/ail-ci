import stat


MODES = [0o104755, 0o102755, 0o41777, 0o10644, 0o20666, 0o60660, 0o140755]


def main():
    for mode in MODES:
        print(mode, stat.filemode(mode))
    print("setuid bit", stat.S_ISUID)
    print("setgid bit", stat.S_ISGID)
    print("sticky bit", stat.S_ISVTX)
    print("enforcement", stat.S_ENFMT)
    print("setuid only", stat.filemode(0o104000))
    print("setgid only", stat.filemode(0o102000))
    print("sticky only", stat.filemode(0o41000))
    print("sticky without exec", stat.filemode(0o41644))
    print("setuid without exec", stat.filemode(0o104644))
    print("setgid without exec", stat.filemode(0o102644))
    print("done")


main()
