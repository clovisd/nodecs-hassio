# Timeout button system — design

**Date:** 2026-10-28 · **Status:** design agreed in conversation with the owner ("Looks good",
2026-10-28); not built. Red-team and blind-builder checks (Fable 5.1) were run on the first draft;
their findings are folded in below and listed in §13. After the checks the owner answered §12
Q1, Q2 and Q4 and added Discord webhooks (§5.13, approved "looks good"). Later the same day the
owner answered Q3 and Q5–Q7 (names, page access with a standalone page, retention, network): no
questions remain open. A second red-team and blind-builder check ran on this version (§13).
**Repos:** `clovisd/nodecs-hassio` (this one, piece 1; **private since 2026-10-28**), and three
repos that do not exist yet: `unityintercom-hassio` (piece 2), `coachpc` (piece 3) and
`coachpc-hassio` (piece 4).
**Builds on:** `2026-10-27-nodecs-hassio-design.md` (NodeCS v0.1, read-only, shipped).

This repo never names the panel's product, the event, its hosts, or real teams. It says "the
panel". It is private for now, but may go public again, so keep it that way in every document
and commit.

---

## 1. Intent

At the owner's CS2 LAN events, each team's coach can call a **tactical timeout** or a
**technical pause** by pressing a Zigbee button at their booth. The panel that runs the game
servers already receives button presses, matches each one to a team through per-match
bindings, and executes the pause on the game server.

This design covers everything around that press: getting it to the panel as fast as the
hardware allows, never losing or doubling one, proving before each match that every button
works for the right team, telling the coach and the admin that a press landed, spotting
problems at a booth before they cost a press, and keeping a permanent record of all of it.

The owner's words, 2026-10-28:

- "high stakes scenarios where we cannot miss a button press, and cannot afford any latency on
  them (while also having full accountability)."
- On the coach PCs: "this needs to have zero impact on teamspeak client and coach communication
  and latency. We sometimes have issues that causes desync and have to restart the teamspeak
  client so we can't afford that."
- Bindings: "For now, keep it manual."

## 2. The room

| Who / what | Where | Notes |
|---|---|---|
| **Booth** | One per team position at a matchup | One Zigbee button and one coach PC. **No beacon at the booth.** Which team sits at a booth changes from match to match. |
| **Button** | At the booth | Sonoff **SNZB-01P**, battery, on ZHA. Tap and hold are used; double press is not. |
| **Coordinator** | Venue | SMLIGHT **SLZB-MR5U**, ZHA. Wired to Home Assistant (Ethernet or USB, never Wi-Fi). |
| **Coach PC** | At the booth, headless | Windows 11, slimmed down. Runs the TeamSpeak client into the coach's headset (wired "AC" headphones on a USB extension). Static LAN IP. Operated over RustDesk. Moved between TeamSpeak team channels to match the booth's team. |
| **Coach** | At the booth | Hears TeamSpeak; until now has no feedback that a press worked, other than the pause itself happening on the server. |
| **Lobby admin** | Lobby desk | Runs the match on the panel. Has the **BlinkyBeacons**, as the "a button was pressed" alert. Uses the Home Assistant page. |
| **Walker** | Moving between booths | An admin with the **Unity Intercom** mobile app, doing the walk-round test. |
| **Unity bot** | An always-on Windows PC near the lobby admin, never a coach PC | A Unity Intercom desktop client logged in as a test-bot user. |
| **Home Assistant** | Venue LAN | ZHA, the SMLIGHT integration, BlinkyBeacon, NodeCS, and the two new integrations. |

## 3. Goals, non-goals, anti-goals

**Goals**

1. A press reaches the panel as fast as the hardware allows: no automation engine, no queue, no
   new connection in the path.
2. No press is lost and none is executed twice.
3. Every press, test step and alert is archived for good, with timings and who did what, and can
   be exported.
4. Before each match, the admin can prove each booth's button works for the right team (admin
   test), and each coach can hear that their own button works (coach test).
5. Problems are announced before they cost a press: a pulled headset, TeamSpeak down, a
   coach PC off the network, a weak or silent Zigbee button, the panel or its button key
   failing, the coordinator or the Unity bot down.
6. One page in Home Assistant shows all of it, per matchup and per booth.
7. Unity Intercom and the coach PCs are their own integrations that report and offer actions,
   usable from the page and from any automation.

**Non-goals (this design)**

- Home Assistant writing button bindings to the panel. Binding stays manual in the panel; the
  page only checks it.
- Changing, configuring, or talking to the TeamSpeak client.
- Replacing the buttons. The SNZB-01P's own tap delay (§5.3) is accepted for now.
- Redundant coordinators or radios.

**Anti-goals**

- Any measurable effect of this system on TeamSpeak, the coach's audio, or their latency.
- A missed press. A pause executed twice. A test that pauses a live match.
- A failure that is silent: every failed press, test step or check is shown and archived.
- A secret (admin login, button key, coach PC token) in a log, an event, the archive, or a repo.

## 4. Architecture

```
  SNZB-01P ──Zigbee──▶ SLZB-MR5U ──▶ ZHA ──zha_event──▶ NodeCS button path ──HTTPS──▶ panel
                                                        │   POST /api/buttons/{id}/press
                                                        │
                       ┌────────────────────────────────┼────────────────────────┐
                       ▼                                ▼                        ▼
               nodecs_button_press event        archive (append-only)    readiness page
                       │                                                  (sidebar panel)
          automations (e.g. spin the                       │ calls actions during tests
          lobby admin's beacon)                ┌───────────┴────────────┐
                                               ▼                        ▼
                                  unity.direct_talk               coachpc.play_sound
                                  (Unity integration)             (coach PC integration)
                                        │ UDP 20119                     │ LAN HTTP + token
                                        ▼                               ▼
                                  Unity bot client ──▶ walker's   coach PC app ──▶ coach's
                                  (desktop, Windows)    phone      (Windows)        headset
```

Four pieces, built in this order (see the build plan):

1. **NodeCS v0.2** (this repo): the button path, the archive, the readiness page, the tests,
   and the health checks.
2. **Unity Intercom integration** (`unityintercom-hassio`, domain `unity_intercom`): the Unity
   server and bot clients as devices.
3. **Coach PC app** (`coachpc`, Go): a small Windows app with a LAN API.
4. **Coach PC integration** (`coachpc-hassio`, domain `coachpc`): each coach PC as a device in
   Home Assistant.

NodeCS works without 2–4 (tests run without beeps, booth health shows only Zigbee and the
panel). Pieces 2 and 4 work on their own in any automation.

**Later, not designed here:** a fifth integration for the **admin timer**, an existing tool with
its own API. The owner, 2026-10-28: "it can also provide additional confirmation on correct
channel". It plugs into the team-at-booth rule (§5.10) as a second, corroborating source. It
needs its own brainstorm once its API is known.

---

## 5. Piece 1 — NodeCS v0.2: the button path

### 5.1 The panel's button API

