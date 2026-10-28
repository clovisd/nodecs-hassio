"""Time read-only query variants against a panel over one kept-alive session."""

from __future__ import annotations

import argparse
import asyncio
import base64
from pathlib import Path
import ssl
import statistics
import sys
import time

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from custom_components.nodecs.const import GRAPHQL_PATH, MATCH_QUERY, STATUS_QUERY  # noqa: E402


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


QUERIES = {
    "ids": "{ cs2Servers { id } }",
    "status": STATUS_QUERY,
    "match": MATCH_QUERY,
}


async def main(args: argparse.Namespace) -> None:
    base, samples = args.base, args.samples
    credentials = Path(args.authfile).read_text().strip()
    headers = {
        "Authorization": "Basic " + base64.b64encode(credentials.encode()).decode()
    }
    url = base.rstrip("/") + GRAPHQL_PATH
    connector = aiohttp.TCPConnector(ssl=tls(args))
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        async with session.post(url, json={"query": QUERIES["ids"]}) as response:
            await response.read()  # warm the connection
        for name, query in QUERIES.items():
            times = []
            for _ in range(samples):
                started = time.perf_counter()
                async with session.post(url, json={"query": query}) as response:
                    await response.read()
                    if response.status != 200:
                        sys.exit(f"{name}: HTTP {response.status}")
                times.append((time.perf_counter() - started) * 1000)
                await asyncio.sleep(0.2)
            times.sort()
            p90 = times[max(0, int(len(times) * 0.9) - 1)]
            median = statistics.median(times)
            print(
                f"{name:7} median {median:6.0f} ms p90 {p90:6.0f} max {times[-1]:6.0f}"
            )


if __name__ == "__main__":
    arguments = parser(__doc__)
    arguments.add_argument("samples", nargs="?", type=int, default=15)
    asyncio.run(main(arguments.parse_args()))
