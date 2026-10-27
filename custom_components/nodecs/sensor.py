"""Each server's status, its match, and the running pause."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import MatchCoordinator, NodeCSConfigEntry, StatusCoordinator
from .entity import NodeCSServerEntity, async_add_server_entities
from .models import Match, Server

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

STATUSES = ["stopped", "starting", "running_valid", "running_invalid"]
PHASES = [
    "unassigned",
    "warmup",
    "knife",
    "live",
    "freeze_time",
    "half_time_break",
    "ended",
    "archived",
]
PAUSE_REASONS = ["tactical", "technical", "restore"]
PAUSED_BY = ["none", "team_a", "team_b", "admin"]


def _option(value: str | None, options: list[str], what: str) -> str | None:
    """The panel's value as one of the options, or None for one this version lacks."""
    if value is None:
        return None
    key = value.lower()
    if key in options:
        return key
    _LOGGER.debug("Unknown %s %r from the panel", what, value)
    return None


def _phase(server: Server) -> str | None:
    if server.match is None:
        return "no_match"
    return _option(server.match.phase, PHASES, "phase")


def _pause(server: Server) -> str | None:
    if server.match is None or (pause := server.match.running_pause) is None:
        return "none"
    return _option(pause.reason, PAUSE_REASONS, "pause reason")


def _paused_by(server: Server) -> str | None:
    return "none" if server.match is None else server.match.paused_by


def _pause_started(server: Server) -> datetime | None:
    if server.match is None or (pause := server.match.running_pause) is None:
        return None
    return pause.started_at


def _bindings(server: Server) -> dict[str, Any] | None:
    if server.match is None:
        return None
    return {
        "bindings": [
            {
                "button": binding.button,
                "team": binding.team.lower() if binding.team else None,
                "action": binding.action.lower(),
            }
            for binding in server.match.bindings
        ]
    }


def _of_match(
    value_fn: Callable[[Match], StateType | datetime],
) -> Callable[[Server], StateType | datetime]:
    """A value of the server's match; None when it has none."""
    return lambda server: None if server.match is None else value_fn(server.match)


@dataclass(frozen=True, kw_only=True)
class NodeCSSensorEntityDescription(SensorEntityDescription):
    """A sensor read from a server's entry in the match query."""

    value_fn: Callable[[Server], StateType | datetime]
    attr_fn: Callable[[Server], dict[str, Any] | None] = lambda _server: None


def _count(key: str, value_fn: Callable[[Match], int]) -> NodeCSSensorEntityDescription:
    return NodeCSSensorEntityDescription(
        key=key, translation_key=key, value_fn=_of_match(value_fn)
    )


def _time(key: str, value_fn: Callable[[Server], datetime | None]):
    return NodeCSSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=value_fn,
    )


MATCH_SENSORS: tuple[NodeCSSensorEntityDescription, ...] = (
    NodeCSSensorEntityDescription(
        key="phase",
        translation_key="phase",
        device_class=SensorDeviceClass.ENUM,
        options=["no_match", *PHASES],
        value_fn=_phase,
    ),
    NodeCSSensorEntityDescription(
        key="map", translation_key="map", value_fn=_of_match(lambda m: m.map.name)
    ),
    NodeCSSensorEntityDescription(
        key="team_a",
        translation_key="team_a",
        value_fn=_of_match(lambda m: m.team_a.name),
    ),
    NodeCSSensorEntityDescription(
        key="team_b",
        translation_key="team_b",
        value_fn=_of_match(lambda m: m.team_b.name),
    ),
    _count("team_a_score", lambda m: m.team_a_score),
    _count("team_b_score", lambda m: m.team_b_score),
    _count("team_a_maps_won", lambda m: m.team_a_maps_won),
    _count("team_b_maps_won", lambda m: m.team_b_maps_won),
    _count("best_of", lambda m: m.best_of),
    _count("team_a_timeouts_left", lambda m: m.team_a_timeouts_left),
    _count("team_b_timeouts_left", lambda m: m.team_b_timeouts_left),
    _count("team_a_timeouts_used", lambda m: m.team_a_timeouts_used),
    _count("team_b_timeouts_used", lambda m: m.team_b_timeouts_used),
    NodeCSSensorEntityDescription(
        key="pause",
        translation_key="pause",
        device_class=SensorDeviceClass.ENUM,
        options=["none", *PAUSE_REASONS],
        value_fn=_pause,
    ),
    NodeCSSensorEntityDescription(
        key="paused_by",
        translation_key="paused_by",
        device_class=SensorDeviceClass.ENUM,
        options=PAUSED_BY,
        value_fn=_paused_by,
    ),
    _time("pause_started", _pause_started),
    _time("assigned_at", _of_match(lambda m: m.assigned_at)),
    _time("live_at", _of_match(lambda m: m.live_at)),
    _time("ended_at", _of_match(lambda m: m.ended_at)),
    NodeCSSensorEntityDescription(
        key="button_bindings",
        translation_key="button_bindings",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_of_match(lambda m: len(m.bindings)),
        attr_fn=_bindings,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NodeCSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add every server's sensors, now and as the panel adds servers."""
    runtime = entry.runtime_data

    def build(server_id: str) -> list[SensorEntity]:
        return [
            NodeCSStatusSensor(runtime.status, runtime.matches, server_id),
            *(
                NodeCSMatchSensor(runtime.matches, server_id, description)
                for description in MATCH_SENSORS
            ),
        ]

    async_add_server_entities(entry, async_add_entities, build)


class NodeCSMatchSensor(NodeCSServerEntity[MatchCoordinator], SensorEntity):
    """A value of the server's match."""

    entity_description: NodeCSSensorEntityDescription

    def __init__(
        self,
        coordinator: MatchCoordinator,
        server_id: str,
        description: NodeCSSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, coordinator, server_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        """The value, or None while the server has no match."""
        server = self.server
        return None if server is None else self.entity_description.value_fn(server)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """The bindings list, for the button bindings sensor."""
        server = self.server
        return None if server is None else self.entity_description.attr_fn(server)


class NodeCSStatusSensor(NodeCSServerEntity[StatusCoordinator], SensorEntity):
    """The server's status, from the slow status read."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = STATUSES

    def __init__(
        self, coordinator: StatusCoordinator, matches: MatchCoordinator, server_id: str
    ) -> None:
        super().__init__(coordinator, matches, server_id, "status")

    @property
    def native_value(self) -> str | None:
        """The status; the panel's UNKNOWN is Home Assistant's unknown."""
        return _option(self.coordinator.data.get(self.server_id), STATUSES, "status")
