# Panel API reference

The panel's API, as read from the **production** schema by GraphQL introspection on 2026-10-27,
read-only, with the owner's permission. Staging, read on 2026-10-28, has one more query
(`buttonOutages`), noted below. The schema shape is all this records: no values, no hosts, no
credentials. Where it stands next to the specs: the v0.1 spec §3 covers what NodeCS reads today,
and the button-system spec §5.1 and §6.1 cover what the next phases use.

## Endpoints

| What | Request | Auth | Notes |
|---|---|---|---|
| GraphQL | `POST <panel>/api/ui/graphql/query`, JSON `{"query", "variables"}` | HTTP Basic: the panel's single admin login (nginx, `realm="Restricted Content"`) | A wrong login answers `401` with an HTML body from nginx. GraphQL errors answer `200` with `{"errors": [{"message": …}], "data": null}`. No subscriptions (`subscriptionType` is null). |
| Push channel | `GET wss://<panel>/api/ui/notifications/subscribe` (WebSocket) | The same Basic Auth header; `401` without it | JSON text frames: `{"type": "match_updated", …}` and `{"type": "notification", "payload": {"id", "kind", "message", "ok", "title"}}`. The kinds the UI knows: `tech_pause`, `overtime`, `gg_quick`, `relay`. The panel's own UI refetches on these, and reconnects 1 s after a close. |
| Button press | `POST <panel>/api/buttons/{buttonID}/press` | `Authorization: Bearer <button key>`, the panel's `Config.buttonApiKey` | From the owner, 2026-10-27. An unknown button ID registers itself. The response shape is not yet known (Phase 0.1). |
| Logos | `GET` of `Team.logoUrl` / `CS2Map.logoUrl`, absolute URLs on the panel (`/api/ui/teams/{id}/logo`, `/api/ui/cs2/maps/{id}/logo`) | Basic Auth | `200 image/png`; one staging logo was 0 bytes. |

## Observed behaviour

- **ids** are ULIDs: `id: ID!`, 26 characters, time-sortable on the panel's clock. Whether press
  ids are strictly ordered is Phase 0.1.
- **`Time`** is RFC 3339 UTC, with or without fractional seconds, up to nanoseconds
  (`2026-10-27T20:21:54.985469598Z`).
- **The certificate** is not trusted by curl or Home Assistant by default, on production and on
  staging.
- **Speed:** the v0.1 full query answers in about 150 ms on the event LAN. On staging over the
  internet with keep-alive, the medians were: ids only 74 ms, the match query 143 ms, `status`
  207 ms. `status` makes the panel probe the game servers.
- **Pauses** across 97 archived production matches:
  - `TACTICAL` always had a team and lasted about 30 s;
  - `TECHNICAL` came with a team (31) or without one (9, called from the panel);
  - `RESTORE` never had a team.
  - The list is newest first.
- **Timeouts used + left** is not constant: admins can take a timeout away as a penalty (the
  owner).
- **A press** observed on staging: outcome `executed`, detail "tac pause for &lt;team&gt;
  requested". `EXECUTED` means *requested*; the server may queue the pause until the next allowed
  moment (the owner, 2026-10-28).
- **Before a match is live**, the panel's Buttons dialog says presses "are only reported, so you
  can check each button is wired to the right team" (outcome `TEST`).
- **Restored matches** can show `WARMUP` with `liveAt` set, so `liveAt` alone does not mean live.
- **`buttonPresses` arguments** are all optional (`buttonID: String`, `matchID: ID`,
  `limit: Int`); `buttonPresses(limit: 15)` works.
- **Secrets the schema can serve,** which no query from NodeCS may ever ask for:
  - `CS2Server.password`, `livePassword`, `rconPassword`, `tvPassword`, `tvPassword1`,
    `tvRelayPassword`, `logsWebSocketUrl`;
  - the whole `Config` type: `basicAuthPass`, `apiKey`, `buttonApiKey`, `ts3Pass`,
    `discordWebhookUrl` and others.

## `CS2Server`

