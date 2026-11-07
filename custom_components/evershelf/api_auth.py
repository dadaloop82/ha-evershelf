"""Shared EverShelf HTTP auth helpers."""
from __future__ import annotations

from typing import Any


def evershelf_headers(token: str = "", *, json_body: bool = False) -> dict[str, str]:
    """Headers accepted by EverShelf API (X-API-Token, Bearer, CSRF)."""
    headers: dict[str, str] = {"X-EverShelf-Request": "1"}
    if json_body:
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-API-Token"] = token
        headers["Authorization"] = f"Bearer {token}"
    return headers


def evershelf_params(token: str = "", params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Query params. The token is deliberately NOT added here: a query string ends up
    in server access logs and proxies. Authentication goes through evershelf_headers()."""
    return dict(params or {})
