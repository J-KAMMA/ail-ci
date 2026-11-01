import fnmatch


def older_backups(names, keep):
    numbered = fnmatch.filter(names, "backup-*.[0-9]")
    numbered.sort()
    return numbered[:max(0, len(numbered) - keep)]


def main():
    names = [
        "backup-a.1",
        "backup-a.2",
        "backup-a.3",
        "backup-b.9",
        "backup-a.10",
        "backup-a.tmp",
        "current",
    ]
    print("all", fnmatch.filter(names, "*"))
    print("numbered", fnmatch.filter(names, "backup-*.[0-9]"))
    print("one digit", fnmatch.filter(names, "backup-*.[!0-9]*"))
    print("old", older_backups(names, 2))
    print("none", older_backups(names, 10))
    print("empty names", fnmatch.filter([], "*"))
    print("empty names 2", older_backups([], 3))
    print("prefix", fnmatch.filter(names, "*backup*"))
    print("suffix", fnmatch.filter(names, "*.[0-9]"))
    print("both", fnmatch.filter(names, "?ackup-a.?"))


main()
