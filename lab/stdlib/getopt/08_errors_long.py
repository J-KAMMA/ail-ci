import getopt


LONG = ["help", "out=", "verbose"]
EXTRA = ["input=", "inspect", "verbose"]


def attempt(args, longopts):
    try:
        options, rest = getopt.getopt(args, "v", longopts)
        print("ok", options, rest)
    except getopt.GetoptError as error:
        print("msg", error.msg)
        print("opt", error.opt)
        print("str", str(error))


def main():
    attempt(["--nope"], LONG)
    attempt(["--out"], LONG)
    attempt(["--help=1"], LONG)
    attempt(["--in"], EXTRA)
    attempt(["--out="], LONG)


main()
