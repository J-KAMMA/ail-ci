import copy

def show(label: str, fn) -> None:
    try:
        fn()
    except Exception as exc:
        print(label, type(exc).__name__)

def main() -> None:
    show("copy no args", lambda: copy.copy())
    show("deepcopy no args", lambda: copy.deepcopy())
    show("deepcopy extra", lambda: copy.deepcopy([1], {}, []))
    show("copy extra", lambda: copy.copy([1], [2]))
    print(copy.copy(5), copy.deepcopy(5))
    print(copy.copy("text"), copy.deepcopy("text"))
    print(copy.copy(None), copy.deepcopy(None))
    print(copy.copy(True), copy.deepcopy(True))

main()
