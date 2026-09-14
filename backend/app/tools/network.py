import socket

import psutil


async def network_interfaces() -> dict:
    addresses = psutil.net_if_addrs()
    statistics = psutil.net_if_stats()

    interfaces = []

    for name, interface_addresses in addresses.items():
        stats = statistics.get(name)

        entry = {
            "name": name,
            "up": stats.isup if stats else None,
            "speed_mbps": stats.speed if stats else None,
            "mtu": stats.mtu if stats else None,
            "addresses": [],
        }

        for address in interface_addresses:
            family = address.family

            if family == socket.AF_INET:
                family_name = "IPv4"
            elif family == socket.AF_INET6:
                family_name = "IPv6"
            elif family == psutil.AF_LINK:
                family_name = "MAC"
            else:
                family_name = str(family)

            entry["addresses"].append(
                {
                    "family": family_name,
                    "address": address.address,
                    "netmask": address.netmask,
                }
            )

        interfaces.append(entry)

    return {
        "count": len(interfaces),
        "interfaces": interfaces,
    }
