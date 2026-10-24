# task: Extract all IPv4 addresses from embedded log lines using regular expressions and print the unique addresses in sorted order.
import re
import ipaddress

# One octet: 0-255, written without leading zeros.
OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"

# A dotted quad that is not part of a longer number or dotted sequence.
IPV4_PATTERN = re.compile(
    rf"(?<![\d.])({OCTET}(?:\.{OCTET}){{3}})(?!\d|\.\d)"
)

LOG_LINES: list[str] = [
    "2024-05-01 12:00:01 INFO  client connected from 192.168.1.10 port 52344",
    "2024-05-01 12:00:02 WARN  retry for 10.0.0.5 failed (timeout)",
    "2024-05-01 12:00:03 ERROR upstream 203.0.113.7 returned 502; see 10.0.0.5.",
    "2024-05-01 12:00:04 DEBUG invalid host 999.1.1.1 ignored",
    "2024-05-01 12:00:05 INFO  request from [192.168.1.10] accepted",
    "2024-05-01 12:00:06 INFO  version 1.2.3.4 deployed to node 10.0.0.12",
    "2024-05-01 12:00:07 WARN  leading zero address 010.0.0.1 skipped",
    "2024-05-01 12:00:08 INFO  forwarded 198.51.100.23, 203.0.113.7, 8.8.8.8",
    "2024-05-01 12:00:09 INFO  partial 1.2.3 and long number 1234.5.6.7.8 ignored",
    "2024-05-01 12:00:10 ERROR connection reset by peer 172.16.254.1 (id=42)",
    "2024-05-01 12:00:11 INFO  heartbeat from 10.0.0.5 ok",
    "2024-05-01 12:00:12 INFO  dns answer 8.8.4.4 cached at 0.0.0.0",
]


def extract_ipv4(lines: list[str]) -> set[ipaddress.IPv4Address]:
    """Return the set of valid IPv4 addresses found in the given lines."""
    found: set[ipaddress.IPv4Address] = set()
    for line in lines:
        for match in IPV4_PATTERN.finditer(line):
            found.add(ipaddress.IPv4Address(match.group(1)))
    return found


def main() -> None:
    addresses = extract_ipv4(LOG_LINES)
    # IPv4Address objects sort numerically by octet value.
    for address in sorted(addresses):
        print(address)


if __name__ == "__main__":
    main()
