import getopt


VALUES = ["42", "-9223372036854775808", "99999999999999999999"]


def main():
    for text in VALUES:
        options, rest = getopt.getopt(["-n", text], "n:")
        number = int(options[0][1])
        print("value", options[0][1])
        print("number", number)
        print("plus one", number + 1)


main()
