"""Tests for the team logos and map image, served through Home Assistant."""

from __future__ import annotations

import logging

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)
from pytest_homeassistant_custom_component.typing import ClientSessionGenerator

from .conftest import FakePanel, setup_integration, tick
from .payloads import BASE, match_json, server_json, team_json

LOGO_A = f"{BASE}/api/ui/teams/TEAM-A/logo"
LOGO_C = f"{BASE}/api/ui/teams/TEAM-C/logo"
ENTITY = "image.server_1_team_a_logo"


def _logo_requests(aioclient_mock: AiohttpClientMocker, url: str) -> list:
    return [
        call
        for call in aioclient_mock.mock_calls
        if call[0].lower() == "get" and str(call[1]) == url
    ]


async def _proxy(hass_client: ClientSessionGenerator, entity_id: str):
    client = await hass_client()
    return await client.get(f"/api/image_proxy/{entity_id}")


async def test_team_logo_served_through_ha(
    hass: HomeAssistant,
    panel: FakePanel,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """The logo behind the panel's login reaches any dashboard."""
    panel.servers = [server_json(match=match_json())]
    aioclient_mock.get(LOGO_A, content=b"PNGA", headers={"Content-Type": "image/png"})
    await setup_integration(hass, mock_config_entry)

    response = await _proxy(hass_client, ENTITY)

    assert response.status == 200
    assert await response.read() == b"PNGA"
    assert response.content_type == "image/png"
    (request,) = _logo_requests(aioclient_mock, LOGO_A)
    assert request[3]["Authorization"].startswith("Basic ")
    assert hass.states.get("image.server_1_map").state != STATE_UNKNOWN


async def test_fetched_once_per_url(
    hass: HomeAssistant,
    panel: FakePanel,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Every dashboard view does not cost the panel a request."""
    panel.servers = [server_json(match=match_json())]
    aioclient_mock.get(LOGO_A, content=b"PNGA", headers={"Content-Type": "image/png"})
    await setup_integration(hass, mock_config_entry)

    await _proxy(hass_client, ENTITY)
    await _proxy(hass_client, ENTITY)

    assert len(_logo_requests(aioclient_mock, LOGO_A)) == 1


async def test_url_change_refetches(
    hass: HomeAssistant,
    panel: FakePanel,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A new team A means a new picture, and a new state for automations."""
    panel.servers = [server_json(match=match_json())]
    aioclient_mock.get(LOGO_A, content=b"PNGA", headers={"Content-Type": "image/png"})
    aioclient_mock.get(LOGO_C, content=b"PNGC", headers={"Content-Type": "image/png"})
    await setup_integration(hass, mock_config_entry)
    await _proxy(hass_client, ENTITY)
    before = hass.states.get(ENTITY).state

    panel.servers = [
        server_json(match=match_json(teamA=team_json("TEAM-C", "Charlie")))
    ]
    await tick(hass, freezer)

    assert hass.states.get(ENTITY).state != before
    response = await _proxy(hass_client, ENTITY)
    assert await response.read() == b"PNGC"


async def test_no_match_no_image(
    hass: HomeAssistant,
    panel: FakePanel,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
) -> None:
    """No match, no picture, and nothing asked of the panel."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(ENTITY).state == STATE_UNKNOWN
    response = await _proxy(hass_client, ENTITY)
    assert response.status != 200
    assert not [c for c in aioclient_mock.mock_calls if c[0].lower() == "get"]


async def test_fetch_failure_logs_and_returns_nothing(
    hass: HomeAssistant,
    panel: FakePanel,
    aioclient_mock: AiohttpClientMocker,
    mock_config_entry: MockConfigEntry,
    hass_client: ClientSessionGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A logo the panel cannot serve is a warning, not a crash."""
    panel.servers = [server_json(match=match_json())]
    aioclient_mock.get(LOGO_A, status=500)
    await setup_integration(hass, mock_config_entry)

    response = await _proxy(hass_client, ENTITY)

    assert response.status != 200
    ours = [
        r
        for r in caplog.records
        if r.name.startswith("custom_components.nodecs")
        and r.levelno == logging.WARNING
    ]
    assert len(ours) == 1
    assert ENTITY in ours[0].getMessage()
