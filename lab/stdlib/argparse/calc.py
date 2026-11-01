import argparse


def main():
    parser = argparse.ArgumentParser(description="Add or multiply numbers.")
    parser.add_argument("--op", choices=["add", "mul"], default="add")
    parser.add_argument("numbers", nargs="+", type=float)
    args, extra = parser.parse_known_args()
    total = args.numbers[0]
    for value in args.numbers[1:]:
        if args.op == "add":
            total = total + value
        else:
            total = total * value
    print("result", total)
    print("unknown", extra)


if __name__ == "__main__":
    main()
