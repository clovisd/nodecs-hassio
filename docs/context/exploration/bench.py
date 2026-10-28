import asyncio, json, statistics, sys, time
import aiohttp
URL = "https://stage.tourney.esportal.xyz/api/ui/graphql/query"
user, pw = open(sys.argv[1]).read().split(":", 1)
full = open(sys.argv[2]).read()
Q = {"ids": "{ cs2Servers { id } }", "status": "{ cs2Servers { id status } }",
     "match": full.replace(" status", ""), "full": full}
async def main():
    auth = aiohttp.BasicAuth(user, pw)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as s:
        await s.post(URL, json={"query": Q["ids"]}, auth=auth)  # warm the connection
        for name in ["ids", "status", "match", "full"] * 1:
            ts = []
            for _ in range(15):
                t = time.perf_counter()
                async with s.post(URL, json={"query": Q[name]}, auth=auth) as r:
                    await r.read(); assert r.status == 200
                ts.append((time.perf_counter() - t) * 1000)
                await asyncio.sleep(0.2)
            ts.sort()
            print(f"{name:7} median {statistics.median(ts):6.0f} ms  p90 {ts[int(len(ts)*0.9)-1]:6.0f}  max {ts[-1]:6.0f}")
asyncio.run(main())