| Field | Type |
|---|---|
| `id` | `ID!` |
| `name` | `String!` |
| `ip` | `String!` |
| `port` | `Int!` |
| `password` | `String!` |
| `livePassword` | `String` |
| `rconPassword` | `String!` |
| `tvPort` | `Int` |
| `tvPort1` | `Int` |
| `tvPassword` | `String` |
| `tvPassword1` | `String` |
| `tvDelay` | `Int` |
| `tvDelay1` | `Int` |
| `tvRelayPassword` | `String` |
| `dockerHost` | `String` |
| `dockerContainer` | `String` |
| `configs` | `[CS2ServerConfig!]` |
| `match` | `CS2Match` |
| `logsWebSocketUrl` | `String!` |
| `playerAgentSkinsInfo` | `PlayerAgentSkinsInfo` |
| `status` | `CS2ServerStatus` |
| `cstvDelays` | `CS2ServerCSTVDelays` |
| `tvRelay` | `CS2TVRelay` |
| `tvRelay1` | `CS2TVRelay` |

## `CS2Match`

| Field | Type |
|---|---|
| `id` | `ID!` |
| `index` | `Int!` |
| `teamA` | `Team!` |
| `teamB` | `Team!` |
| `teamATSChannel` | `TS3Channel!` |
| `teamBTSChannel` | `TS3Channel!` |
| `pickSidesMode` | `PickSidesMode!` |
| `bestOfX` | `Int!` |
| `bestOfXAScore` | `Int!` |
| `bestOfXBScore` | `Int!` |
| `map` | `CS2Map!` |
| `phase` | `Phase!` |
| `server` | `CS2Server` |
| `teamAReady` | `Boolean!` |
| `teamBReady` | `Boolean!` |
| `teamAScore` | `Int!` |
| `teamBScore` | `Int!` |
| `teamATimeoutsUsed` | `Int!` |
| `teamBTimeoutsUsed` | `Int!` |
| `teamATimeoutsLeft` | `Int!` |
| `teamBTimeoutsLeft` | `Int!` |
| `insertedAt` | `Time!` |
| `assignedAt` | `Time` |
| `liveAt` | `Time` |
| `endedAt` | `Time` |
| `archivedAt` | `Time` |
| `pauses` | `[CS2MatchPause!]` |
| `demos` | `[CS2Demo!]` |
| `backups` | `[CS2MatchBackup!]` |
| `logs` | `[CS2MatchLog!]` |
| `playerSubstitutions` | `[PlayerSubstitution!]` |
| `buttonBindings` | `[ButtonBinding!]!` |
| `buttonBindingsSuggestion` | `CS2Match` |

## `CS2MatchPause`

| Field | Type |
|---|---|
| `id` | `ID!` |
| `match` | `CS2Match!` |
| `team` | `Team` |
| `reason` | `PauseReason!` |
| `startedAt` | `Time!` |
| `endedAt` | `Time` |

## `Team`

| Field | Type |
|---|---|
| `id` | `ID!` |
| `name` | `String!` |
| `flag` | `String` |
| `logoUrl` | `String!` |
| `members` | `[TeamMember!]!` |

## `CS2Map`

| Field | Type |
|---|---|
| `id` | `ID!` |
| `name` | `String!` |
| `map` | `String!` |
| `logoUrl` | `String!` |

## `Button`

| Field | Type |
|---|---|
| `id` | `ID!` |
| `firstSeenAt` | `Time!` |
| `lastPressedAt` | `Time!` |

## `ButtonBinding`

| Field | Type |
|---|---|
| `id` | `ID!` |
| `buttonID` | `String!` |
| `action` | `ButtonAction!` |
| `team` | `MatchTeam` |

## `ButtonPress`

| Field | Type |
|---|---|
| `id` | `ID!` |
| `buttonID` | `String!` |
| `pressedAt` | `Time!` |
| `match` | `CS2Match` |
| `outcome` | `ButtonPressOutcome!` |
| `detail` | `String` |

## `ButtonBindingInput`

