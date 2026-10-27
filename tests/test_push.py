"""Tests for the push channel: a message means an immediate read."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nodecs.api import NodeCSAuthError, NodeCSConnectionError

from .conftest import FakeChannel, FakePanel, settle, setup_integration


async def test_every_message_triggers_a_read(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    push_channel: FakeChannel,
) -> None:
    """The panel says something changed; the match query runs now, not in a second."""
    await setup_integration(hass, mock_config_entry)
    await settle(hass)
    assert mock_config_entry.runtime_data.push.connected
    before = panel.reads["match"]

    await push_channel.queue.put({"type": "match_updated"})
    await settle(hass)

    assert panel.reads["match"] == before + 1
    assert panel.reads["status"] == 1


async def test_burst_costs_at_most_two_reads(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    push_channel: FakeChannel,
) -> None:
    """Ten messages at once: one read straight away, one more 0.3 s later."""
    await setup_integration(hass, mock_config_entry)
    await settle(hass)
    before = panel.reads["match"]

    for _ in range(10):
        push_channel.queue.put_nowait({"type": "notification", "payload": {}})
    await settle(hass)
    assert panel.reads["match"] == before + 1

    await asyncio.sleep(0.4)
    await settle(hass)
    assert panel.reads["match"] == before + 2


async def test_reconnect_backoff(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Retries wait 1, 2, 4 s; one warning for the outage, one line for the return."""
    channel = FakeChannel()
    open_push = AsyncMock(
        side_effect=[
            NodeCSConnectionError("down"),
            NodeCSAuthError("401"),
            NodeCSConnectionError("down"),
            channel,
        ]
    )
    caplog.set_level(logging.INFO, logger="custom_components.nodecs")
    with (
        patch("custom_components.nodecs.api.NodeCSClient.open_push", open_push),
        patch("custom_components.nodecs.push.sleep", AsyncMock()) as sleep,
    ):
        await setup_integration(hass, mock_config_entry)
        await settle(hass)

    assert [call.args[0] for call in sleep.await_args_list] == [1, 2, 4]
    assert mock_config_entry.runtime_data.push.connected
    ours = [r for r in caplog.records if r.name.startswith("custom_components.nodecs")]
    warnings = [r for r in ours if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "every second" in warnings[0].getMessage()
    assert any(r.levelno == logging.INFO and "back" in r.getMessage() for r in ours)


async def test_drop_after_connected(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    push_channel: FakeChannel,
) -> None:
    """A dropped channel shows as disconnected and is reopened after 1 s."""
    second = FakeChannel()
    open_push = AsyncMock(side_effect=[push_channel, second])
    with (
        patch("custom_components.nodecs.api.NodeCSClient.open_push", open_push),
        patch("custom_components.nodecs.push.sleep", AsyncMock()) as sleep,
    ):
        await setup_integration(hass, mock_config_entry)
        await settle(hass)
        push = mock_config_entry.runtime_data.push
        changes = []
        push.async_add_listener(lambda: changes.append(push.connected))

        await push_channel.queue.put(NodeCSConnectionError("closed"))
        await settle(hass)

    assert push_channel.closed
    assert sleep.await_args_list[0].args[0] == 1
    assert changes == [False, True]
    assert push.connected


async def test_backoff_caps_at_30_s(
    hass: HomeAssistant, panel: FakePanel, mock_config_entry: MockConfigEntry
) -> None:
    """A panel that never opens the channel is retried every 30 s at most."""
    channel = FakeChannel()
    failures = [NodeCSConnectionError("down")] * 7
    open_push = AsyncMock(side_effect=[*failures, channel])
    with (
        patch("custom_components.nodecs.api.NodeCSClient.open_push", open_push),
        patch("custom_components.nodecs.push.sleep", AsyncMock()) as sleep,
    ):
        await setup_integration(hass, mock_config_entry)
        await settle(hass)

    assert [call.args[0] for call in sleep.await_args_list] == [1, 2, 4, 8, 16, 30, 30]


async def test_unload_closes_channel(
    hass: HomeAssistant,
    panel: FakePanel,
    mock_config_entry: MockConfigEntry,
    push_channel: FakeChannel,
) -> None:
    """Removing or reloading the entry closes the channel."""
    await setup_integration(hass, mock_config_entry)
    await settle(hass)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await settle(hass)

    assert push_channel.closed
