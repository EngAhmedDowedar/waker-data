#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Set
from urllib.parse import urlparse

URL_RE = re.compile(
    r"https?://[A-Za-z0-9.-]+(?::\d{2,5})?(?:/[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]*)?"
)
PRINTF_TOKEN_RE = re.compile(r"%(\d+\$)?[sd]")
PLACEHOLDER_HOSTS = {"hostname", "close_view", "close"}
IP_RE = re.compile(r"^\d{1,3}(?:\.\d{1,3}){3}$")
IP_PORT_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d{2,5})?\b")
HOST_PORT_RE = re.compile(
    r"\b((?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)\.)+[A-Za-z]{2,63}):(\d{2,5})\b"
)

TEXT_EXTS = {
    ".smali",
    ".xml",
    ".json",
    ".txt",
    ".properties",
    ".cfg",
    ".ini",
    ".meta",
    ".yml",
}
SCAN_DIRS = ("smali", "assets", "res", "unknown")
NATIVE_DIR = "lib"
SKIP_TEXT_FILES = {"protobuf.meta"}


def extract_strings_from_binary(blob: bytes, minimum: int = 4) -> Iterable[str]:
    pattern = re.compile(rf"[\x20-\x7E]{{{minimum},}}".encode("ascii"))
    for match in pattern.findall(blob):
        try:
            yield match.decode("utf-8", errors="ignore")
        except Exception:
            continue


def collect_patterns(text: str, source: str, hits: Dict[str, List[str]], out: Dict[str, Set[str]]) -> None:
    raw_urls = URL_RE.findall(text)
    urls: List[str] = []

    def is_valid_host(host: str) -> bool:
        if not host:
            return False
        if host.startswith(".") or host.endswith("."):
            return False
        if "%" in host:
            return False
        if "." not in host:
            return False
        if IP_RE.match(host):
            return False
        if host in PLACEHOLDER_HOSTS:
            return False
        return True

    for raw_url in raw_urls:
        if PRINTF_TOKEN_RE.search(raw_url):
            continue
        try:
            parsed = urlparse(raw_url)
        except Exception:
            continue
        if parsed.scheme not in {"http", "https"}:
            continue
        if not parsed.hostname:
            continue
        if not is_valid_host(parsed.hostname):
            continue
        urls.append(raw_url)
    ips = IP_PORT_RE.findall(text)
    host_ports = [f"{h}:{p}" for h, p in HOST_PORT_RE.findall(text)]

    hosts: Set[str] = set()
    for url in urls:
        try:
            host = urlparse(url).hostname
        except Exception:
            host = None
        if host:
            if not is_valid_host(host):
                continue
            hosts.add(host)
    for hp in host_ports:
        host = hp.split(":", 1)[0]
        if not is_valid_host(host):
            continue
        hosts.add(host)

    if urls or hosts or ips or host_ports:
        hits[source] = sorted(set(urls + list(hosts) + ips + host_ports))
    out["urls"].update(urls)
    out["hosts"].update(hosts)
    out["ip_or_ip_port"].update(ips)
    out["host_ports"].update(host_ports)


def scan_text_files(root: Path, out: Dict[str, Set[str]], hits: Dict[str, List[str]]) -> None:
    for rel_dir in SCAN_DIRS:
        base = root / rel_dir
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_EXTS:
                continue
            if path.name in SKIP_TEXT_FILES:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            collect_patterns(text, str(path.relative_to(root)), hits, out)


def scan_native_libs(root: Path, out: Dict[str, Set[str]], hits: Dict[str, List[str]]) -> None:
    lib_base = root / NATIVE_DIR
    if not lib_base.exists():
        return
    for so_file in lib_base.rglob("*.so"):
        try:
            blob = so_file.read_bytes()
        except Exception:
            continue
        joined = "\n".join(extract_strings_from_binary(blob))
        collect_patterns(joined, str(so_file.relative_to(root)), hits, out)


def build_result(root: Path) -> Dict[str, object]:
    out: Dict[str, Set[str]] = {
        "urls": set(),
        "hosts": set(),
        "ip_or_ip_port": set(),
        "host_ports": set(),
    }
    hits: Dict[str, List[str]] = {}
    scan_text_files(root, out, hits)
    scan_native_libs(root, out, hits)

    protocols = set()
    for url in out["urls"]:
        if url.startswith("https://"):
            protocols.add("https")
        elif url.startswith("http://"):
            protocols.add("http")

    return {
        "scan_root": str(root),
        "protocols_detected": sorted(protocols),
        "urls": sorted(out["urls"]),
        "hosts": sorted(out["hosts"]),
        "ip_or_ip_port": sorted(out["ip_or_ip_port"]),
        "host_ports": sorted(out["host_ports"]),
        "file_hits": hits,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract potential game endpoints/hosts from decompiled APK files.")
    parser.add_argument("--root", default=".", help="Repository root to scan.")
    parser.add_argument(
        "--output",
        default="revival/endpoint_inventory.json",
        help="Path to write JSON inventory.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    result = build_result(root)

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = root / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
