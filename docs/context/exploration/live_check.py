"""Read-only live check of the integration's client against the staging panel."""
import asyncio, sys, time
import aiohttp
sys.path.insert(0, "/home/clovisd/nodecs-hassio")
from custom_components.nodecs.api import NodeCSClient, NodeCSError

user, pw = open(sys.argv[1]).read().split(":", 1)
BASE = "https://stage.tourney.esportal.xyz"

async def main() -> None:
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
        client = NodeCSClient(session, BASE, user, pw)
        t = time.perf_counter(); servers = await client.fetch_matches()
        print(f"fetch_matches: {len(servers)} servers in {(time.perf_counter()-t)*1000:.0f} ms")
        for s in servers.values():
            m = s.match
            print(f"  {s.name}: " + ("no match" if m is None else
                  f"{m.phase} {m.map.name} {m.team_a.name} {m.team_a_score}-{m.team_b_score} {m.team_b.name}, "
                  f"pause={m.running_pause and m.running_pause.reason} by={m.paused_by} bindings={len(m.bindings)}"))
        t = time.perf_counter(); statuses = await client.fetch_statuses()
        print(f"fetch_statuses in {(time.perf_counter()-t)*1000:.0f} ms: {statuses}")
        logo = next((s.match.team_a.logo_url for s in servers.values() if s.match), None)
        if logo:
            content, ctype = await client.fetch_image(logo)
            print(f"fetch_image: {len(content)} bytes {ctype}")
        bad = NodeCSClient(session, BASE, user, "wrong-password")
        try:
            await bad.fetch_matches()
        except NodeCSError as err:
            print(f"wrong password -> {type(err).__name__}")
        channel = await client.open_push()
        print("push channel open; listening 20 s")
        try:
            async with asyncio.timeout(20):
                async for message in channel:
                    print("  message:", message.get("type"), str(message)[:120])
        except TimeoutError:
            pass
        await channel.close()
        print("done")

asyncio.run(main())
