# Round 1 red team — timeout button system design

**Date:** 2026-10-28 · **Model:** Fable 5.1 · **Mode:** read-only. The reviewer had the spec, the
v0.1 spec and the v0.1 code. **Reviewed version:** the first draft of
`docs/superpowers/specs/2026-10-28-button-system-design.md` (commit `bbd099c`, before §13 was
filled).
**What happened to each finding:** spec §13, the R1–R16 rows.

The report follows as delivered. Section references point at the first draft.

---

## Findings, most severe first

**1. Critical — The admin path check can pause a live match (§5.11).**

- **Problem:** it sends real presses to *bound* IDs of both booths. The phase re-read is about
  150 ms stale.
- **Failure:** a second admin clicks go-live, or the panel's "report only" rule covers fewer
  phases than assumed (the knife round?). Up to four synthetic presses then become `EXECUTED`
  tac and tech pauses at the knife round, burning a team's timeout.
- **Mitigation:** never press a bound ID synthetically.
  - Prove the key and round trip with an unbound sentinel ID (`nodecs-probe`, outcome `NONE`).
  - Prove the bindings by reading `buttonBindings`, already in the 1 s read.
  - Keep only the physical walk-round and the coach test.

**2. Critical — A double tap loses the tech pause (§5.3, §5.4 step 1).**

- **Problem:** a coach with no feedback and a 0.6 s tap delay will tap twice. The SNZB-01P then
  sends `on` (double press), which the design "logs and ignores".
- **Failure:** the press is lost, silently from the coach's point of view.
- **Mitigation:** map `on` to `tap_id` as well, since double press is otherwise unused.

**3. Critical — The ambiguity resolver compares two clocks (§5.4 step 4).**

- **Problem:** "a press newer than the send time" compares the panel's `pressedAt` with Home
  Assistant's clock.
- **Failure:**
  - panel clock 1 s behind: a delivered press looks old, so NodeCS resends, causing a double
    pause;
  - panel clock ahead: the previous press looks new, so a lost press is called delivered.
- **Mitigation:** compare panel press `id`s against those NodeCS already archived for that
  button, which needs no clock. Record the newest id before sending.
- **Also:** v0.1's `_query` wraps everything in `asyncio.timeout` and collapses "failed to
  connect" and "failed after sending" into one `NodeCSConnectionError`. The press client needs
  `aiohttp.ClientTimeout(sock_connect=1, total=3)` and distinct exception classes, or "provably
  never left" is a fiction.

**4. High — In-flight suppression drops a legitimate repeat (§5.4 step 3).**

- **Problem:** the ambiguity path can take about 10 s: a 3 s timeout, 2 s of retries, 2 s of log
  waits, and a resend.
- **Failure:** a coach who re-taps at 4 s is silently not sent.
- **Mitigation:** queue, never drop, and archive the repeat either way.

**5. High — Giving up at 2 s loses a press that was still useful (§5.4 step 4).**

- **Problem:** three retries in 2 s, or one resend after a `5xx`, then "failed". A panel backend
  restart lasts longer, and a tac pause 5 s late beats none.
- **Mitigation:** keep retrying at a 0.5 s cadence for about 10 s, alerting at 2 s. Still resolve
  ambiguity by id.

**6. High — Zigbee and ZHA outages are silent for 30 minutes to 2 hours (§5.8).**

- **Problem:** in these cases no `zha_event` fires, and nothing alerts until "button heard from"
  trips:
  - a ZHA reload (an SMLIGHT Ethernet blip, a DHCP renewal, an admin clicking the coordinator
    firmware update in Home Assistant, ZHA auto-reloading on socket loss);
  - a Home Assistant restart;
  - an integration reload after the config-flow key step.
- **Thresholds:** SNZB-01P battery reports are roughly hourly, so 30 minutes warns on healthy
  buttons (alert fatigue) and 2 hours misses a dead one for three matches.
- **Range:** no routers are mentioned, and booths at 2.4 GHz esports distances will be marginal.
- **Mitigation:**
  - alert critically when ZHA is not loaded, the coordinator link is down, or NodeCS has no bus
    subscription;
  - require a passed coach test per match: critical when a match leaves `WARMUP` without one;
  - add mains-powered routers;
  - forbid updates during events.

**7. High — The press path is hostage to the first match read (`__init__.py:40`).**

- **Problem:** if `async_config_entry_first_refresh` raises `ConfigEntryNotReady`, the whole
  entry stays unloaded, press path included.
- **Failure:** after a Home Assistant boot while the panel blips, buttons are dead for 80 s or
  more of retry backoff.
- **Mitigation:** set up the ZHA subscription and press client before, and independently of,
  the coordinators.

**8. High — A cross-server misbinding executes on the wrong match (§5.10).**

- **Problem:** a booth ID bound in another server's match is not detected, because the check
  compares only the booth's own server.
- **Failure:** the press pauses the other match.
- **Mitigation:** check every match's bindings for every booth ID. Critical if an ID is bound on
  a server other than `booth.server_id`.

**9. High — The button key and admin login cross a shared LAN with TLS verification off (§5.12,
v0.1 §7).**

