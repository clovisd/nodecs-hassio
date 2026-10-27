"""Fixtures for the NodeCS tests."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)
from yarl import URL

from custom_components.nodecs.const import DOMAIN, MATCH_QUERY

from .payloads import BASE, GRAPHQL, matches_reply, server_json, status_reply

USERNAME = "admin"
PASSWORD = "hunter2"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let Home Assistant load the integration from custom_components."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A config entry for the panel at panel.example.lan."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="panel.example.lan",
        data={
            CONF_URL: BASE,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_VERIFY_SSL: True,
        },
        unique_id="panel.example.lan:443",
    )


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add the entry and set it up."""
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


class FakePanel:
    """Answers both queries from one list of servers, and counts each read."""

    def __init__(self, aioclient_mock: AiohttpClientMocker) -> None:
        self.servers: list[dict[str, Any]] = [server_json()]
        # An exception to raise, or an HTTP status to answer, instead of data.
        self.fail: BaseException | int | None = None
        # Which query `fail` applies to: "match", "status", or None for both.
        self.fail_kind: str | None = None
        self.reads = {"match": 0, "status": 0}
        aioclient_mock.post(GRAPHQL, side_effect=self._answer)

    async def _answer(
        self, method: str, url: URL, data: dict[str, Any]
    ) -> AiohttpClientMockResponse:
        kind = "match" if data["query"] == MATCH_QUERY else "status"
        self.reads[kind] += 1
        failing = self.fail_kind in (None, kind)
        if failing and isinstance(self.fail, BaseException):
            raise self.fail
        if failing and isinstance(self.fail, int):
            return AiohttpClientMockResponse(method, url, status=self.fail, text="no")
        reply = (
            matches_reply(*self.servers)
            if kind == "match"
            else status_reply(*self.servers)
        )
        return AiohttpClientMockResponse(method, url, json=reply)


@pytest.fixture
def panel(aioclient_mock: AiohttpClientMocker) -> FakePanel:
    """A panel with one idle server, server_1."""
    return FakePanel(aioclient_mock)


class FakeChannel:
    """A push channel the test feeds; silent until it does."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict[str, Any] | BaseException] = asyncio.Queue()
        self.closed = False

    def __aiter__(self) -> FakeChannel:
        return self

    async def __anext__(self) -> dict[str, Any]:
        item = await self.queue.get()
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def push_channel() -> Iterator[FakeChannel]:
    """Every test's push channel opens and stays quiet unless the test speaks."""
    channel = FakeChannel()
    with patch(
        "custom_components.nodecs.api.NodeCSClient.open_push",
        AsyncMock(return_value=channel),
    ):
        yield channel


async def settle(hass: HomeAssistant) -> None:
    """Let background tasks (the push listener) run until they wait again."""
    for _ in range(20):
        await asyncio.sleep(0)
    await hass.async_block_till_done()


async def tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float = 1
) -> None:
    """Move time on and run whatever was due."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
