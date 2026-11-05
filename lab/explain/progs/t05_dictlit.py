# expect: point=typed show=typed main=typed
def point(x: int, y: int) -> dict[str, int]:
    return {"x": x, "y": y}


def show(d: dict[str, int]) -> None:
    print(d["x"] + d["y"])


def main() -> None:
    show(point(2, 5))
    print("ok")

main()
