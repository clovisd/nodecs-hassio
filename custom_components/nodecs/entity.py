"""Devices, and the base for entities that belong to one game server."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import MatchCoordinator, NodeCSConfigEntry, NodeCSCoordinator
from .models import Server


def panel_device_info(entry: NodeCSConfigEntry) -> DeviceInfo:
    """The panel itself."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_panel")},
        name=entry.title,
        manufacturer=NAME,
        model="Panel",
        configuration_url=entry.data[CONF_URL],
    )


def server_device_info(
    entry: NodeCSConfigEntry, server_id: str, name: str
) -> DeviceInfo:
    """One game server, under the panel."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}_{server_id}")},
        name=name,
        manufacturer=NAME,
        model="CS2 server",
        via_device=(DOMAIN, f"{entry.entry_id}_panel"),
        configuration_url=entry.data[CONF_URL],
    )


class NodeCSServerEntity[C: NodeCSCoordinator](CoordinatorEntity[C]):
    """An entity of one game server; unavailable once the panel drops the server."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: C, matches: MatchCoordinator, server_id: str, key: str
    ) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._matches = matches
        self.server_id = server_id
        self._attr_translation_key = key
        self._attr_unique_id = f"{entry_id}_{server_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{server_id}")}
        )

    @property
    def server(self) -> Server | None:
        """The server as last read, or None once the panel no longer has it."""
        return (self._matches.data or {}).get(self.server_id)

    @property
    def available(self) -> bool:
        """Available while the read works and the panel still has the server."""
        return super().available and self.server is not None


@callback
def async_add_server_entities(
    entry: NodeCSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    build: Callable[[str], list[Entity]],
) -> None:
    """Add a server's entities now, and for every server the panel adds later."""
    matches = entry.runtime_data.matches
    known: set[str] = set()

    @callback
    def add_new() -> None:
        new = [server_id for server_id in matches.data if server_id not in known]
        if not new:
            return
        known.update(new)
        async_add_entities([entity for server_id in new for entity in build(server_id)])

    add_new()
    entry.async_on_unload(matches.async_add_listener(add_new))
