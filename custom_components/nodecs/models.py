"""The panel's servers and matches, parsed from its GraphQL replies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util


@dataclass(frozen=True)
class Team:
    """One side of a match."""

    id: str
    name: str
    logo_url: str


@dataclass(frozen=True)
class MapInfo:
    """The map a match is played on."""

    name: str
    logo_url: str


@dataclass(frozen=True)
class Pause:
    """A pause; running while it has no end."""

    reason: str
    started_at: datetime | None
    ended_at: datetime | None
    team_id: str | None


@dataclass(frozen=True)
class Binding:
    """A physical button bound to a team's pause."""

    button: str
    action: str
    team: str | None


@dataclass(frozen=True)
class Match:
    """The match on a server, as the panel reports it."""

    id: str
    phase: str
    best_of: int
    team_a: Team
    team_b: Team
    map: MapInfo
    team_a_ready: bool
    team_b_ready: bool
    team_a_score: int
    team_b_score: int
    team_a_maps_won: int
    team_b_maps_won: int
    team_a_timeouts_used: int
    team_b_timeouts_used: int
    team_a_timeouts_left: int
    team_b_timeouts_left: int
    assigned_at: datetime | None
    live_at: datetime | None
    ended_at: datetime | None
    pauses: tuple[Pause, ...]
    bindings: tuple[Binding, ...]

    @property
    def running_pause(self) -> Pause | None:
        """The pause with no end; the latest one if the panel ever has two."""
        running = [pause for pause in self.pauses if pause.ended_at is None]
        if not running:
            return None
        return max(
            running,
            key=lambda pause: (
                pause.started_at or datetime.min.replace(tzinfo=dt_util.UTC)
            ),
        )

    @property
    def paused_by(self) -> str | None:
        """none, team_a, team_b or admin; None for a team that is in neither side."""
        if (pause := self.running_pause) is None:
            return "none"
        if pause.team_id is None:
            return "admin"
        if pause.team_id == self.team_a.id:
            return "team_a"
        if pause.team_id == self.team_b.id:
            return "team_b"
        return None


@dataclass(frozen=True)
class Server:
    """A game server and the match on it, if any."""

    id: str
    name: str
    match: Match | None


def parse_time(value: object) -> datetime | None:
    """An RFC 3339 time from the panel, or None for anything else."""
    if not isinstance(value, str):
        return None
    return dt_util.parse_datetime(value)


def parse_matches(reply: dict[str, Any]) -> dict[str, Server]:
    """The match query's reply, keyed by server id in the panel's order."""
    servers: dict[str, Server] = {}
    for item in _servers(reply):
        server_id = _str(item, "id")
        match = item.get("match", ...)
        if match is ...:
            raise ValueError("server without a match field")
        servers[server_id] = Server(
            id=server_id,
            name=_str(item, "name"),
            match=None if match is None else _match(_dict(match)),
        )
    return servers


def parse_statuses(reply: dict[str, Any]) -> dict[str, str | None]:
    """The status query's reply: each server's raw status, None when null."""
    statuses: dict[str, str | None] = {}
    for item in _servers(reply):
        status = item.get("status")
        if status is not None and not isinstance(status, str):
            raise ValueError(f"status is {status!r}")
        statuses[_str(item, "id")] = status
    return statuses


def _servers(reply: dict[str, Any]) -> list[dict[str, Any]]:
    data = reply.get("data") if isinstance(reply, dict) else None
    servers = data.get("cs2Servers") if isinstance(data, dict) else None
    if not isinstance(servers, list):
        raise ValueError("reply has no cs2Servers list")
    return [_dict(item) for item in servers]


def _match(item: dict[str, Any]) -> Match:
    pauses = item.get("pauses") or []
    if not isinstance(pauses, list):
        raise ValueError("pauses is not a list")
    bindings = item.get("buttonBindings")
    if not isinstance(bindings, list):
        raise ValueError("buttonBindings is not a list")
    return Match(
        id=_str(item, "id"),
        phase=_str(item, "phase"),
        best_of=_int(item, "bestOfX"),
        team_a=_team(_dict(item.get("teamA"))),
        team_b=_team(_dict(item.get("teamB"))),
        map=_map(_dict(item.get("map"))),
        team_a_ready=_bool(item, "teamAReady"),
        team_b_ready=_bool(item, "teamBReady"),
        team_a_score=_int(item, "teamAScore"),
        team_b_score=_int(item, "teamBScore"),
        team_a_maps_won=_int(item, "bestOfXAScore"),
        team_b_maps_won=_int(item, "bestOfXBScore"),
        team_a_timeouts_used=_int(item, "teamATimeoutsUsed"),
        team_b_timeouts_used=_int(item, "teamBTimeoutsUsed"),
        team_a_timeouts_left=_int(item, "teamATimeoutsLeft"),
        team_b_timeouts_left=_int(item, "teamBTimeoutsLeft"),
        assigned_at=parse_time(item.get("assignedAt")),
        live_at=parse_time(item.get("liveAt")),
        ended_at=parse_time(item.get("endedAt")),
        pauses=tuple(_pause(_dict(pause)) for pause in pauses),
        bindings=tuple(_binding(_dict(binding)) for binding in bindings),
    )


def _team(item: dict[str, Any]) -> Team:
    return Team(
        id=_str(item, "id"), name=_str(item, "name"), logo_url=_str(item, "logoUrl")
    )


def _map(item: dict[str, Any]) -> MapInfo:
    return MapInfo(name=_str(item, "name"), logo_url=_str(item, "logoUrl"))


def _pause(item: dict[str, Any]) -> Pause:
    team = item.get("team")
    return Pause(
        reason=_str(item, "reason"),
        started_at=parse_time(item.get("startedAt")),
        ended_at=parse_time(item.get("endedAt")),
        team_id=None if team is None else _str(_dict(team), "id"),
    )


def _binding(item: dict[str, Any]) -> Binding:
    team = item.get("team")
    if team is not None and not isinstance(team, str):
        raise ValueError(f"binding team is {team!r}")
    return Binding(
        button=_str(item, "buttonID"), action=_str(item, "action"), team=team
    )


def _dict(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"expected an object, got {value!r}")
    return value


def _str(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str):
        raise ValueError(f"{key} is {value!r}")
    return value


def _int(item: dict[str, Any], key: str) -> int:
    value = item.get(key)
    if type(value) is not int:
        raise ValueError(f"{key} is {value!r}")
    return value


def _bool(item: dict[str, Any], key: str) -> bool:
    value = item.get(key)
    if type(value) is not bool:
        raise ValueError(f"{key} is {value!r}")
    return value
