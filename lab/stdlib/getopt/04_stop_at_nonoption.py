import getopt


def show(args, shortopts):
    options, rest = getopt.getopt(args, shortopts)
    print("args", args)
    print("options", options)
    print("rest", rest)


def main():
    show(["-a", "file", "-b"], "ab:")
    show(["-b", "value", "file"], "ab:")
    show(["-a", "--", "file", "-b"], "ab:")
    show(["-", "-a"], "a")


main()
