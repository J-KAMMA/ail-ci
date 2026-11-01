import argparse


def main():
    parser = argparse.ArgumentParser(description="Manage labels for a record.")
    parser.add_argument("name")
    parser.add_argument("label", nargs="?")
    parser.add_argument("--pair", nargs=2, metavar=("KEY", "VALUE"))
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("-v", action="count", default=0)
    parser.add_argument("--color", action="store_const", const="blue", dest="color", default="none")
    args = parser.parse_args()
    print("name", args.name)
    print("label", args.label)
    print("pair", args.pair)
    print("tags", args.tag)
    print("verbose", args.v)
    print("color", args.color)


if __name__ == "__main__":
    main()
