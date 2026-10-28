# Round 2 red team: timeout button system design

**Date:** 2026-10-28 · **Model:** Fable 5.1 · **Mode:** read-only; the reviewer had the spec, the
build plan, the v0.1 spec and the v0.1 code.
**Reviewed version:** the spec and plan after the owner's answers to Q1–Q7 (commit `9d76a85`).
**What happened to each finding:** spec §13.2, the 2.1–2.15 rows.

The report follows as delivered. Section references point at that version.

---

## Findings, most severe first

**1. Critical: changing an option reloads the entry and opens a gap where presses are lost
(§5.9.1, §5.12, §5.13; plan Phase 1).**

- Passwords, Discord URLs and level, and the button key all live in one options flow. The spec
  promises "no reload" only for the key.
- Home Assistant's default options-update listener reloads the entry. The reload tears down the
  `zha_event` subscription and the warm connector for about 1–3 s.
- A `zha_event` fired in that gap has no listener and is gone; the bus does not queue.
- Scenario: the owner fixes a webhook URL during a live map, and a coach holds. Nothing reaches
  the panel, and nothing is archived.

Mitigation:

- One rule in §5.12: *NodeCS never reloads itself on options changes; every option applies in
  place.*
- A Phase 1 acceptance test: "an options update with a press in flight loses nothing".
- Reauth and reconfigure, which do reload, must warn when any server is live.

**2. High: the sentinel ID can be bound, which brings back R1 (§5.11).**

- `nodecs-probe` registers on the panel at its first press, and the panel's Buttons dialog
  invites binding "an unbound button you just pressed".
- One mis-click binds it to a team. The next admin test's path check then sends a real press to
  a bound ID.
- In WARMUP that press is `TEST`. Under the unverified report-only rule (knife round, restored
  match), it executes.

Mitigation:

- Before every sentinel press, read `buttonBindings` for every server's current match. Refuse,
  with a critical alert, if the sentinel is bound anywhere.
- Name it `zz-nodecs-probe-do-not-bind`.
- Record it, so reconciliation doesn't flag it as foreign.

**3. High: scrypt on the event loop delays presses (§5.9.1).**

- The press path runs on Home Assistant's loop. Its 10 ms target is lost if a login hashes there
  (about 50–150 ms per scrypt).
- The 5-per-minute limit is per IP. Any laptop on the VLAN can rotate IPv6 temporary addresses
  for free, and a lobby screen that auto-refreshes a stale login page re-submits.

Mitigation:

- Throttle *before* hashing.
- Hash in the executor, with a concurrency cap of 1.
- Add a global per-role backoff on top of the per-IP limit.
- Forbid any CPU-bound work on the loop: archive hashing and fsync, SSE serialisation. The spec
  says this for the archive writer, but not for the page.

**4. High: stored XSS in the "who you are" field reaches Home Assistant's origin (§5.9.1).**

- The free-text name is archived and rendered in the press log, the test steps and the alerts.
  It shows on both the standalone page and the Home Assistant sidebar panel, which share Home
  Assistant's origin.
- Home Assistant's frontend keeps the refresh token in `localStorage` on that origin.
- A `<script>` or `onerror` payload typed at the lobby screen runs when the lobby admin opens the
  panel, and steals an admin token.
- "CSP limited to own assets" only helps if it is `script-src 'self'` with no `'unsafe-inline'`,
  and the component uses no inline handlers.

Mitigation:

- Restrict names to `[A-Za-z0-9 _-]{1,32}`.
- Escape every free string: names, team names, booth names, `detail`.
- Put a fixed CSP string in the spec.
- Add a Phase 2 acceptance test with a hostile name.

**5. High: an unseeded id-check gives a false "delivered" (§5.4 step 5, against R7).**

- Seeding "at startup" fails when the panel is down at boot, which is now explicitly survivable.
- On the first press with an ambiguous answer, every id in `buttonPresses` is "unseen",
  yesterday's included. NodeCS declares the press delivered and stops: a missed press.

Mitigation:

- Persist the newest id per panel ID in the Store, across restarts.
- Seed opportunistically on the first successful panel read.
- Treat "unseeded" as a distinct state, shown on the status strip.
- Use the press response body's id, if Phase 0 finds one.

**6. High: `429` and `408` fall under "other 4xx: no retry" (§5.4).**

- Phase 0 lists rate limits as unknown, yet the classifier drops a rate-limited press for good.
- DNS: with the venue's resolver quirks, a DNS stall is bounded only by `total=3`, so "every
  0.5 s" becomes "every 3 s".

Mitigation:

- `429` and `408` join the "never executed" retry class, honouring `Retry-After`.
- Pin the resolved IP for the press connector, re-resolving in the background, or allow an IP in
  the config.

**7. Medium: the page outruns the VLAN assumption, and the lockout is a denial of service
(§5.9.1).**

- A `requires_auth=False` view is served everywhere Home Assistant is: Nabu Casa remote, a port
  forward, Tailscale.
- Behind a reverse proxy without `trusted_proxies`, every client shares one IP. Five wrong tries
  by anyone lock the lobby screen and staff laptops out for 5 minutes, right when an operator
  must assign a team.

Mitigation:

- LAN-only by default (`is_local(request.remote)`), and never parse `X-Forwarded-For` yourself.
- An opt-in CIDR allow-list.
- Refuse to enable while Cloud remote is on, unless explicitly overridden.
- Lockouts never touch existing sessions.
- Never call `process_wrong_login`, since an IP ban of the lobby desk is worse, and say so in the
  spec.

