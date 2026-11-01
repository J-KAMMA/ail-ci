import argparse


def build_parser():
    parser = argparse.ArgumentParser(description="Scan paths.")
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("--color", choices=["auto", "always", "never"], default="auto")
    parser.add_argument("paths", nargs="*")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    print("verbose", args.verbose)
    print("color", args.color)
    print("paths", len(args.paths), args.paths)


if __name__ == "__main__":
    main()
