"""Print every frame from a panel's push channel, with its arrival time (read-only)."""

from __future__ import annotations

import argparse
import asyncio
import base64
from pathlib import Path
import ssl
import sys
import time

import aiohttp
from yarl import URL

PUSH_PATH = "/api/ui/notifications/subscribe"


def tls(args: argparse.Namespace) -> ssl.SSLContext | bool:
    """Verify the panel's certificate by default; --cafile pins the event's CA."""
    if args.insecure:
        print("WARNING: TLS verification is OFF (--insecure)", file=sys.stderr)
        return False
    if args.cafile:
        return ssl.create_default_context(cafile=args.cafile)
    return True


def parser(description: str) -> argparse.ArgumentParser:
    """The arguments every probe takes."""
    parse = argparse.ArgumentParser(description=description)
    parse.add_argument(
        "base", help="the panel's base URL, e.g. https://panel.example.lan"
    )
    parse.add_argument("authfile", help="a file holding one line, user:password")
    parse.add_argument(
        "--cafile", help="PEM file of the CA that signed the panel's cert"
    )
    parse.add_argument(
        "--insecure", action="store_true", help="skip TLS verification (last resort)"
    )
    return parse


async def main(args: argparse.Namespace) -> None:
    base, seconds = args.base, args.seconds
    credentials = Path(args.authfile).read_text().strip()
    headers = {
        "Authorization": "Basic " + base64.b64encode(credentials.encode()).decode()
    }
    url = URL(base)
    url = url.with_scheme("wss" if url.scheme == "https" else "ws").with_path(PUSH_PATH)
    connector = aiohttp.TCPConnector(ssl=tls(args))
    async with aiohttp.ClientSession(connector=connector) as session:
        started = time.monotonic()
        try:
            ws = await session.ws_connect(url, headers=headers)
        except aiohttp.WSServerHandshakeError as err:
            sys.exit(f"handshake failed: {err.status}")
        print(f"connected in {(time.monotonic() - started) * 1000:.0f} ms")
        deadline = started + seconds
        while (left := deadline - time.monotonic()) > 0:
            try:
                frame = await asyncio.wait_for(ws.receive(), left)
            except TimeoutError:
                break
            offset = time.monotonic() - started
            print(f"+{offset:7.2f}s {frame.type.name}: {str(frame.data)[:400]}")
            if frame.type in (
                aiohttp.WSMsgType.CLOSE,
                aiohttp.WSMsgType.CLOSED,
                aiohttp.WSMsgType.ERROR,
            ):
                break
        await ws.close()


if __name__ == "__main__":
    arguments = parser(__doc__)
    arguments.add_argument("seconds", nargs="?", type=float, default=60)
    asyncio.run(main(arguments.parse_args()))
