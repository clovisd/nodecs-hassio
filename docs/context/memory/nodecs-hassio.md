---
name: nodecs-hassio
description: "Read-only HA integration for the CS2 LAN-event server panel (~/nodecs-hassio, clovisd/nodecs-hassio — private since 2026-10-28, domain nodecs); step 2 of the CS timeout-button system"
metadata:
  node_type: memory
  type: project
  originSessionId: 29e05096-c70e-4698-882a-6659bdb8d1d1
  modified: 2026-10-27T22:54:31.397Z
---

Shipped v0.1.0 on 2026-10-27 at `~/nodecs-hassio` → `clovisd/nodecs-hassio` (was public/HACS; the owner made it **private** on 2026-10-28, so HACS can't install it now).
Each game server on the panel is a device (status, phase, map, teams, scores, timeouts, ready
flags, running pause + who called it, button bindings, logos as image entities); a panel
device has a "Live updates" connectivity sensor.

**Why:** the owner's CS2 events run on an internal panel; the end goal is Zigbee buttons →
tac/tech pause for a team ([[blinkybeacon-hassio]] was step 1). This step is read-only.

**How to apply:**
- 2026-10-28 the owner moved everything to the (private) GitHub repo, real names included
  (`docs/context/` holds the transcript, memory snapshot, exploration, names and hosts). Rule now:
  names allowed while private, scrub history with `docs/context/leak-patterns.txt` before ever
  going public; credentials are never committed (owner passes them to each session).
- Owner's priority (2026-10-27): "lowest latency possible, and highest reliability". Design:
  push WebSocket triggers immediate reads, 1 s backstop poll, status every 10 s (it makes the
  panel probe game servers), 6 s grace against flapping.
- Panel API: GraphQL `POST /api/ui/graphql/query` (nginx Basic Auth, the admin login is the only
  account); push `wss://…/api/ui/notifications/subscribe` (`match_updated`, `notification`);
  button presses `POST /api/buttons/{buttonID}/press` with `Authorization: Bearer <button key>`
  (the next step). Certificates are untrusted → Verify SSL off. No GraphQL subscriptions.
- Test against the owner's **staging** panel (stage.tourney.esportal.xyz), not production
  (panel.tourney.local, LAN). Read-only unless asked; credentials come from the owner, never
  stored in memory or the repo.
- `.venv` was cloned from blinkybeacon-hassio's (same pins); pip resolving HA from scratch is
  very slow here.
- 2026-10-28: the **timeout button system** (NodeCS v0.2 button path + readiness page, a Unity
  Intercom integration, a coach-PC Windows app, a coach-PC integration) is designed, not built.
  Start any continuation from `~/nodecs-hassio/docs/HANDOFF.md` (on `main`, private repo; all
  design questions answered); Phase 0 (verify unknowns with the owner) comes first. The owner
  wants red-team + blind checks on Fable 5.1 for designs, re-run after each round of owner
  answers. Spec §14 lists future features that could change decisions.
- Name list for the pre-public scrub: `docs/context/leak-patterns.txt` in the repo (credential
  patterns kept only locally in `~/.config/nodecs/leak-patterns.txt`).