| Field | Type |
|---|---|
| `buttonID` | `String!` |
| `action` | `ButtonAction!` |
| `team` | `MatchTeam` |

## `ButtonOutage` (staging only, so far)

| Field | Type |
|---|---|
| `id` | `ID!` |
| `buttonID` | `String!` |
| `startedAt` | `Time!` |
| `endedAt` | `Time` |
| `detail` | `String` |

## Enums

| Enum | Values |
|---|---|
| `CS2ServerStatus` | `STOPPED`, `STARTING`, `RUNNING_INVALID`, `RUNNING_VALID`, `UNKNOWN` |
| `Phase` | `UNASSIGNED`, `WARMUP`, `KNIFE`, `LIVE`, `HALF_TIME_BREAK`, `ENDED`, `ARCHIVED`, `FREEZE_TIME` |
| `PauseReason` | `TACTICAL`, `TECHNICAL`, `RESTORE` |
| `ButtonAction` | `TAC_PAUSE`, `TECH_PAUSE` |
| `ButtonPressOutcome` | `NONE`, `TEST`, `EXECUTED`, `ERROR` |
| `MatchTeam` | `A`, `B` |
| `PickSidesMode` | `KNIFE`, `TEAM_A_CT`, `TEAM_B_CT` |
| `CS2ServerConfigType` | `LIVE`, `SECOND_HALF`, `OVERTIME` |

## Queries

| Field | Type |
|---|---|
| `config` | `Config!` |
| `cs2Maps` | `[CS2Map!]!` |
| `cs2Map(id: ID!)` | `CS2Map` |
| `cs2DefaultAvatar` | `Bytes!` |
| `notifications` | `[Notification!]!` |
| `buttons` | `[Button!]!` |
| `buttonPresses(buttonID: String, matchID: ID, limit: Int)` | `[ButtonPress!]!` |
| `cs2Matches(ids: [ID!], archived: Boolean)` | `[CS2Match!]!` |
| `cs2Match(id: ID!)` | `CS2Match` |
| `cs2TVRelays` | `[CS2TVRelay!]!` |
| `cs2TVRelay(id: ID!)` | `CS2TVRelay` |
| `fragnetLocations` | `[FragnetLocation!]!` |
| `cs2ServerConfigs` | `[CS2ServerConfig!]!` |
| `cs2ServerConfig(id: ID!)` | `CS2ServerConfig` |
| `cs2Servers` | `[CS2Server!]!` |
| `cs2Server(id: ID!)` | `CS2Server` |
| `teams` | `[Team!]!` |
| `team(id: ID!)` | `Team` |
| `tournaments` | `[Tournament!]!` |
| `tournament(id: ID!)` | `Tournament` |
| `ts3Channels` | `[TS3Channel!]!` |
| `ts3Channel(id: ID!)` | `TS3Channel` |
| `ts3Clients` | `[TS3Client!]!` |

Staging adds `buttonOutages(buttonIDs: [String!], limit: Int): [ButtonOutage!]!`.

## Mutations (never called by NodeCS; listed for awareness)

