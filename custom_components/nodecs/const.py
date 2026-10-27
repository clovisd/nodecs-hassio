"""Constants for the NodeCS integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "nodecs"
NAME = "NodeCS"

GRAPHQL_PATH = "/api/ui/graphql/query"
PUSH_PATH = "/api/ui/notifications/subscribe"

# The match query is the fast path: read on every push message and every second.
# It names every field the integration shows and nothing else; the panel's schema
# also serves passwords and API keys, which must never be asked for.
MATCH_QUERY = """\
query HomeAssistantMatches {
  cs2Servers {
    id name
    match {
      id phase bestOfX bestOfXAScore bestOfXBScore
      teamA { id name logoUrl } teamB { id name logoUrl }
      map { name logoUrl }
      teamAReady teamBReady teamAScore teamBScore
      teamATimeoutsUsed teamBTimeoutsUsed teamATimeoutsLeft teamBTimeoutsLeft
      assignedAt liveAt endedAt
      pauses { reason startedAt endedAt team { id } }
      buttonBindings { buttonID action team }
    }
  }
}
"""

# The status query is the slow path: answering it makes the panel probe the game
# servers, so it is not asked every second.
STATUS_QUERY = "query HomeAssistantStatus { cs2Servers { id status } }"

MATCH_INTERVAL = timedelta(seconds=1)
STATUS_INTERVAL = timedelta(seconds=10)
REQUEST_TIMEOUT = 3
SETUP_TIMEOUT = 10
IMAGE_TIMEOUT = 10
STALE_AFTER = timedelta(seconds=6)
REFRESH_COOLDOWN = 0.3
PUSH_RETRY_MIN = 1
PUSH_RETRY_MAX = 30
PUSH_HEARTBEAT = 15
