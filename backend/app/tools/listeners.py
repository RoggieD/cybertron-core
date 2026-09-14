import asyncio

import psutil


def _listener_inventory_sync() -> dict:
    listeners = []

    try:
        connections = psutil.net_connections(
            kind="inet"
        )
    except psutil.AccessDenied:
        return {
            "available": False,
            "error": "Access denied while reading network listeners.",
            "count": 0,
            "listeners": [],
        }

    for connection in connections:
        if connection.status != psutil.CONN_LISTEN:
            continue

        local = connection.laddr

        if not local:
            continue

        pid = connection.pid
        process_name = None

        if pid:
            try:
                process_name = psutil.Process(
                    pid
                ).name()
            except (
                psutil.NoSuchProcess,
                psutil.AccessDenied,
            ):
                process_name = None

        listeners.append(
            {
                "address": local.ip,
                "port": local.port,
                "pid": pid,
                "process": process_name,
                "family": str(
                    connection.family
                ),
                "type": str(
                    connection.type
                ),
            }
        )

    listeners.sort(
        key=lambda item: (
            item["port"],
            item["address"],
        )
    )

    return {
        "available": True,
        "count": len(listeners),
        "listeners": listeners,
    }


async def listener_inventory() -> dict:
    return await asyncio.to_thread(
        _listener_inventory_sync
    )


async def port_owner(port: int) -> dict:
    inventory = await listener_inventory()

    matches = [
        listener
        for listener in inventory.get("listeners", [])
        if listener.get("port") == port
    ]

    return {
        "port": port,
        "listening": bool(matches),
        "matches": matches,
        "count": len(matches),
    }
