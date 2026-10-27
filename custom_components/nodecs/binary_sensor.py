"""The teams' ready flags, and whether the panel's live updates are flowing."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MatchCoordinator, NodeCSConfigEntry
from .entity import NodeCSServerEntity, async_add_server_entities, panel_device_info
from .push import PushListener

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NodeCSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the panel's Live updates sensor and every server's ready flags."""
    runtime = entry.runtime_data
    async_add_entities([NodeCSLiveUpdates(entry, runtime.push)])
    async_add_server_entities(
        entry,
        async_add_entities,
        lambda server_id: [
            NodeCSReady(runtime.matches, server_id, "team_a_ready"),
            NodeCSReady(runtime.matches, server_id, "team_b_ready"),
        ],
    )


class NodeCSReady(NodeCSServerEntity[MatchCoordinator], BinarySensorEntity):
    """On once the team has readied up."""

    def __init__(self, coordinator: MatchCoordinator, server_id: str, key: str) -> None:
        super().__init__(coordinator, coordinator, server_id, key)

    @property
    def is_on(self) -> bool | None:
        """None while the server has no match."""
        if (server := self.server) is None or (match := server.match) is None:
            return None
        if self._attr_translation_key == "team_a_ready":
            return match.team_a_ready
        return match.team_b_ready


class NodeCSLiveUpdates(BinarySensorEntity):
    """On while the panel's push channel is open; off means one-second polling."""

    _attr_has_entity_name = True
    _attr_translation_key = "live_updates"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False

    def __init__(self, entry: NodeCSConfigEntry, push: PushListener) -> None:
        self._push = push
        self._attr_unique_id = f"{entry.entry_id}_live_updates"
        self._attr_device_info = panel_device_info(entry)

    async def async_added_to_hass(self) -> None:
        """Follow the channel."""
        self.async_on_remove(self._push.async_add_listener(self.async_write_ha_state))

    @property
    def is_on(self) -> bool:
        """Whether the channel is open."""
        return self._push.connected
