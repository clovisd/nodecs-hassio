---
name: blinkybeacon-hassio
description: "HA custom integration for BlinkyBeacon trays (~/blinkybeacon-hassio, public clovisd/blinkybeacon-hassio); step 1 of a CS timeout-button system"
metadata:
  node_type: memory
  type: project
  originSessionId: 29e05096-c70e-4698-882a-6659bdb8d1d1
  modified: 2026-10-25T15:21:37.537Z
---

Home Assistant custom integration (domain `blinkybeacon`, HACS) shipped 2026-10-25 at
`~/blinkybeacon-hassio` → public `clovisd/blinkybeacon-hassio`. One config entry per
blinkybeacon-tray (`host:port`); light with spin/flash effects, USB-connected sensor, and
`blinkybeacon.spin/flash/stop` actions that target devices (HA silently skips unavailable
entities in entity actions, so device targeting is what makes failures show in traces).

**Why:** the owner runs CS matches with two SLZB-01P Zigbee buttons (MR5U coordinator), one
per team (home/away). End goal: short press = tech timeout, long press = tac timeout for that
team via the CS server API — a *separate, later* HA integration used side by side in the same
automations. The beacon is the visible signal while testing button range/reliability.

**How to apply:**
- Owner's words: "Nothing to do in HASSIO right now" — don't touch their HA instance unless asked.
- Beacon only does spin / flash / stop (no colour or speed). Tray binds 127.0.0.1 by default.
- "Beacon stops after 1–2 s" (reported 2026-10-25): the tray's `dashboard` build has a watcher
  that, when a dashboard URL + token are set, resets the light every poll (2 s default). The
  integration was not at fault; the owner is clearing the watcher on the test PCs.
- Tests: `.venv` (Python 3.14 via uv, HA 2026.10.4 through
  pytest-homeassistant-custom-component 0.13.375). uv itself was only in that session's
  scratchpad — reinstall it if needed.
- HA 2026.10 swapped voluptuous for probatio (aliased, `import voluptuous as vol` still works)
  and deprecated `device_registry.devices.get` / `DeviceEntry.config_entries`.
- Repo-local git author `clovisd <clovisdelmotte@gmail.com>`, matching blinkybeacon-web.
- Related: [[nodecs-hassio]] (step 2: the panel, read-only), [[tournament-pc-scripts]], [[monitor-profile-tool]].
