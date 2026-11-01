import argparse


def main():
    parser = argparse.ArgumentParser(
        prog="deploy",
        description="Deploy an artifact.",
        epilog="Use --dry-run first.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("artifact", help="artifact to deploy")
    parser.add_argument("-e", "--env", choices=["dev", "staging", "prod"], default="dev",
                        help="target environment")
    parser.add_argument("--dry-run", action="store_true", help="print the plan only")
    parser.add_argument("--retries", type=int, default=3, metavar="N", help="number of retries")
    parser.add_argument("--verbose", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.dry_run:
        print("plan", args.artifact, args.env, args.retries)
    else:
        print("deploying", args.artifact, "to", args.env, "retries", args.retries)


if __name__ == "__main__":
    main()
