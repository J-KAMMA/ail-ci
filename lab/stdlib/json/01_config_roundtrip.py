import json

DEFAULT = (
    '{"name": "service", "port": 8080, '
    '"features": {"cache": true, "debug": false}, '
    '"hosts": ["a.example.com", "b.example.com"]}'
)


def load_config(text: str) -> dict:
    try:
        cfg = json.loads(text)
    except json.JSONDecodeError as exc:
        print("bad config:", exc)
        return {}
    if not isinstance(cfg, dict):
        return {}
    cfg.setdefault("timeout", 30)
    return cfg


def main() -> None:
    cfg = load_config(DEFAULT)
    cfg["port"] = 9090
    text = json.dumps(cfg, indent=2, sort_keys=True)
    print(text)
    with open("config.json", "w", encoding="utf-8") as out:
        out.write(text)
    with open("config.json", "r", encoding="utf-8") as src:
        again = json.loads(src.read())
    print(again == cfg, again["features"]["cache"], again["hosts"][0])


main()
