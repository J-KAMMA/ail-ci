import stat


FIELDS = ["mode", "ino", "dev", "nlink", "uid", "gid", "size",
          "atime", "mtime", "ctime"]
VALUES = [0o100644, 42, 7, 1, 1000, 1000, 4096, 1700000000, 1700000100,
          1700000200]


def main():
    print("indexes", stat.ST_MODE, stat.ST_INO, stat.ST_DEV, stat.ST_NLINK,
          stat.ST_UID, stat.ST_GID, stat.ST_SIZE, stat.ST_ATIME, stat.ST_MTIME,
          stat.ST_CTIME)
    for index in range(len(FIELDS)):
        print(index, FIELDS[index], VALUES[index])
    print("mode field", VALUES[stat.ST_MODE])
    print("size field", VALUES[stat.ST_SIZE])
    print("uid field", VALUES[stat.ST_UID])
    print("is regular", stat.S_ISREG(VALUES[stat.ST_MODE]))
    print("mode string", stat.filemode(VALUES[stat.ST_MODE]))
    print("done")


main()
