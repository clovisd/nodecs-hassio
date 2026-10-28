# Handoff — start here

## Where things stand (2026-10-28)

- **NodeCS v0.1.0 is shipped:** read-only, with servers, matches and pauses as devices, push
  first with a 1 s backstop. Spec: `docs/superpowers/specs/2026-10-27-nodecs-hassio-design.md`.
  It was public and installed through HACS until 2026-10-28; the repo is now private (below), so
  install by hand.
- **The timeout button system is designed, not built.** Read in this order:
  1. `docs/superpowers/specs/2026-10-28-button-system-design.md`, the spec:
     - §12 has the owner's answers;
     - §13 and §13.2 hold both rounds of red-team and blind-builder findings;
     - §14 lists future features and what each could change.
  2. `docs/superpowers/plans/2026-10-28-button-system-build-plan.md`, the phases. **Start with
     Phase 0.**
  3. `docs/design/mockups/`, the page layouts the owner approved.
  4. `docs/retro/2026-10-28-session-retro.md`, what happened and the rules it left.
  5. `docs/reviews/`, the four check reports in full: both red-team rounds and both blind
     builder rounds, on Fable 5.1. The spec's §13 tables say what was done with each finding.
  6. `docs/reference/panel-api.md`, the panel's API: endpoints, observed behaviour, and the
     typed schema for every type NodeCS touches.
  7. `tools/phase0/`, the read-only probe scripts (query timing, a client check, a push-channel
     listener) for Phase 0. They were cleaned after their last live run and not re-run since.
- **All design questions are answered** (spec §12). Q8: an unproven press is never resent; it
  raises a critical alert. Spec §14 lists future features that could change decisions like that
  one.
- **Next action:** Phase 0 (verify the unknowns) with the owner present. Several steps are
  writes on staging and need their OK.
- **The repo is private** since 2026-10-28, at the owner's request. HACS cannot install or
  update NodeCS while it is private. The no-names rule still applies, in case it goes public
  again.
- **Later:** an admin-timer integration (an existing tool with its own API) as a second check on
  booth teams; it needs its own brainstorm. See spec §14 for the rest.
- **Where it lives:** everything is on `main` in the private repo, and CI is green (hassfest,
  tests, lint; the HACS check skips itself while private). The `docs/button-system` branch is
  merged and mirrors `main`.

## Rules the owner set

- **No names in the repo** (private now, possibly public later): never name the panel's
  product, the event, its hosts or real teams. Say "the panel".
- **The panel:** use staging, never production, and stay read-only unless the owner approves a
  specific write. Credentials come from the owner in the session; never store them anywhere.
- **Coach PCs:** zero impact on TeamSpeak (spec §7.1).
- **Bindings** stay manual in the panel.
- **Priority:** lowest latency and highest reliability, with full accountability.
- **Reviews:** the owner asked for red-team and blind checks on Fable 5.1 for designs. Ask
  before assuming the same for code.
- **Shipping:** merge, push, release and repo creation only with the owner's go-ahead.

## Working environment (this machine, WSL2)

- **Python 3.14:** `~/.local/share/uv/python/cpython-3.14.8-linux-x86_64-gnu/bin/python3.14`.
  `uv` itself is not installed.
- **The venv:** `pip install` of Home Assistant's test pins is very slow here. Clone a venv
  with the same pins instead:
  ```bash
  cp -a ~/nodecs-hassio/.venv <new-repo>/.venv
  grep -rlI "/home/clovisd/nodecs-hassio/.venv" <new-repo>/.venv/bin \
    | xargs sed -i "s#/home/clovisd/nodecs-hassio/.venv#<new-repo>/.venv#g"
  ```
  Pins: `pytest-homeassistant-custom-component==0.13.375` (Home Assistant 2026.10.4),
  `ruff==0.17.2`.
- **Tests:** `timeout 110 .venv/bin/pytest -q -p no:cacheprovider`. The timeout guards against
  a hung fixture.
- **GitHub CLI:** `~/.local/bin/gh` (not on PATH). Logged in as the owner.
- **Git author:** repo-local, `clovisd <clovisdelmotte@gmail.com>`.
- **Leak scan:** the pattern list lives **outside** any repo, at `~/.config/nodecs/leak-patterns.txt`.
  Run before every commit and push:
  ```bash
  git log -p --all | grep -i -c -F -f ~/.config/nodecs/leak-patterns.txt   # must print 0
  git ls-files -z | xargs -0 grep -i -l -F -f ~/.config/nodecs/leak-patterns.txt  # must print nothing
  ```
- **CI:** hassfest, HACS, pytest and ruff. hassfest rejects URLs inside `strings.json`.

## Related repos

- `~/blinkybeacon-hassio` (public): the BlinkyBeacon integration, the lobby admin's press alert.
- The BlinkyBeacon tray app (`clovisd/blinkybeacon-web`): the Go Windows tray pattern the coach
  PC app should follow.
- To create in Phases 3–5: the Unity Intercom integration, the coach PC app, and the coach PC
  integration (names in spec §12).
