import getopt
import sys


def parse(args):
    try:
        options, rest = getopt.getopt(args, "vo:", ["verbose", "output="])
    except getopt.GetoptError as error:
        sys.stderr.write("tool: " + error.msg + "\n")
        print("usage: tool [-v] [-o FILE] [FILE...]", file=sys.stderr)
        sys.exit(2)
    return options, rest


def main():
    options, rest = parse(["-v", "-o", "out.txt", "in.txt"])
    print("options", options)
    print("rest", rest)
    parse(["--bad"])


main()
