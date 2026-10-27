"""Tests for setting the panel up, its devices, and taking it down."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nodecs import async_remove_config_entry_device
from custom_components.nodecs.const import DOMAIN, STATUS_TIMEOUT

from .conftest import FakePanel, setup_integration, tick
from .payloads import BASE, server_json


async def test_setup_and_unload(
    hass: HomeAssistant, panel: FakePanel, mock_config_entry: MockConfigEntry
) -> None:
    """The entry loads with both reads done, and unloads cleanly."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert panel.reads == {"match": 1, "status": 1}

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_retries_when_unreachable(
    hass: HomeAssistant, panel: FakePanel, mock_config_entry: MockConfigEntry
) -> None:
    """A panel that does not answer at start-up is retried later."""
    panel.fail = aiohttp.ClientConnectionError()
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_failure(
    hass: HomeAssistant, panel: FakePanel, mock_config_entry: MockConfigEntry
) -> None:
    """A refused login at start-up asks for it again."""
    panel.fail = 401
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert len(list(mock_config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})))


def _device(hass: HomeAssistant, entry: MockConfigEntry, key: str) -> dr.DeviceEntry:
    wanted = (DOMAIN, f"{entry.entry_id}_{key}")
    devices = dr.async_entries_for_config_entry(dr.async_get(hass), entry.entry_id)
    (device,) = [device for device in devices if wanted in device.identifiers]
    return device


async def test_devices(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A panel device, a device per server under it, new ones live, renames followed."""
    panel.servers = [server_json("SRV-1", "server_1"), server_json("SRV-2", "server_2")]
    await setup_integration(hass, mock_config_entry)

    panel_device = _device(hass, mock_config_entry, "panel")
    assert panel_device.name == "panel.example.lan"
    assert panel_device.model == "Panel"
    server = _device(hass, mock_config_entry, "SRV-1")
    assert server.name == "server_1"
    assert server.model == "CS2 server"
    assert server.manufacturer == "NodeCS"
    assert server.via_device_id == panel_device.id
    assert server.configuration_url == BASE
    _device(hass, mock_config_entry, "SRV-2")

    panel.servers = [
        server_json("SRV-1", "Stage 1"),
        server_json("SRV-2", "server_2"),
        server_json("SRV-3", "server_3"),
    ]
    await tick(hass, freezer)

    assert _device(hass, mock_config_entry, "SRV-3").via_device_id == panel_device.id
    assert _device(hass, mock_config_entry, "SRV-1").name == "Stage 1"


async def test_user_rename_is_kept(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A name given in Home Assistant wins over the panel's."""
    await setup_integration(hass, mock_config_entry)
    registry = dr.async_get(hass)
    device = _device(hass, mock_config_entry, "SRV-1")
    registry.async_update_device(device.id, name_by_user="Main stage")

    panel.servers = [server_json("SRV-1", "Stage 1")]
    await tick(hass, freezer)

    device = _device(hass, mock_config_entry, "SRV-1")
    assert device.name_by_user == "Main stage"
    assert device.name == "Stage 1"


async def test_remove_device(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Only servers the panel no longer has can be deleted."""
    panel.servers = [server_json("SRV-1"), server_json("SRV-2", "server_2")]
    await setup_integration(hass, mock_config_entry)
    panel.servers = [server_json("SRV-1")]
    await tick(hass, freezer)

    remove = async_remove_config_entry_device
    assert await remove(
        hass, mock_config_entry, _device(hass, mock_config_entry, "SRV-2")
    )
    assert not await remove(
        hass, mock_config_entry, _device(hass, mock_config_entry, "SRV-1")
    )
    assert not await remove(
        hass, mock_config_entry, _device(hass, mock_config_entry, "panel")
    )


async def test_setup_does_not_wait_for_status(
    hass: HomeAssistant, panel: FakePanel, mock_config_entry: MockConfigEntry
) -> None:
    """A status read that fails (a game server slow to probe) does not block setup."""
    panel.fail = aiohttp.ClientConnectionError()
    panel.fail_kind = "status"
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.server_1_status").state == STATE_UNAVAILABLE
    assert hass.states.get("sensor.server_1_phase").state == "no_match"


async def test_status_read_has_its_own_timeout(
    hass: HomeAssistant, panel: FakePanel, mock_config_entry: MockConfigEntry
) -> None:
    """The status read may take longer than the fast path's 3 s."""
    fetch = AsyncMock(return_value={"SRV-1": "RUNNING_VALID"})
    with patch("custom_components.nodecs.api.NodeCSClient.fetch_statuses", fetch):
        await setup_integration(hass, mock_config_entry)

    assert STATUS_TIMEOUT == 10
    assert fetch.await_args.kwargs["timeout"] == STATUS_TIMEOUT
