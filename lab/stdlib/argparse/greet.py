import argparse


def main():
    parser = argparse.ArgumentParser(prog="greet", description="Print a greeting.")
    parser.add_argument("name")
    parser.add_argument("--greeting", default="Hello")
    parser.add_argument("--times", type=int, default=1, metavar="N")
    parser.add_argument("--excited", action="store_true")
    args = parser.parse_args()
    end = "!" if args.excited else "."
    for _ in range(args.times):
        print(f"{args.greeting}, {args.name}{end}")


if __name__ == "__main__":
    main()
