import argparse


def main():
    parser = argparse.ArgumentParser(description="Show a development server configuration.")
    parser.add_argument("-H", "--host", default="127.0.0.1")
    parser.add_argument("-p", "--port", type=int, default=8080, metavar="PORT")
    parser.add_argument("--log-level", dest="level", choices=["debug", "info", "warn"], default="info")
    parser.add_argument("--workers", nargs="?", const=4, type=int, default=1)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--tag", action="append_const", const="server", dest="tags", default=[])
    args = parser.parse_args()
    print(f"{args.host}:{args.port}")
    print("level", args.level)
    print("workers", args.workers)
    print("debug", args.debug)
    print("tags", ",".join(args.tags))


if __name__ == "__main__":
    main()
