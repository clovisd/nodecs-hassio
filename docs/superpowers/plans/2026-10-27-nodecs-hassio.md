# nodecs-hassio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A HACS-installable, read-only Home Assistant integration that shows every game server on the CS2 panel, and the match on it, as devices whose entities update as soon as the panel announces a change.

**Architecture:** One config entry per panel. A push listener holds the panel's WebSocket open and asks the match coordinator for an immediate read on every message; the match coordinator also polls every 1 s, and a status coordinator reads server status every 10 s. Both coordinators keep their last values for 6 s through failed reads. Sensors, binary sensors and image entities read the coordinators; a panel device carries the "Live updates" sensor.

**Tech Stack:** Python 3.14, Home Assistant 2026.10.4, aiohttp (HA's shared session, `ws_connect`), `pytest-homeassistant-custom-component==0.13.375`, ruff 0.17.2.

**Spec:** `docs/superpowers/specs/2026-10-27-nodecs-hassio-design.md`

## Global Constraints

- Domain `nodecs`; name `NodeCS`; version `0.1.0`; `codeowners: ["@clovisd"]`; `config_flow: true`; `integration_type: hub`; `iot_class: local_push`; `requirements: []`; documentation and issue tracker `https://github.com/clovisd/nodecs-hassio`.
- Endpoints: `POST <base>/api/ui/graphql/query`; WebSocket `<base with ws/wss>/api/ui/notifications/subscribe`.
- Login: `Authorization: Basic base64(user:password)` built by hand (aiohttp 3.14 deprecates `BasicAuth`; HA 2025.1 lacks `encode_basic_auth`). Sent only to the panel's own scheme+host+port.
- Timings: match poll 1 s; status poll 10 s; request timeout 3 s; setup-form timeout 10 s; stale grace 6 s; refresh coalescing cooldown 0.3 s; push retry 1 s doubling to 30 s; WebSocket heartbeat 15 s.
- The two query texts are exactly those in spec §5 (match query named `HomeAssistantMatches`, status query `HomeAssistantStatus`); a test pins them. No other GraphQL is ever sent; nothing writes to the panel.
- No product, event or host names from the real panel anywhere in the repo or its history: fixtures use `https://panel.example.lan`, made-up ids, and teams "Alpha" and "Bravo".
- Every user-facing string lives in `strings.json` and an identical `translations/en.json`.
- `hacs.json` minimum HA `2025.1.0`; tested on 2026.10.4. Commands run from the repo root with `.venv/bin/pytest` and `.venv/bin/ruff`.

## Review Focus

- One failed read (timeout, 502, connection reset) during a running pause: every entity keeps its state, no unavailable blip; after 6 s without a good read they go unavailable. Test in Task 4.
- A burst of push messages (ten within 100 ms): reads start immediately and the burst costs at most two reads, never a 10 s delay. Test in Task 4.
- A logo URL on a host other than the panel: fetched without the `Authorization` header. Test in Task 2.
- Times with nanoseconds (`2026-10-27T20:21:54.985469598Z`), `null`, or garbage: parsed, `None`, `None`; never a failed read. Test in Task 1.
- The next map of a series lands on the same server with the teams swapped: "Paused by" compares against the current match's team ids, entity ids do not change. Test in Task 5.

---

### Task 1: Scaffold and the panel's data model

**Files:**
- Create: `.gitignore` (`.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.superpowers/`), `pyproject.toml` (as blinkybeacon-hassio's, name `nodecs-hassio`), `requirements_test.txt` (`pytest-homeassistant-custom-component==0.13.375`), `custom_components/__init__.py` (empty), `custom_components/nodecs/__init__.py` (docstring only), `custom_components/nodecs/manifest.json`, `custom_components/nodecs/const.py`, `custom_components/nodecs/models.py`
- Test: `tests/__init__.py`, `tests/conftest.py`, `tests/payloads.py`, `tests/test_models.py`

**Interfaces:**
- Produces (`const.py`): `DOMAIN = "nodecs"`, `NAME = "NodeCS"`, `GRAPHQL_PATH`, `PUSH_PATH`, `MATCH_QUERY`, `STATUS_QUERY`, `MATCH_INTERVAL = timedelta(seconds=1)`, `STATUS_INTERVAL = timedelta(seconds=10)`, `REQUEST_TIMEOUT = 3`, `SETUP_TIMEOUT = 10`, `STALE_AFTER = timedelta(seconds=6)`, `REFRESH_COOLDOWN = 0.3`, `PUSH_RETRY_MIN = 1`, `PUSH_RETRY_MAX = 30`, `PUSH_HEARTBEAT = 15`.
- Produces (`models.py`), all `@dataclass(frozen=True)`:
  - `Team(id: str, name: str, logo_url: str)`, `MapInfo(name: str, logo_url: str)`, `Pause(reason: str, started_at: datetime | None, ended_at: datetime | None, team_id: str | None)`, `Binding(button: str, action: str, team: str | None)`.
  - `Match(id, phase: str, best_of: int, team_a: Team, team_b: Team, map: MapInfo, team_a_ready: bool, team_b_ready: bool, team_a_score: int, team_b_score: int, team_a_maps_won: int, team_b_maps_won: int, team_a_timeouts_used: int, team_b_timeouts_used: int, team_a_timeouts_left: int, team_b_timeouts_left: int, assigned_at, live_at, ended_at: datetime | None, pauses: tuple[Pause, ...], bindings: tuple[Binding, ...])` with properties `running_pause -> Pause | None` (open pause with the latest `started_at`) and `paused_by -> str | None` (`"none"` without a running pause, `"admin"` for a null team, `"team_a"`/`"team_b"` by id, `None` when the id matches neither).
  - `Server(id: str, name: str, match: Match | None)`.
  - `parse_time(value: object) -> datetime | None`; `parse_matches(data: dict) -> dict[str, Server]` (keyed by id, panel order); `parse_statuses(data: dict) -> dict[str, str | None]`. Both parsers raise `ValueError` on a missing or mistyped field; a `null` `pauses` is `()`.
- Produces (`tests/payloads.py`): `BASE = "https://panel.example.lan"`, `GRAPHQL = BASE + GRAPHQL_PATH`, `team_json(id, name)`, `match_json(**overrides) -> dict` (Alpha `TEAM-A` vs Bravo `TEAM-B` on Nuke, phase `LIVE`, no pauses), `pause_json(reason, team_id=None, started="2026-10-27T18:00:00Z", ended=None)`, `server_json(id="SRV-1", name="server_1", match=None, status="RUNNING_VALID")`, `matches_reply(*servers) -> dict`, `status_reply(*servers) -> dict` (both `{"data": {"cs2Servers": [...]}}`).
- Produces (`tests/conftest.py`): autouse custom-integrations fixture; `USERNAME = "admin"`, `PASSWORD = "hunter2"`; `mock_config_entry` → `MockConfigEntry(domain=DOMAIN, title="panel.example.lan", data={url: BASE, username, password, verify_ssl: True}, unique_id="panel.example.lan:443")`; `setup_integration(hass, entry)`; fixture `no_push` that patches `NodeCSClient.open_push` to raise `NodeCSConnectionError` (default for entity tests; Task 4 replaces it).

- [ ] **Step 1: Write the scaffold files** per Global Constraints (manifest, pyproject, requirements, .gitignore, const with the §5 query texts verbatim).
- [ ] **Step 2: Write the failing tests in `tests/test_models.py`:**
  - `test_parse_matches_reads_every_field`: a server with `match_json(teamAScore=7, teamBTimeoutsLeft=2, bestOfXBScore=1, liveAt="2026-10-26T08:02:05Z")` ⇒ `Server.match.team_a_score == 7`, `team_b_timeouts_left == 2`, `team_b_maps_won == 1`, `live_at == datetime(2026,10,26,8,2,5,tzinfo=UTC)`, `team_a.name == "Alpha"`, `map.name == "Nuke"`.
  - `test_parse_matches_server_without_match`: `match: null` ⇒ `Server.match is None`.
  - `test_parse_time` parametrized: `"2026-10-27T20:21:54.985469598Z"` ⇒ `datetime(2026,10,27,20,21,54,985469,UTC)`; `None` ⇒ `None`; `"not a time"` ⇒ `None`; `5` ⇒ `None`.
  - `test_null_pauses_is_empty`: `pauses: None` ⇒ `()`.
  - `test_running_pause_is_latest_open_one`: two open pauses started 18:00 and 18:05 plus a closed one ⇒ the 18:05 one.
  - `test_paused_by` parametrized: no pauses ⇒ `"none"`; open TACTICAL by `TEAM-A` ⇒ `"team_a"`; by `TEAM-B` ⇒ `"team_b"`; open TECHNICAL with no team ⇒ `"admin"`; open by `"TEAM-X"` ⇒ `None`; only closed pauses ⇒ `"none"`.
  - `test_bindings`: `[{"buttonID": "coach-a", "action": "TAC_PAUSE", "team": "A"}]` ⇒ `(Binding("coach-a", "TAC_PAUSE", "A"),)`.
  - `test_parse_matches_rejects_bad_shape` parametrized: `{}`, `{"cs2Servers": None}`, a server without `id`, `teamAScore: "7"` ⇒ `ValueError`.
  - `test_parse_statuses`: `RUNNING_VALID` and `null` ⇒ `{"SRV-1": "RUNNING_VALID", "SRV-2": None}`.
- [ ] **Step 3: Run** `.venv/bin/pytest tests/test_models.py -q` (after creating `.venv` with the uv-installed Python 3.14 and installing `requirements_test.txt`). Expected: FAIL, `ModuleNotFoundError: custom_components.nodecs.models`.
- [ ] **Step 4: Implement `models.py`.** `parse_time` uses `homeassistant.util.dt.parse_datetime` and returns `None` for anything not a parseable string; ints are checked with `type(x) is int`, bools with `type(x) is bool`.
- [ ] **Step 5: Run** the same command. Expected: PASS.
- [ ] **Step 6: Commit** `feat: scaffold and the panel's data model`.

### Task 2: Panel client

**Files:**
- Create: `custom_components/nodecs/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes: `models.parse_matches`, `parse_statuses`; `const` paths, queries, timeouts.
- Produces (`api.py`):
  - `NodeCSError(Exception)`; `NodeCSConnectionError(NodeCSError)`; `NodeCSCertificateError(NodeCSConnectionError)`; `NodeCSAuthError(NodeCSError)`; `NodeCSResponseError(NodeCSError)`.
  - `NodeCSClient(session: aiohttp.ClientSession, base_url: str, username: str, password: str)` with `base_url: str`, `async fetch_matches(timeout: float = REQUEST_TIMEOUT) -> dict[str, Server]`, `async fetch_statuses(timeout: float = REQUEST_TIMEOUT) -> dict[str, str | None]`, `async fetch_image(url: str) -> tuple[bytes, str]`, `async open_push() -> PushChannel`.
  - `PushChannel`: `async for message in channel` yields each JSON-object text frame as `dict` (other frames skipped) and raises `NodeCSConnectionError` when the socket closes or errors; `async close() -> None`.

- [ ] **Step 1: Write the failing tests** (client on `async_get_clientsession(hass)`, `aioclient_mock`):
  - `test_fetch_matches_posts_the_pinned_query`: reply `matches_reply(server_json())` ⇒ one POST to `GRAPHQL` whose JSON body is `{"query": MATCH_QUERY}` and whose headers include `Authorization: Basic YWRtaW46aHVudGVyMg==`; result has key `"SRV-1"`.
  - `test_fetch_statuses_posts_the_status_query`: body `{"query": STATUS_QUERY}`.
  - `test_errors` parametrized over the reply ⇒ exception: status 401 ⇒ `NodeCSAuthError`; `exc=aiohttp.ClientConnectionError()` ⇒ `NodeCSConnectionError`; `exc=TimeoutError()` ⇒ `NodeCSConnectionError`; `exc=aiohttp.ClientSSLError(...)` ⇒ `NodeCSCertificateError`; status 502 ⇒ `NodeCSResponseError`; HTML `text="<html>"` ⇒ `NodeCSResponseError`; `{"errors":[{"message":"boom"}],"data":null}` ⇒ `NodeCSResponseError` with `"boom"` in `str()`; `{"data":{"cs2Servers":[{"name":"x"}]}}` ⇒ `NodeCSResponseError`.
  - `test_fetch_image_sends_login_to_panel_host`: GET `BASE + "/api/ui/teams/T/logo"` → `content=b"PNG"`, `headers={"Content-Type": "image/png"}` ⇒ `(b"PNG", "image/png")` and the request carried `Authorization`.
  - `test_fetch_image_other_host_without_login`: `https://cdn.example.org/a.png` ⇒ fetched, and its recorded headers have no `Authorization`.
  - `test_fetch_image_rejects_non_image`: `Content-Type: text/html` ⇒ `NodeCSResponseError`.
  - `test_push_channel_yields_json_objects` (fake ws object with `receive()` returning TEXT `{"type":"match_updated"}`, TEXT `not json`, TEXT `[1]`, then CLOSED) ⇒ yields exactly `[{"type": "match_updated"}]`, then raises `NodeCSConnectionError`.
  - `test_open_push_url_and_auth`: `ws_connect` patched on the session ⇒ called with `"wss://panel.example.lan/api/ui/notifications/subscribe"`, the Basic header, `heartbeat=15`; an `http://` base gives `ws://`. A `WSServerHandshakeError(status=401)` ⇒ `NodeCSAuthError`; any other `ClientError` ⇒ `NodeCSConnectionError`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_api.py -q`. Expected: FAIL, `ModuleNotFoundError: custom_components.nodecs.api`.
- [ ] **Step 3: Implement `api.py`.** `asyncio.timeout(timeout)` around each request; catch `aiohttp.ClientSSLError` before `aiohttp.ClientError`; `response.json(content_type=None)`; the parser's `ValueError` becomes `NodeCSResponseError`. "Same origin" compares `yarl.URL` scheme, host and port.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat: panel client for the two queries, logos and the push channel`.

### Task 3: Config flow

**Files:**
- Create: `custom_components/nodecs/config_flow.py`, `custom_components/nodecs/strings.json`, `custom_components/nodecs/translations/en.json` (config section only for now)
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Consumes: `NodeCSClient`, its exceptions; `SETUP_TIMEOUT`.
- Produces: `normalize_url(raw: str) -> str` (`"https://host[:port]"`, lower-case host, default port dropped; raises `ValueError`), `unique_id_for(url: str) -> str` (`"host:port"` with the default port filled in). Entry data keys: `CONF_URL`, `CONF_USERNAME`, `CONF_PASSWORD`, `CONF_VERIFY_SSL`. Error keys: `invalid_url`, `cannot_connect`, `certificate_error`, `invalid_auth`, `invalid_reply`, `unknown`. Entry title: the URL's host.

- [ ] **Step 1: Write the failing tests:**
  - `test_normalize_url` parametrized: `panel.example.lan` ⇒ `https://panel.example.lan`; `https://Panel.Example.lan/` ⇒ `https://panel.example.lan`; `http://10.0.0.5:8080` ⇒ `http://10.0.0.5:8080`; `https://panel.example.lan/api/ui/graphql/query` ⇒ `https://panel.example.lan`; `https://panel.example.lan:443` ⇒ `https://panel.example.lan`; `ftp://x`, `https://panel.example.lan/dashboard`, `""`, `https://` ⇒ `ValueError`.
  - `test_user_flow_creates_entry`: reply `matches_reply()` ⇒ `CREATE_ENTRY`, title `panel.example.lan`, data `{url: BASE, username, password, verify_ssl: True}`, unique id `panel.example.lan:443`.
  - `test_user_flow_errors` parametrized (client `fetch_matches` patched to raise): `NodeCSConnectionError` ⇒ `cannot_connect`; `NodeCSCertificateError` ⇒ `certificate_error`; `NodeCSAuthError` ⇒ `invalid_auth`; `NodeCSResponseError` ⇒ `invalid_reply`; `RuntimeError` ⇒ `unknown`; bad URL ⇒ `{"url": "invalid_url"}`. Then a good attempt still creates the entry.
  - `test_user_flow_verify_ssl_off_uses_unverified_session`: `verify_ssl: False` ⇒ `async_get_clientsession` called with `verify_ssl=False`; entry data stores `False`.
  - `test_duplicate_aborts`: same host ⇒ `already_configured`.
  - `test_reauth_updates_password`: `start_reauth_flow` → new password, good reply ⇒ `reauth_successful`, entry password updated; a 401 ⇒ form error `invalid_auth`.
  - `test_reconfigure_changes_url_and_ssl`: new URL `https://panel2.example.lan`, `verify_ssl: False` ⇒ `reconfigure_successful`, data and unique id updated; reconfiguring onto another entry's host ⇒ `already_configured`.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_config_flow.py -q`. Expected: FAIL (no config flow).
- [ ] **Step 3: Implement** the flow (one `_async_check(url, username, password, verify_ssl) -> str | None` shared by all steps, using `fetch_matches(timeout=SETUP_TIMEOUT)`), and the `config` section of the strings: the user step's description says to untick "Verify SSL certificate" for a panel with the event's own certificate; `certificate_error` says the same.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat: config flow with reauth and reconfigure`.

### Task 4: Coordinators, push listener, setup

**Files:**
- Create: `custom_components/nodecs/coordinator.py`, `custom_components/nodecs/push.py`, `custom_components/nodecs/entity.py`; fill `custom_components/nodecs/__init__.py`
- Test: `tests/test_coordinator.py`, `tests/test_push.py`, `tests/test_init.py`

**Interfaces:**
- Consumes: `NodeCSClient`, exceptions, `const` timings.
- Produces (`coordinator.py`):
  - `class NodeCSCoordinator[T](DataUpdateCoordinator[T])` with the 6 s grace: a `NodeCSAuthError` raises `ConfigEntryAuthFailed`; another `NodeCSError` returns the previous data while `dt_util.utcnow() - last good read < STALE_AFTER`, else raises `UpdateFailed`. `always_update=False`.
  - `MatchCoordinator(NodeCSCoordinator[dict[str, Server]])`: `MATCH_INTERVAL`, `request_refresh_debouncer=Debouncer(hass, _LOGGER, cooldown=REFRESH_COOLDOWN, immediate=True)`.
  - `StatusCoordinator(NodeCSCoordinator[dict[str, str | None]])`: `STATUS_INTERVAL`.
  - `@dataclass class NodeCSRuntime: client, matches, status, push`; `type NodeCSConfigEntry = ConfigEntry[NodeCSRuntime]`.
- Produces (`push.py`): `PushListener(hass, entry, client, on_message: Callable[[], Awaitable[None]])` (`__init__.py` passes `matches.async_request_refresh`, whose 0.3 s debouncer does the coalescing) with `connected: bool`, `async_add_listener(cb: Callable[[], None]) -> CALLBACK_TYPE`, `async run() -> None` (forever: `open_push`, mark connected, await `on_message` for every message; a `NodeCSAuthError` from `open_push` is treated like any failure, since the next 1 s read raises the reauth; on error mark disconnected and sleep 1, 2, 4 … 30 s; reset to 1 s after an open; closes the channel when cancelled). One warning on the first failure (or a drop after being connected), one info line on recovery.
- Produces (`entity.py`): `server_device_info(entry, client, server_id, name) -> DeviceInfo` (identifiers `(DOMAIN, f"{entry_id}_{server_id}")`, manufacturer `NAME`, model `"CS2 server"`, `via_device=(DOMAIN, f"{entry_id}_panel")`, `configuration_url=client.base_url`); `panel_device_info(entry, client)` (model `"Panel"`, name entry title); `NodeCSServerEntity[C](CoordinatorEntity[C])` with `server_id`, `_attr_has_entity_name = True`, unique id `f"{entry_id}_{server_id}_{key}"`, `available` additionally requires the server in the match data; `async_add_server_entities(entry, async_add_entities, build: Callable[[str], list[Entity]]) -> None` adding entities for current servers and for each new id the match coordinator reports.
- Produces (`__init__.py`): `async_setup_entry` (session via `async_get_clientsession(hass, verify_ssl=...)`; both first refreshes; runtime data; `entry.async_create_background_task(hass, push.run(), "nodecs push")`; forward `[BINARY_SENSOR, IMAGE, SENSOR]`; a match-coordinator listener renaming server devices whose panel name changed); `async_unload_entry`; `async_remove_config_entry_device` (refuses the panel device and servers still on the panel).

- [ ] **Step 1: Write the failing tests:**
  - `test_coordinator.py::test_failed_read_keeps_values_within_grace`: set up with a match whose `paused_by` is `team_a`; next poll raises `NodeCSConnectionError`; tick 1 s ⇒ `coordinator.last_update_success` is True and data unchanged; ticks to 7 s of failures ⇒ `last_update_success` False.
  - `test_auth_error_starts_reauth`: next poll raises `NodeCSAuthError` ⇒ a reauth flow is in progress for the entry, without waiting 6 s.
  - `test_recovery_after_unavailable`: after going unavailable, a good read ⇒ `last_update_success` True.
  - `test_status_polls_every_10_s_and_matches_every_1_s`: over 10 s of ticks ⇒ about 10 match reads, 1 status read (count POST bodies by query).
  - `test_push.py::test_every_message_triggers_a_read`: fake `open_push` yielding one message ⇒ a match read within the same loop iteration, without ticking time.
  - `test_burst_costs_at_most_two_reads`: ten messages yielded back to back ⇒ reads counted after `async_block_till_done` plus 0.3 s tick ≤ 2 and ≥ 1.
  - `test_reconnect_backoff`: `open_push` fails three times then succeeds ⇒ sleeps of 1, 2, 4 s (patch `asyncio.sleep` in `push`), `connected` True at the end, listeners called on each change; one warning logged, one info logged.
  - `test_unload_closes_channel`: unloading the entry ⇒ the fake channel's `close()` awaited.
  - `test_init.py::test_setup_and_unload`: `LOADED` then `NOT_LOADED`.
  - `test_setup_retries_when_unreachable`: first read fails ⇒ `SETUP_RETRY`. `test_setup_auth_failure`: 401 ⇒ `SETUP_ERROR` and a reauth flow.
  - `test_devices`: two servers ⇒ a panel device and two server devices with `via_device` the panel; a third server appearing on the next poll ⇒ a third device without reload; renaming `server_1` to `Stage 1` on the panel ⇒ device name `Stage 1`.
  - `test_remove_device`: a server gone from the panel ⇒ removable; a present server and the panel device ⇒ not.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_coordinator.py tests/test_push.py tests/test_init.py -q`. Expected: FAIL (modules missing).
- [ ] **Step 3: Implement** `coordinator.py`, `push.py`, `entity.py`, `__init__.py` per the Interfaces (until Task 5 and 6 exist, forward only the platforms that exist, then all three).
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat: push-first coordinators with a 1 s backstop and a 6 s grace`.

### Task 5: Sensors and binary sensors

**Files:**
- Create: `custom_components/nodecs/sensor.py`, `custom_components/nodecs/binary_sensor.py`, `custom_components/nodecs/icons.json`; extend `strings.json` / `translations/en.json` with `entity`
- Test: `tests/test_sensor.py`, `tests/test_binary_sensor.py`

**Interfaces:**
- Consumes: `NodeCSServerEntity`, `async_add_server_entities`, `panel_device_info`, `NodeCSRuntime`, `Match.paused_by`, `Match.running_pause`.
- Produces: entity keys (= translation keys, unique-id suffixes) `status`, `phase`, `map`, `team_a`, `team_b`, `team_a_score`, `team_b_score`, `team_a_maps_won`, `team_b_maps_won`, `best_of`, `team_a_timeouts_left`, `team_b_timeouts_left`, `team_a_timeouts_used`, `team_b_timeouts_used`, `pause`, `paused_by`, `pause_started`, `assigned_at`, `live_at`, `ended_at`, `button_bindings` (sensors); `team_a_ready`, `team_b_ready`, `live_updates` (binary sensors). Enum options and binding attribute exactly as spec §4.

- [ ] **Step 1: Write the failing tests** (entity ids `sensor.server_1_<key>`; `no_push` fixture):
  - `test_live_match_values`: a live match ⇒ `phase` `live`, `map` `Nuke`, `team_a` `Alpha`, scores, maps won, best of, timeouts, `pause` `none`, `paused_by` `none`, `live_at` `2026-10-26T08:02:05+00:00`, `team_a_ready` off.
  - `test_no_match`: `phase` `no_match`, `pause` `none`, `paused_by` `none`, `map`/`team_a`/`team_a_score`/`live_at` `unknown`, `team_a_ready` `unknown`.
  - `test_status_values` parametrized: `RUNNING_VALID` ⇒ `running_valid`, `STOPPED` ⇒ `stopped`, `UNKNOWN` ⇒ `unknown`, `null` ⇒ `unknown`, `"REBOOTING"` ⇒ `unknown` (no error logged).
  - `test_unknown_phase_is_unknown`: phase `"OVERTIME"` ⇒ `unknown`, no exception.
  - `test_tactical_pause_by_team_a`: open TACTICAL by `TEAM-A` ⇒ `pause` `tactical`, `paused_by` `team_a`, `pause_started` its start time; next poll with it closed ⇒ `none`, `none`, `unknown`.
  - `test_admin_technical_pause` ⇒ `technical`, `admin`.
  - `test_next_map_with_sides_swapped`: next poll has a new match id with `teamA`=Bravo `TEAM-B`, `teamB`=Alpha `TEAM-A` and an open pause by `TEAM-B` ⇒ `team_a` `Bravo`, `paused_by` `team_a`; entity registry ids unchanged.
  - `test_button_bindings`: two bindings ⇒ state `2`, attribute `bindings == [{"button": "coach-a", "team": "a", "action": "tac_pause"}, {"button": "admin-1", "team": None, "action": "tech_pause"}]`, entity category diagnostic.
  - `test_status_entity_follows_status_coordinator`: status read fails beyond grace while matches succeed ⇒ `status` unavailable, `phase` still available.
  - `test_live_updates_sensor`: `push.connected` False ⇒ off; set True and notify listeners ⇒ on; it belongs to the panel device and is diagnostic.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_sensor.py tests/test_binary_sensor.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** with `SensorEntityDescription` subclasses carrying `value_fn(server: Server) -> StateType | datetime` (and `attr_fn` for bindings); enum sensors map the panel's value through a dict and return `None` with a debug log for anything else; timestamps use `SensorDeviceClass.TIMESTAMP`; counts have no unit and no state class. Strings: names and enum state names; icons for status, phase, map, pause, paused by, timeouts.
- [ ] **Step 4: Run** the same command. Expected: PASS.
- [ ] **Step 5: Commit** `feat: server, match and pause sensors`.

### Task 6: Logo and map images

**Files:**
- Create: `custom_components/nodecs/image.py`; extend strings with the three image names
- Test: `tests/test_image.py`

**Interfaces:**
- Consumes: `NodeCSServerEntity`, `client.fetch_image`.
- Produces: image keys `team_a_logo`, `team_b_logo`, `map_image`; `url_fn(server) -> str | None`.

- [ ] **Step 1: Write the failing tests** (`hass_client` reads `/api/image_proxy/<entity_id>`):
  - `test_team_logo_served_through_ha`: match with team A logo `BASE/api/ui/teams/TEAM-A/logo` → `b"PNGA"` ⇒ proxy returns `b"PNGA"`, content type `image/png`; the panel request carried `Authorization`.
  - `test_fetched_once_per_url`: two proxy reads ⇒ one panel request.
  - `test_url_change_refetches_and_updates_state`: next poll with a different team A ⇒ entity state (last-updated time) changes and the next read fetches the new URL.
  - `test_no_match_no_image`: state `unknown`, proxy answers an error status, no panel request.
  - `test_fetch_failure_logs_and_returns_none`: panel answers 500 ⇒ proxy error status, one warning naming the entity, no exception.
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_image.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement** `NodeCSImage(NodeCSServerEntity, ImageEntity)`: `ImageEntity.__init__(self, hass)`; on each coordinator update compare `url_fn`, and when it changes clear the cache and set `_attr_image_last_updated = dt_util.utcnow()` (or `None` without a URL); `async_image()` returns the cache or calls `fetch_image`, sets `_attr_content_type`, and on `NodeCSError` logs a warning and returns `None`.
- [ ] **Step 4: Run** the full suite `.venv/bin/pytest -q`. Expected: all pass, no warnings about deprecations or lingering tasks.
- [ ] **Step 5: Commit** `feat: team logos and map image through Home Assistant`.

### Task 7: Packaging, docs, live check, ship

**Files:**
- Create: `hacs.json` (`{"name": "NodeCS", "homeassistant": "2025.1.0", "render_readme": true}`), `LICENSE` (MIT, 2026 clovisd), `README.md`, `.github/workflows/validate.yml` (blinkybeacon-hassio's, unchanged jobs)

- [ ] **Step 1: Write the README:** what it does and does not do (read-only); setup (URL, login, Verify SSL); the entity table; how updates work (push, 1 s backstop, status every 10 s, 6 s grace, "Live updates"); a dashboard card example for one server; an automation that spins a BlinkyBeacon for 30 s when `sensor.server_1_paused_by` changes to `team_a` while `sensor.server_1_pause` is `tactical` (trigger with `to: team_a`, condition on pause); a note that Team A/B are the panel's sides; limits; development commands. No product, event or host names.
- [ ] **Step 2: Lint:** `.venv/bin/ruff check custom_components tests && .venv/bin/ruff format --check custom_components tests`. Expected: clean.
- [ ] **Step 3: Live check against the owner's staging panel** with a scratch script outside the repo (read-only: both queries, `fetch_image` on one logo, the push channel for 30 s). Expected: servers parsed, a PNG, the channel open. Nothing written to the panel.
- [ ] **Step 4: Check the history for leaks:** `git log -p | grep -i -E "<product>|<event>|<hosts>|<password>"` (patterns kept in the scratch dir). Expected: no match.
- [ ] **Step 5: Commit, create the public repo `clovisd/nodecs-hassio`, push, wait for CI green, tag and release `v0.1.0`.**
