import getopt


def show(args, shortopts):
    options, rest = getopt.getopt(args, shortopts)
    print("args", args)
    print("options", options)
    print("rest", rest)


def main():
    show(["-a", "-b", "value", "-c"], "ab:c")
    show(["-bvalue", "-ac"], "ab:c")
    show(["-ab", "x", "-c"], "ab:c")
    show(["-a", "-a"], "a")


main()
