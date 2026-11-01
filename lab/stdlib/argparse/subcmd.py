import argparse


def main():
    parser = argparse.ArgumentParser(prog="tool", description="Manage records.")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="add a record")
    add.add_argument("name")
    add.add_argument("--force", action="store_true")
    remove = commands.add_parser("remove", help="remove a record")
    remove.add_argument("name")
    args = parser.parse_args()
    if args.command == "add":
        print("add", args.name, args.force)
    else:
        print("remove", args.name)


if __name__ == "__main__":
    main()
