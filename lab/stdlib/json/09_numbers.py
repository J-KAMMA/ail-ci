import json
import math


def main() -> None:
    values: list[float] = json.loads("[1.5, 2.0, -0.0, 1e3, 1E-2]")
    for value in values:
        print(value, json.dumps(value))
    print(json.dumps(values, allow_nan=True))
    print(json.dumps(float("nan")), json.dumps(float("inf")), json.dumps(float("-inf")))
    for bad in (float("nan"), float("inf")):
        try:
            json.dumps(bad, allow_nan=False)
        except ValueError as exc:
            print("ValueError:", exc)
    print(json.dumps({"a": 1e22, "b": 1e-7, "c": -0.0}, sort_keys=True))
    print(json.loads("1e400") if math.isinf(json.loads("1e400")) else "finite")


main()
