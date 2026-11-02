from typing import Final, Literal, TypeAlias

Mode = Literal["fast", "safe", "debug"]
Name: TypeAlias = str
MAX_RETRIES: Final = 3
DEFAULT_MODE: Final[Mode] = "safe"


def attempts(mode: Mode) -> int:
    if mode == "fast":
        return 1
    if mode == "debug":
        return MAX_RETRIES * 2
    return MAX_RETRIES


def banner(name: Name, mode: Mode) -> str:
    return name + ":" + mode


def main() -> None:
    print(MAX_RETRIES)
    print(DEFAULT_MODE)
    for mode in ("fast", "safe", "debug"):
        print(mode, attempts(mode))
    print(banner("worker", "fast"))
    chosen: Mode = "safe"
    print(chosen, chosen == "safe")


main()
