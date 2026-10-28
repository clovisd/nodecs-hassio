"""Print every frame from a panel's push channel, with its arrival time (read-only)."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
import sys
import time

import aiohttp
from yarl import URL

PUSH_PATH = "/api/ui/notifications/subscribe"


async def main(base: str, auth_file: str, seconds: float) -> None:
    credentials = Path(auth_file).read_text().strip()
    headers = {
        "Authorization": "Basic " + base64.b64encode(credentials.encode()).decode()
    }
    url = URL(base)
    url = url.with_scheme("wss" if url.scheme == "https" else "ws").with_path(PUSH_PATH)
    connector = aiohttp.TCPConnector(ssl=False)
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
    if len(sys.argv) not in (3, 4):
        sys.exit(
            "usage: ws_listen.py <panel base URL> <auth file (user:password)> [seconds]"
        )
    asyncio.run(
        main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) == 4 else 60)
    )
