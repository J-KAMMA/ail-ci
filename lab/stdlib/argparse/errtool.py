import argparse


def main():
    parser = argparse.ArgumentParser(description="Retry a job.")
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--label", default="job")
    try:
        args = parser.parse_args()
    except SystemExit as error:
        print("usage error", error.code)
        return
    print("label", args.label)
    print("count", args.count)


if __name__ == "__main__":
    main()
