"""Tests for the server, match and pause sensors."""

from __future__ import annotations

import logging

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import FakePanel, setup_integration, tick
from .payloads import match_json, pause_json, server_json, team_json


def _state(hass: HomeAssistant, name: str, platform: str = "sensor") -> str:
    state = hass.states.get(f"{platform}.server_1_{name}")
    assert state is not None, f"{platform}.server_1_{name} does not exist"
    return state.state


async def test_live_match_values(
    hass: HomeAssistant, panel: FakePanel, mock_config_entry: MockConfigEntry
) -> None:
    """Every value of a live match, as Home Assistant shows it."""
    panel.servers = [server_json(match=match_json(teamAScore=7, bestOfXBScore=1))]
    await setup_integration(hass, mock_config_entry)

    expected = {
        "status": "running_valid",
        "phase": "live",
        "map": "Nuke",
        "team_a": "Alpha",
        "team_b": "Bravo",
        "team_a_score": "7",
        "team_b_score": "4",
        "team_a_maps_won": "0",
        "team_b_maps_won": "1",
        "best_of": "3",
        "team_a_timeouts_left": "3",
        "team_b_timeouts_left": "2",
        "team_a_timeouts_used": "0",
        "team_b_timeouts_used": "1",
        "pause": "none",
        "paused_by": "none",
        "pause_started": STATE_UNKNOWN,
        "assigned": "2026-10-26T07:33:45+00:00",
        "went_live": "2026-10-26T08:02:05+00:00",
        "ended": STATE_UNKNOWN,
        "button_bindings": "0",
    }
    assert {name: _state(hass, name) for name in expected} == expected
    assert _state(hass, "team_a_ready", "binary_sensor") == "off"
    assert _state(hass, "team_b_ready", "binary_sensor") == "off"


async def test_no_match(
    hass: HomeAssistant, panel: FakePanel, mock_config_entry: MockConfigEntry
) -> None:
    """A server with nothing assigned: no match, not paused, the rest unknown."""
    await setup_integration(hass, mock_config_entry)

    assert _state(hass, "phase") == "no_match"
    assert _state(hass, "pause") == "none"
    assert _state(hass, "paused_by") == "none"
    for name in ("map", "team_a", "team_a_score", "went_live", "button_bindings"):
        assert _state(hass, name) == STATE_UNKNOWN, name
    assert _state(hass, "team_a_ready", "binary_sensor") == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("RUNNING_VALID", "running_valid"),
        ("RUNNING_INVALID", "running_invalid"),
        ("STARTING", "starting"),
        ("STOPPED", "stopped"),
        ("UNKNOWN", STATE_UNKNOWN),
        (None, STATE_UNKNOWN),
        ("REBOOTING", STATE_UNKNOWN),
    ],
)
async def test_status_values(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    status: str | None,
    expected: str,
) -> None:
    """The panel's statuses; its UNKNOWN, and anything new, show as unknown."""
    panel.servers = [server_json(status=status)]
    await setup_integration(hass, mock_config_entry)

    assert _state(hass, "status") == expected
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


async def test_unknown_phase_is_unknown(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A phase a newer panel adds is unknown, not an error."""
    panel.servers = [server_json(match=match_json(phase="OVERTIME"))]
    await setup_integration(hass, mock_config_entry)

    assert _state(hass, "phase") == STATE_UNKNOWN
    assert not [r for r in caplog.records if r.levelno >= logging.ERROR]


async def test_tactical_pause_by_team_a(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A team's tactical timeout, from start to end."""
    panel.servers = [
        server_json(
            match=match_json(
                pauses=[
                    pause_json("TACTICAL", "TEAM-A", started="2026-10-27T18:17:37Z")
                ]
            )
        )
    ]
    await setup_integration(hass, mock_config_entry)
    assert _state(hass, "pause") == "tactical"
    assert _state(hass, "paused_by") == "team_a"
    assert _state(hass, "pause_started") == "2026-10-27T18:17:37+00:00"

    panel.servers = [
        server_json(
            match=match_json(
                pauses=[
                    pause_json(
                        "TACTICAL",
                        "TEAM-A",
                        started="2026-10-27T18:17:37Z",
                        ended="2026-10-27T18:18:07Z",
                    )
                ]
            )
        )
    ]
    await tick(hass, freezer)
    assert _state(hass, "pause") == "none"
    assert _state(hass, "paused_by") == "none"
    assert _state(hass, "pause_started") == STATE_UNKNOWN


async def test_admin_technical_pause(
    hass: HomeAssistant, panel: FakePanel, mock_config_entry: MockConfigEntry
) -> None:
    """A technical pause called from the panel has no team: admin."""
    panel.servers = [server_json(match=match_json(pauses=[pause_json("TECHNICAL")]))]
    await setup_integration(hass, mock_config_entry)
    assert _state(hass, "pause") == "technical"
    assert _state(hass, "paused_by") == "admin"


async def test_next_map_with_sides_swapped(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
) -> None:
    """Team A is whoever the current match says; entity ids never move."""
    panel.servers = [server_json(match=match_json())]
    await setup_integration(hass, mock_config_entry)
    before = {
        e.entity_id
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }

    panel.servers = [
        server_json(
            match=match_json(
                id="MATCH-2",
                teamA=team_json("TEAM-B", "Bravo"),
                teamB=team_json("TEAM-A", "Alpha"),
                pauses=[pause_json("TACTICAL", "TEAM-B")],
            )
        )
    ]
    await tick(hass, freezer)

    assert _state(hass, "team_a") == "Bravo"
    assert _state(hass, "paused_by") == "team_a"
    after = {
        e.entity_id
        for e in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert after == before


async def test_button_bindings(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Bound buttons: a count, with the bindings as an attribute."""
    panel.servers = [
        server_json(
            match=match_json(
                buttonBindings=[
                    {"buttonID": "coach-a", "action": "TAC_PAUSE", "team": "A"},
                    {"buttonID": "admin-1", "action": "TECH_PAUSE", "team": None},
                ]
            )
        )
    ]
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("sensor.server_1_button_bindings")
    assert state.state == "2"
    assert state.attributes["bindings"] == [
        {"button": "coach-a", "team": "a", "action": "tac_pause"},
        {"button": "admin-1", "team": None, "action": "tech_pause"},
    ]
    entry = entity_registry.async_get("sensor.server_1_button_bindings")
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_status_entity_follows_status_read(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failing status read takes down the status sensor only."""
    await setup_integration(hass, mock_config_entry)
    panel.fail = aiohttp.ClientConnectionError()
    panel.fail_kind = "status"

    for _ in range(20):
        await tick(hass, freezer)

    assert _state(hass, "status") == STATE_UNAVAILABLE
    assert _state(hass, "phase") == "no_match"


async def test_server_removed_from_panel(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A server the panel no longer lists is unavailable, not stale."""
    panel.servers = [server_json("SRV-1"), server_json("SRV-2", "server_2")]
    await setup_integration(hass, mock_config_entry)

    panel.servers = [server_json("SRV-2", "server_2")]
    await tick(hass, freezer)

    assert _state(hass, "phase") == STATE_UNAVAILABLE
    assert hass.states.get("sensor.server_2_phase").state == "no_match"


async def test_new_server_gets_entities(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A server added on the panel shows up without a reload."""
    await setup_integration(hass, mock_config_entry)

    panel.servers = [server_json(), server_json("SRV-2", "server_2")]
    await tick(hass, freezer)
    await tick(hass, freezer, 10)

    assert hass.states.get("sensor.server_2_phase").state == "no_match"
    assert hass.states.get("sensor.server_2_status").state == "running_valid"
