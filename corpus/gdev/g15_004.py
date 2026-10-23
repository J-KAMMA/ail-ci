# task: Use exception chaining with raise from to wrap a KeyError in a custom ConfigError and print the type of the stored __cause__.
from typing import Optional


class ConfigError(Exception):
    """Raised when a configuration lookup fails."""


def load_setting(config: dict[str, str], key: str) -> str:
    """Return the configuration value for key, wrapping KeyError in ConfigError."""
    try:
        return config[key]
    except KeyError as exc:
        raise ConfigError(f"missing configuration key: {key!r}") from exc


def main() -> None:
    config: dict[str, str] = {"host": "localhost", "port": "8080"}

    caught: Optional[ConfigError] = None
    try:
        load_setting(config, "timeout")
    except ConfigError as err:
        caught = err

    if caught is not None:
        print(f"Caught: {caught}")
        cause = caught.__cause__
        print(f"Type of __cause__: {type(cause).__name__}")
        print(f"Cause type is KeyError: {isinstance(cause, KeyError)}")


if __name__ == "__main__":
    main()
