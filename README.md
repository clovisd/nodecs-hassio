# NodeCS for Home Assistant

A read-only Home Assistant integration for a CS2 LAN-event server panel. Every game server on
the panel becomes a device, and the match on it (phase, map, teams, score, timeouts, the running
pause) becomes entities. Dashboards can show every server at a glance, and automations can react
to the match. For example, a team's tactical timeout can spin that team's
[BlinkyBeacon](https://github.com/clovisd/blinkybeacon-hassio).

It **never changes anything on the panel**. It sends two read-only GraphQL queries and listens to
the panel's push channel. It never asks for passwords, RCON details or the panel's config, even
though the panel's API serves them.

## What you get

**The panel** is one device with one diagnostic sensor, **Live updates**. It is on while the
panel's push channel is open. While it is off, the integration falls back to reading the panel
every second.

**Each game server** is a device named after the server, for example `server_1`:

| Entity | State | With no match |
|---|---|---|
| Status | stopped, starting, running, running (invalid) | — |
| Phase | no match, unassigned, warmup, knife round, live, freeze time, half-time break, ended, archived | no match |
| Map | the map's name | unknown |
| Team A, Team B | the team's name | unknown |
| Team A score, Team B score | rounds won on this map | unknown |
| Team A maps won, Team B maps won | the series score | unknown |
| Best of | 1, 3, 5 | unknown |
| Team A / Team B timeouts left, timeouts used | counts as the panel reports them, penalties included | unknown |
| Team A ready, Team B ready (binary) | on once the team has readied up | unknown |
| Pause | none, tactical, technical, restore | none |
| Paused by | nobody, Team A, Team B, admin | nobody |
| Pause started | when the running pause began | unknown |
| Assigned, Went live, Ended | the match's times | unknown |
| Button bindings (diagnostic) | how many buttons are bound; the `bindings` attribute lists them | unknown |
| Team A logo, Team B logo, Map (images) | the pictures, fetched with the panel's login | no image |

**Team A and Team B are the panel's sides.** They are not home and away. The entity ids stay the
same from match to match, and the Team A / Team B sensors say who is playing. "Paused by" is
worked out from the current match's teams, so the next map with the sides swapped still says
the right thing.

A server added on the panel appears straight away. A server the panel drops goes unavailable,
and its device can then be deleted.

## How fresh it is

- **Push first.** The integration keeps the panel's push channel open and reads the panel again
  as soon as the panel announces a change. Several messages arriving at once cost at most two
  reads.
- **A read every second as a backstop.** This catches anything the panel doesn't announce, and
  covers the time while the channel reconnects (after 1 s, then doubling up to 30 s).
- **Server status every 10 seconds,** because answering it makes the panel probe the game
  servers.
- **No flapping.** A failed read keeps the last values for up to 6 seconds, so a single dropped
  request doesn't turn every entity unavailable and back, which would re-fire automations. After
  that, the entities go unavailable until the panel answers again.
- **A refused login** starts Home Assistant's re-authentication straight away.

## Installing

Through [HACS](https://hacs.xyz/):

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/clovisd/nodecs-hassio` with
   type **Integration**.
2. Find **NodeCS** in HACS, download it, and restart Home Assistant.

Or by hand: copy `custom_components/nodecs` into your Home Assistant `config/custom_components/`
and restart.

## Adding the panel

Settings → Devices & services → **Add integration** → **NodeCS**, then enter:

- **URL**: the panel's address, for example `https://panel.example.lan`. A bare host gets
  `https://`, and a pasted dashboard address works too.
- **Username** and **Password**: the login you use for the panel's web page.
- **Verify SSL certificate**: untick it if the panel uses your event's own certificate, which
  Home Assistant doesn't trust.

The form reads the panel once before saving. If the panel's address changes, use
**Reconfigure**. If its password changes, Home Assistant asks for the new one.

## Examples

A dashboard card for one server:

```yaml
type: entities
title: Server 1
entities:
  - sensor.server_1_phase
  - sensor.server_1_map
  - sensor.server_1_team_a
  - sensor.server_1_team_a_score
  - sensor.server_1_team_b
  - sensor.server_1_team_b_score
  - sensor.server_1_pause
  - sensor.server_1_paused_by
  - sensor.server_1_team_a_timeouts_left
  - sensor.server_1_team_b_timeouts_left
```

A team logo: `type: picture-entity` with `entity: image.server_1_team_a_logo`.

Spin a beacon for 30 seconds when Team A on server 1 calls a tactical timeout (needs
[blinkybeacon-hassio](https://github.com/clovisd/blinkybeacon-hassio)):

```yaml
alias: Server 1 – Team A tactical timeout
triggers:
  - trigger: state
    entity_id: sensor.server_1_paused_by
    to: team_a
conditions:
  - condition: state
    entity_id: sensor.server_1_pause
    state: tactical
actions:
  - action: blinkybeacon.spin
    data:
      device_id: <the beacon at team A's booth>
      duration: 30
```

Which booth is Team A depends on how the match was set up on the panel. Copy the automation for
Team B and its beacon.

## Limits

- Read-only. Forwarding button presses to the panel is the next step.
- The panel's own login is its only account, so Home Assistant stores the admin login. It's
  kept in the config entry like every integration's credentials, and never logged.
- Notifications, TeamSpeak, demos, backups, TV relays and tournaments are not shown.

## Development

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv/bin/python -r requirements_test.txt ruff==0.17.2
.venv/bin/pytest -q
.venv/bin/ruff check custom_components tests && .venv/bin/ruff format --check custom_components tests
```

Tested on Home Assistant 2026.10.4.

## Licence

MIT. See [LICENSE](LICENSE).
