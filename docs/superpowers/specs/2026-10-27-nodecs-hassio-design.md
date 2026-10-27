# nodecs-hassio — design

**Date:** 2026-10-27 · **Repo:** `clovisd/nodecs-hassio` (public, HACS) ·
**Status:** approved by the owner ("Approved, build it", 2026-10-27)

## 1. Intent

The owner runs CS2 at LAN events with a private web panel ("the panel") that manages the
game servers and the matches on them. The end goal is unchanged from blinkybeacon-hassio: Zigbee
buttons (one per team) call a team's tactical or technical timeout. The panel already models
this itself (see §3), so the later step is to route the button presses to the panel.

This step is **read-only**. This repository is a Home Assistant custom integration that reads the
panel's state and shows each game server, and the match on it, as a device in Home Assistant.
Two things follow from that:

- the owner can see every server at a glance on a Home Assistant dashboard;
- the panel's state can drive automations: for example, a team's tactical timeout spins that team's
  BlinkyBeacon through the `blinkybeacon` integration, side by side in the same automation.

Owner, 2026-10-27: "This will initially only provide data through it on a read only, reading data
from this api and providing it in home assistant as an intergration that provides all the info
about the server(s) visually, and usable with other automations (like blinkybeacon)."

## 2. Goals, non-goals, anti-goals

**Goals**
- The panel is added once from the HA UI (URL, login). Every game server on it becomes its own
  device; servers added to the panel later appear without a restart.
- For each server: its status, and for its current match the phase, map, teams, score, series
  score, timeouts used and left, ready flags, the running pause (reason and who called it), and
  the times the match was assigned, went live and ended. Also the button bindings, and the team
  logos and map image.
- Every value is something an automation can trigger on or test in a condition. "Team A started a
  tactical timeout" is a plain state trigger.
- **Lowest latency and highest reliability** (owner, 2026-10-27: "the priority with this is
  lowest latency possible, and highest reliability"). A change on the panel shows in Home
  Assistant as soon as the panel announces it, and within 1 s when it does not.
- Values are never stale for long: when the panel stops answering, the entities go unavailable
  (after a short grace that keeps one dropped request from flapping every entity, §6).
- Works with the panel's own certificate (the event's internal CA, untrusted by HA).

**Non-goals (this version)**
- Anything that writes to the panel: no pause, unpause, timeouts, bindings, go-live or RCON. The
  integration has no actions.
- Forwarding button presses to the panel (the later step; §9).
- The panel-wide buttons list and the press log, notifications, TeamSpeak, demos, backups, logs,
  TV relays, tournaments.
- Changes to the owner's Home Assistant instance or to the panel.

**Anti-goals**
- Any request that changes the panel. The integration sends one query, and nothing else.
- A secret reaching Home Assistant. The schema exposes server, RCON and TV passwords and the
  panel's own config (its login and API keys); the query never asks for them (§5).
- A value shown as current when it is not (a stale score, or a pause that already ended).

## 3. The panel API it uses

Read from the live panel on 2026-10-27, read-only, with the owner's permission (no mutations, no
secret fields).

- **Endpoint:** `POST https://<panel>/api/ui/graphql/query`, JSON `{"query", "variables"}`.
- **Login:** HTTP Basic Auth in front of the panel (nginx, `realm="Restricted Content"`). A wrong
  login answers `401` with an HTML body. It is the panel's only account: the admin login.
- **Errors:** `200` with `{"errors": [{"message": ...}], "data": null}`.
- **No GraphQL subscriptions** (`subscriptionType` is null), **but a push channel:** the panel's
  own UI opens `wss://<panel>/api/ui/notifications/subscribe` (same Basic Auth; `401` without it)
  and receives JSON text messages: `{"type": "match_updated", …}`, on which it refetches its
  match queries, and `{"type": "notification", "payload": {"id", "kind", "message", "ok",
  "title"}}` (kinds seen in the UI: `tech_pause`, `overtime`, `gg_quick`, `relay`). The UI does
  not poll; it reconnects 1 s after the channel closes. On staging it connected in about 400 ms
  and a `notification` arrived within 30 s. Not yet observed: which changes send
  `match_updated` (staging was idle), so the design does not rely on it alone.
- **Certificate:** not trusted by curl or Home Assistant by default, on the event panel and on the
  owner's staging panel alike.
