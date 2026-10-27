"""A read-only client for the panel's GraphQL API, its logos and its push channel."""

from __future__ import annotations

import asyncio
import base64
from http import HTTPStatus
import json
from typing import Any

import aiohttp
from yarl import URL

from .const import (
    GRAPHQL_PATH,
    IMAGE_TIMEOUT,
    MATCH_QUERY,
    PUSH_HEARTBEAT,
    PUSH_PATH,
    REQUEST_TIMEOUT,
    SETUP_TIMEOUT,
    STATUS_QUERY,
)
from .models import Server, parse_matches, parse_statuses


class NodeCSError(Exception):
    """The panel did not give what was asked for."""


class NodeCSConnectionError(NodeCSError):
    """The panel did not answer, or the connection broke."""


class NodeCSCertificateError(NodeCSConnectionError):
    """The panel's certificate is not trusted."""


class NodeCSAuthError(NodeCSError):
    """The panel refused the login."""


class NodeCSResponseError(NodeCSError):
    """The panel answered with something this client does not understand."""


_CLOSED = (
    aiohttp.WSMsgType.CLOSE,
    aiohttp.WSMsgType.CLOSING,
    aiohttp.WSMsgType.CLOSED,
    aiohttp.WSMsgType.ERROR,
)


class PushChannel:
    """The panel's push channel: each JSON object it sends, until it closes."""

    def __init__(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        self._ws = ws

    def __aiter__(self) -> PushChannel:
        return self

    async def __anext__(self) -> dict[str, Any]:
        while True:
            try:
                message = await self._ws.receive()
            except (TimeoutError, aiohttp.ClientError) as err:
                raise NodeCSConnectionError(f"push channel failed: {err!r}") from err
            if message.type in _CLOSED:
                raise NodeCSConnectionError(
                    f"push channel closed ({message.type.name.lower()})"
                )
            if message.type is not aiohttp.WSMsgType.TEXT:
                continue
            try:
                data = json.loads(message.data)
            except ValueError:
                continue
            if isinstance(data, dict):
                return data

    async def close(self) -> None:
        """Close the channel."""
        await self._ws.close()


class NodeCSClient:
    """Reads one panel. Never sends anything that changes it."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        username: str,
        password: str,
    ) -> None:
        self._session = session
        self._base = URL(base_url)
        token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        self._headers = {"Authorization": f"Basic {token}"}

    @property
    def base_url(self) -> str:
        """The panel's address, without a trailing slash."""
        return str(self._base)

    async def fetch_matches(
        self, timeout: float = REQUEST_TIMEOUT
    ) -> dict[str, Server]:
        """Every server and the match on it."""
        reply = await self._query(MATCH_QUERY, timeout)
        try:
            return parse_matches(reply)
        except ValueError as err:
            raise NodeCSResponseError(f"unexpected match reply: {err}") from err

    async def fetch_statuses(
        self, timeout: float = REQUEST_TIMEOUT
    ) -> dict[str, str | None]:
        """Every server's status, as the panel names it."""
        reply = await self._query(STATUS_QUERY, timeout)
        try:
            return parse_statuses(reply)
        except ValueError as err:
            raise NodeCSResponseError(f"unexpected status reply: {err}") from err

    async def fetch_image(self, url: str) -> tuple[bytes, str]:
        """An image and its content type; the login goes only to the panel itself."""
        target = URL(url)
        headers = self._headers if self._same_origin(target) else None
        try:
            async with (
                asyncio.timeout(IMAGE_TIMEOUT),
                self._session.get(
                    target, headers=headers, allow_redirects=False
                ) as response,
            ):
                if response.status != HTTPStatus.OK:
                    raise NodeCSResponseError(f"{url} answered {response.status}")
                content_type = (
                    response.headers.get("Content-Type", "").split(";")[0].strip()
                )
                if not content_type.startswith("image/"):
                    raise NodeCSResponseError(f"{url} is {content_type or 'untyped'}")
                return await response.read(), content_type
        except aiohttp.ClientSSLError as err:
            raise NodeCSCertificateError(str(err)) from err
        except (TimeoutError, aiohttp.ClientError) as err:
            raise NodeCSConnectionError(f"{url}: {err!r}") from err

    async def open_push(self) -> PushChannel:
        """Open the push channel."""
        scheme = "wss" if self._base.scheme == "https" else "ws"
        url = self._base.with_scheme(scheme).with_path(PUSH_PATH)
        try:
            async with asyncio.timeout(SETUP_TIMEOUT):
                ws = await self._session.ws_connect(
                    url, headers=self._headers, heartbeat=PUSH_HEARTBEAT
                )
        except aiohttp.WSServerHandshakeError as err:
            if err.status == HTTPStatus.UNAUTHORIZED:
                raise NodeCSAuthError("push channel refused the login") from err
            raise NodeCSConnectionError(f"push channel answered {err.status}") from err
        except aiohttp.ClientSSLError as err:
            raise NodeCSCertificateError(str(err)) from err
        except (TimeoutError, aiohttp.ClientError) as err:
            raise NodeCSConnectionError(f"push channel: {err!r}") from err
        return PushChannel(ws)

    def _same_origin(self, url: URL) -> bool:
        return (url.scheme, url.host, url.port) == (
            self._base.scheme,
            self._base.host,
            self._base.port,
        )

    async def _query(self, query: str, timeout: float) -> dict[str, Any]:
        try:
            async with (
                asyncio.timeout(timeout),
                self._session.post(
                    self._base.with_path(GRAPHQL_PATH),
                    json={"query": query},
                    headers=self._headers,
                    allow_redirects=False,
                ) as response,
            ):
                if response.status == HTTPStatus.UNAUTHORIZED:
                    raise NodeCSAuthError("the panel refused the login")
                if response.status != HTTPStatus.OK:
                    raise NodeCSResponseError(f"the panel answered {response.status}")
                try:
                    body = await response.json(content_type=None)
                except ValueError as err:
                    raise NodeCSResponseError("the panel did not answer JSON") from err
        except aiohttp.ClientSSLError as err:
            raise NodeCSCertificateError(str(err)) from err
        except (TimeoutError, aiohttp.ClientError) as err:
            raise NodeCSConnectionError(repr(err)) from err

        if not isinstance(body, dict):
            raise NodeCSResponseError(f"the panel answered {body!r}")
        if errors := body.get("errors"):
            first = errors[0] if isinstance(errors, list) and errors else errors
            message = first.get("message") if isinstance(first, dict) else first
            raise NodeCSResponseError(f"the panel reported: {message}")
        return body
