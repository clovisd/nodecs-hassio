# Timeout button system — build plan

**Spec:** `docs/superpowers/specs/2026-10-28-button-system-design.md` (read it first, then §13
for the review findings).
**Status:** not started. This is the roadmap across sessions. Each phase gets its own detailed,
test-first implementation plan (superpowers:writing-plans) at the start of that phase, in the
repo it changes.

## How to run each phase

1. Re-read the spec sections for the phase and its §13 findings.
2. Settle the phase's open questions with the owner (spec §12) before planning.
3. Write the phase plan with superpowers:writing-plans:
   `docs/superpowers/plans/YYYY-MM-DD-<phase>.md` in the repo the phase changes.
4. Execute it with superpowers:executing-plans (inline) or subagent-driven-development. The
   owner chose inline for v0.1.
5. Final review. The owner asked for red-team and blind checks on Fable 5.1 for designs. Ask
   whether the same applies to code reviews.
6. Ship only with the owner's go-ahead: merge, push, CI green, tag, release.

Standing rules for every phase:

- No product, event, host or real-team names in any public repo or its history. Scan the full
  history before every push, with the pattern list kept outside the repo (see `docs/HANDOFF.md`).
- Nothing writes to the panel without the owner's explicit approval for that kind of write.
  Use staging, never production.
- Credentials come from the owner during the session. They are never stored in repos, memory
  or logs.
- Coach PCs: nothing may touch TeamSpeak (spec §7.1).

---

## Phase 0 — Verify the unknowns (no product code)

**Goal:** replace the spec's assumptions with measurements (spec §10). Each item needs the
owner's OK, because some are writes on staging. **Settle spec §12 Q2 with the owner first:**
it changes Phase 2. (Q1 was answered on 2026-10-28.)

| # | What | How | Decides |
|---|---|---|---|
| 0.1 | Press endpoint behaviour | Against **staging**, with a spare button ID bound in a WARMUP match: press once; press twice within 1 s; press during a running pause, and while a pause is requested but not yet started (does a second timeout queue?); find how long a tactical and a technical request wait before the pause starts, and whether a pending request is visible in the API; press an unbound **sentinel** ID and note what the panel UI shows (notification? sound?). Record status codes, bodies, `buttonPresses` rows and outcomes, and **whether press ids are ordered**. | §5.4 classification and the id-based ambiguity check; §5.11 sentinel path check |
| 0.2 | "Report only" rule | The owner steps a test match through every phase, **including the knife round and a restored match**, and a test ID is pressed in each | §5.11 when tests may start |
| 0.3 | SNZB-01P timing | Confirm ZHA emits `toggle`/`on`/`off`. Log `zha_event` `time_fired` while timing taps and holds on 240 fps video, ten of each. Leave a button idle for a day and log its check-ins. | §5.3; hold at threshold or on release; §5.8 "heard from" thresholds |
| 0.4 | Duplicates and range | Press 200 times near and far from the coordinator; count duplicate `zha_event`s and their spacing. Run a range survey of the booth positions. | The 1 s window; router placement |
| 0.5 | Clocks and loop lag | Measure the panel-vs-HA clock offset (HTTP `Date` against NTP on both), and HA event-loop lag on the event machine under normal load | §5.5 cross-clock display; Phase 1's latency acceptance |
| 0.6 | Unity bot | Set up the bot client, virtual cable and tone. Drive Keydown/Keyup from a script; measure Keydown → phone vibration on video. **Kill the controller mid-hold** and see whether the talk stays latched. | §6.2, §6.3, the known offset |
| 0.7 | Coach PC audio | On one coach PC: list endpoints; unplug the USB extension and the 3.5 mm jack separately and record what Windows reports; read peak meters; check the ducking opt-out; A/B TeamSpeak's own stats with a prototype reading meters | §7.1, §7.2, §7.5 |
| 0.8 | TeamSpeak view | Read `ts3Clients` on staging (read-only): coach PC nicknames, uniqueness, and whether `teamATSChannel`/`teamBTSChannel` are set for every match | §5.10, the §12 Q2 default |

**Done when** each row has a recorded result in `docs/verification/YYYY-MM-DD-phase0.md` and the
spec is updated where results differ.

## Phase 1 — NodeCS v0.2a: the button path, archive and events

**Repo:** nodecs-hassio. **Spec:** §5.1–§5.8, §5.12.

- **Setup that can't strand the press path:** the press path (ZHA listener, press client,
  archive writer) is set up **before and independently of** the coordinators. The coordinators
  retry on their own instead of raising `ConfigEntryNotReady`.
- **The button key:** an optional config-flow step for it, a repair issue while it is missing,
  and replacement from the options flow without a reload.
