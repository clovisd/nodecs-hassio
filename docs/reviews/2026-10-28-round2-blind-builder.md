# Round 2 blind builder check: timeout button system design and build plan

**Date:** 2026-10-28 · **Model:** Fable 5.1 · **Mode:** read-only. The reviewer had only the
documents and the v0.1 code, and no access to the conversation.
**Reviewed version:** the spec, the build plan and the handoff after the owner's answers to
Q1–Q7 (commit `9d76a85`).
**What happened to each question:** spec §13.2 (rows B2.1–B2.6, B2.c1–B2.c3). The owner answered
B2.1 as §12 Q8: raise an alert, never resend.

The report follows as delivered. Section references point at that version.

---

Reviewed, read-only:

- `docs/HANDOFF.md`;
- the 2026-10-28 design spec;
- the 2026-10-28 build plan;
- the v0.1 spec, the retro and the mockups;
- `custom_components/nodecs/{__init__,api,coordinator,push,const,config_flow}.py`.

## Questions I would still need answered, ranked

**1. What does NodeCS do when it cannot prove delivery?**

Spec §5.4 step 5 resolves an ambiguous result by reading `buttonPresses`. It says nothing about
these cases:

- the read itself fails: the admin GraphQL API is unreachable or slow, which is likely exactly
  when the press POST timed out;
- 10 s pass and the result is still ambiguous;
- Home Assistant restarts between `press_sent` and `press_outcome`.

Plan Phase 1 acceptance names "HA restarting with a press in flight", but not the expected
outcome.

- Resending risks a second pause, which is an anti-goal.
- Stopping risks a missed press, which is the owner's stated top priority.

Phase 0.1 partly settles it: if the panel ignores or merges a second press while one is pending
or running, resending is safe. If it does not, which way should NodeCS err? The answer shapes the
retry loop, the restart recovery, and what the critical alert says.

**2. How is a press attributed to NodeCS in reconciliation when its panel press id was never
learned?**

- Step 6 waits only 2 s for the log entry, and after a restart the seed is rebuilt from the panel.
- In both cases NodeCS's own press later shows up as an unknown id on a linked ID. It becomes a
  `foreign_press` and raises a critical alert to the beacon and Discord, mid-match.
- The spec bans clock comparison for the ambiguity check. Is a time-window attribution ("an
  unknown id on a linked ID within N s of our send") acceptable here? Or must a sent ledger
  persist across restarts and match on something else?

A wrong guess means either false critical alerts during live matches, or a press made with a
leaked key mistaken for NodeCS's own.

**3. How does the page ship?**

- The spec treats "one web component" as a given. But:
  - HACS installs only `custom_components/nodecs/`, so the JavaScript must live there;
  - a Home Assistant custom panel needs a registered static path and a JavaScript module;
  - the standalone page sits outside Home Assistant's frontend, so it cannot borrow Home
    Assistant's bundled Lit.
- The choices:
  - **TypeScript and Lit with a Node build and a committed bundle.** This adds a new CI job
    beside hassfest, HACS, pytest and ruff, and a minified file that the leak scan runs over and
    nobody reviews.
  - **Dependency-free, hand-written ES modules.**
- This decides Phase 2's size, the CI, the CSP in §5.9.1, and whether the two pages can really be
  the same component.
- The owner maintains Go and Python. A Node toolchain would be their maintenance burden.

**4. The keep-warm request on the press session (§5.4 step 4).**

- The spec says "a tiny authenticated request every 5 s" on the button-key connector. The only
  known button-key endpoint is the press itself.
- A sentinel press every 5 s means about 17,000 press-log rows a day, and a panel notification
  each time.
- If no harmless button-key endpoint exists, keep-warm should be the existing GraphQL ids query
  (Basic Auth) over the same connector. The TCP/TLS connection is what matters, not the header.
- Add to Phase 0.1: does anything other than `press` accept the button key?

**5. Is `matchID` optional on `buttonPresses(buttonID, matchID, limit)`?**

- The seed, the 10 s reconciliation and the sentinel confirmation all read by button ID, across
  matches or with no match.
- If `matchID` is required:
  - the sentinel path check cannot be confirmed from the log;
  - the seed and the reconciliation must iterate over matches.
- Add to Phase 0.1.

**6. A standalone operator against a non-admin Home Assistant user.**

- §5.9: a logged-in non-admin Home Assistant user cannot start tests or assign teams.
- §5.9.1: a standalone operator, with a shared password and a free-text name, can.
- So the anonymous role outranks the authenticated one. If that is unintended, both the Phase 2
  WebSocket role check and the standalone command set change.

## Spec and plan contradictions, and gaps

- **Action names.** The domain is `unity_intercom` (§4, §12 Q3), but the actions are
  `unity.direct_talk` and `unity.press_button` (§4 diagram, §6.2, §9; plan Phase 3). Home
  Assistant names actions `<domain>.<action>`, so one of them is wrong. The domain should win, and
  the NodeCS call sites in §9 follow.
- **Unlinked buttons (internal to §5.4).** The `zha_event` subscription is "filtered to the IEEE
  addresses in the booth list". Yet "a button not in the booth list … is shown on the page
  (unlinked button pressed)". Both cannot hold.
  - NodeCS must listen to every `zha_event`.
  - Which devices count as an unlinked button (any ZHA device, or only SNZB-01P models) decides
    how noisy that indicator is.
- **Health checks with no phase.** Plan Phase 1 lists press-path-alive, the binding check,
  hysteresis and live-match mode, and Phase 2 lists none. These spec §5.8 alerts appear in no
  phase and no acceptance list:
  - button heard-from, LQI and battery;
  - key refused;
  - foreign press;
  - archive write.

  This is decidable (Phase 1), but the plan should say so.
- **Mockups against the spec.** The path check to bound IDs, tests disabled while live, and booth
  beacons are already settled by the spec's "the spec wins" rule. Nothing to add.

Everything else I checked is either a Phase 0 measurement or a builder's call I can make.

- **Phase 0 measurements:** the ZHA command mapping, the hold timing, the report-only phases,
  press-id ordering, the clocks, and the TeamSpeak fields.
- **Builder's calls:**
  - the sentinel is refused if it is ever bound;
  - `zha` goes in `after_dependencies`, so NodeCS loads without ZHA;
  - the SSL context is built off the event loop;
  - one booth store per entry.
