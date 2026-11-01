import pprint


def build_record() -> dict:
    return {
        "user": {"name": "Ada", "id": 42},
        "tags": ["math", "code"],
        "scores": (3, 5, 8),
        "active": True,
    }


def main() -> None:
    data = build_record()
    pprint.pprint(data)
    print("---")
    print(pprint.pformat(data))
    print("---")
    print(pprint.pformat(data, indent=4))


main()
