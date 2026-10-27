"""Tests for the panel client."""

from __future__ import annotations

import json
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.nodecs.api import (
    NodeCSAuthError,
    NodeCSCertificateError,
    NodeCSClient,
    NodeCSConnectionError,
    NodeCSResponseError,
)
from custom_components.nodecs.const import MATCH_QUERY, PUSH_HEARTBEAT, STATUS_QUERY

from .conftest import PASSWORD, USERNAME
from .payloads import BASE, GRAPHQL, matches_reply, server_json, status_reply

# base64("admin:hunter2")
BASIC = "Basic YWRtaW46aHVudGVyMg=="


@pytest.fixture(autouse=True)
def push_channel() -> None:
    """These tests exercise the real open_push, not the shared fake channel."""


def _client(hass: HomeAssistant, base: str = BASE) -> NodeCSClient:
    return NodeCSClient(async_get_clientsession(hass), base, USERNAME, PASSWORD)


async def test_fetch_matches_posts_the_pinned_query(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """One POST, the exact match query, the login in the header."""
    aioclient_mock.post(GRAPHQL, json=matches_reply(server_json()))

    servers = await _client(hass).fetch_matches()

    assert list(servers) == ["SRV-1"]
    assert aioclient_mock.call_count == 1
    method, url, body, headers = aioclient_mock.mock_calls[0]
    assert method.lower() == "post"
    assert str(url) == GRAPHQL
    assert body == {"query": MATCH_QUERY}
    assert headers["Authorization"] == BASIC


async def test_fetch_statuses_posts_the_status_query(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The status query, nothing else."""
    aioclient_mock.post(GRAPHQL, json=status_reply(server_json()))

    assert await _client(hass).fetch_statuses() == {"SRV-1": "RUNNING_VALID"}
    assert aioclient_mock.mock_calls[0][2] == {"query": STATUS_QUERY}


def _ssl_error() -> aiohttp.ClientSSLError:
    return aiohttp.ClientSSLError(MagicMock(), OSError("certificate verify failed"))


@pytest.mark.parametrize(
    ("reply", "error"),
    [
        ({"status": 401, "text": "<html>401</html>"}, NodeCSAuthError),
        ({"exc": aiohttp.ClientConnectionError()}, NodeCSConnectionError),
        ({"exc": TimeoutError()}, NodeCSConnectionError),
        ({"exc": _ssl_error()}, NodeCSCertificateError),
        ({"status": 502, "text": "bad gateway"}, NodeCSResponseError),
        ({"text": "<html>login</html>"}, NodeCSResponseError),
        (
            {"json": {"errors": [{"message": "boom"}], "data": None}},
            NodeCSResponseError,
        ),
        ({"json": {"data": {"cs2Servers": [{"name": "x"}]}}}, NodeCSResponseError),
        ({"json": ["not", "an", "object"]}, NodeCSResponseError),
    ],
)
async def test_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    reply: dict[str, Any],
    error: type[Exception],
) -> None:
    """Every way a read can go wrong maps to one error type."""
    aioclient_mock.post(GRAPHQL, **reply)

    with pytest.raises(error):
        await _client(hass).fetch_matches()


async def test_graphql_error_message_is_kept(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The panel's own words reach the log."""
    aioclient_mock.post(GRAPHQL, json={"errors": [{"message": "boom"}], "data": None})

    with pytest.raises(NodeCSResponseError, match="boom"):
        await _client(hass).fetch_matches()


async def test_fetch_image_sends_login_to_panel_host(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A logo on the panel is fetched with the login."""
    url = f"{BASE}/api/ui/teams/T/logo"
    aioclient_mock.get(url, content=b"PNG", headers={"Content-Type": "image/png"})

    assert await _client(hass).fetch_image(url) == (b"PNG", "image/png")
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == BASIC


async def test_fetch_image_other_host_without_login(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A logo anywhere else never gets the password."""
    url = "https://cdn.example.org/a.png"
    aioclient_mock.get(url, content=b"PNG", headers={"Content-Type": "image/png"})

    assert await _client(hass).fetch_image(url) == (b"PNG", "image/png")
    headers = aioclient_mock.mock_calls[0][3] or {}
    assert "Authorization" not in headers


async def test_fetch_image_same_host_other_port_without_login(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Another port on the same host is another origin."""
    url = "https://panel.example.lan:8443/a.png"
    aioclient_mock.get(url, content=b"PNG", headers={"Content-Type": "image/png"})

    await _client(hass).fetch_image(url)
    assert "Authorization" not in (aioclient_mock.mock_calls[0][3] or {})


async def test_fetch_image_rejects_non_image(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A login page is not a logo."""
    url = f"{BASE}/api/ui/teams/T/logo"
    aioclient_mock.get(url, text="<html>", headers={"Content-Type": "text/html"})

    with pytest.raises(NodeCSResponseError):
        await _client(hass).fetch_image(url)


async def test_fetch_image_errors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A failed logo request is a client error, not a crash."""
    url = f"{BASE}/api/ui/teams/T/logo"
    aioclient_mock.get(url, status=500)

    with pytest.raises(NodeCSResponseError):
        await _client(hass).fetch_image(url)


class FakeWebSocket:
    """Plays back a list of frames, then reports the socket closed."""

    def __init__(self, frames: list[aiohttp.WSMessage]) -> None:
        self._frames = list(frames)
        self.close = AsyncMock()

    async def receive(self, timeout: float | None = None) -> aiohttp.WSMessage:
        if self._frames:
            return self._frames.pop(0)
        return aiohttp.WSMessage(aiohttp.WSMsgType.CLOSED, None, None)


def _text(data: str) -> aiohttp.WSMessage:
    return aiohttp.WSMessage(aiohttp.WSMsgType.TEXT, data, None)


async def test_push_channel_yields_json_objects(hass: HomeAssistant) -> None:
    """Only JSON-object text frames come out; a close ends the channel."""
    client = _client(hass)
    ws = FakeWebSocket(
        [
            _text(json.dumps({"type": "match_updated"})),
            _text("not json"),
            _text("[1]"),
            aiohttp.WSMessage(aiohttp.WSMsgType.BINARY, b"\x00", None),
            _text(json.dumps({"type": "notification", "payload": {"ok": True}})),
        ]
    )
    with patch.object(client._session, "ws_connect", AsyncMock(return_value=ws)):
        channel = await client.open_push()

    received = []
    with pytest.raises(NodeCSConnectionError):
        async for message in channel:
            received.append(message)
    assert received == [
        {"type": "match_updated"},
        {"type": "notification", "payload": {"ok": True}},
    ]

    await channel.close()
    ws.close.assert_awaited()


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        (BASE, "wss://panel.example.lan/api/ui/notifications/subscribe"),
        ("http://10.0.0.5:8080", "ws://10.0.0.5:8080/api/ui/notifications/subscribe"),
    ],
)
async def test_open_push_url_and_auth(
    hass: HomeAssistant, base: str, expected: str
) -> None:
    """The channel is opened with the login and a heartbeat."""
    client = _client(hass, base)
    connect = AsyncMock(return_value=FakeWebSocket([]))
    with patch.object(client._session, "ws_connect", connect):
        await client.open_push()

    args, kwargs = connect.call_args
    assert str(args[0]) == expected
    assert kwargs["headers"]["Authorization"] == BASIC
    assert kwargs["heartbeat"] == PUSH_HEARTBEAT


@pytest.mark.parametrize(
    ("exc", "error"),
    [
        (
            aiohttp.WSServerHandshakeError(MagicMock(), (), status=401),
            NodeCSAuthError,
        ),
        (
            aiohttp.WSServerHandshakeError(MagicMock(), (), status=502),
            NodeCSConnectionError,
        ),
        (aiohttp.ClientConnectionError(), NodeCSConnectionError),
        (TimeoutError(), NodeCSConnectionError),
    ],
)
async def test_open_push_errors(
    hass: HomeAssistant, exc: Exception, error: type[Exception]
) -> None:
    """A refused or failed handshake maps to the client's errors."""
    client = _client(hass)
    with (
        patch.object(client._session, "ws_connect", AsyncMock(side_effect=exc)),
        pytest.raises(error),
    ):
        await client.open_push()


# Everything the panel's schema could leak, and that no query may ever ask for.
SECRETS = {
    "config",
    "password",
    "livePassword",
    "rconPassword",
    "tvPassword",
    "tvPassword1",
    "tvRelayPassword",
    "logsWebSocketUrl",
    "ip",
    "port",
    "apiKey",
    "buttonApiKey",
    "basicAuthPass",
}


def _fields(query: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", query))


def test_match_query_asks_only_for_what_is_shown() -> None:
    """A new field in the match query is a reviewed change, and never a secret."""
    assert _fields(MATCH_QUERY) == {
        "query", "HomeAssistantMatches", "cs2Servers", "id", "name", "match",
        "phase", "bestOfX", "bestOfXAScore", "bestOfXBScore", "teamA", "teamB",
        "logoUrl", "map", "teamAReady", "teamBReady", "teamAScore", "teamBScore",
        "teamATimeoutsUsed", "teamBTimeoutsUsed", "teamATimeoutsLeft",
        "teamBTimeoutsLeft", "assignedAt", "liveAt", "endedAt", "pauses", "reason",
        "startedAt", "team", "buttonBindings", "buttonID", "action",
    }  # fmt: skip
    assert not _fields(MATCH_QUERY) & SECRETS


def test_status_query_asks_only_for_status() -> None:
    """The status query names the server and its status, nothing else."""
    assert _fields(STATUS_QUERY) == {
        "query",
        "HomeAssistantStatus",
        "cs2Servers",
        "id",
        "status",
    }