- **A CA certificate option (PEM)** with a custom SSL context, so TLS verification can stay on.
- **The booth store** (§5.2, with the server name and re-linking), editable through a WebSocket
  command, so tests can drive it. The page comes in Phase 2.
- **The press path** (§5.4):
  - `nodecs_button_received` at `t_zha`;
  - the mapping, with double press = tap;
  - duplicates dropped within 1 s, queued beyond;
  - a dedicated warm press connector with separate connect and total timeouts and distinct
    error types;
  - retries for 10 s, with an alert at 2 s;
  - the id-based ambiguity check, seeded at startup;
  - the outcome read and refresh;
  - linking each `EXECUTED` press to the pause it started (`pause_started`,
    `nodecs_pause_started`), with "requested, waiting" shown in the meantime.
- **Latency** on the monotonic clock (§5.5).
- **The archive** (§5.6): `press_sent` and `press_outcome`, reconciliation of foreign presses,
  the cross-day hash chain with head hash, and export.
- **Events** (§5.7).
- **Health checks and alerts** that need only the panel, ZHA and SMLIGHT (§5.8):
  - press path alive;
  - every-match binding check (without TeamSpeak);
  - hysteresis;
  - live-match mode.

**Acceptance:**

- Every §5.4 branch has a test, including:
  - Home Assistant restarting with a press in flight;
  - the panel down at boot (presses are still sent once it answers, within 10 s);
  - the ambiguous-timeout path resolved both ways;
  - a 5 s re-tap being queued, not dropped.
- In tests, the time from `zha_event` to the press request is under 10 ms, with no await on a
  read, the archive or an outcome in between.
- A forced archive write failure alerts without delaying a send.
- The chain verifies across two days.
- Leak scan clean; CI green.

## Phase 2 — NodeCS v0.2b: the readiness page and tests

**Repo:** nodecs-hassio. **Spec:** §5.9–§5.11. The mockups are in `docs/design/mockups/`;
where they differ from the spec, the spec wins.

- The sidebar panel (a web component served by the integration, admin only) and the WebSocket
  API.
- Booth editing.
- **The admin test:**
  - the path check uses the **sentinel ID and the bindings read, never a bound ID**;
  - the walk-round runs without a walker yet;
  - the team at each booth comes from the §12 Q2 answer.
- The coach test, without beeps.
- **Test windows end when the match starts**, for both tests (the owner's rule). There is a
  "test window open" banner while one is open.
- Archive browsing, export and the head-hash display.
- The binding check with TeamSpeak (`ts3Clients`, read-only).

**Acceptance:**

- Tests start only in WARMUP, or under the Phase 0 rule.
- A phase change mid-test closes the window, and physical presses keep being forwarded.
- No code path sends a press to a bound ID except a physical press.
- Every test step is archived with the user who ran it.
- The page works on a phone-width screen.

## Phase 3 — Unity Intercom integration

**New repo** (name from spec §12). **Spec:** §6.

- The server device and its users.
- The emulated Stream Deck for the bot client: poll handshake, labels → user map, Keydown/Keyup,
  double Keyup, watchdog.
- `unity.direct_talk` and `unity.press_button`.
- Wiring into NodeCS: the walker dropdown and a beep per walk-round press.

**Acceptance:** against the owner's real Unity setup, a direct talk beep reaches a chosen phone.
A dropped Keyup is recovered by the watchdog. The page shows the walker's beep send time.

## Phase 4 — Coach PC app

**New repo** (Go, Windows). **Spec:** §7.

- `/status`, `/sound`, `/events`.
- The settings page.
- The device notifications.
- The pings.
- The clock check.
- The tray app.
- A start-at-login installer.

**Acceptance:** on a real coach PC with TeamSpeak in a call, an A/B run shows no change in
TeamSpeak's packet loss, latency or CPU. Pulling the headset is reported in under 1 s. A sound
starts in under 50 ms of the request.

## Phase 5 — Coach PC integration and wiring

**New repo. Spec:** §8, §9.

- The devices, entities, `coachpc.play_sound`, and the alerts in NodeCS.
- Coach test beeps (hold 3 s, twice).
- Live-press confirmations, if the owner wants them (spec §12).

**Acceptance:** a full dry run on staging with two booths. The admin test runs with the walker
hearing beeps. The coach test passes with headset beeps. A pulled headset raises a critical
alert. The archive holds the whole run, with an intact chain.

## Dependencies

```
Phase 0 ──▶ Phase 1 ──▶ Phase 2 ──┬──▶ Phase 3 (walker beeps on the page)
                                  └──▶ Phase 4 ──▶ Phase 5 (coach beeps, booth health)
```

Phases 3 and 4 can run in parallel once Phase 2 is in.
