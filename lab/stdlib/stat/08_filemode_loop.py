import stat


def main():
    total = 0
    modes = 0
    mode = 0
    while mode < 4096:
        text = stat.filemode(0o100000 | mode)
        index = 0
        while index < len(text):
            total = (total * 31 + ord(text[index])) % 1000000007
            index = index + 1
        if mode % 500 == 0:
            print("sample", mode, text)
        modes = modes + 1
        mode = mode + 1
    print("modes", modes)
    print("checksum", total)
    print("done")


main()