- **Problem:** the event's CA is untrusted, so the owner unticks verification.
- **Failure:** ARP spoofing on the player LAN captures the Basic login (full panel control,
  RCON) and the button key (pause any match, from anywhere, replayable).
- **Mitigation:**
  - accept a CA PEM in the config flow (a custom `ssl_context`), or put Home Assistant and the
    panel on a VLAN away from players;
  - rotate the key without reloading the entry.

**10. Medium — Accountability gaps (§5.6).**

- **(a)** The archive record is written after up to 2 s of outcome polling, so a Home Assistant
  crash in between loses the fact of sending. Write `press_sent` at `t_sent` and
  `press_outcome` later.
- **(b)** Presses the panel saw but NodeCS did not send (a leaked key, a curl) are invisible.
  Reconcile `buttonPresses` into the archive as `foreign_press`.
- **(c)** The hash chain restarts daily, and anyone with file access can rewrite it. Chain
  across days and publish the head hash off-box.
- **(d)** Wall-clock deltas go negative on an NTP step. Use monotonic time for latencies.
- **(e)** "Home Assistant's own NTP status" has no Core API; this is unverified.

**11. Medium — The lobby alert fires late (§5.7).**

- **Problem:** `nodecs_button_press` fires only after step 6, so the beacon spins 0.3–2.5 s
  after the press.
- **Mitigation:** fire an immediate `nodecs_button_pressed` at `t_zha`, and the outcome event
  later.

**12. Medium — Physical test presses after a phase change (§5.11).**

- **Problem:** a real press cannot be gated.
- **Failure:** if the match goes live during a coach test, the coach's 3 s hold is a live tac
  pause.
- **Mitigation:** decide this explicitly. One option: during an open test window, hold and flag
  a press when the phase is no longer `WARMUP`, and auto-close the window.

**13. Medium — Alert fatigue (§5.8, §8).**

- **Problem:**
  - noisy rules: ping loss over 5 % is critical, "mic silent 10 minutes", "button unheard
    30 minutes";
  - flapping around thresholds, with no hysteresis;
  - the beacon flashing for both presses and health alerts.
- **Mitigation:** hysteresis and minimum durations, distinct beacon patterns, and a "match
  live" mode that shows only press-path alerts.

**14. Medium — The Unity latch, and an open control channel (§6.2).**

- **Problem:** what happens is unknown when Home Assistant dies between Keydown and Keyup, or
  when the emulated panel stops polling.
- **Failure:** with the constant-tone cable, a latched talk floods the walker, or everyone if the
  key is a group talk.
- **Problem:** UDP 20119 is allowlisted by IP only, so any LAN host can drive the bot.
- **Mitigation:**
  - a Phase 0 "controller vanishes mid-hold" test;
  - a Windows firewall rule allowing only Home Assistant's IP;
  - direct talk only.

**15. Low — Coach PC audio.**

- **Ducking:** TeamSpeak is a communications session, so Windows will duck the app's beep
  (making it inaudible), not the other way round. Set "do nothing", or opt the session out.
- **Hung test:** a `SendMessageTimeout`-based test posts to TeamSpeak's message queue; use
  `IsHungAppWindow` instead.
- **API:** the coach API is a plain-HTTP bearer API; firewall it to Home Assistant's IP.

**16. Low — The warm connection is only probabilistic.**

- **Problem:** the 1 s poll occupies the pooled connection about 15 % of the time, so a press
  then pays a TLS handshake. nginx also recycles connections after `keepalive_requests`.
- **Mitigation:** consider a dedicated two-connection connector for presses.

## Assumptions most likely wrong

1. The panel ignores a second press of the same ID during a running pause. It may queue a second
   timeout.
2. "Report only" covers exactly `WARMUP`. The knife round and restored matches are unknown.
3. The SNZB-01P sends `off` at the threshold, not on release. Otherwise 10 s holds.
4. ZHA fires `zha_event` for the 01P's `toggle` / `on` / `off` as assumed (quirk coverage).
5. A single coordinator with no routers reaches every booth through an event crowd.
6. `ts3Clients` nicknames are unique and untouched by coaches, and `teamXTSChannel` is set per
   match.
7. Home Assistant's event loop stays under 50 ms on the event box under recorder and template
   load.
8. The panel's and Home Assistant's clocks agree (no NTP at the venue).

## Three changes I would insist on before building

1. **No synthetic presses to bound IDs.** The path check becomes a sentinel ID plus a read of
   `buttonBindings`. (Findings 1, 12.)
2. **NodeCS never drops a press:**
   - `on` maps to tap;
   - repeats are queued, not suppressed;
   - retries continue for about 10 s;
   - ambiguity is resolved by panel press id, not timestamps;
   - the press path is set up independently of the first read. (Findings 2–5, 7.)
3. **Liveness and proof per match:**
   - a critical alert when ZHA, NodeCS or the coordinator is not live;
   - a match may not leave `WARMUP` without a passed coach test;
   - `press_sent` archived at `t_sent`;
   - the panel's press log reconciled into the archive. (Findings 6, 10.)
