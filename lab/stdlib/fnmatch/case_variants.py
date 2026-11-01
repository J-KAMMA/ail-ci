import fnmatch


def main():
    names = ["README", "readme", "ReadMe.md", "LICENSE", "license.txt", "Makefile"]
    print("upper", fnmatch.filter(names, "*README*"))
    print("lower", fnmatch.filter(names, "*readme*"))
    print("mixed", fnmatch.filter(names, "ReadMe.*"))
    print("license", fnmatch.filter(names, "LICENSE*"))
    for name in names:
        print(name,
              fnmatch.fnmatch(name, "readme*"),
              fnmatch.fnmatchcase(name, "readme*"),
              fnmatch.fnmatch(name, "README"),
              fnmatch.fnmatchcase(name, "README"))
    print("case-insensitive style", fnmatch.filter([n.lower() for n in names], "readme*"))
    print("suffix", fnmatch.fnmatchcase("archive.TAR.GZ", "*.tar.gz"))
    print("suffix lower", fnmatch.fnmatchcase("archive.tar.gz", "*.tar.gz"))


main()