- **Speed:** the full query answers in about 150 ms on the event LAN. On staging, over the
  internet on a kept-alive connection (15 samples each): ids only 74 ms median, the match query
  143 ms, `status` alone 207 ms. `status` costs the panel extra work (it appears to ask each game
  server), so it is kept off the fast path (§6).
- **Logos:** `Team.logoUrl` and `CS2Map.logoUrl` are absolute panel URLs
  (`/api/ui/teams/{id}/logo`, `/api/ui/cs2/maps/{id}/logo`) behind the same login; with it they
  answer `200 image/png`. A browser showing a Home Assistant dashboard cannot load them directly.

The types it reads (non-null `!` as the schema declares):

| Type | Fields read |
|---|---|
| `CS2Server` | `id: ID!`, `name: String!`, `status: CS2ServerStatus`, `match: CS2Match` |
| `CS2Match` | `id`, `phase: Phase!`, `bestOfX`, `bestOfXAScore`, `bestOfXBScore`, `teamA`/`teamB: Team!`, `map: CS2Map!`, `teamAReady`, `teamBReady`, `teamAScore`, `teamBScore`, `teamATimeoutsUsed`, `teamBTimeoutsUsed`, `teamATimeoutsLeft`, `teamBTimeoutsLeft` (all `Int!`/`Boolean!`), `assignedAt`, `liveAt`, `endedAt: Time`, `pauses: [CS2MatchPause!]`, `buttonBindings: [ButtonBinding!]!` |
| `Team` | `id`, `name`, `logoUrl` |
| `CS2Map` | `name`, `logoUrl` |
| `CS2MatchPause` | `reason: PauseReason!`, `startedAt: Time!`, `endedAt: Time`, `team: Team` (`id`) |
| `ButtonBinding` | `buttonID: String!`, `action: ButtonAction!`, `team: MatchTeam` |

Enums: `CS2ServerStatus` = STOPPED, STARTING, RUNNING_INVALID, RUNNING_VALID, UNKNOWN.
`Phase` = UNASSIGNED, WARMUP, KNIFE, LIVE, FREEZE_TIME, HALF_TIME_BREAK, ENDED, ARCHIVED (there is
no paused phase). `PauseReason` = TACTICAL, TECHNICAL, RESTORE. `ButtonAction` = TAC_PAUSE,
TECH_PAUSE. `MatchTeam` = A, B. `Time` is RFC 3339 UTC, with or without fractional seconds, up
to nanoseconds (`2026-10-26T08:02:05Z`, `2026-10-27T20:21:54.985469598Z`).

What the data looked like across 97 archived matches: a TACTICAL pause always has a team and lasts
about 30 s; TECHNICAL pauses come with a team (31) or without one (9, called from the panel);
RESTORE pauses never have a team. The pauses list is newest first. Timeouts used plus timeouts
left is not a constant: the admins can take a timeout away as a penalty (owner, 2026-10-27).

## 4. What the owner sees in Home Assistant

One config entry per panel. A **panel device** (named after the entry, model "Panel") carries
one diagnostic binary sensor, **Live updates** (connectivity): on while the push channel is open.
One device per game server, named after the server (`server_a1`), manufacturer "NodeCS", model
"CS2 server", linked to the panel device (`via_device`) and to the panel's web page.

Entities per server (`has_entity_name`, so `sensor.server_a1_team_a_score`). "No match" means the
server's `match` is null.

| Entity | Platform | State | With no match |
|---|---|---|---|
| Status | sensor (enum) | stopped, starting, running (valid), running (invalid) | — |
| Phase | sensor (enum) | no match, unassigned, warmup, knife, live, freeze time, half-time break, ended, archived | no match |
| Map | sensor | map name (`Nuke`) | unknown |
| Team A, Team B | sensor | team name | unknown |
| Team A score, Team B score | sensor | rounds won on this map | unknown |
| Team A maps won, Team B maps won | sensor | series score | unknown |
| Best of | sensor | 1, 3, 5 | unknown |
| Team A timeouts left / used, Team B timeouts left / used | sensor | count | unknown |
| Team A ready, Team B ready | binary sensor | on when ready | unknown |
| Pause | sensor (enum) | none, tactical, technical, restore | none |
| Paused by | sensor (enum) | none, team A, team B, admin | none |
| Pause started | sensor (timestamp) | when the running pause began; unknown while not paused | unknown |
| Assigned, Went live, Ended | sensor (timestamp) | the match's times | unknown |
| Button bindings | sensor (diagnostic) | number of bound buttons; attribute `bindings`: list of `{button, team, action}` | unknown |
| Team A logo, Team B logo, Map | image | the picture, fetched with the login | no image |