| | Source |
|---|---|
| `POST <panel>/api/buttons/{buttonID}/press` with `Authorization: Bearer <button key>` | The owner, 2026-10-27, with a working curl. |
| The button key is the panel's `Config.buttonApiKey`, separate from the admin login. | Panel schema. |
| A button that has never pressed registers itself (`Button.firstSeenAt`). | Schema; the panel UI: "Press an unbound button to see its ID here and in the notifications." |
| Bindings are per match: button ID → `TAC_PAUSE` or `TECH_PAUSE` → team A or B. | Schema; the panel's Buttons dialog. |
| Every press is logged: `buttonPresses(buttonID, matchID, limit)` → `id`, `buttonID`, `pressedAt`, `match`, `outcome` (`NONE`, `TEST`, `EXECUTED`, `ERROR`), `detail`. | Schema; staging showed `executed` / "tac pause for &lt;team&gt; requested". |
| "Before the match is live, presses are only reported, so you can check each button is wired to the right team." | The panel's Buttons dialog. |
| Newer panel builds have `buttonOutages(buttonIDs, limit)` → `buttonID`, `startedAt`, `endedAt`, `detail`. | Staging schema only. |
| **A press is a request, not an instant pause.** A tac pause "may not actually trigger a tac right away, and instead queue it for next possible time per server support … It won't allow it to fire right away normally." So `EXECUTED` means *requested* (the detail reads "tac pause for &lt;team&gt; requested"); the pause itself starts later and shows up in the match's `pauses`. | The owner, 2026-10-28; the staging press log. |

**Not yet known, and the build must find out first (Phase 0):**

- What the press endpoint answers: status codes, and whether the body carries the outcome, the
  press id, or nothing.
- What the panel does with the same button ID pressed twice in a row, during a running pause
  and outside one: a second pause, an error, or nothing.
- What `NONE` means (unbound button? no match on the server?).
- How long a requested pause waits, by type: does a technical pause start at once while a
  tactical one waits for the next freeze time? Is a pending, not-yet-started request visible
  anywhere in the API? What does a second press do while one is pending?
- Exactly when the panel stops "only reporting" and starts executing: which phases, and whether
  it uses `liveAt`. Staging showed a match in `WARMUP` with `liveAt` set (a restored match), so
  `liveAt` alone is not the answer.
- The press endpoint's rate limits, if any.
- How `buttonOutages` decides an outage, and whether it applies to buttons that do not send
  heartbeats.

### 5.2 Booths and links

The page keeps a **booth list**, stored by NodeCS (Home Assistant `Store`, versioned):

```
booth:
  id: "a1-left"                 # short, stable, chosen by the admin
  name: "Server 1 · left"
  server_id: <panel server id>  # the matchup this booth belongs to
  server_name: "Server 1"       # kept beside the id, for re-linking and the archive
  side_hint: none               # informational only; the team comes from the bindings
  button:
    ieee: "00:12:4b:…"          # the SNZB-01P, picked from ZHA devices
    tap_id: "a1-left-tech"      # panel button ID sent on a tap
    hold_id: "a1-left-tac"      # panel button ID sent on a hold
  coach_pc: <coach PC device>   # optional, from piece 4
  teamspeak_nickname: "Booth A1 L"  # optional, how this coach PC appears on the TS server
```

- Each SNZB-01P has **two panel IDs**, one per gesture, because a binding gives one ID one
  action. The admin binds both, per match, in the panel (manual, by design).
- One button belongs to one booth. A button in two booths, or one panel ID used twice, is
  refused when saving.
- Panel IDs are free text on the panel. The page suggests `<booth>-tech` and `<booth>-tac`.
- If the panel no longer lists a booth's server id (for example a fresh panel database at the
  next event), the page marks the booth **unlinked** and offers to re-link it to a server by
  name. The archive stores names beside every id, so old records stay readable. (Blind B5.)

### 5.3 What the SNZB-01P sends

Under ZHA each gesture is a `zha_event` from the device's IEEE address:

