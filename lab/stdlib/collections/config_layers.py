from collections import ChainMap


def main() -> int:
    defaults = {"host": "localhost", "port": 80, "debug": False}
    file_cfg = {"port": 8080, "user": "svc"}
    env_cfg = {"user": "admin", "debug": True}
    cfg = ChainMap(env_cfg, file_cfg, defaults)
    print(cfg["host"], cfg["port"], cfg["user"], cfg["debug"])
    print(cfg.get("missing"), cfg.get("missing", "fallback"))
    print("host" in cfg, "missing" in cfg, len(cfg))
    for key in sorted(cfg):
        print(key, cfg[key])
    print(sorted(cfg.keys()), sorted(str(value) for value in cfg.values()))
    cfg["port"] = 9090
    print(file_cfg["port"], defaults["port"])
    cfg["new"] = 1
    print(env_cfg)
    child = cfg.new_child({"host": "child", "extra": 2})
    print(child["host"], child["extra"], child["port"], len(child.maps))
    print(child.parents["host"], child.parents["port"])
    print(cfg.pop("new"), "new" in cfg)
    print(cfg.setdefault("host", "nope"), cfg.setdefault("fresh", "yes"))
    try:
        print(cfg["nope"])
    except KeyError as exc:
        print("KeyError", exc)
    try:
        del cfg["host"]
    except KeyError as exc:
        print("KeyError", exc)
    print({key: cfg[key] for key in cfg})
    return 0


main()
