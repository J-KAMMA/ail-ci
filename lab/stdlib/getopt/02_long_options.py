import getopt


LONG = ["help", "out=", "verbose"]


def show(args, shortopts):
    options, rest = getopt.getopt(args, shortopts, LONG)
    print("args", args)
    print("options", options)
    print("rest", rest)


def main():
    show(["--help"], "v")
    show(["--out=x"], "v")
    show(["--out", "x"], "v")
    show(["--verbose", "-v", "file"], "v")
    show(["--out=result.txt", "--verbose"], "v")


main()
