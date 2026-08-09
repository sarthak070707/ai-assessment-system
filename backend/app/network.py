"""Restricts exam access to approved networks.

An institution runs its papers on lab machines and does not want them reachable
from a hostel room. Expressed as CIDR ranges so it covers a subnet rather than
individual machines.

This is a real control but a soft one, and worth being straight about in a viva:
it is defeated by a VPN or by someone sitting on the campus network who should
not be. Treat it as one layer alongside the access code and the proctor signals,
not as the thing standing between a candidate and the paper.
"""
from __future__ import annotations

import ipaddress

from fastapi import HTTPException, Request, status

from .config import get_settings

settings = get_settings()


def client_ip(request: Request) -> str:
    """Best-effort client address.

    X-Forwarded-For is honoured because the app may sit behind a reverse proxy,
    but note the header is client-supplied and trivially spoofed unless the proxy
    overwrites it. Trust it only when you control the proxy in front.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def is_allowed(address: str) -> bool:
    if not settings.exam_allowed_networks:
        return True
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    for network in settings.exam_allowed_networks:
        try:
            if ip in ipaddress.ip_network(network, strict=False):
                return True
        except ValueError:
            continue
    return False


def require_exam_network(request: Request) -> None:
    """FastAPI dependency: reject exam access from outside approved networks."""
    address = client_ip(request)
    if not is_allowed(address):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This assessment can only be taken from an approved campus network. "
            f"Your connection ({address or 'unknown'}) is not on that list.",
        )