**8. Medium: an admin assignment silences TeamSpeak, giving a wrong "pass" (§5.10).**

- Rule 1 makes TeamSpeak irrelevant once a team is assigned.
- An admin who misreads the seating assigns Booth L = team A *and* binds L to A. The check
  compares two copies of the same mistake and passes. TeamSpeak, the only independent source,
  disagrees and is ignored.

Mitigation:

- When an assignment exists and TeamSpeak disagrees, show the warning "assignment contradicts
  TeamSpeak", and name it in the test modal.
- Two clients with one nickname yield "unknown", never the first match.

**9. Medium: a wrong action is not checked (§5.8, §5.10).**

- A `tap_id` bound to `TAC_PAUSE` on the right team passes every listed severity. A tech-pause
  tap then burns a tac.
- §5.11 mentions "right action" for the path check only.

Mitigation: an action mismatch, and both of a booth's IDs bound to the same action, are critical
in the binding check.

**10. Medium: the go-live instant is the noisiest moment, and §5.8 contradicts itself.**

- §5.8 says "critical alerts raise a persistent notification", and also "while any match is live
  only press-path alerts go to notifications".
- At the WARMUP exit, "coach test not done" and "TS mismatch now critical" fire together.

Mitigation:

- State one rule: non-press-path criticals are page-only while live.
- Fold the two go-live checks into one page notice, "went live with: …".
- Add `test_window: bool` to `nodecs_button_received`. Otherwise the beacon spins the same way for
  a walk-round press on Server 1 and a live tac on Server 2.

**11. Medium: coach-test holds during the phase lag (§5.11, §5.4 step 8).**

- NodeCS learns the phase up to 1 s late. A hold in that second executes and returns `EXECUTED`,
  not `TEST`, so there is no beep.
- The coach then holds again, and a second tac is queued (R4 says never drop).
- The pause link ("first new pause by that team of that kind") binds an admin-called tactical
  pause to a pending press.

Mitigation:

- An `EXECUTED` outcome during an open window closes it at once, and beeps (team matched).
- The modal says "do not go live until this closes", and flashes "LIVE — stop" on the phase
  change.
- Phase 0.1 must answer what a second request does while one is pending, since that decides
  whether R4's queueing can burn two timeouts.
- Mark pause links as "probable".

**12. Medium: releasing a hold may emit `toggle` (§5.3; Phase 0.3).**

- If the 01P sends `off` at the threshold and `toggle` on release, every tac is followed by a
  tech pause, which stops play immediately.
- The 1 s duplicate window is per gesture, so it does not catch this.

Mitigation: Phase 0.3 tests the release explicitly. If it happens, suppress a `toggle` within 1 s
after an `off` from the same button.

**13. Medium: Discord (§5.13).**

- **(a)** Both options set to the same URL: two senders share one Discord bucket and fight, and
  tacs queue behind log spam. Detect this and share one sender, with tac priority.
- **(b)** A walk-round posts 20 test tacs in a minute. The webhook's limit of about 30 per minute
  delays a real tac's message. Route test tacs to all-messages, or give live tacs queue
  priority.
- **(c)** Queues and pending message ids are in memory, so a restart loses edits and up to 200
  tacs. Persist the ids with the press record, and post a "restarted" note.
- **(d)** "TAC requested" is competitive information until the pause starts. The README must say
  the tac channel is admin-only.
- **(e)** `debug` and `warning` records carry IPs, IEEE addresses and failed-login names off
  site. Redact them in the Discord formatter.
- **(f)** Use a separate `ClientSession`, with its own connector and timeout.

**14. Low: session hygiene (§5.9.1).**

- There is no logout endpoint, although logouts are archived.
- 12-hour operator sessions on a public lobby screen mean anyone can stop a test or assign a team.
  Add an idle timeout, and re-prompt for operator actions.
- Issue a fresh token on every login, against session fixation.
- Set the cookie `Path=/nodecs/board`.
- Send `X-Accel-Buffering: no` for SSE through nginx.
- Cap the number of SSE clients per session.
- Home Assistant's `IndexView` captures `/nodecs/board/` if the sidebar panel's
  `frontend_url_path` is `nodecs`. Use a different path.

**15. Low: R16's keep-alive is unspecified.** "A tiny authenticated request every 5 s" must be a
cheap GET with Basic auth on the press connector, never the press endpoint.

## §13 consistency

- R1, R2, R4, R5, R8, R9, R11, R12, B5 and B6 are reflected consistently.
- R3 and R7 interact badly (finding 5).
- R13 leaves the contradiction in finding 10.
- R6's "coach test done" critical conflicts with live-match mode.
- Plan Phase 1 omits in-place options (finding 1).
- Phase 2 omits logout, the CSP text, executor hashing and LAN-only (findings 3, 4, 7, 14).

## Insist on before building

1. In-place options, with "never reload mid-event", tested with a press in flight (finding 1).
2. A sentinel-bound guard before every path check (finding 2).
3. A login throttle before hashing, hashing off the loop, a LAN-only default, and no
   `process_wrong_login` (findings 3, 7).
4. A persisted press-id seed, plus `429` and `408` in the retry class (findings 5, 6).
5. Escaped free text, with a fixed CSP and a hostile-name acceptance test (finding 4).
