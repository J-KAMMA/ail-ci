import argparse


def main():
    parser = argparse.ArgumentParser(description="Search source trees.")
    parser.add_argument("--pattern", required=True)
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--mode", choices=["fast", "full"], default="fast")
    parser.add_argument("query", nargs="+")
    args = parser.parse_args()
    print("pattern", args.pattern)
    print("paths", len(args.path), args.path)
    print("limit", args.limit)
    print("mode", args.mode)
    print("query", " ".join(args.query))


if __name__ == "__main__":
    main()
