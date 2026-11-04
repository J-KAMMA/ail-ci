import getopt


def show(args, shortopts):
    options, rest = getopt.gnu_getopt(args, shortopts, [])
    print("args", args)
    print("options", options)
    print("rest", rest)


def main():
    show(["-a", "file", "-b", "x"], "+ab:")
    show(["--", "-a", "file"], "+ab:")
    show(["-b", "x", "--", "tail"], "+ab:")
    show(["file", "--", "-a"], "ab:")
    show(["file", "-a", "tail"], "+a")


main()
