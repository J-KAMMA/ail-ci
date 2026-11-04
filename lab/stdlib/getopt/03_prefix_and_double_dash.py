import getopt


LONG = ["help", "out=", "verbose"]


def show(args, shortopts):
    options, rest = getopt.getopt(args, shortopts, LONG)
    print("args", args)
    print("options", options)
    print("rest", rest)


def main():
    show(["--he"], "v")
    show(["--verb"], "v")
    show(["--out=result.txt", "--", "-v", "input"], "v")
    show(["-v", "--", "--help"], "v")
    show(["--", "plain"], "v")


main()
