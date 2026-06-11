#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


DEFAULT_HOSTS = [
    "wild-city-9abb9.firebaseio.com",
    "wild-city-9abb9.appspot.com",
]
HOST_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*$"
)
IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")


def is_valid_host(host: str) -> bool:
    if not host or "%" in host or " " in host:
        return False
    if host.startswith(".") or host.endswith("."):
        return False
    if not HOST_RE.match(host):
        return False
    if IP_RE.match(host):
        return False
    if "." not in host:
        return False
    tld = host.rsplit(".", 1)[-1]
    if len(tld) < 2 or not tld.isalpha():
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate local hosts override entries from extracted endpoint inventory.")
    parser.add_argument("--inventory", default="revival/endpoint_inventory.json")
    parser.add_argument("--ip", default="127.0.0.1")
    parser.add_argument("--output", default="revival/hosts.override")
    args = parser.parse_args()

    inventory_path = Path(args.inventory)
    hosts = set(DEFAULT_HOSTS)

    if inventory_path.exists():
        data = json.loads(inventory_path.read_text(encoding="utf-8"))
        for host in data.get("hosts", []):
            if "." in host and is_valid_host(host):
                hosts.add(host)
        for hp in data.get("host_ports", []):
            host = hp.split(":", 1)[0]
            if "." in host and is_valid_host(host):
                hosts.add(host)

    lines = [f"{args.ip} {h}" for h in sorted(hosts)]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
