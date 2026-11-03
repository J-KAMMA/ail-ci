# task: Trigger KeyError, IndexError, and TypeError deliberately and print a lookup table that maps each exception type to a recovery action.
from typing import Callable


def trigger_key_error() -> None:
    config: dict[str, int] = {"retries": 3}
    _ = config["timeout"]


def trigger_index_error() -> None:
    items: list[int] = [10, 20, 30]
    _ = items[5]


def trigger_type_error() -> None:
    _ = "count: " + 5  # type: ignore[operator]


def recover_key_error(exc: Exception) -> str:
    return f"use dict.get() with a default value (missing key: {exc.args[0]!r})"


def recover_index_error(exc: Exception) -> str:
    return f"check len() before indexing or fall back to a default item ({exc})"


def recover_type_error(exc: Exception) -> str:
    return f"convert operands explicitly (e.g. str()/int()) before combining ({exc})"


def probe(
    trigger: Callable[[], None],
    recover: Callable[[Exception], str],
) -> tuple[str, str]:
    try:
        trigger()
    except (KeyError, IndexError, TypeError) as exc:
        return type(exc).__name__, recover(exc)
    return "none", "no exception raised"


def main() -> None:
    cases: list[tuple[Callable[[], None], Callable[[Exception], str]]] = [
        (trigger_key_error, recover_key_error),
        (trigger_index_error, recover_index_error),
        (trigger_type_error, recover_type_error),
    ]

    rows: list[tuple[str, str]] = [probe(trigger, recover) for trigger, recover in cases]

    print("Exception Recovery Lookup Table")
    print("=" * 72)
    print(f"{'Exception':<14}| Recovery Action")
    print("-" * 72)
    for name, action in rows:
        print(f"{name:<14}| {action}")
    print("=" * 72)


if __name__ == "__main__":
    main()
