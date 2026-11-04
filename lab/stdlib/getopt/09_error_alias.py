import getopt


def attempt(args):
    try:
        options, rest = getopt.getopt(args, "a")
        print("ok", options, rest)
    except getopt.error as error:
        print("caught", error.msg)
        print("opt", error.opt)
        print("str", str(error))


def main():
    print("alias", getopt.error is getopt.GetoptError)
    attempt(["-x"])
    attempt(["-a"])
    raised = getopt.error("manual failure", "m")
    print("manual", raised.msg, raised.opt)
    print("manual str", str(raised))


main()