| Gesture | ZHA command | Timing (to verify on a real unit in Phase 0) |
|---|---|---|
| Tap | `toggle` | Sent about **0.6 s after release**: the button waits to rule out a double press. (Zigbee2MQTT's SNZB-01 page; assumed for the 01P.) |
| Double press | `on` | **Treated as a tap.** A coach with no feedback who taps twice must not lose the press. (Red team R2.) |
| Hold | `off` | After **about 2–3 s** of holding. Whether it is sent when the threshold is reached or on release decides the hold latency. |

- The tap's ~0.6 s and the hold's 2–3 s are the button's own decision time. No software can
  remove them. The page shows them as a fixed part of the latency, separate from the part the
  system controls.
- The hold time is deliberate: a tac pause needs a hold so it cannot be called by accident
  (owner, 2026-10-27).
- If the tap delay ever matters, the fix is a button that reports a press immediately. That is a
  hardware decision for the owner, out of scope here.

### 5.4 The press, step by step

**The press path does not depend on the panel reads.** It is set up at entry setup **before and
independently of** the match and status coordinators. A panel that does not answer at boot no
longer leaves the entry unloaded. The coordinators retry on their own, and presses are received,
queued and sent with retries the whole time. (Red team R7. This changes v0.1's setup, where a
failed first read raised `ConfigEntryNotReady`.)

NodeCS subscribes to `zha_event` on Home Assistant's bus, filtered to the IEEE addresses in the
booth list. For each event:

1. **Received:** at `t_zha`, `nodecs_button_received` fires at once with the booth, gesture and
   panel ID. The lobby admin's beacon automation hangs off this event, not off the outcome.
   (Red team R11.)
2. **Map:** `toggle` and `on` (double press) → the booth's `tap_id`; `off` → `hold_id`. Anything
   else is logged and ignored. A button not in the booth list is ignored, but shown on the page
   ("unlinked button pressed"), so a forgotten link is visible.
3. **Drop true duplicates only:**
   - the same button and gesture again within **1 s** is a duplicate. It is archived as
     `duplicate_dropped` and never sent;
   - beyond 1 s, a repeat is **queued** behind the press still in flight for that booth and
     gesture, never dropped. (Red team R4.)
4. **Send at once:**
   - `POST /api/buttons/{id}/press` with the button key goes out on a **dedicated press
     session**: its own aiohttp connector with two connections, kept warm by a tiny
     authenticated request every 5 s. The 1 s match read can't occupy it. (Red team R16.)
   - Timeouts are `aiohttp.ClientTimeout(sock_connect=1, total=3)`, with distinct error types
     for "never connected" and "failed after sending". v0.1's client merges these into one
     connection error, and the press client must not. (Red team R3.)
   - The send runs as its own task: never behind a read, the read debouncer, or an automation.
   - A `press_sent` record is handed to the archive writer at `t_sent` without waiting for the
     disk. (Red team R10a.)
5. **Classify the result:**
   - `2xx`: delivered.
   - **Never left** (connection refused, DNS failure, TLS handshake failure, connect timeout):
     retry every **0.5 s for up to 10 s**, then failed. A critical alert is raised at **2 s**,
     while the retries continue. A tactical timeout that lands late still takes effect at the
     next freeze time, so late beats never. (Red team R5.)
   - **Ambiguous** (timeout after sending, reset after sending, `5xx`): the press may already
     have been executed. NodeCS resolves this by **the panel's press ids, never by comparing
     clocks** (red team R3; blind B3):
     - NodeCS keeps the newest press id it has seen for each panel button ID. It seeds this at
       startup by reading `buttonPresses` for every linked ID, and updates it after each outcome
       read and by reconciliation (§5.6).
     - It then reads `buttonPresses(buttonID, limit: 5)`. A press id it has not seen before,
       newer than the stored one, means **delivered**. Ids are ordered by the panel itself,
       which Phase 0 confirms.
     - None means **resend**, and the same check repeats for up to 10 s.
   - `401` or `403`: the button key was refused. Failed, no retry. A repair issue and a critical
     alert are raised.
   - Other `4xx`: failed, no retry.
6. **Confirm the request:** after delivery NodeCS reads the press log for this ID to get the
   panel's `outcome` and `detail`, waiting up to 2 s for the entry to appear. `EXECUTED` means
   the pause was **requested** and accepted, not that the game has paused (§5.1). NodeCS also
   asks the match coordinator for an immediate read.
7. **Record and announce:**
   - the archive gets a `press_outcome` record (§5.6);
   - `nodecs_button_press` fires with every field, minus secrets.
8. **Watch for the pause to start:**
   - after an `EXECUTED` press NodeCS watches that server's match for the **first new pause by
     that team** of the matching kind (`TACTICAL` for a hold, `TECHNICAL` for a tap) starting
     after the request;
   - when it appears, the archive gets a `pause_started` record linked to the press, and
     `nodecs_pause_started` fires with the delay;
   - until then the page shows the press as **"requested, waiting for the server"**, with how
     long it has waited. That wait is the game's rule, not a fault, so it is never an alert by
     itself;
   - if the match ends, or the team's timeouts-left count drops without a matching pause, the
     page shows it for the admin to judge.

**Failure is loud.** A press that fails, or ends in `ERROR`, raises a persistent notification
and a critical `nodecs_alert` at once, naming the booth, the team and the reason.

### 5.5 Latency

For each press NodeCS records:

| Field | Clock | Meaning |
|---|---|---|
| `t_zha` | Home Assistant | `time_fired` of the `zha_event`. The earliest moment Home Assistant knows. |
| `t_sent`, `t_answered`, `t_outcome` | Home Assistant wall clock | When the request started, when the panel answered, when the log entry was read. |
| `latency_ms` | Monotonic clock | `t_answered − t_zha`, measured on the monotonic clock so an NTP step can't make it negative. (Red team R10d.) |
| `pressed_at_panel` | Panel | The log entry's `pressedAt`. |
| `pause_started_at` | Panel | The linked pause's `startedAt` (§5.4 step 8). The time from the request to it is **the game's waiting time**, shown separately and never counted as press latency. |

- The page shows **HA → panel** (`latency_ms`) as the press latency, with the button's own
  decision time (§5.3) beside it as a fixed note.
- A cross-clock figure (`pressed_at_panel − t_zha`) is shown only when the offset between the
  panel's clock and Home Assistant's has been measured (Phase 0). Otherwise it is hidden, not
  shown wrong. Home Assistant has no core API for its own NTP state, so none is assumed.
  (Red team R10e.)
- The radio hop from finger to coordinator cannot be measured from Home Assistant.

### 5.6 The archive

- **Storage:** append-only JSON Lines files, one per day:
  `<config>/nodecs/archive/YYYY-MM-DD.jsonl`. NodeCS never prunes or rewrites them, and the
  recorder is not used because it purges.
- **Record types:** `press_sent`, `press_outcome`, `pause_started`, `duplicate_dropped`, `unlinked_press`,
  `foreign_press`, `test_run`, `test_step`, `alert`, `alert_cleared`, `config_change` (booth
  list edits). Each carries:
  - a UTC timestamp and a monotonic sequence;
  - the Home Assistant user id and name, for anything a person started;
  - the match, server, team, booth and panel IDs it concerns, each with its name.
- **Two records per press:** `press_sent` at the moment of sending, then `press_outcome`. A
  crash between the two still leaves proof that the press was sent. (Red team R10a.)
- **Reconciliation:**
  - every 10 s NodeCS reads `buttonPresses` for the linked IDs (a cheap, slow-path query);
  - any press the panel logged but NodeCS did not send (a leaked key, a curl, another
    controller) is archived as `foreign_press`;
  - a foreign press with outcome `EXECUTED` is a critical alert. (Red team R10b.)
- **Tamper evidence:**
  - each line carries the SHA-256 of the previous line, and the chain **continues across days**:
    a day's first line carries the previous day's last hash;
  - the page shows the current head hash and a "chain intact" check;
  - every export includes the head hash, so a copy kept elsewhere proves later files were not
    rewritten. (Red team R10c.)
- **Export:** CSV or JSON, for a day, a match or a test run, from the page.
- **Retention: never delete** (owner, 2026-10-28). NodeCS never removes or rotates archive files,
  and offers no "clear" action. Disk use is shown on the page.
- **Writing:** a dedicated writer task, off the event loop, flushed and fsynced per record. A
  write failure raises a critical alert. It never blocks or delays a send.
- **Size:** a few KB per match.

### 5.7 Events (the contract other pieces and automations use)

| Event | When | Key fields |
|---|---|---|
| `nodecs_button_received` | Immediately at `t_zha`, before sending | `booth`, `gesture`, `panel_id`, `server_id`, `t_zha` |
| `nodecs_button_press` | After step 7 of §5.4, for every press, including test-window presses | `booth`, `gesture` (`tap`/`hold`), `panel_id`, `server_id`, `match_id`, `team` (`a`/`b`/`null`, from the bindings), `team_name`, `result` (`delivered`/`failed`), `outcome` (`executed`/`test`/`error`/`none`/`unknown`), `detail`, `t_zha`, `t_sent`, `t_answered`, `latency_ms`, `test_run_id` |
| `nodecs_pause_started` | The pause a press requested has started (§5.4 step 8) | `booth`, `panel_id`, `server_id`, `match_id`, `team`, `reason` (`tactical`/`technical`), `requested_at`, `started_at`, `waited_s`, `press_seq` |
| `nodecs_test_step` | Each step of a test | `test_run_id`, `kind` (`admin`/`coach`), `step`, `booth`, `gesture`, `status` (`passed`/`failed`/`waiting`), `latency_ms`, `team_matched`, `note` |
| `nodecs_alert` | An alert starts or clears | `alert_id`, `severity` (`critical`/`warning`), `source`, `booth`, `message`, `active` |

### 5.8 Health checks and alerts

| Check | Source | Warning | Critical |
|---|---|---|---|
| **Press path alive** | ZHA config entry state, the coordinator link (SMLIGHT integration, if installed), NodeCS's own `zha_event` subscription | — | **Immediately** when ZHA is not loaded, the coordinator link is down, or NodeCS is not subscribed. (Red team R6.) |
| Panel answers | match coordinator | — | unavailable (after the 6 s grace) |
| Live updates | push listener | off > 60 s | — |
| Button key | the last press, or the path check | — | refused (401/403) |
| Button heard from | ZHA `last_seen` per booth button | above the SNZB-01P's measured check-in interval × 1.5 while its server has a match | above × 3 (Phase 0 measures the interval; no fixed 30 min / 2 h) |
| Button signal | ZHA LQI / RSSI at the last message | LQI < 100 | LQI < 50 |
| Button battery | ZHA battery | < 30 % | < 15 % |
| **Coach test done** | the archive | — | a match leaves WARMUP without a passed coach test for every booth on its server (alert only; the panel is never blocked). (Red team R6.) |
| Binding sanity | panel bindings for **every** match, the booth list, TeamSpeak | a booth's tap or hold ID not bound for its current match | a booth's ID bound on **another** server's match (red team R8); or bound to the team whose TeamSpeak channel this booth's coach PC is not in (§5.10) |
| Foreign press | reconciliation (§5.6) | — | a press NodeCS did not send, executed |
| Archive | the writer | — | a write failed |
| Coach PC | piece 4 | §8 | §8 |
| Unity bot | piece 2 | logged out | client not polling |

**Against alert fatigue** (red team R13):

- Every threshold has hysteresis and a minimum duration before raising or clearing (builder's
  values).
- While any match is live, only **press-path alerts** go to the beacon and notifications (press
  path alive, key refused, a failed press, foreign press, wrong-server binding). Everything else
  shows on the page.
- The README's beacon automation uses distinct patterns: **spin** for a press, **flash** for a
  critical alert.

**How alerts surface:**

- Critical alerts raise a persistent notification and `nodecs_alert`.
- Warnings show on the page and in the archive.
- An alert clears itself when its condition clears. Both moments are archived.
- Thresholds live in one place and are easy to change.

**Venue hardware note:** the booths are at 2.4 GHz esports distances with one coordinator, so
plan mains-powered Zigbee routers between the coordinator and the booths. Phase 0 runs a range
survey. Never update the coordinator, ZHA or Home Assistant during an event. (Red team R6.)

### 5.9 The readiness page

- **Placement:** a Home Assistant **sidebar panel** registered by NodeCS, plus a **standalone
  page** (§5.9.1). Both are the same web component.
  - In Home Assistant it talks to NodeCS over Home Assistant's WebSocket API: one subscription
    for live state, plus commands for tests, team assignments and booth edits.
- **Who may do what** (owner, 2026-10-28):
  - **Home Assistant admins:** everything, including booth editing.
  - **Non-admin Home Assistant users:** see the page read-only (status, presses, tests,
    archive), but cannot start tests, assign teams, edit booths or export.
  - Every WebSocket command checks the role server-side; the page hiding buttons is not the
    check.
- **Status strip:**
  - the panel: answering, live updates, read time p50/p95;
  - the button key;
  - the coordinator;
  - the Unity bot;
  - the count of active alerts.
- **One card per matchup:**
  - the server, the teams, the phase;
  - per booth:
    - the button: signal, last heard, battery;
    - its two panel IDs and what each is bound to now;
    - the coach PC: up, headset, TeamSpeak, channel;
    - the last press and its latency;
    - the last admin and coach test results.
  - **Admin test: Go** and **Coach test** buttons.
- **Press log:** recent presses across all matchups, newest first, with every field from §5.5.
- **Archive:** browse by day, match or test run; export; chain check.
- **Booths:** add, edit or remove booths (§5.2). Every change is archived.
- The mockups in `docs/design/mockups/` show the layout and content the owner reacted to, not
  final styling. **Where they disagree with this spec, the spec wins.** For example, the
  mockups show a booth beacon, which does not exist, and an older path check. (Blind B4.)

#### 5.9.1 The standalone page

The owner, 2026-10-28: "if there's a way to serve it as a standalone page too, so it can be
directly accessed without HA ui / frame, and make that page password protected".

**What it is:** NodeCS serves the same page at `/nodecs/board/` on Home Assistant's own port, as
a plain page outside Home Assistant's frontend and login. It suits a lobby screen or a staff
laptop. It is **off unless a password is set.**

**Two roles,** each with its own password in NodeCS's options. An empty password turns that role
off.

| Role | Can |
|---|---|
| **Viewer** | Everything a non-admin Home Assistant user sees: status, presses, tests and the archive, read-only |
| **Operator** | Viewer, plus start and stop tests, choose the walker, and assign teams to booths. Booth editing, NodeCS's options and archive export stay Home Assistant admin-only. |

**Accountability:** the login form also asks **who you are** (a free-text name). That name and
the role are archived with every action taken from the standalone page, and with every login
and logout. Actions taken in Home Assistant use the Home Assistant user.

**Security** (builder's calls; the owner's network keeps these pages on a VLAN players cannot
reach):

- **Passwords** are stored as scrypt hashes in the options, never in plain text, and never
  logged.
- **Sessions:** a random token in an `HttpOnly`, `SameSite=Strict` cookie (`Secure` when Home
  Assistant serves HTTPS). It expires after 12 hours, and changing a password ends every session
  of that role.
- **Logins** are limited to 5 tries a minute per IP, then a 5-minute lockout. Every failed login
  is archived, and a burst raises a warning alert.
- **Actions:** every state-changing request carries a CSRF token and is checked server-side
  against the role.
- **Its own narrow endpoints only:**
  - a Server-Sent Events stream for live state, using the same data as the Home Assistant
    WebSocket subscription;
  - a few POST commands for the operator actions.
  - It never exposes Home Assistant's API, tokens, the panel's login, the button key, the
    Discord URLs, or the coach PC tokens.
- **Response headers:** `Content-Security-Policy` limited to the page's own assets,
  `X-Frame-Options: DENY`, and `Cache-Control: no-store`.

### 5.10 The team at each booth, and the binding check

**The team at a booth** is the reference for the tests and the binding check. One rule decides
it everywhere. The owner, 2026-10-28: "first ts (note that sometimes, its updated later), then
admin with direct overwrite somewhere to ASSIGN a button."

1. **An admin assignment wins.** On each matchup card every booth has an **Assign** control: the
   admin sets the booth's team for the current match (team A, team B, or clear).
   - It overrides TeamSpeak for that match only, and is cleared when the server gets a new
     match.
   - It is archived as a `config_change` with the admin's user.
2. **Otherwise, TeamSpeak:** the team whose channel the booth's coach PC is in (below).
   - Coach PCs are sometimes moved to their team channel late, so a TeamSpeak answer is shown as
     **"from TeamSpeak"** and re-checked continuously, never frozen.
3. **Otherwise, unknown:** the page asks for an assignment before a test can judge that booth.
4. **Later, the admin timer** (§4) adds a second opinion. When it and TeamSpeak agree, the page
   marks the team **confirmed**. When they disagree, it shows a warning and asks the admin to
   assign.

The page always shows where a booth's team came from: assigned, TeamSpeak, confirmed, or
unknown.

**The binding check** compares three things, for **every** match on the panel:

1. the panel's bindings: which team and action each ID is bound to, on which server;
2. the booth list: which booth owns which IDs, on which server;
3. TeamSpeak, read from the panel's `ts3Clients` (read-only): which team channel each booth's
   coach PC is in, matched by `teamspeak_nickname`, against each match's `teamATSChannel` /
   `teamBTSChannel`.

What it raises:

- **Critical:** a booth's ID is bound in a match on **another server**, where the press would
  pause the wrong match. (Red team R8.)
- **Critical:** a booth's IDs are bound to one team while an **admin assignment** puts the
  other team there.
- **A TeamSpeak-only mismatch is a warning first,** because the channel may simply not be
  updated yet. It becomes critical only if it is still there when the match leaves the test
  phase, or when a test starts.
- **Warning:** a booth's coach PC is not found in TeamSpeak, or two TeamSpeak clients share its
  nickname.

Nothing is ever changed: bindings stay manual.

### 5.11 Tests

**No synthetic press ever goes to a bound ID.** The first draft's path check pressed every bound
ID. A stale phase read, or the panel executing in a phase assumed to be "report only" (the knife
round?), would have burned a team's timeout. (Red team R1.)

**A test window ends when the match starts, for both tests.** The owner, 2026-10-28: "A test
window should end when a match starts. For both admin and coach test. Once its live, it should go
live and that's all. A press is a press once live."

- The moment a server's match leaves the test phase (from the push channel or the 1 s read),
  any admin or coach test open on that server ends. It is archived as ended by the match
  start, with what had passed so far.
- From then on every press on that server is a **live press**, forwarded like any other. NodeCS
  never holds back a physical press, in or out of a test window. (Red team R12 and blind B1,
  settled by the owner.)
- **When a test may be started:** only while the panel would only *report* presses for that
  server's match. The rule comes from Phase 0 (§5.1); until then, **`WARMUP` only**.
- While a test window is open, the page shows a prominent "test window open on Server N"
  banner.
- Every test is archived, whether it passes, fails or ends at the match start.

**Who sits where.** A test compares the team the panel matched with **the team at the booth**,
from the rule in §5.10: an admin assignment, else TeamSpeak, else ask. (Blind B2, settled by the
owner.)

- **When a test starts,** the modal lists every booth's team and where it came from.
- **A booth with no team, or a TeamSpeak-only mismatch,** must be assigned in the modal first.
  The Assign control is right there.
- **The modal re-reads TeamSpeak** while it is open, so a late channel move shows up.

**Admin test (the "Go" button).** It opens a modal and runs two parts, recorded under one
`test_run_id` with the admin's Home Assistant user:

1. **Path check, with no bound IDs:**
   - **Key and round trip:** one press to an **unbound sentinel ID** (`nodecs-probe`, outcome
     `NONE`) proves the button key, the panel's press API and the round trip. Phase 0 checks
     what a sentinel press shows on the panel, such as a notification.
   - **Bindings:** read from `buttonBindings`, already part of the 1 s match read. Each booth
     ID must be bound, with the right action, to the team at that booth.
   - This takes about a second and never touches a match.
2. **Walk-round:**
   - **The walker:** before starting, the admin picks one from a dropdown of logged-in Unity
     users (piece 2), or "none".
   - **Each step:** while the window is open, every physical press on that server's booths is
     a step. It shows the booth, the gesture, when Home Assistant received it, the round trip,
     the team and action the panel matched, and the signal at that moment.
   - **The beep:** each press triggers `unity.direct_talk` to the walker, one short beep sent as
     soon as the press is received, so the walker hears the delay as they walk. The beep's
     send time is archived too.
   - **Controls:** the modal can repeat a step, fail it with a note, or export.
   - **Wrong team:** a step that lands on the wrong team turns red and names the team the panel
     matched.

**Coach test.** It is simpler, with one tile per team.

1. The admin starts it for a matchup.
2. Each coach is asked to **hold the button for 3 seconds**.
3. When the hold reaches the panel as `TEST` for the team at that booth, the coach PC plays
   **the beep** in the coach's headset (`coachpc.play_sound`, piece 4). Their tile turns green
   with the latency.
4. This is done **twice** per coach. On a wrong-team match the coach hears **no beep**. Their
   tile turns red and names the team the panel matched, so the admin sorts it out. (There is
   one sound only for now; see "Sounds" below.)

Without piece 4 the test still runs; the admin tells the coach.

**Sounds: the minimum for now.** The owner, 2026-10-28: "For now, on sounds we want the minimum,
and we can expand later. For now, we want a beep when a tac is registered. No words, just short
beep that a tac has been requested and sent."

- **One sound exists: a short beep. No words, and no other tones.**
- **In a live match:** the coach hears the beep in their headset when their **tac (hold)** is
  accepted by the panel (`EXECUTED`, meaning requested and sent; the pause may start later,
  §5.1).
- **Nothing else makes a sound for now:**
  - a tech pause (tap);
  - a failed press;
  - a pause actually starting.
  Failures go to the admin as alerts (§5.8), never into the coach's ear.
- **In the coach test:** the same beep marks a passed hold (above).
- **Later:** the coach PC app and integration keep a sound name in their API, so more sounds
  can be added without changing the contract.
- It can be switched off per event.

### 5.12 Security

- **The network:** the owner confirmed (2026-10-28) that Home Assistant, the panel and the
  coach PCs are on a **separate VLAN players cannot reach**. That is what the design relies on,
  and the README states it as a requirement.
- **Verify TLS with the event's own CA (defence in depth):** the config flow accepts a **CA
  certificate (PEM)** and builds a custom SSL context, so "Verify SSL certificate" can stay on
  with the event's CA. With the VLAN in place this is a nice-to-have, not a must. Unticking
  verification stays possible. (Red team R9.)
- **The button key** is its own config-entry field:
  - it is **optional:** after upgrading from v0.1, NodeCS keeps working read-only, and a repair
    issue asks for the key (blind B6);
  - it can be replaced from the options flow without reloading the entry or interrupting the
    press path;
  - it is never logged or put in events.
- **The admin login:** unchanged from v0.1.
- **The page:** roles as in §5.9 and §5.9.1, checked server-side on every command.
- **The archive** holds user names and panel IDs, but no keys.

### 5.13 Discord webhooks

The owner, 2026-10-28: "We want to add a discord channel, or two. One for tac pauses, and one for
all messages (logs, errors, etc) using discord webhooks. For all messages, allow selecting the
level of alert to display in it. If not provided, do not output webhooks."

**Configuration.** It lives in NodeCS's options flow, and every field is optional:

| Option | Default | Effect |
|---|---|---|
| Tac channel webhook URL | empty | Empty: nothing is ever posted for tacs. |
| All-messages webhook URL | empty | Empty: nothing is ever posted. |
| All-messages level | **off** | Off: nothing is posted, even with a URL. Otherwise one of `debug`, `info`, `warning`, `error`, `critical`; that level and above are posted. |

- **URLs are checked for shape** (`https://discord.com/api/webhooks/…` or `discordapp.com`). The
  options flow can send a **test message** to each.
- **The URLs are secrets:** anyone holding one can post. They are never logged, never put in
  events or the archive, and are redacted from diagnostics. Messages never carry keys, tokens or
  webhook URLs.

**The tac channel** gets one message per **tac (hold) press** on any linked booth, live or in a
test (tests are marked as such):

1. When the panel accepts it (`EXECUTED`): "TAC requested", with the server, the teams, the
   team calling it, the booth, the time, and the press latency. The message is posted with
   `?wait=true` so NodeCS keeps its id.
2. When the pause starts (§5.4 step 8): the same message is **edited**, adding "started at …,
   waited N s". One message tells the whole story of one tac.
3. A tac press that fails, or ends in `ERROR`: the message says so, with the reason. A tac
   attempt never disappears from the channel just because it failed. (Builder's call; the
   owner asked for "a channel for tac pauses".)

Tech pauses (taps) do not go to the tac channel. They go to the all-messages channel, as `info`.

**The all-messages channel** gets every archive record (§5.6) at or above the chosen level:

| Level | What it includes |
|---|---|
| `debug` | Everything: `press_sent`, reconciliation reads, duplicates dropped, config changes, push reconnects |
| `info` | Every press and its outcome, pauses started, tests started, passed and ended, team assignments |
| `warning` | Warning alerts, failed test steps, TeamSpeak-only mismatches, a slow press (over 500 ms) |
| `error` | Failed presses, `ERROR` outcomes, a refused button key, an archive write failure |
| `critical` | Critical alerts, and their clearing |

The mapping is a builder's call, kept in one table in the code. Each line is one short message,
with a timestamp and the level.

**Reliability:** Discord is outside the LAN and can be slow, rate-limited or unreachable, and
none of that may affect a press.

- **One background sender per webhook,** each with its own queue. The press path and the archive
  writer only enqueue and never wait.
- **Rate limits:** sending follows Discord's `429` `retry_after` and rate-limit headers. The
  all-messages channel batches bursts into one message, up to 10 lines or 1 s apart.
- **When Discord is unreachable:**
  - messages wait in their queues and go out later marked "delayed", with their original time;
  - the tac queue holds up to 200 messages and never drops a tac while it has room;
  - the all-messages queue holds 500 and drops the oldest first, posting "N messages dropped"
    once it can send again.
- **The archive stays the record.** Discord is a convenience view: a message that never reaches
  Discord is still in the archive.
- **Privacy:** team names, booth names and Home Assistant user names leave the venue LAN through
  Discord. The owner chooses this by entering a URL. The README says so.

The owner approved this section's content on 2026-10-28 ("looks good"), including failed and
test tacs in the tac channel, and the edit when the pause starts.

---

## 6. Piece 2 — Unity Intercom integration

### 6.1 What Unity Intercom exposes (researched 2026-10-28)

- **The server** is a macOS app. It answers `GET http://<server>:20101/userconfig` with the
  users and whether each is logged in, as used by Bitfocus Companion's
  `companion-module-audivero-unityintercom-server`. It has **no action API**; that module's
  help says so.
- **The desktop clients** (Mac and Windows) accept **Stream Deck control over UDP 20119**,
  including from another computer once that computer's IP is entered in the client. Bitfocus
  Companion's `companion-module-audivero-unityintercom-client` emulates a panel:
  - JSON messages `{"DeviceID": <32 hex>, "Type": "Keydown" | "Keyup" | "Rotate" | …,
    "Button": <n>}`;
  - an answer to the client's polls that carries protocol `Version` 1.4 and a layout version;
  - the client pushes each button's text and colour back to the panel.
- **The owner confirmed (2026-10-28)** that a Stream Deck button can be assigned to a direct
  talk to any specific user, and that Companion behaves the same.
- Mobile clients can be set to vibrate or beep on an incoming direct talk (owner, 2026-10-28).

### 6.2 Devices, entities, actions

- **Server device** (host, port 20101; polled every 5 s):
  - a binary sensor "answering";
  - a sensor "users logged in" (count);
  - one binary sensor per user, logged in;
  - a list attribute of logged-in users for the NodeCS dropdown.
- **Bot client device** (the client's IP; this integration acts as one emulated Stream Deck):
  - a binary sensor "connected" (the client polled within the last few seconds);
  - a sensor per configured button with its label;
  - a map of user → button, learned from the labels the client pushes. The owner can override
    it.
- **Actions:**
  - `unity.direct_talk` (target: bot device; `user`; `duration_ms`, default 150): presses the
    user's button, holds, releases.
  - `unity.press_button` (target: bot device; `button`; `hold_ms`): the same, by number.
  - Every press sends **Keyup twice**. A watchdog sends Keyup if a hold outlives its duration by
    1 s. A latched talk would leave the walker's line open.
  - Both actions fail loudly (a Home Assistant error) when the client is not connected or the
    user has no button.
  - **Direct-talk buttons only:** the user map ignores any button whose label is not a single
    user's direct talk, so a group or all-call talk can never be latched. (Red team R14.)
- **The control channel is open to the LAN:** the Unity client accepts UDP 20119 from the IP
  entered in its settings, so the bot PC's firewall must allow UDP 20119 only from Home
  Assistant's IP. This goes in the README. (Red team R14.)
- **Phase 0 verifies** what the client does when its controller vanishes mid-hold. If it keeps
  talking, the bot PC needs a local fallback that releases the talk.

### 6.3 The beep's sound

The bot client's microphone input is a **virtual audio cable fed with a constant tone** on the
bot PC (the owner's setup, done once). A 150 ms direct talk is then a 150 ms beep in the
walker's ear. The phone also vibrates or beeps on the incoming direct talk, per the walker's own
setting.

This needs no app on the bot PC. (Builder's call; the alternative is the coach PC app in "bridge"
mode playing a beep into the cable on demand.)

### 6.4 Open points

- Port the Companion client protocol only after checking that module's licence. If it is not
  compatible, reimplement from the observed behaviour.
- How long Unity takes from Keydown to the phone vibrating. It is measured in Phase 0 and shown
  on the page as a known offset.
- Whether one bot client accepts two controllers, for example Companion and Home Assistant at
  once. Plan for Home Assistant to be the only one.

---

## 7. Piece 3 — Coach PC app (Windows)

### 7.1 Rules: zero impact on TeamSpeak

1. **Never touch the TeamSpeak client:**
   - no plugin, no ClientQuery, no reading or writing its files;
   - no starting, stopping or restarting it;
   - no window automation.
2. **Audio in shared mode only:**
   - never take a device exclusively;
   - never change the default device, a device's volume or mute, or any device setting.
3. **Preloaded sounds:** for now **one short beep** (owner, 2026-10-28: "No words, just short
   beep"), held in memory as a WAV. The API takes a sound name so more can be added later.
   Playing one opens a shared-mode stream on the configured output device and closes it when
   done.
   - The app's audio session **opts out of Windows communications ducking**
     (`IAudioSessionControl2::SetDuckingPreference(TRUE)`, a per-session setting). Otherwise
     Windows would turn the beep down while TeamSpeak is in a call. It never changes the
     system-wide ducking setting, which would touch TeamSpeak. (Red team R15.)
4. **Event-driven, not polling, for audio devices:** device added or removed, state changes,
   and default-device changes come from Windows notifications.
5. **Light:**
   - below-normal process priority;
   - no busy loops;
   - a LAN API that answers in microseconds;
   - pings only to the TeamSpeak server and Home Assistant, a few per second at most.
6. **No self-updates, restarts or reconfiguration while running.** Updates are installed by
   hand between events.
7. **A crash or hang of the app must not affect anything else:** no hooks, no injected DLLs, no
   shared audio session tricks.

### 7.2 What it reports (`GET /status`)

- **The app:** version, uptime, process priority, last error.
- **Output device** (the configured headset, by Windows endpoint id and name):
  - present or absent;
  - default or not;
  - muted or not, and volume (read only);
  - the peak meter level (audio is flowing out).
- **Input device** (the headset mic, if any): present, muted, peak meter (the mic hears
  something). Levels only, never audio.
- **TeamSpeak process:** running or not; its CPU and memory; responding or hung, tested with
  `IsHungAppWindow` on its main window, which sends no messages to TeamSpeak's queue (never
  `SendMessageTimeout`). (Red team R15.)
- **Network:** the link up and its speed. Ping to the TeamSpeak server and to Home Assistant:
  RTT, jitter, loss over the last minute.
- **Clock:** the offset from NTP, or from Home Assistant if NTP is unreachable.
- **The PC:** CPU and memory use, uptime.

### 7.3 What it does

- `POST /sound` `{ "name": "beep", "volume": 0–100 }` (only `beep` for now): plays a preloaded
  sound into the configured output. It answers when playback has **started**, with the time
  from request to first sample.
- `GET /events` (Server-Sent Events): pushes status changes as they happen, for example
  "headset removed", so Home Assistant learns in milliseconds, not at its next poll.

### 7.4 Shape

- **Go**, following blinkybeacon-tray's pattern (the owner already maintains it).
- **Startup:** at login, in the same user session as TeamSpeak, with a tray icon visible over
  RustDesk. A service in session 0 cannot reliably play audio into the user's session.
- **Config:** a JSON file — the API token, bind address and port, the output and input device
  ids, the TeamSpeak server address, the sound volume.
- **The API:** binds the LAN address, and the installer firewalls the port to Home Assistant's
  IP (red team R15). Every request needs `Authorization: Bearer <token>`.
  `GET /status` may optionally be open for monitoring. A token-protected `/settings` page lets
  the owner pick the devices over RustDesk.
- **Logs:** a rolling local log, without the token.

### 7.5 Open points

- Whether the USB sound device reports a jack being unplugged, or only the whole USB device. If
  only the latter, the 3.5 mm cable check falls back to "no output signal while TeamSpeak is
  carrying voice", a heuristic, shown as a warning, never critical.
- Choosing the sound files and their loudness against TeamSpeak's level.

---

## 8. Piece 4 — Coach PC integration

- **Devices:** one per coach PC: host, port, token, and a name such as "Booth A1 left PC".
  - Reads `/status` every 5 s.
  - Listens to `/events` for immediate changes.
  - Unavailable after 10 s without either.
- **Entities:**
  - binary sensors: app answering, headset present, mic present, TeamSpeak running, TeamSpeak
    responding, output muted;
  - sensors: output peak, mic peak, ping RTT, jitter and loss to the TeamSpeak server, clock
    offset, CPU, uptime, app version.
- **Actions:**
  - `coachpc.play_sound` (target device; `sound`; optional `volume`). It fails loudly when the
    PC does not answer.
  - The response includes the measured start time, so NodeCS can archive when the coach heard
    it.
- **Health and alerts NodeCS raises from these, per booth:**
  - **critical:** headset absent, TeamSpeak not running or hung, PC not answering, or ping loss
    above 5 % over a minute;
  - **warning:** output muted, mic silent for 10 minutes while TeamSpeak is up, jitter above
    30 ms, or clock offset above 50 ms.
  - All thresholds are builder's calls.

---

## 9. Cross-piece contracts

- **NodeCS optional dependencies:** `unity_intercom` and `coachpc` (manifest
  `after_dependencies`). The page hides walker selection and coach beeps when they are absent.
- **What NodeCS calls:**
  - `unity.direct_talk` with `blocking=False` and a 1 s timeout;
  - `coachpc.play_sound` with `blocking=True` and a 1 s timeout during tests, so the start time
    can be archived;
  - `blocking=False` for live-press confirmations, so the press path never waits.
- **Events from §5.7** are the only thing automations need. The BlinkyBeacon admin alert is an
  automation on **`nodecs_button_received`** (the fastest event; red team R11), documented in the
  README, with distinct patterns for presses and critical alerts.

## 10. Prerequisites to verify (Phase 0)

Each needs the owner's go-ahead, because some are writes on staging. The build plan has the
method for each.

1. **The press endpoint:**
   - its response;
   - a repeated press, and a press during a running pause: does the panel queue a second
     timeout?
   - `NONE`, and what a **sentinel** (unbound) press shows on the panel;
   - the "report only" rule, phase by phase, including the knife round and restored matches;
   - whether press ids are ordered;
   - rate limits. (§5.1)
2. **The SNZB-01P on a real unit:**
   - that ZHA really emits `toggle` / `on` / `off` for it;
   - the tap delay after release;
   - whether the hold is sent at the threshold or on release;
   - its check-in interval, which sets the "heard from" thresholds;
   - duplicate frames, counted near and far. (§5.3, §5.8)
3. **Radio coverage:** a range survey of the booth positions, deciding where routers go. (§5.8)
4. **Clocks:** whether the panel's and Home Assistant's clocks are NTP-synced at the venue, and
   the measured offset. (§5.5)
5. **Home Assistant event-loop lag** on the event machine under normal load (recorder,
   dashboards), with a target under 50 ms.
6. **The Unity bot:**
   - Keydown → phone vibration delay;
   - that the constant-tone cable gives a clean beep;
   - that the client accepts Home Assistant as its panel;
   - what happens when the controller vanishes mid-hold. (§6)
7. **The coach PC:**
   - what the USB headset device reports on unplug;
   - peak meters readable without effect;
   - the ducking opt-out working;
   - an A/B test of TeamSpeak's own statistics with the app running. (§7)
8. **TeamSpeak via the panel:** `ts3Clients` nicknames, whether they are unique, and whether
   `teamATSChannel` / `teamBTSChannel` are set for every match. (§5.10)

## 11. Calls made without the owner

- **Duplicates:** the window is 1 s; repeats beyond it are queued, never dropped. A double press
  counts as a tap.
- **Retries:**
  - a request that provably never left is retried every 0.5 s for 10 s, with an alert at 2 s;
  - an ambiguous result is resolved by the panel's press ids, never by clocks.
- **Setup:** the press path is set up independently of the panel reads, and the press session
  has its own warm connector.
- **The path check** uses a sentinel ID and a read of the bindings, never a press to a bound ID.
- **Tests** may start only in `WARMUP` until Phase 0 settles the rule. Windows close on a phase
  change, and an open window shows a banner.
- **The archive:** append-only daily JSON Lines, with a hash chain that continues across days
  and a head hash in every export. Each press gets `press_sent` and `press_outcome`. Foreign
  presses are reconciled in. The recorder is not used.
- **Health:**
  - thresholds have hysteresis;
  - the "heard from" threshold comes from the measured check-in interval;
  - during live matches, only press-path alerts go to the beacon;
  - critical alerts fire for a dead press path, for a match going live without a passed coach
    test, and for a wrong-server binding.
- **Discord:** tac messages are edited when the pause starts, failed tacs are shown, and the
  level mapping, queue sizes and batching are as in §5.13. The all-messages level defaults to
  off.
- **Sounds** (decided by the owner, not a builder's call): a single short beep for an accepted
  tac and a passed coach-test hold; nothing else for now (§5.11).
- **The Unity integration:** the beep is a constant tone on the bot's input, with no app on the
  bot PC. Only direct-talk buttons are used, and UDP 20119 is firewalled to Home Assistant.
- **The coach PC app:**
  - written in Go, it starts at login with a tray icon and serves an SSE event stream;
  - it opts its own audio session out of ducking and tests TeamSpeak with `IsHungAppWindow`;
  - its API is firewalled to Home Assistant.
- **Security:** an optional CA certificate keeps TLS verification on. The button key is
  optional on upgrade and can be replaced without a reload.
- **The page** is one web component, served both as a sidebar panel and as a standalone page.
  - Roles: admin, read-only non-admin, and standalone viewer and operator.
  - The standalone page's security is as in §5.9.1: scrypt hashes, cookie sessions, a login
    limit, CSRF, strict headers, and the operator's name archived.
  - Where the mockups and this spec disagree, the spec wins.
- **Booths** store the server name beside its id and can be re-linked.

## 12. Open questions for the owner

Ranked by importance. Q1 and Q2 came from the red-team and blind checks.

1. ~~A press during an open test window, just as the match goes live.~~ **Answered,
   2026-10-28:** a test window ends when the match starts, for both tests; once live, a press
   is a press and is forwarded. A press may be queued by the server until the next possible
   moment (§5.1, §5.4 step 8, §5.11).
2. ~~Who decides which team sits at a booth, for the tests?~~ **Answered, 2026-10-28:**
   TeamSpeak first (it is sometimes updated late), then an admin override that **assigns** a
   booth's team directly. Later, an admin-timer integration adds a second confirmation of the
   channel (§4, §5.10).
3. ~~Names.~~ **Answered, 2026-10-28:** `unityintercom-hassio` (domain `unity_intercom`),
   `coachpc` (the Go app), `coachpc-hassio` (domain `coachpc`).
4. ~~Live-press headset sounds?~~ **Answered, 2026-10-28:** the minimum for now. One short beep,
   no words, when a tac is requested and sent; nothing else. It will be expanded later
   (§5.11).
5. ~~Page access.~~ **Answered, 2026-10-28:** admins do everything, and other Home Assistant
   users see the page read-only. There is also a password-protected standalone page outside
   Home Assistant's interface (§5.9.1).
6. ~~Retention.~~ **Answered, 2026-10-28:** never delete.
7. ~~Network.~~ **Answered, 2026-10-28:** a separate VLAN players cannot reach.

All questions are answered.

## 13. Review findings folded in

Two checks on 2026-10-28, both on Fable 5.1 at the owner's request, read-only:

- a **red team** (R), given the spec and the v0.1 code;
- a **blind builder check** (B), given only the documents.

| # | Finding | Severity | Disposition |
|---|---|---|---|
| R1 | The path check sends real presses to bound IDs and can pause a live match | Critical | **Changed:** sentinel ID plus a read of the bindings (§5.11) |
| R2 | A double tap (`on`) is ignored, so the press is lost | Critical | **Changed:** double press = tap (§5.3, §5.4) |
| R3 | The ambiguity check compares two clocks; v0.1 can't tell "never left" from "after send" | Critical | **Changed:** resolved by panel press id; separate timeouts and error types (§5.4) |
| R4 | In-flight suppression drops a legitimate repeat | High | **Changed:** queue, never drop (§5.4) |
| R5 | Retries give up at 2 s | High | **Changed:** 0.5 s retries for 10 s, alert at 2 s (§5.4) |
| R6 | Zigbee and ZHA outages are silent for up to 2 h; no routers; updates mid-event | High | **Changed:** an immediate press-path-alive alert, thresholds from the measured check-in, a coach-test-done alert, a router and no-updates note, a range survey (§5.8, §10) |
| R7 | The press path depends on the first panel read | High | **Changed:** the press path is set up independently (§5.4) |
| R8 | A cross-server misbinding pauses the wrong match | High | **Changed:** every match's bindings are checked against every booth (§5.8, §5.10) |
| R9 | The login and button key cross a shared LAN with TLS verification off | High | **Changed:** a CA PEM option; network separation recommended; §12 Q7 (§5.12) |
| R10 | Accountability gaps: a crash before the record, foreign presses, a daily chain, wall-clock deltas, no HA NTP API | Medium | **Changed:** `press_sent`/`press_outcome`, reconciliation, a cross-day chain with exported head hash, monotonic latency, no NTP assumption (§5.5, §5.6) |
| R11 | The lobby alert fires only after the outcome | Medium | **Changed:** `nodecs_button_received` at `t_zha` (§5.4, §5.7, §9) |
| R12 | A physical press in a test window after go-live | Medium | **The owner decided (2026-10-28):** test windows end when the match starts; live presses are forwarded (§5.11) |
| R13 | Alert fatigue | Medium | **Changed:** hysteresis, live-match mode, distinct beacon patterns (§5.8) |
| R14 | The Unity latch, and an open UDP control channel | Medium | **Changed:** direct-talk buttons only, firewall, a Phase 0 vanish test (§6.2) |
| R15 | Coach PC: ducking, the hung-window test, a plain-HTTP API | Low | **Changed:** a per-session ducking opt-out, `IsHungAppWindow`, firewall (§7) |
| R16 | The warm connection is only probabilistic | Low | **Changed:** a dedicated press connector, kept warm (§5.4) |
| B1 | Forward or drop a press during a test window after go-live | High | Same as R12: decided by the owner |
| B2 | No source of truth for the team at a booth during tests | High | **The owner decided (2026-10-28):** admin assignment wins, then TeamSpeak (may lag), with the admin timer as a future second check (§5.10) |
| B3 | Panel clock sync matters to the ambiguity check | High | **Changed:** id-based, clock-free (§5.4); clocks measured in Phase 0 |
| B4 | The status of the mockups | Medium | **Changed:** committed and sanitised; the spec wins (§5.9) |
| B5 | Panel server ids may not survive between events | Medium | **Changed:** names stored beside ids; booth re-linking (§5.2) |
| B6 | Upgrading v0.1 without the button key | Low | **Changed:** the key is optional, with a repair issue (§5.12) |

**Assumptions the red team rated most likely wrong.** Each is now a Phase 0 item (§10):

- the panel ignores a second press during a running pause;
- "report only" covers exactly WARMUP;
- the hold is sent at the threshold;
- ZHA emits the expected commands for the 01P;
- one coordinator covers every booth without routers;
- TeamSpeak nicknames are unique and the team channels are set per match;
- Home Assistant's event loop stays fast under load;
- the clocks agree.
