import getopt


def attempt(args, shortopts):
    try:
        options, rest = getopt.getopt(args, shortopts)
        print("ok", options, rest)
    except getopt.GetoptError as error:
        print("msg", error.msg)
        print("opt", error.opt)
        print("str", str(error))


def main():
    attempt(["-x"], "ab:c")
    attempt(["-b"], "ab:c")
    attempt(["-ab"], "ab:c")
    attempt(["-a", "-z"], "ab:c")
    attempt(["-ac"], "ab:c")


main()
