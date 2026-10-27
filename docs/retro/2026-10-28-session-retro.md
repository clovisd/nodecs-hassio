# Retro — 2026-10-25 → 2026-10-28 session

One long working session with the owner, in three parts: BlinkyBeacon follow-ups, NodeCS v0.1
(read-only) built and shipped, and the design of the timeout button system.

## What happened

### 1. BlinkyBeacon follow-ups (blinkybeacon-hassio v0.1.0, shipped earlier in the session)

- **"Does turning the light on stop by itself?"** No. Only the `spin`/`flash` actions with a
  `duration` stop by themselves. Options were offered; the owner did not ask for a change.
- **"Beacons stop after 1–2 s."** Diagnosed without code changes. The integration sends one
  `POST /spin`. On the tray's `dashboard` build, the dashboard watcher resets the light on
  every poll (2 s by default) whenever a dashboard URL and token are set. Fix on the owner's
  side: blank the dashboard URL on the test PCs.

### 2. NodeCS v0.1 (this repo), 2026-10-27

- **Brainstorm.** The panel speaks GraphQL. The owner pasted a query, the endpoint, and an
  introspection dump. Exploration was read-only and showed:
  - each server's stable id;
  - no GraphQL subscriptions;
  - the panel's own button model and button key;
  - secrets in the schema (never queried).
- **Name.** The owner chose `nodecs-hassio`, public. The panel's product and event names were
  kept out of the repo.
- **Design change mid-stream.** The owner said "the priority with this is lowest latency
  possible, and highest reliability". Reading the panel's web bundle showed its UI does not
  poll: it listens on a WebSocket (`/api/ui/notifications/subscribe`) for `match_updated` and
  `notification`. The design became push first, with a 1 s backstop poll, status every 10 s
  (status makes the panel probe the game servers), and a 6 s grace against flapping.
- **The build.** The plan was written and executed inline in 7 tasks, test-first, ending at
  118 tests.
- **The final review** was a self-review, under the session's rule against spawning agents
  unasked. It found three Important issues, all fixed test-first, for 124 tests:
  - a pasted dashboard URL was refused;
  - the status read could block setup;
  - no test pinned the query fields against secrets.
- **Shipped v0.1.0.** The first CI run failed hassfest (a URL in `strings.json`); fixed, then
  everything went green.

### 3. Design of the timeout button system, 2026-10-28

Brainstormed with the owner, with mockups in the visual companion, then documented here.

- The spec: `docs/superpowers/specs/2026-10-28-button-system-design.md`.
- The build plan: `docs/superpowers/plans/2026-10-28-button-system-build-plan.md`.
- The four pieces: the NodeCS button path and page, a Unity Intercom integration, a coach PC
  Windows app, and a coach PC integration.
- The owner asked for documentation only, plus red-team and blind checks on Fable 5.1, before
  any building.
- **The red team** found 16 problems; **the blind builder check** raised 6 questions. Twenty were
  folded into the design, and two went to the owner (spec §12 Q1–Q2). Spec §13 holds the
  table.

## What went well

- **Looking at how the vendor's own UI stays fresh** found the push channel. That beat any
  amount of poll tuning.
- **Read-only exploration of the live panel** answered schema questions in minutes. Staging
  then let it continue without touching production.
- **Mutation checks** (break the code, watch the test fail, restore) proved the security and
  grace tests actually bite.
- **The visual companion** turned "a page with tests" into concrete decisions (admin test = both
  parts plus a modal; tests blocked while live; archive everything) in three rounds.
- **Leak scanning before the first push**, with a pattern file kept outside the repo, caught
  nothing at push time.
- **Squashing the first commit** earlier kept the product name out of the history.
- **Adversarial checks before planning** caught three critical flaws the conversation had
  agreed to:
  - test presses sent to bound IDs, which could pause a live match;
  - an ignored double tap, losing the press;
  - a delivery check comparing two clocks.
  Run them on every design before planning.

## What went badly, and the rule it leaves

| What | Cost | Rule for next time |
|---|---|---|
| The first design commit named the panel's product; caught only when the owner chose a neutral name | A history rewrite (safe, as nothing had been pushed) | Scan for names **before the first commit** of a public repo, not just before the push |
| Production was explored before staging was offered | Read-only, but production | Ask for staging first |
| `pip install` of Home Assistant's test pins stalled resolving for minutes | Time | Clone an existing venv with the same pins and rewrite its paths (see HANDOFF) |
| `pkill -f <pattern>` matched the calling shell and killed it | One lost command | `pgrep` to find the PID, then `kill <pid>` |
| An autouse fixture replaced `open_push` for every test, so the client's own push tests waited forever | A hung suite | Override the fixture in that module; run suites under `timeout` |
| A regex text extraction over a PDF hung | Time | Use a PDF tool or skill; don't hand-roll regexes over binary |
| hassfest rejects URLs inside `strings.json` | A failed CI run | No URLs in translation strings; use placeholders |
| A literal spec rule ("unavailable after 6 s") was wrong for a 10 s poll | Caught while writing the test | When a timing rule meets a slower loop, write the test for the slower loop first |
| The final review was a self-review | Weaker than a fresh reviewer | The owner now wants red-team and blind checks on Fable 5.1 for designs; ask whether the same applies to code reviews |
| The live-match flag on staging (`liveAt` set while in `WARMUP`) showed a restored match's state can mislead | Would have made tests unsafe | Gate tests on the panel's own rule, verified in Phase 0 |

## After the checks, the same day

The owner settled four things:

- **Test windows** end when the match starts. A live press is always forwarded, and the server
  may queue the pause it requests.
- **The team at a booth:** an admin assignment wins, then TeamSpeak (which can lag). An
  admin-timer integration comes later as a second check.
- **Sounds:** one short beep, for an accepted tac and a passed coach-test hold; nothing else for
  now.
- **Discord webhooks:** a tac channel, plus an all-messages channel with a chosen level. Both
  are optional, and neither is ever in the press path.

## Second review round

- After the owner's answers, a second red team found 15 problems and a second blind check raised
  6 questions and 3 contradictions. All but one were folded in (spec §13.2).
- The worst: an options change would reload the integration and drop presses for a second or
  two; the "safe" probe ID could be bound in the panel; and a hostile name on the standalone page
  could reach an admin's Home Assistant session.
- The one left for the owner is §12 Q8: resend, or alert, when delivery can't be proven.
- **Lesson:** a second adversarial pass on the *answered* design found problems introduced by
  the answers themselves (the standalone page, the options). Re-run the checks after every round
  of owner decisions, not only once.

## Open items carried forward

- NodeCS v0.1 deferred minors:
  - closing the push channel on a dead network can wait for aiohttp's close timeout;
  - a server re-listed after its device was deleted gets no entities until a reload;
  - a logo re-uploaded at the same URL isn't refetched.
- The timeout button system: Phase 0 first (build plan).
- Spec §12 Q8 (resend or alert when delivery can't be proven) is open. The owner answered Q3 and
  Q5–Q7 the same day:
  - names `unityintercom-hassio` and `coachpc` / `coachpc-hassio`;
  - admins do everything and other users are read-only, plus a password-protected standalone
    page;
  - the archive is never deleted;
  - Home Assistant, the panel and the coach PCs are on a separate VLAN.
- The repo was made **private** on 2026-10-28, at the owner's request. HACS can't install it
  while private.
