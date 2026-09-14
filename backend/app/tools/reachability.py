import asyncio
import time
from urllib.parse import urlparse

import httpx


async def _check_http(
    url: str,
    timeout: float = 5.0,
) -> dict:
    started = time.perf_counter()

    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
        ) as client:
            response = await client.get(url)

        latency_ms = round(
            (time.perf_counter() - started) * 1000,
            2,
        )

        return {
            "type": "http",
            "target": url,
            "reachable": True,
            "status_code": response.status_code,
            "reason": response.reason_phrase,
            "latency_ms": latency_ms,
            "final_url": str(response.url),
        }

    except Exception as exc:
        latency_ms = round(
            (time.perf_counter() - started) * 1000,
            2,
        )

        return {
            "type": "http",
            "target": url,
            "reachable": False,
            "latency_ms": latency_ms,
            "error": str(exc),
        }


async def _check_tcp(
    host: str,
    port: int,
    timeout: float = 3.0,
) -> dict:
    started = time.perf_counter()

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port),
            timeout=timeout,
        )

        writer.close()
        await writer.wait_closed()

        latency_ms = round(
            (time.perf_counter() - started) * 1000,
            2,
        )

        return {
            "type": "tcp",
            "target": f"{host}:{port}",
            "host": host,
            "port": port,
            "reachable": True,
            "latency_ms": latency_ms,
        }

    except Exception as exc:
        latency_ms = round(
            (time.perf_counter() - started) * 1000,
            2,
        )

        return {
            "type": "tcp",
            "target": f"{host}:{port}",
            "host": host,
            "port": port,
            "reachable": False,
            "latency_ms": latency_ms,
            "error": str(exc),
        }


async def network_reachability(
    target: str | None = None,
    host: str | None = None,
    port: int | None = None,
    service_name: str | None = None,
) -> dict:
    if target:
        parsed = urlparse(target)

        if parsed.scheme in {"http", "https"}:
            result = await _check_http(target)
            if service_name:
                result["service_name"] = service_name
            return result

        if ":" in target:
            candidate_host, candidate_port = target.rsplit(":", 1)

            try:
                parsed_port = int(candidate_port)
            except ValueError:
                return {
                    "reachable": False,
                    "target": target,
                    "error": "Invalid TCP target.",
                }

            result = await _check_tcp(
                candidate_host,
                parsed_port,
            )
            if service_name:
                result["service_name"] = service_name
            return result

    if host and port:
        result = await _check_tcp(host, port)
        if service_name:
            result["service_name"] = service_name
        return result

    return {
        "reachable": False,
        "target": target,
        "error": (
            "Provide an HTTP/HTTPS URL or a host and port."
        ),
    }