Enum option keys (translated for display): status `stopped`, `starting`, `running_valid`,
`running_invalid`; phase `no_match` plus the panel's values in lower case; pause `none`,
`tactical`, `technical`, `restore`; paused by `none`, `team_a`, `team_b`, `admin`. A binding in the
attribute is `{"button": "BOOTH-1", "team": "a" | "b" | null, "action": "tac_pause" |
"tech_pause"}`. A null `pauses` list counts as empty.

Identifiers (builder's call, recorded): device `(nodecs, "<entry_id>_<server id>")`, entity
unique id `<entry_id>_<server id>_<key>`, as in blinkybeacon-hassio. Server ids are the panel's
ULIDs and do not change when a server is renamed; the device name follows the panel's name.

- **Team A and Team B are the panel's sides,** not home and away. Entity ids stay fixed while the
  teams change from match to match; the team's name is the Team A / Team B sensor.
- **The running pause** is the entry in `pauses` with no `endedAt` (if there were ever two, the one
  that started last). "Paused by" compares its team's id with team A's and team B's; no team means
  admin. A team id that matches neither gives unknown.
- **Server status UNKNOWN** is Home Assistant's own unknown state, not an option.
- **A value this version does not know** (a phase or status a newer panel adds) gives unknown and
  a debug log line, not an error.
- **Images** are fetched by the integration with the login and the certificate setting, and
  served by Home Assistant's image proxy, so any dashboard can show them. They are fetched again
  only when the URL changes. The login is sent only to the panel's own address: a logo URL on
  another host is fetched without it, so a team logo can never carry the password elsewhere.

## 5. The query

Two queries, each for all servers. They name every field they read and nothing else.

The match query (the fast path):

```graphql
query HomeAssistantMatches {
  cs2Servers {
    id name
    match {
      id phase bestOfX bestOfXAScore bestOfXBScore
      teamA { id name logoUrl } teamB { id name logoUrl }
      map { name logoUrl }
      teamAReady teamBReady teamAScore teamBScore
      teamATimeoutsUsed teamBTimeoutsUsed teamATimeoutsLeft teamBTimeoutsLeft
      assignedAt liveAt endedAt
      pauses { reason startedAt endedAt team { id } }
      buttonBindings { buttonID action team }
    }
  }
}
```

The status query (the slow path): `query HomeAssistantStatus { cs2Servers { id status } }`.

Neither ever asks for `config`, `password`, `livePassword`, `rconPassword`, `tvPassword*`,
`tvRelayPassword`, `logsWebSocketUrl`, or the server's `ip` and `port`. Tests pin the query text
so a new field is a reviewed change.

## 6. Behaviour

- **Push first.** The integration keeps the push channel open. Every message on it
  (`match_updated` or `notification`) triggers an immediate read of the match query; messages
  that arrive while a read is running are covered by one more read straight after it (a 0.3 s
  coalescing window, not Home Assistant's default 10 s).
- **Backstop poll.** The match query also runs every **1 s** whatever the channel does, so a
  change the panel does not announce, or one made while the channel was reconnecting, shows
  within about a second.
- **Server status** is read every **10 s** with its own query and a 10 s timeout, because
  answering it makes the panel probe the game servers; doing that every second would load them
  during matches. Its first read may fail without stopping setup (the status sensors start
  unavailable), so one slow game server never keeps the matches from loading.
- **Channel drops:** reconnect after 1 s, doubling to at most 30 s, and back to 1 s once
  connected. The 1 s poll carries on meanwhile. "Live updates" shows the state; the drop and the
  recovery are each logged once.
- **Timeouts:** 3 s per request (the panel answers in about 150 ms on the LAN); 10 s for the
  setup form's first contact.
- **Transient failures:** a failed read keeps the last values for up to **6 s**, so one dropped
  request does not flip every entity to unavailable and back, which would re-fire automations
  that trigger on a state. After 6 s without a good read, every entity of that query goes
  unavailable until the next good read. The first failed read in a row is always tolerated, so
  the 10 s status read also survives one dropped request.
- **Connections are reused:** Home Assistant's shared HTTP session keeps them alive, so a poll
  does not pay for a TLS handshake.
- **401** on a read: Home Assistant starts its re-authentication flow ("NodeCS needs its login
  again"); the entities go unavailable until it is done. No grace for a 401. A 401 on the channel
  is treated as a drop; the next read, within 1 s, raises the re-authentication.
- **GraphQL `errors`:** a failed read; the first message is in the log.
- **Servers added on the panel:** their devices and entities are added at the next match read.
- **Servers deleted on the panel:** their entities go unavailable; the device can then be deleted
  from Home Assistant's device page.
- **Unload, reload, shutdown:** the channel is closed and the polls stop; the integration holds no
  state on the panel.

## 7. Setup

Settings → Devices & services → Add integration → **NodeCS**:

- **URL** — `https://panel.example/`. A bare host gets `https://`. A pasted page address
  (`…/dashboard`, `…/api/ui/graphql/query`) is accepted: the path is dropped, because the
  panel's API paths are absolute from the site root.
- **Username**, **Password** — the panel login.
- **Verify SSL certificate** — on by default. The form's description says to untick it for a
  panel with the event's own certificate.

The form runs the query before saving. Errors: cannot connect; wrong username or password; the
certificate is not trusted (with the hint to untick the box); the address answered but is not the
panel's API. One entry per panel address (`host:port`). **Reconfigure** changes the URL and
the certificate setting; **re-authenticate** changes the login.

## 8. Packaging and tests

- Same shape as blinkybeacon-hassio: `custom_components/nodecs/`, a config flow, a
  `DataUpdateCoordinator`, `runtime_data`, translated strings, `hacs.json`, MIT licence, a README
  with setup and example automations, a validate workflow (hassfest, HACS, pytest, ruff).
- Tests with `pytest-homeassistant-custom-component` against a mocked panel. The fixtures copy the
  live reply's shape with made-up ids, teams and hostnames; nothing from the event is committed.
- README examples: a dashboard card for one server, and an automation that spins a BlinkyBeacon
  while "Paused by" is a given team and "Pause" is tactical.

## 9. The later step (not built here)

The panel already handles physical buttons:

- **Buttons** register themselves when first pressed (`Button.firstSeenAt`, `lastPressedAt`). IDs
  are free text (the UI suggests `BOOTH-…`).
- **Bindings** are set per match in the panel: button → team A/B and TAC_PAUSE or TECH_PAUSE.
  "Before the match is live, presses are only reported, so you can check each button is wired to
  the right team."
- **Every press is logged** with an outcome: NONE, TEST, EXECUTED, ERROR.
- **Presses arrive on their own endpoint** with their own key (`Config.buttonApiKey`), supplied by
  the owner on 2026-10-27: `POST /api/buttons/{buttonID}/press` with
  `Authorization: Bearer <button key>`. A button that has never pressed registers itself.
- **A newer panel build also tracks button outages** (`buttonOutages(buttonIDs, limit)`:
  `buttonID`, `startedAt`, `endedAt`, `detail`), which suits the range tests.

So the later integration step is most likely "forward each Zigbee press to the panel's button
endpoint with the button key, and let the panel's bindings decide", not "call `pauseCS2Match`
from Home Assistant". The press log and the buttons list are the natural things to add to this
integration at that point.

## 10. Calls made without the owner

- **Names:** the owner chose `nodecs-hassio` and a public repo (2026-10-27). Domain `nodecs` and
  title "NodeCS" follow from it (the casing is the builder's call).
- **No product or event names in the public repo:** it says "the panel", never the panel's
  product name, the event, or its hostnames. The fixtures use made-up teams and hosts.
- **Push plus a 1 s backstop poll, status every 10 s, a 6 s grace, 3 s timeouts,** none of them
  configurable (Home Assistant's guidance for integrations). These follow the owner's latency and
  reliability priority and the measurements in §3.
- **A panel device with a "Live updates" sensor,** so falling back to polling is visible.
- **Team A / Team B** naming rather than home / away, because the panel's sides are A and B.
- **No-match values are unknown**, not unavailable: unavailable is kept for "the panel is not
  answering".
- **Images through Home Assistant,** because the logos sit behind the panel's login.
- **Re-authentication flow,** because event logins change.
- **Risk accepted:** Home Assistant stores the panel's admin login, its only account. It is kept in
  the config entry like every other integration's credentials and never logged.
