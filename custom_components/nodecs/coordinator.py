"""The two reads of the panel: matches fast, server status slow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import NodeCSAuthError, NodeCSClient, NodeCSError
from .const import (
    DOMAIN,
    MATCH_INTERVAL,
    REFRESH_COOLDOWN,
    STALE_AFTER,
    STATUS_INTERVAL,
)
from .models import Server

if TYPE_CHECKING:
    from .push import PushListener

_LOGGER = logging.getLogger(__name__)


@dataclass
class NodeCSRuntime:
    """Everything one panel entry runs."""

    client: NodeCSClient
    matches: MatchCoordinator
    status: StatusCoordinator
    push: PushListener


type NodeCSConfigEntry = ConfigEntry[NodeCSRuntime]


class NodeCSCoordinator[T](DataUpdateCoordinator[T]):
    """A read of the panel that rides out short outages.

    A failed read keeps the last values while it is the first failure in a row or
    the last good read is under STALE_AFTER old, so one dropped request never
    flips every entity to unavailable and back. A refused login gets no grace.
    """

    config_entry: NodeCSConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: NodeCSConfigEntry,
        client: NodeCSClient,
        name: str,
        update_interval: timedelta,
        request_refresh_debouncer: Debouncer | None = None,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title} {name}",
            update_interval=update_interval,
            always_update=False,
            request_refresh_debouncer=request_refresh_debouncer,
        )
        self.client = client
        self._last_good: datetime | None = None
        self._failures = 0

    async def _fetch(self) -> T:
        raise NotImplementedError

    async def _async_update_data(self) -> T:
        try:
            data = await self._fetch()
        except NodeCSAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NodeCSError as err:
            self._failures += 1
            if (
                self.data is not None
                and self._last_good is not None
                and (
                    self._failures == 1
                    or dt_util.utcnow() - self._last_good < STALE_AFTER
                )
            ):
                _LOGGER.debug("%s: keeping the last values after %s", self.name, err)
                return self.data
            raise UpdateFailed(f"{self.name}: {err}") from err
        self._failures = 0
        self._last_good = dt_util.utcnow()
        return data


class MatchCoordinator(NodeCSCoordinator[dict[str, Server]]):
    """Every server and its match: read every second and on every push message.

    Push messages that arrive while a read runs are covered by one more read
    REFRESH_COOLDOWN later, not Home Assistant's default 10 s.
    """

    def __init__(
        self, hass: HomeAssistant, entry: NodeCSConfigEntry, client: NodeCSClient
    ) -> None:
        super().__init__(
            hass,
            entry,
            client,
            "matches",
            MATCH_INTERVAL,
            Debouncer(hass, _LOGGER, cooldown=REFRESH_COOLDOWN, immediate=True),
        )

    async def _fetch(self) -> dict[str, Server]:
        return await self.client.fetch_matches()


class StatusCoordinator(NodeCSCoordinator[dict[str, str | None]]):
    """Every server's status: answering it makes the panel probe the servers."""

    def __init__(
        self, hass: HomeAssistant, entry: NodeCSConfigEntry, client: NodeCSClient
    ) -> None:
        super().__init__(hass, entry, client, "status", STATUS_INTERVAL)

    async def _fetch(self) -> dict[str, str | None]:
        return await self.client.fetch_statuses()
