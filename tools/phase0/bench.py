"""Time read-only query variants against a panel over one kept-alive session."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
import statistics
import sys
import time

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from custom_components.nodecs.const import GRAPHQL_PATH, MATCH_QUERY, STATUS_QUERY  # noqa: E402

QUERIES = {
    "ids": "{ cs2Servers { id } }",
    "status": STATUS_QUERY,
    "match": MATCH_QUERY,
}


async def main(base: str, auth_file: str, samples: int) -> None:
    credentials = Path(auth_file).read_text().strip()
    headers = {
        "Authorization": "Basic " + base64.b64encode(credentials.encode()).decode()
    }
    url = base.rstrip("/") + GRAPHQL_PATH
    connector = aiohttp.TCPConnector(ssl=False)
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
    if len(sys.argv) not in (3, 4):
        sys.exit(
            "usage: bench.py <panel base URL> <auth file (user:password)> [samples]"
        )
    asyncio.run(
        main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) == 4 else 15)
    )
