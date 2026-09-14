import asyncio

from backend.app.services.catalog import SERVICES
from backend.app.tools.reachability import network_reachability


def _unique_services() -> list[dict]:
    unique = {}

    for service in SERVICES.values():
        if service.get("scope") == "docker":
            identity = (
                service.get("name"),
                service.get("container"),
                service.get("port"),
            )
        else:
            identity = (
                service.get("name"),
                service.get("target"),
            )

        if identity not in unique:
            unique[identity] = service

    return list(unique.values())


async def _check_service(service: dict) -> dict:
    name = service["name"]
    scope = service.get("scope", "host")

    if scope == "docker":
        result = await network_reachability(
            container=service["container"],
            port=service["port"],
            protocol=service.get("protocol", "http"),
            path=service.get("health_path", "/"),
            service_name=name,
        )
    else:
        result = await network_reachability(
            target=service["target"],
            service_name=name,
        )

    return {
        "name": name,
        "scope": scope,
        "reachable": result.get("reachable", False),
        "target": result.get("target"),
        "status_code": result.get("status_code"),
        "reason": result.get("reason"),
        "latency_ms": result.get("latency_ms"),
        "error": result.get("error"),
    }


async def service_status() -> dict:
    services = _unique_services()

    results = await asyncio.gather(
        *(
            _check_service(service)
            for service in services
        )
    )

    reachable = sum(
        1
        for item in results
        if item.get("reachable")
    )

    return {
        "total": len(results),
        "reachable": reachable,
        "unreachable": len(results) - reachable,
        "services": sorted(
            results,
            key=lambda item: item["name"].lower(),
        ),
    }
