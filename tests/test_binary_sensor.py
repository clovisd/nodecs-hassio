"""Tests for the ready flags and the Live updates sensor."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nodecs.api import NodeCSConnectionError
from custom_components.nodecs.const import DOMAIN

from .conftest import FakeChannel, FakePanel, settle, setup_integration, tick
from .payloads import match_json, server_json

LIVE_UPDATES = "binary_sensor.panel_example_lan_live_updates"


async def test_ready_flags(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The ready flags follow the warmup."""
    panel.servers = [server_json(match=match_json(phase="WARMUP", teamAReady=True))]
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("binary_sensor.server_1_team_a_ready").state == "on"
    assert hass.states.get("binary_sensor.server_1_team_b_ready").state == "off"

    panel.servers = [
        server_json(match=match_json(phase="WARMUP", teamAReady=True, teamBReady=True))
    ]
    await tick(hass, freezer)
    assert hass.states.get("binary_sensor.server_1_team_b_ready").state == "on"


async def test_live_updates_sensor(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    push_channel: FakeChannel,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """On while the push channel is open, off while it is being reopened."""
    await setup_integration(hass, mock_config_entry)
    await settle(hass)
    assert hass.states.get(LIVE_UPDATES).state == "on"

    entry = entity_registry.async_get(LIVE_UPDATES)
    assert entry.entity_category is EntityCategory.DIAGNOSTIC
    device = device_registry.async_get(entry.device_id)
    assert (DOMAIN, f"{mock_config_entry.entry_id}_panel") in device.identifiers

    reopen = asyncio.Event()

    async def wait(_seconds: float) -> None:
        await reopen.wait()

    with patch("custom_components.nodecs.push.sleep", side_effect=wait):
        await push_channel.queue.put(NodeCSConnectionError("closed"))
        await settle(hass)
        assert hass.states.get(LIVE_UPDATES).state == "off"

        reopen.set()
        await settle(hass)
        assert hass.states.get(LIVE_UPDATES).state == "on"
