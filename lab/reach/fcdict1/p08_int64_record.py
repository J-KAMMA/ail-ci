import sys


def main():
    if len(sys.argv) > 1:
        n = int(sys.argv[1])
    else:
        n = 9223372036854775807 + len(sys.argv)
    d = {}
    d['a'] = ['big', n, True]
    print(d['a'][1])
    print(d['a'][1] + 1)


main()
