import argparse


def main():
    parser = argparse.ArgumentParser(description="Copy files to a backup directory.")
    parser.add_argument("source")
    parser.add_argument("destination")
    parser.add_argument("-c", "--compress", action="store_true")
    parser.add_argument("--level", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("-q", "--quiet", dest="verbose", action="store_false")
    args = parser.parse_args()
    print("source", args.source)
    print("destination", args.destination)
    print("compress", args.compress)
    print("level", args.level)
    print("exclude", ",".join(args.exclude))
    print("verbose", args.verbose)


if __name__ == "__main__":
    main()
