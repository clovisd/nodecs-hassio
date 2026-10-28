# Round 1 blind builder check — timeout button system design

**Date:** 2026-10-28 · **Model:** Fable 5.1 · **Mode:** read-only. The reviewer had only the
documents and the v0.1 code, and no access to the conversation. **Reviewed version:** the first
draft of `docs/superpowers/specs/2026-10-28-button-system-design.md` (commit `bbd099c`).
**What happened to each question:** spec §13, the B1–B6 rows.

The prompt asked for questions a builder would need answered before planning well, ranked. The
report follows as delivered. Section references point at the first draft.

---

I read both specs, the build plan, the v0.1 code under `custom_components/nodecs/`, the README
and the mockup folders.

I skipped everything Phase 0 is scheduled to measure (§5.1, §5.3, §6.4, §7.5, §10), the §11
builder's calls, and the four §12 owner questions the build plan already says to settle before
planning. What follows is what is still unresolved beyond those, ranked.

**1. A physical press that arrives during a test window after the match has gone live: forward
it or drop it?**

§5.11 says the phase is re-read "before each walk-round step", and that the test stops if it
changed. But a walk-round step *is* a physical press: by the time NodeCS can re-read, the press
has happened. Two anti-goals collide here: "a missed press" against "a test that pauses a live
match".

- **"Forward, it is a real press":** the press path stays untouched, and the test just closes.
- **"Drop":**
  - the press path gains a gate that exists only while a test run is open;
  - a synchronous phase read (about 150 ms) goes in front of the send;
  - the Phase 1 acceptance test "zha_event to request in under 10 ms with no awaits" needs a
    test-window exception.

The same question applies to the coach test, where coaches are explicitly told to hold the
button. I would also need to know whether the 1 s coordinator phase is an acceptable gate, or a
fresh read is required.

**2. What is the source of truth for "the right team" at a booth during the tests?**

- **The conflict:** §5.2 says `side_hint` is "informational only; the team comes from the
  bindings", and the booth list carries no team. Yet:
  - the path check passes an ID when the panel "matches it to the team … the booth list
    expects";
  - `nodecs_test_step` carries `team_matched`;
  - the walk-round turns red on "the wrong team".

  Checking the bindings against themselves is a tautology.
- **The candidates:**
  - the admin picks the team per booth when starting the test (new modal UI);
  - the coach PC's TeamSpeak channel via `ts3Clients` (works only with the nickname set, and
    only in Phase 2 and later);
  - nobody: the page shows the matched team and the walker judges, so `team_matched` is
    informational.

Each gives a different test UI, pass criterion and event contract. The test exists to catch
exactly this error, so I do not want to guess.

**3. Is the panel's clock NTP-synced to the same source as Home Assistant's?**

- **Why it matters:** the ambiguity check in §5.4 step 4 decides "delivered" against "resend
  once" by comparing the panel's `pressedAt` with Home Assistant's `t_sent`. A panel clock a few
  seconds off turns that into either a double pause or a lost press.
- **The gap:** §5.5 lists Home Assistant's NTP and the coach PCs' clocks as the sync evidence,
  but never the panel's, which is the clock that matters here.
- **If sync is not guaranteed:**
  - the check must key on the panel's press `id` (so Phase 0.1 must also record whether ids
    are monotonic), or on a count before and after, which is a different algorithm;
  - `pressed_at_panel − t_zha` is never shown.

**4. Which mockups are approved, and which wins where they and the spec disagree?**

- **Where they are:** `docs/design/mockups/` existed but was empty when I read it. The only
  mockup files were in `.superpowers/brainstorm/…/content/`, which is gitignored, so they vanish
  with the workspace.
- **Their status:** they are labelled "my first guess, click any you disagree with", and they
  predate decisions in the spec:
  - coach feedback via a booth beacon, where the spec says no beacon at the booth and a headset
    beep instead;
  - an "Ask coaches to press" flow;
  - a "Zigbee network" status line.
- **What I need to know:** Phase 2's plan is told to use these mockups. Are those four files the
  approved set? Does the spec override them? May they be committed to the public repo?

**5. Do the panel's server ids survive between events?**

- **Why it matters:** the booth list keys each booth on the panel's server ULID, and so do the
  archive records. If the owner reinstalls the panel, or starts a fresh database per event,
  every booth dangles at the next event and the archive's `server_id` no longer resolves.
- **What it decides:**
  - whether booths key on server id or server name;
  - whether the page needs a "re-link booth to server" flow;
  - what the archive stores beside the id for later export.

**Lower, but it would change Phase 1's config flow:** after the existing v0.1 entry is upgraded,
must NodeCS keep working read-only until the button key is entered (an optional key, with a
repair issue), or may the upgrade block on the key? I would default to optional. I flag it only
because the opposite breaks the owner's running entry on upgrade.

*Note: the mockups were committed, cleaned of real names, right after this check started. That is
why the reviewer found the folder empty.*
