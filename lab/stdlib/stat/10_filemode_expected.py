import stat


MODES = [0o100644, 0o40755, 0o120777, 0o20666, 0o60660, 0o10644,
         0o140755, 0o104755, 0o102755, 0o41777, 0]
EXPECTED = ["-rw-r--r--", "drwxr-xr-x", "lrwxrwxrwx", "crw-rw-rw-",
            "brw-rw----", "-rwSr--r--", "srwxr-xr-x", "-rwsr-xr-x",
            "-rwxr-sr-x", "drwxrwxrwt", "----------"]


def main():
    for index in range(len(MODES)):
        got = stat.filemode(MODES[index])
        print(MODES[index], got, got == EXPECTED[index])
    for index in range(len(MODES)):
        if stat.filemode(MODES[index]) != EXPECTED[index]:
            print("mismatch", index)
    print("all", stat.filemode(MODES[0]) == EXPECTED[0])
    print("done")


main()
