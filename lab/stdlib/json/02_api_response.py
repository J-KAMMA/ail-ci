import json

RESPONSE = (
    '{"status": "ok", "items": ['
    '{"id": 1, "tags": ["a", "b"], "price": 1.5}, '
    '{"id": 2, "tags": [], "price": 2}], '
    '"meta": {"page": 1}}'
)


def main() -> None:
    payload = json.loads(RESPONSE)
    total = 0.0
    for item in payload["items"]:
        total += item["price"]
        print(item["id"], len(item["tags"]))
    summary = {
        "count": len(payload["items"]),
        "total": total,
        "page": payload["meta"]["page"],
        "status": payload["status"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(json.dumps(payload["items"][0]["tags"], indent=2))


main()
