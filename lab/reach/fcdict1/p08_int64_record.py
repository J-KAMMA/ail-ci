import sys

def main():
    d = {}
    n = int(sys.argv[1])
    d['a'] = ['big', n, True]
    print(d['a'][1])
    print(d['a'][1] + 1)
main()
