import copy

DEFAULTS = {
    "server": {"host": "example.com", "ports": [80, 443]},
    "limits": {"timeout": 30, "retries": 3},
    "tags": ["edge", "public"],
}

def main() -> None:
    live = copy.deepcopy(DEFAULTS)
    live["server"]["ports"].append(8080)
    live["tags"].append("staging")
    live["limits"]["timeout"] = 5
    print(DEFAULTS["server"]["ports"])
    print(live["server"]["ports"])
    print(DEFAULTS["tags"])
    print(live["tags"])
    print(DEFAULTS["limits"])
    print(live["limits"])
    print(DEFAULTS == live)
    print(DEFAULTS["server"] == live["server"])

main()
