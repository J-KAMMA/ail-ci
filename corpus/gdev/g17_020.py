# task: Sort a list of IPv4 address strings numerically by their octets using a key function.
import ipaddress
from typing import Callable


def ipv4_sort_key(address: str) -> tuple[int, int, int, int]:
    """Return a numeric sort key made of the four octets of an IPv4 address."""
    octets = tuple(int(part) for part in address.split("."))
    if len(octets) != 4:
        raise ValueError(f"not an IPv4 address: {address!r}")
    return octets  # type: ignore[return-value]


def sort_ipv4_addresses(
    addresses: list[str],
    key: Callable[[str], tuple[int, ...]] = ipv4_sort_key,
) -> list[str]:
    """Return a new list of IPv4 address strings sorted numerically by octets."""
    return sorted(addresses, key=key)


def main() -> None:
    addresses: list[str] = [
        "192.168.1.10",
        "10.0.0.255",
        "192.168.1.2",
        "10.0.0.1",
        "172.16.5.4",
        "192.168.10.1",
        "0.0.0.0",
        "255.255.255.255",
        "10.0.10.1",
        "1.2.3.4",
    ]

    # Validate inputs using the standard library so the output stays trustworthy.
    for address in addresses:
        ipaddress.IPv4Address(address)

    sorted_addresses = sort_ipv4_addresses(addresses)

    print("Sorted IPv4 addresses:")
    for address in sorted_addresses:
        print(address)


if __name__ == "__main__":
    main()
