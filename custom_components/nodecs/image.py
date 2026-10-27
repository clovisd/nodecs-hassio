"""Team logos and the map's picture, fetched with the panel's login."""

from __future__ import annotations

from collections.abc import Callable
import logging

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import NodeCSError
from .coordinator import MatchCoordinator, NodeCSConfigEntry
from .entity import NodeCSServerEntity, async_add_server_entities
from .models import Match

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

IMAGES: tuple[tuple[str, Callable[[Match], str]], ...] = (
    ("team_a_logo", lambda match: match.team_a.logo_url),
    ("team_b_logo", lambda match: match.team_b.logo_url),
    ("map_image", lambda match: match.map.logo_url),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NodeCSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add every server's pictures, now and as the panel adds servers."""
    matches = entry.runtime_data.matches
    async_add_server_entities(
        entry,
        async_add_entities,
        lambda server_id: [
            NodeCSImage(hass, matches, server_id, key, url_fn) for key, url_fn in IMAGES
        ],
    )


class NodeCSImage(NodeCSServerEntity[MatchCoordinator], ImageEntity):
    """A picture of the server's match; fetched once per URL.

    The panel serves pictures only behind its login, which a dashboard does not
    have, so Home Assistant fetches them and serves them through its image proxy.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: MatchCoordinator,
        server_id: str,
        key: str,
        url_fn: Callable[[Match], str],
    ) -> None:
        NodeCSServerEntity.__init__(self, coordinator, coordinator, server_id, key)
        ImageEntity.__init__(self, hass)
        self._url_fn = url_fn
        self._url: str | None = None
        self._cache: bytes | None = None
        self._follow_url()

    @callback
    def _follow_url(self) -> None:
        """When the URL moves, forget the cached picture and mark the entity changed."""
        server = self.server
        url = (
            None
            if server is None or server.match is None
            else self._url_fn(server.match)
        )
        if url == self._url:
            return
        self._url = url
        self._cache = None
        self._attr_image_last_updated = dt_util.utcnow() if url else None

    @callback
    def _handle_coordinator_update(self) -> None:
        self._follow_url()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """The picture, from the cache or the panel; None if there is none."""
        if (url := self._url) is None:
            return None
        if self._cache is None:
            try:
                content, content_type = await self.coordinator.client.fetch_image(url)
            except NodeCSError as err:
                _LOGGER.warning("%s: could not fetch %s: %s", self.entity_id, url, err)
                return None
            if url != self._url:
                return None
            self._cache = content
            self._attr_content_type = content_type
        return self._cache
