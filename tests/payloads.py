"""Panel replies, shaped like the real ones, with made-up teams, ids and hosts."""

from __future__ import annotations

from typing import Any

from custom_components.nodecs.const import GRAPHQL_PATH

BASE = "https://panel.example.lan"
GRAPHQL = BASE + GRAPHQL_PATH


def team_json(team_id: str, name: str) -> dict[str, Any]:
    """A team as the match query returns it."""
    return {
        "id": team_id,
        "name": name,
        "logoUrl": f"{BASE}/api/ui/teams/{team_id}/logo",
    }


def match_json(**overrides: Any) -> dict[str, Any]:
    """A live match, Alpha against Bravo on Nuke, with no pauses."""
    match = {
        "id": "MATCH-1",
        "phase": "LIVE",
        "bestOfX": 3,
        "bestOfXAScore": 0,
        "bestOfXBScore": 0,
        "teamA": team_json("TEAM-A", "Alpha"),
        "teamB": team_json("TEAM-B", "Bravo"),
        "map": {"name": "Nuke", "logoUrl": f"{BASE}/api/ui/cs2/maps/MAP-NUKE/logo"},
        "teamAReady": False,
        "teamBReady": False,
        "teamAScore": 3,
        "teamBScore": 4,
        "teamATimeoutsUsed": 0,
        "teamBTimeoutsUsed": 1,
        "teamATimeoutsLeft": 3,
        "teamBTimeoutsLeft": 2,
        "assignedAt": "2026-10-26T07:33:45Z",
        "liveAt": "2026-10-26T08:02:05Z",
        "endedAt": None,
        "pauses": [],
        "buttonBindings": [],
    }
    match.update(overrides)
    return match


def pause_json(
    reason: str,
    team_id: str | None = None,
    started: str = "2026-10-27T18:00:00Z",
    ended: str | None = None,
) -> dict[str, Any]:
    """A pause; open while `ended` is None."""
    return {
        "reason": reason,
        "startedAt": started,
        "endedAt": ended,
        "team": None if team_id is None else {"id": team_id},
    }


def server_json(
    server_id: str = "SRV-1",
    name: str = "server_1",
    match: dict[str, Any] | None = None,
    status: str | None = "RUNNING_VALID",
) -> dict[str, Any]:
    """A server with everything either query could return for it."""
    return {"id": server_id, "name": name, "match": match, "status": status}


def matches_reply(*servers: dict[str, Any]) -> dict[str, Any]:
    """The match query's reply for these servers."""
    return {
        "data": {
            "cs2Servers": [
                {"id": s["id"], "name": s["name"], "match": s["match"]} for s in servers
            ]
        }
    }


def status_reply(*servers: dict[str, Any]) -> dict[str, Any]:
    """The status query's reply for these servers."""
    return {
        "data": {
            "cs2Servers": [{"id": s["id"], "status": s["status"]} for s in servers]
        }
    }
