"""Census probe: environment (getenv through ail.get_env)."""

from ail import get_env


def main() -> None:
    print("PATH =", get_env("PATH", "missing"))


main()
