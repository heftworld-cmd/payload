#!/usr/bin/env python3
"""
Minimal lab helper for the local MCP server.

What this script does:
1. Sends `initialize` to the local `/mcp` endpoint.
2. Reads the `Mcp-Session-Id` response header.
3. Sends `notifications/initialized`.
4. Sends `tools/list`.
5. Closes the MCP session unless `--keep-session` is used.

This is intended for local testing of the current `/mcp` transport behavior.
It uses the same lab token shape discussed during review, which is enough to
pass the server's local decode-and-exp check, but it will not work for real
Graph-backed tool execution.

Usage:
    python3 security/list_mcp_tools_lab.py

Optional:
    python3 security/list_mcp_tools_lab.py --url http://localhost:3002/mcp
    python3 security/list_mcp_tools_lab.py --token "<your token>"
    python3 security/list_mcp_tools_lab.py --keep-session
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


# Default lab token:
# - three JWT-like parts
# - valid JSON payload
# - exp far in the future
# - no real signature / no Graph validity
DEFAULT_TOKEN = (
    "eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0."
    "eyJleHAiOjQxMDI0NDQ4MDAsInVwbiI6ImxvY2FsLWxhYkBleGFtcGxlLnRlc3QiLCJvaWQiOiJsYWItdXNlciIs"
    "InByZWZlcnJlZF91c2VybmFtZSI6ImxvY2FsLWxhYkBleGFtcGxlLnRlc3QifQ."
    "x"
)
DEFAULT_URL = "http://localhost:3002/mcp"
DEFAULT_PROTOCOL_VERSION = "2025-11-25"


def parse_args() -> argparse.Namespace:
    """Read command-line options for the MCP URL, token, and session behavior."""
    parser = argparse.ArgumentParser(
        description="Initialize the local MCP server and print tools/list output."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"MCP Streamable HTTP endpoint. Default: {DEFAULT_URL}",
    )
    parser.add_argument(
        "--token",
        default=DEFAULT_TOKEN,
        help="Bearer token to send to the local MCP server.",
    )
    parser.add_argument(
        "--protocol-version",
        default=DEFAULT_PROTOCOL_VERSION,
        help=f"MCP protocol version to advertise. Default: {DEFAULT_PROTOCOL_VERSION}",
    )
    parser.add_argument(
        "--keep-session",
        action="store_true",
        help="Do not send DELETE /mcp after listing tools.",
    )
    return parser.parse_args()


def pretty_json(raw_text: str) -> str:
    """Pretty-print JSON when possible; otherwise return the raw body."""
    try:
        return json.dumps(json.loads(raw_text), indent=2)
    except json.JSONDecodeError:
        return raw_text


def request_json(
    url: str,
    method: str,
    payload: dict | None,
    headers: dict[str, str],
    timeout: int = 30,
) -> tuple[int, dict[str, str], str]:
    """
    Send one HTTP request using only the Python standard library.

    Returns:
        (status_code, response_headers, response_body_text)
    """
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url=url, data=body, method=method)

    for key, value in headers.items():
        request.add_header(key, value)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8", errors="replace")
            return response.status, dict(response.headers.items()), response_body
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        return exc.code, dict(exc.headers.items()), response_body


def extract_session_id(headers: dict[str, str]) -> str | None:
    """Read the MCP session header without relying on exact header casing."""
    for key, value in headers.items():
        if key.lower() == "mcp-session-id":
            return value
    return None


def build_common_headers(token: str) -> dict[str, str]:
    """Headers shared by all JSON-RPC calls in this lab flow."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }


def main() -> int:
    """Run the MCP handshake, print the tool list, and optionally close the session."""
    args = parse_args()
    common_headers = build_common_headers(args.token)

    # Step 1: initialize the MCP session.
    initialize_payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": args.protocol_version,
            "capabilities": {},
            "clientInfo": {
                "name": "security-list-mcp-tools-lab",
                "version": "1.0",
            },
        },
    }

    print("[1/4] initialize")
    status, headers, body = request_json(
        url=args.url,
        method="POST",
        payload=initialize_payload,
        headers=common_headers,
    )
    print(f"HTTP {status}")
    print(pretty_json(body))

    session_id = extract_session_id(headers)
    if not session_id:
        print("\nNo Mcp-Session-Id was returned. Initialization did not complete cleanly.", file=sys.stderr)
        return 1

    print(f"\nSession ID: {session_id}")

    # Step 2: tell the server initialization is complete.
    session_headers = {
        **common_headers,
        "MCP-Protocol-Version": args.protocol_version,
        "Mcp-Session-Id": session_id,
    }
    initialized_payload = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
    }

    print("\n[2/4] notifications/initialized")
    status, _, body = request_json(
        url=args.url,
        method="POST",
        payload=initialized_payload,
        headers=session_headers,
    )
    print(f"HTTP {status}")
    if body.strip():
        print(pretty_json(body))

    # Step 3: ask the server for the active tool catalog.
    tools_list_payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }

    print("\n[3/4] tools/list")
    status, _, body = request_json(
        url=args.url,
        method="POST",
        payload=tools_list_payload,
        headers=session_headers,
    )
    print(f"HTTP {status}")
    print(pretty_json(body))

    try:
        parsed = json.loads(body)
        tools = parsed.get("result", {}).get("tools", [])
        print(f"\nTool count returned: {len(tools)}")
    except json.JSONDecodeError:
        pass

    # Step 4: close the session unless the caller wants to inspect it further.
    if args.keep_session:
        print("\n[4/4] keeping session open because --keep-session was requested")
        return 0

    print("\n[4/4] closing session")
    status, _, body = request_json(
        url=args.url,
        method="DELETE",
        payload=None,
        headers={"Mcp-Session-Id": session_id},
    )
    print(f"HTTP {status}")
    if body.strip():
        print(pretty_json(body))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
