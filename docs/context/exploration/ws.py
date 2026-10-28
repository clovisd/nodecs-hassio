import asyncio, sys, time
import aiohttp
URL = "wss://stage.tourney.esportal.xyz/api/ui/notifications/subscribe"
user, pw = open(sys.argv[1]).read().split(":", 1)
secs = float(sys.argv[2])
async def main():
    hdr = {"Authorization": aiohttp.encode_basic_auth(user, pw)}
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as s:
        t0 = time.monotonic()
        try:
            ws = await s.ws_connect(URL, headers=hdr, heartbeat=None)
        except aiohttp.WSServerHandshakeError as e:
            print("handshake failed:", e.status, e.message); return
        print(f"connected in {(time.monotonic()-t0)*1000:.0f} ms; protocol={ws.protocol!r}")
        end = time.monotonic() + secs
        while (left := end - time.monotonic()) > 0:
            try:
                msg = await asyncio.wait_for(ws.receive(), left)
            except TimeoutError:
                break
            print(f"+{time.monotonic()-t0:6.2f}s {msg.type.name}: {str(msg.data)[:400]}")
            if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                break
        await ws.close()
        print("done")
asyncio.run(main())
