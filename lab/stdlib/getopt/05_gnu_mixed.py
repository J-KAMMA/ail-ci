import getopt


def show(args, shortopts, longopts):
    options, rest = getopt.gnu_getopt(args, shortopts, longopts)
    print("args", args)
    print("options", options)
    print("rest", rest)


def main():
    show(["one", "-a", "two", "-b", "x", "three"], "ab:", [])
    show(["--out=o", "one", "--verbose", "two"], "v", ["out=", "verbose"])
    show(["-a", "file", "--", "-b", "x"], "ab:", [])
    show(["first", "--verbose", "last", "-v"], "v", ["verbose"])


main()
