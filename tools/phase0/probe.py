"""Read-only check of NodeCS's client against a panel: queries, logo, login, push."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import ssl
import sys
import time

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from custom_components.nodecs.api import NodeCSClient, NodeCSError  # noqa: E402


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
    base = args.base
    user, password = Path(args.authfile).read_text().strip().split(":", 1)
    connector = aiohttp.TCPConnector(ssl=tls(args))
    async with aiohttp.ClientSession(connector=connector) as session:
        client = NodeCSClient(session, base, user, password)

        started = time.perf_counter()
        servers = await client.fetch_matches()
        elapsed = (time.perf_counter() - started) * 1000
        print(f"fetch_matches: {len(servers)} servers in {elapsed:.0f} ms")
        for server in servers.values():
            match = server.match
            if match is None:
                print(f"  {server.name}: no match")
                continue
            pause = match.running_pause
            score = f"{match.team_a_score}-{match.team_b_score}"
            teams = f"{match.team_a.name} {score} {match.team_b.name}"
            print(f"  {server.name}: {match.phase} {match.map.name} {teams}")
            print(
                f"    pause={pause and pause.reason} by={match.paused_by} "
                f"bindings={len(match.bindings)}"
            )

        started = time.perf_counter()
        statuses = await client.fetch_statuses()
        elapsed = (time.perf_counter() - started) * 1000
        print(f"fetch_statuses in {elapsed:.0f} ms: {statuses}")

        logo = next(
            (s.match.team_a.logo_url for s in servers.values() if s.match), None
        )
        if logo:
            content, content_type = await client.fetch_image(logo)
            print(f"fetch_image: {len(content)} bytes {content_type}")

        wrong = NodeCSClient(session, base, user, "deliberately-wrong-password")
        try:
            await wrong.fetch_matches()
            print("wrong password: ACCEPTED (unexpected)")
        except NodeCSError as err:
            print(f"wrong password -> {type(err).__name__}")

        channel = await client.open_push()
        print("push channel open; listening 20 s")
        try:
            async with asyncio.timeout(20):
                async for message in channel:
                    print("  message:", message.get("type"), str(message)[:160])
        except TimeoutError:
            pass
        await channel.close()


if __name__ == "__main__":
    asyncio.run(main(parser(__doc__).parse_args()))
