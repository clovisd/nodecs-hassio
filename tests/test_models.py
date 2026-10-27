"""Tests for parsing the panel's replies."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from custom_components.nodecs.models import (
    Binding,
    parse_matches,
    parse_statuses,
    parse_time,
)

from .payloads import match_json, matches_reply, pause_json, server_json, status_reply


def _match(**overrides: Any):
    servers = parse_matches(matches_reply(server_json(match=match_json(**overrides))))
    return servers["SRV-1"].match


def test_parse_matches_reads_every_field() -> None:
    """Every field the query asks for lands in the model."""
    match = _match(
        teamAScore=7,
        teamBTimeoutsLeft=2,
        bestOfXBScore=1,
        liveAt="2026-10-26T08:02:05Z",
        teamAReady=True,
    )
    assert match.id == "MATCH-1"
    assert match.phase == "LIVE"
    assert match.best_of == 3
    assert match.team_a_score == 7
    assert match.team_b_score == 4
    assert match.team_a_maps_won == 0
    assert match.team_b_maps_won == 1
    assert match.team_a_timeouts_used == 0
    assert match.team_b_timeouts_used == 1
    assert match.team_a_timeouts_left == 3
    assert match.team_b_timeouts_left == 2
    assert match.team_a_ready is True
    assert match.team_b_ready is False
    assert match.live_at == datetime(2026, 10, 26, 8, 2, 5, tzinfo=UTC)
    assert match.assigned_at == datetime(2026, 10, 26, 7, 33, 45, tzinfo=UTC)
    assert match.ended_at is None
    assert match.team_a.name == "Alpha"
    assert match.team_a.id == "TEAM-A"
    assert match.team_b.logo_url.endswith("/api/ui/teams/TEAM-B/logo")
    assert match.map.name == "Nuke"


def test_parse_matches_keeps_panel_order_and_names() -> None:
    """Servers are keyed by id, in the panel's order, with their names."""
    servers = parse_matches(
        matches_reply(server_json("SRV-2", "b"), server_json("SRV-1", "a"))
    )
    assert list(servers) == ["SRV-2", "SRV-1"]
    assert servers["SRV-1"].name == "a"


def test_parse_matches_server_without_match() -> None:
    """A server with nothing assigned has no match."""
    assert parse_matches(matches_reply(server_json()))["SRV-1"].match is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "2026-10-27T20:21:54.985469598Z",
            datetime(2026, 10, 27, 20, 21, 54, 985469, tzinfo=UTC),
        ),
        ("2026-10-26T08:02:05Z", datetime(2026, 10, 26, 8, 2, 5, tzinfo=UTC)),
        (None, None),
        ("not a time", None),
        (5, None),
    ],
)
def test_parse_time(value: object, expected: datetime | None) -> None:
    """Nanoseconds are cut to microseconds; anything unparseable is None."""
    assert parse_time(value) == expected


def test_bad_time_does_not_fail_the_read() -> None:
    """A garbled time is just an unknown time."""
    assert _match(liveAt="yesterday").live_at is None


def test_null_pauses_is_empty() -> None:
    """The schema allows a null pause list."""
    assert _match(pauses=None).pauses == ()


def test_running_pause_is_latest_open_one() -> None:
    """With two open pauses (should not happen), the later one counts."""
    match = _match(
        pauses=[
            pause_json("TACTICAL", "TEAM-A", started="2026-10-27T18:05:00Z"),
            pause_json(
                "TECHNICAL",
                started="2026-10-27T17:00:00Z",
                ended="2026-10-27T17:01:00Z",
            ),
            pause_json("TECHNICAL", "TEAM-B", started="2026-10-27T18:00:00Z"),
        ]
    )
    pause = match.running_pause
    assert pause is not None
    assert pause.reason == "TACTICAL"
    assert pause.team_id == "TEAM-A"
    assert pause.started_at == datetime(2026, 10, 27, 18, 5, tzinfo=UTC)


@pytest.mark.parametrize(
    ("pauses", "expected"),
    [
        ([], "none"),
        ([pause_json("TACTICAL", "TEAM-A")], "team_a"),
        ([pause_json("TACTICAL", "TEAM-B")], "team_b"),
        ([pause_json("TECHNICAL")], "admin"),
        ([pause_json("TACTICAL", "TEAM-X")], None),
        ([pause_json("TACTICAL", "TEAM-A", ended="2026-10-27T18:00:30Z")], "none"),
    ],
)
def test_paused_by(pauses: list[dict[str, Any]], expected: str | None) -> None:
    """Who called the running pause, by the current match's team ids."""
    assert _match(pauses=pauses).paused_by == expected


def test_bindings() -> None:
    """Button bindings keep the panel's values."""
    match = _match(
        buttonBindings=[{"buttonID": "coach-a", "action": "TAC_PAUSE", "team": "A"}]
    )
    assert match.bindings == (Binding("coach-a", "TAC_PAUSE", "A"),)


@pytest.mark.parametrize(
    "reply",
    [
        {},
        {"data": None},
        {"data": {"cs2Servers": None}},
        {"data": {"cs2Servers": [{"name": "x", "match": None}]}},
        matches_reply(server_json(match=match_json(teamAScore="7"))),
        matches_reply(server_json(match=match_json(teamAReady=1))),
        matches_reply(server_json(match=match_json(teamA=None))),
    ],
)
def test_parse_matches_rejects_bad_shape(reply: dict[str, Any]) -> None:
    """A reply that does not match the schema is an error, not a guess."""
    with pytest.raises(ValueError):
        parse_matches(reply)


def test_parse_statuses() -> None:
    """Statuses are kept raw, keyed by server id; null stays None."""
    reply = status_reply(server_json("SRV-1"), server_json("SRV-2", status=None))
    assert parse_statuses(reply) == {"SRV-1": "RUNNING_VALID", "SRV-2": None}


def test_parse_statuses_rejects_bad_shape() -> None:
    """A status that is not a string or null is an error."""
    with pytest.raises(ValueError):
        parse_statuses({"data": {"cs2Servers": [{"id": "SRV-1", "status": 3}]}})
