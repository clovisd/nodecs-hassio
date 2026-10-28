# Context: everything from the original working session

On 2026-10-28 the owner moved the work fully to GitHub: "include everything into the github,
we're moving over fully." This folder holds everything that used to live only on the original
machine.

**The repo is private.** Real names and hosts are allowed here while it stays private. Before it
is ever made public, the history must be scrubbed: `leak-patterns.txt` lists the names to remove.
**Credentials are never in this repo;** the owner hands them to each session directly.

## Real names and hosts

| What | Value |
|---|---|
| The panel (product) | **PGL Esportal**, the organiser's internal CS2 tournament panel. The web UI title is "PGL Esportal - Servers". |
| Production panel | `https://panel.tourney.local/` on the event LAN (resolved to `10.97.24.11` on 2026-10-27). Read-only exploration only, done before staging was offered; **do not use it.** |
| Staging panel | `https://stage.tourney.esportal.xyz/` (resolved to `185.62.206.37`), with the dashboard at `/dashboard`. **Use this one** for all checks, read-only unless the owner approves a write. |
| Login | The same admin user on both, by HTTP Basic Auth. The button API takes a separate Bearer key. Neither is in this repo. |
| Staging servers (2026-10-28) | Server A.1, Server A.2, Server B.1, Server B.2 |
| Production servers (2026-10-27) | server_a1, server_a2, server_b1, server_b2 |
| Staging test button | `coach-a`, bound to `TAC_PAUSE` for team A on Server A.1's match. On 2026-10-27 at 22:26:44 local time the owner pressed it: `executed`, "tac pause for Astralis requested". |
| Button press curl (from the owner) | `curl --insecure -X POST -H "Authorization: Bearer <button key>" "$TOURNEY/api/buttons/coach-a/press"` |
| Office network | The owner's office network has its own DNS notes (`memory/pgl-network-dns.md`). |

## What is here

| Path | What it is |
|---|---|
| `transcript/2026-10-25-to-28-session.md` | The whole working session as markdown: every message from the owner (including those sent mid-task), every reply, and one line per tool call. Tool output and internal reasoning are dropped. Credentials are `[REDACTED]`. |
| `memory/` | A snapshot (2026-10-28) of every note the assistant kept on the original machine, for all of the owner's projects, not just this one. `MEMORY.md` is the index. The originals lived in `~/.claude/projects/-home-clovisd/memory/`. |
| `exploration/` | The raw read-only exploration of the panel, with real data: the GraphQL queries used, the introspection dumps (`introspect.json` is production, `stage_introspect.json` is staging), state snapshots, the logo and timing probes, the push-channel listener, and a failed attempt to extract text from the Unity Intercom manual PDF. The scripts read the login from a separate file that is not here. Cleaned, reusable versions are in `tools/phase0/`. |
| `brainstorm/` | The original visual-companion screens shown to the owner while designing the page, unsanitised. Cleaned copies with notes are in `docs/design/mockups/`. In `layout.html` the owner clicked "both" for "what should Admin test: Go do?". |
| `leak-patterns.txt` | Names, hosts and real team names to scrub from history before the repo is ever made public, one per line. Credential patterns are kept out of it on purpose. |

## Where the decisions are

- **Design:** `docs/superpowers/specs/2026-10-28-button-system-design.md`. §12 holds the owner's
  answers in their own words, §13 the review findings, §14 the future features.
- **Build order:** `docs/superpowers/plans/2026-10-28-button-system-build-plan.md`.
- **Start here:** `docs/HANDOFF.md`.
- **What happened, and the lessons:** `docs/retro/2026-10-28-session-retro.md`.
- **The four review reports, in full:** `docs/reviews/`.
- **The panel's API:** `docs/reference/panel-api.md`.
