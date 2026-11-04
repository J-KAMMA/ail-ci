import getopt


def show(args, shortopts, longopts):
    options, rest = getopt.getopt(args, shortopts, longopts)
    print("args", args)
    print("options", options)
    print("rest", rest)


def main():
    show(["-vvv"], "v", [])
    show(["-o-", "-o", "-"], "o:", [])
    show(["--out=", "--verbose"], "v", ["out=", "verbose"])
    show(["--out=a=b"], "v", ["out="])
    show(["-o", "--"], "o:", [])


main()
