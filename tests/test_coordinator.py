"""Tests for the two reads: their cadence, their grace, and a refused login."""

from __future__ import annotations

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .conftest import FakePanel, setup_integration, tick
from .payloads import match_json, pause_json, server_json


async def test_failed_read_keeps_values_within_grace(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """One dropped request mid-pause changes nothing; 6 s of them does."""
    panel.servers = [
        server_json(match=match_json(pauses=[pause_json("TACTICAL", "TEAM-A")]))
    ]
    await setup_integration(hass, mock_config_entry)
    matches = mock_config_entry.runtime_data.matches
    assert matches.data["SRV-1"].match.paused_by == "team_a"

    panel.fail = aiohttp.ClientConnectionError()
    for _ in range(5):
        await tick(hass, freezer)
        assert matches.last_update_success
        assert matches.data["SRV-1"].match.paused_by == "team_a"

    await tick(hass, freezer)
    await tick(hass, freezer)
    assert not matches.last_update_success


async def test_recovery_after_unavailable(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The first good read after the grace brings the values back."""
    await setup_integration(hass, mock_config_entry)
    matches = mock_config_entry.runtime_data.matches
    panel.fail = 502
    for _ in range(8):
        await tick(hass, freezer)
    assert not matches.last_update_success

    panel.fail = None
    await tick(hass, freezer)
    assert matches.last_update_success


async def test_auth_error_starts_reauth_at_once(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A refused login gets no grace: re-authentication starts on the next read."""
    await setup_integration(hass, mock_config_entry)
    panel.fail = 401

    await tick(hass, freezer)

    assert not mock_config_entry.runtime_data.matches.last_update_success
    flows = mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
    assert len(list(flows)) == 1


async def test_matches_every_second_status_every_ten(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The match query is the fast path; the status query is not."""
    await setup_integration(hass, mock_config_entry)
    # Stands in for the status sensors: a coordinator nobody listens to does not poll.
    mock_config_entry.runtime_data.status.async_add_listener(lambda: None)
    panel.reads = {"match": 0, "status": 0}

    for _ in range(10):
        await tick(hass, freezer)

    assert 9 <= panel.reads["match"] <= 11
    assert panel.reads["status"] == 1


async def test_status_grace_is_its_own(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A status read that fails twice, 10 s apart, is past the 6 s grace."""
    await setup_integration(hass, mock_config_entry)
    status = mock_config_entry.runtime_data.status
    status.async_add_listener(lambda: None)
    panel.fail = aiohttp.ClientConnectionError()

    await tick(hass, freezer, 10)
    assert status.last_update_success
    await tick(hass, freezer, 10)
    assert not status.last_update_success
