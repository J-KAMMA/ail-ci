def make() -> int:
    x = 1; i = 0
    while i < 70:
        x = x * 2; i += 1
    return x
def keep(d: dict[str, int], w: str) -> int:
    return d.get(w, 1)
def main() -> None:
    d: dict[str, int] = {"x": make()}
    print(keep(d, "x")); print(keep(d, "y"))
main()
