# task: Create a dataclass Config loaded from a dict with nested dataclass conversion via a recursive from_dict function.
from __future__ import annotations

import types
from dataclasses import MISSING, asdict, dataclass, field, fields, is_dataclass
from typing import Any, Mapping, TypeVar, Union, get_args, get_origin, get_type_hints

T = TypeVar("T")


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432


@dataclass
class LoggingConfig:
    level: str = "INFO"
    handlers: list[str] = field(default_factory=list)


@dataclass
class Config:
    name: str
    debug: bool = False
    timeout: float | None = None
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    tags: dict[str, int] = field(default_factory=dict)
    replicas: list[DatabaseConfig] = field(default_factory=list)


def _convert(tp: Any, value: Any) -> Any:
    """Convert a raw value (from a dict) to the annotated type tp, recursively."""
    origin = get_origin(tp)

    # Optional / Union handling (both typing.Union and X | Y syntax)
    if origin is Union or origin is types.UnionType:
        args = get_args(tp)
        if value is None:
            if type(None) in args:
                return None
            raise TypeError(f"None is not allowed for {tp!r}")
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _convert(non_none[0], value)
        for arg in non_none:
            try:
                return _convert(arg, value)
            except (TypeError, ValueError):
                continue
        raise TypeError(f"Value {value!r} does not match {tp!r}")

    if value is None:
        raise TypeError(f"None is not allowed for {tp!r}")

    # Nested dataclass
    if isinstance(tp, type) and is_dataclass(tp):
        if not isinstance(value, Mapping):
            raise TypeError(f"Expected mapping for {tp.__name__}, got {type(value).__name__}")
        return from_dict(tp, value)

    # Containers
    if origin is list:
        (elem_tp,) = get_args(tp) or (Any,)
        if not isinstance(value, list):
            raise TypeError(f"Expected list, got {type(value).__name__}")
        return [_convert(elem_tp, v) for v in value]

    if origin is dict:
        key_tp, val_tp = get_args(tp) or (Any, Any)
        if not isinstance(value, Mapping):
            raise TypeError(f"Expected mapping, got {type(value).__name__}")
        return {_convert(key_tp, k): _convert(val_tp, v) for k, v in value.items()}

    # Primitive scalars
    if tp is float and isinstance(value, int) and not isinstance(value, bool):
        return float(value)
    if isinstance(tp, type) and tp is not Any:
        if not isinstance(value, tp):
            raise TypeError(f"Expected {tp.__name__}, got {type(value).__name__}")
        return value

    return value


def from_dict(cls: type[T], data: Mapping[str, Any]) -> T:
    """Recursively build a dataclass instance of type cls from a plain dict."""
    if not (isinstance(cls, type) and is_dataclass(cls)):
        raise TypeError(f"{cls!r} is not a dataclass")

    hints = get_type_hints(cls)
    known = {f.name for f in fields(cls)}

    unknown = sorted(set(data) - known)
    if unknown:
        raise ValueError(f"Unknown keys for {cls.__name__}: {unknown}")

    kwargs: dict[str, Any] = {}
    for f in fields(cls):
        if f.name in data:
            kwargs[f.name] = _convert(hints[f.name], data[f.name])
        elif f.default is MISSING and f.default_factory is MISSING:
            raise ValueError(f"Missing required key '{f.name}' for {cls.__name__}")

    return cls(**kwargs)


def main() -> None:
    raw: dict[str, Any] = {
        "name": "demo-service",
        "debug": True,
        "timeout": 3,
        "database": {"host": "db.internal", "port": 6543},
        "logging": {"level": "DEBUG", "handlers": ["console", "file"]},
        "tags": {"env": 1, "tier": 2},
        "replicas": [{"host": "replica-1"}, {"port": 5433}],
    }

    config = from_dict(Config, raw)
    print("Loaded config:")
    print(config)
    print()

    print("Types:")
    print(f"  database is DatabaseConfig: {isinstance(config.database, DatabaseConfig)}")
    print(f"  replicas[0] is DatabaseConfig: {isinstance(config.replicas[0], DatabaseConfig)}")
    print(f"  timeout type: {type(config.timeout).__name__}")
    print()

    print("Round trip via asdict:")
    print(asdict(config))
    print()

    minimal = from_dict(Config, {"name": "minimal"})
    print("Minimal config defaults:")
    print(minimal)
    print()

    for bad in (
        {"name": "x", "colour": "red"},
        {"debug": False},
        {"name": "x", "database": {"port": "not-a-number"}},
    ):
        try:
            from_dict(Config, bad)
        except (TypeError, ValueError) as exc:
            print(f"Rejected {bad!r}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
