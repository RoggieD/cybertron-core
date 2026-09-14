import asyncio
import json
import shutil
import subprocess
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
        _, writer = await asyncio.wait_for(
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


async def _resolve_container_ip(
    container: str,
) -> dict:
    def _inspect() -> dict:
        docker = shutil.which("docker")

        if not docker:
            return {
                "found": False,
                "error": "Docker CLI not found.",
            }

        result = subprocess.run(
            [
                docker,
                "inspect",
                container,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        if result.returncode != 0:
            return {
                "found": False,
                "error": result.stderr.strip(),
            }

        data = json.loads(result.stdout)

        if not data:
            return {
                "found": False,
                "error": "Container not found.",
            }

        networks = (
            data[0]
            .get("NetworkSettings", {})
            .get("Networks", {})
        )

        for network_name, details in networks.items():
            ip_address = details.get("IPAddress")

            if ip_address:
                return {
                    "found": True,
                    "container": container,
                    "network": network_name,
                    "ip_address": ip_address,
                }

        return {
            "found": True,
            "container": container,
            "error": "Container has no IPv4 address.",
        }

    return await asyncio.to_thread(_inspect)


async def _check_docker_service(
    container: str,
    port: int,
    protocol: str = "http",
    path: str = "/",
) -> dict:
    resolved = await _resolve_container_ip(container)

    if not resolved.get("found") or not resolved.get("ip_address"):
        return {
            "type": "docker",
            "scope": "docker",
            "container": container,
            "port": port,
            "reachable": False,
            "error": resolved.get(
                "error",
                "Unable to resolve container address.",
            ),
        }

    ip_address = resolved["ip_address"]
    network = resolved.get("network")

    if protocol.lower() in {"http", "https"}:
        normalized_path = path if path.startswith("/") else f"/{path}"
        url = (
            f"{protocol.lower()}://"
            f"{ip_address}:{port}"
            f"{normalized_path}"
        )

        result = await _check_http(url)
    else:
        result = await _check_tcp(
            ip_address,
            port,
        )

    result["scope"] = "docker"
    result["container"] = container
    result["container_ip"] = ip_address
    result["docker_network"] = network
    result["container_port"] = port

    return result


async def network_reachability(
    target: str | None = None,
    host: str | None = None,
    port: int | None = None,
    service_name: str | None = None,
    container: str | None = None,
    protocol: str = "http",
    path: str = "/",
) -> dict:
    if container and port:
        result = await _check_docker_service(
            container,
            port,
            protocol,
            path,
        )

        if service_name:
            result["service_name"] = service_name

        return result

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
            "Provide a URL, host/port, "
            "or Docker container/port."
        ),
    }
