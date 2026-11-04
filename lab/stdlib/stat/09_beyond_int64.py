import stat


def main():
    try:
        mode = 2
        step = 0
        while step < 70:
            mode = mode * 2
            step = step + 1
        print("mode", mode)
        print("filemode", stat.filemode(mode))
    except Exception as error:
        print("error name", type(error).__name__)
    print("done")


main()