| Field | Type |
|---|---|
| `restartSamba` | `Boolean!` |
| `updateConfig(input: ConfigInput!)` | `Config!` |
| `createCS2Map(input: CS2MapInput!)` | `CS2Map!` |
| `updateCS2Map(id: ID!, input: CS2MapInput!)` | `CS2Map!` |
| `deleteCS2Map(id: ID!)` | `Boolean!` |
| `setCS2DefaultAvatar(png: Bytes!)` | `Boolean!` |
| `setNotificationAcknowledgement(id: ID!, ackd: Boolean!)` | `Boolean!` |
| `acknowledgeAllNotifications` | `Boolean!` |
| `backup` | `Boolean!` |
| `setCS2MatchButtonBindings(matchID: ID!, bindings: [ButtonBindingInput!]!)` | `Boolean!` |
| `createCS2Matches(input: CreateCS2MatchInput!)` | `[CS2Match!]!` |
| `updateCS2Match(id: ID!, input: UpdateCS2MatchInput!)` | `CS2Match!` |
| `deleteCS2Match(id: ID!)` | `Boolean!` |
| `resetCS2Match(id: ID!)` | `Boolean!` |
| `archiveCS2Match(id: ID!)` | `Boolean!` |
| `unarchiveCS2Match(id: ID!)` | `Boolean!` |
| `assignCS2Match(matchID: ID!, serverID: ID)` | `Boolean!` |
| `restoreCS2Match(matchID: ID!, backupID: ID!)` | `Boolean!` |
| `goLiveCS2Match(id: ID!, force: Boolean, countdown: Int)` | `Boolean!` |
| `pauseCS2Match(id: ID!, teamID: ID, reason: PauseReason!)` | `ID!` |
| `unpauseCS2Match(matchID: ID!, pauseID: ID!, force: Boolean)` | `Boolean!` |
| `setCS2MatchTimeouts(matchID: ID!, teamID: ID!, timeouts: Int!)` | `Boolean!` |
| `storeMatchLog(id: ID!)` | `Boolean!` |
| `substituteMatchPlayer(matchID: ID!, oldPlayerID: ID!, newPlayerID: ID!)` | `Boolean!` |
| `createCS2TVRelay(input: CS2TVRelayInput!)` | `CS2TVRelay!` |
| `updateCS2TVRelay(id: ID!, input: CS2TVRelayInput!)` | `CS2TVRelay!` |
| `deleteCS2TVRelay(id: ID!)` | `Boolean!` |
| `cs2TVRelayRconExec(id: ID!, command: String!)` | `String!` |
| `cs2TVRelayConsoleExec(id: ID!, command: String!)` | `Boolean!` |
| `restartCS2TVRelay(id: ID!)` | `Boolean!` |
| `assignCS2TVRelay(relayID: ID!, origin: String!, password: String!)` | `Boolean!` |
| `provisionCS2TVRelay(name: String!, locationID: Int!)` | `CS2TVRelay!` |
| `createCS2ServerConfig(input: CS2ServerConfigInput!)` | `CS2ServerConfig!` |
| `updateCS2ServerConfig(id: ID!, input: CS2ServerConfigInput!)` | `CS2ServerConfig!` |
| `deleteCS2ServerConfig(id: ID!)` | `Boolean!` |
| `createCS2Server(input: CS2ServerInput!)` | `CS2Server!` |
| `updateCS2Server(id: ID!, input: CS2ServerInput!)` | `CS2Server!` |
| `deleteCS2Server(id: ID!)` | `Boolean!` |
| `cs2ServerRconExec(id: ID!, command: String!)` | `String!` |
| `cs2ServerConsoleExec(id: ID!, command: String!)` | `Boolean!` |
| `restartCS2Server(id: ID!)` | `Boolean!` |
| `startCS2Broadcast(id: ID!, stream: String!)` | `Boolean!` |
| `stopCS2Broadcast(id: ID!)` | `Boolean!` |
| `updateCS2Servers` | `Boolean!` |
| `createTeam(input: TeamInput!)` | `Team!` |
| `updateTeam(id: ID!, input: TeamInput!)` | `Team!` |
| `deleteTeam(id: ID!)` | `Boolean!` |
| `addTeamMember(input: TeamMemberInput!)` | `Boolean!` |
| `removeTeamMember(id: ID!)` | `Boolean!` |
| `updateTeamMember(id: ID!, input: TeamMemberInput!)` | `Boolean!` |
| `batchInsertTeams(xlsx: Bytes!)` | `Boolean!` |
| `addTournament(tournament: TournamentInput!)` | `Tournament!` |
| `refreshTS3Channels` | `[TS3Channel!]!` |
| `ts3SetChannelRequiredTalkPower(channelID: ID!, talkPower: Int!)` | `Boolean!` |
| `ts3ExecuteCommand(command: String!)` | `[String!]` |
| `ts3SetClientChannelTalkPower(cid: Int!, cldbid: Int!, talkPower: Int!)` | `Boolean!` |
| `ts3ResetChannelTalkPowers(channelID: ID!)` | `Boolean!` |
