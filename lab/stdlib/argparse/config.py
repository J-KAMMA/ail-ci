import argparse


def main():
    parser = argparse.ArgumentParser(description="Write a configuration file.")
    parser.add_argument("--version", action="version", version="config 1.2.3")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--json", action="store_true")
    group.add_argument("--yaml", action="store_true")
    parser.add_argument("-o", "--output", default="-")
    parser.add_argument("--name", default="app")
    args = parser.parse_args()
    if args.json:
        fmt = "json"
    elif args.yaml:
        fmt = "yaml"
    else:
        fmt = "text"
    print("name", args.name)
    print("format", fmt)
    print("output", args.output)


if __name__ == "__main__":
    main()
