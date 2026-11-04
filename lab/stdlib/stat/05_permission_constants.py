import stat


def main():
    owner = stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR
    group = stat.S_IRGRP | stat.S_IWGRP
    other = stat.S_IROTH
    mask = owner | group | other
    print("owner", owner)
    print("group", group)
    print("other", other)
    print("mask", mask)
    print("masks", stat.S_IRWXU, stat.S_IRWXG, stat.S_IRWXO)
    print("owner read", owner & stat.S_IRUSR != 0)
    print("owner write", owner & stat.S_IWUSR != 0)
    print("owner exec", owner & stat.S_IXUSR != 0)
    print("group exec", group & stat.S_IXGRP != 0)
    print("other write", other & stat.S_IWOTH != 0)
    print("special", stat.S_ISUID, stat.S_ISGID, stat.S_ISVTX)
    print("enf is gid", stat.S_ENFMT == stat.S_ISGID)
    print("v7 synonyms", stat.S_IREAD, stat.S_IWRITE, stat.S_IEXEC)
    print("built", stat.filemode(0o100600 | mask))
    print("done")


main()
