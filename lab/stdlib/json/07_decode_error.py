import json


def show(text: str) -> None:
    try:
        json.loads(text)
    except json.JSONDecodeError as exc:
        print(exc.msg, exc.pos, exc.lineno, exc.colno)
        print(str(exc))
    except ValueError as exc:
        print("value error:", exc)
    else:
        print("valid")


def main() -> None:
    for text in ["", "{", "[1,]", '{"a": }', '"unterminated', "01"]:
        show(text)
    show('{"a": 1}')


main()
