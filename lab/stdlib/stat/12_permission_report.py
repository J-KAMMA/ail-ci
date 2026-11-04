import stat


def report(mode):
    parts = []
    if mode & stat.S_IRUSR:
        parts.append("u+r")
    if mode & stat.S_IWUSR:
        parts.append("u+w")
    if mode & stat.S_IXUSR:
        parts.append("u+x")
    if mode & stat.S_IRGRP:
        parts.append("g+r")
    if mode & stat.S_IWGRP:
        parts.append("g+w")
    if mode & stat.S_IXGRP:
        parts.append("g+x")
    if mode & stat.S_IROTH:
        parts.append("o+r")
    if mode & stat.S_IWOTH:
        parts.append("o+w")
    if mode & stat.S_IXOTH:
        parts.append("o+x")
    if mode & stat.S_ISUID:
        parts.append("setuid")
    if mode & stat.S_ISGID:
        parts.append("setgid")
    if mode & stat.S_ISVTX:
        parts.append("sticky")
    return " ".join(parts)


def main():
    for mode in [0o100644, 0o100755, 0o104755, 0o102755, 0o41777, 0o100600]:
        print(mode, report(mode))
    print("permissions", stat.S_IMODE(0o104755))
    print("type", stat.S_IFMT(0o104755))
    print("done")


main()
