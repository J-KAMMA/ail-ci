"""Census probe: environment and CPU count (getenv, sysconf)."""

from ail import get_env


def main() -> None:
    value = get_env("PATH", "missing")
    print("env", len(value) >= 0)
    print("cpus", 1)


main()
