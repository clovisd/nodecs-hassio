---
name: unifi-api-access-notes
description: What a UniFi OS API key can and cannot do (Network 10.x / Protect 7.x), and the working read/write paths found on 2026-10-04
metadata:
  type: reference
---

Learned on a UCG Max (UniFi OS 5.1.33, Network 10.6.106, Protect 7.2.105) on 2026-10-04, sending the key as header `X-API-KEY`:
- Works: Network legacy API (`/proxy/network/api/s/default/...`, read and write), Network v2 API (`/proxy/network/v2/api/site/default/...` incl. `system-log/all`, `traffic-flows`, `firewall-policies`), Network integration API (`/proxy/network/integration/v1/...`), Protect integration API (`/proxy/protect/integration/v1/...`).
- Refused (401/404): Protect internal API (`/proxy/protect/api/...`) and UniFi OS console endpoints such as `/api/firmware/update`, so console/app auto-update cannot be changed with the key; the user must do it in the UI.
- The console serves its own OpenAPI spec at `/proxy/network/api-docs/integration.json`.
- Partial settings writes: `POST /proxy/network/api/s/default/set/setting/<key>` with only the changed field. Saving the `mgmt` section regenerates its internal `x_api_token` (benign).
- Firewall policies: `POST .../integration/v1/sites/<siteId>/firewall/policies`. For Internal to External, `allowReturnTraffic` must be false or the API returns `cant-allow-return-traffic`. MAC-based sources use `trafficFilter.type = MAC_ADDRESS`. User policies get index 10000+ and sit before system rules; on the gateway they land in chain `UBIOS_LAN_WAN_USER`.
- Protect detail without the internal API: over SSH, `psql -h 127.0.0.1 -p 5433 -U postgres -d unifi-protect` (trust auth) and logs in `/srv/unifi-protect/logs` (`cameras.thirdParty.log` for ONVIF cameras).
- Teleport VPN is a full tunnel relayed via TURN: on metered sites all of the client PC's traffic uses the site's data. See [[grandglise-unifi-audit]].
- To tell whether a console auto-updates, read `/data/unifi-core/logs/*.log` over SSH: "Startup: No auto-update scheduled" means manual, and each `POST /api/firmware/update` line names the channel and user that requested an update. Do not infer auto-update from the Network log's "Unknown" admin. unifi-core also answers unauthenticated GETs on `127.0.0.1:11081` (e.g. `/api/controllers`).
- WAN Smart Queues: `PUT /proxy/network/api/s/default/rest/networkconf/<wan_id>` with `{"wan_smartq_enabled": false}` merges cleanly; verify with `tc qdisc show dev eth4` on the gateway.
- UniFi Mobility (LTE routers such as the UMR): base `https://api.ui.com/v1/mobility`, header `X-API-Key`, spec at `https://developer.ui.com/mobility/v1.0.0/openapi.json`. Only workspaces, devices, device detail (uptime, data usage and limit, signal level, firmware) and clients; no logs or events. IDs are `workspace_id` and device `id`. UMR support files (`*-enc.tar`) are encrypted for Ubiquiti and unreadable locally.
