# Phase 0 probe tools (read-only)

These are the scripts used on 2026-10-27/28 to explore the panel, cleaned for the repo. They
**never write to the panel**: no mutations, no button presses. The press tests in Phase 0.1 need
the owner's go-ahead and are deliberately not here.

Every script takes the panel's base URL and a credentials file as arguments. The file holds one
line, `user:password`. Keep it outside the repo, with `chmod 600`. Run them with the repo's venv
(`.venv/bin/python`) from the repo root. Certificates are not verified, because the panel's
certificate isn't trusted by default.

| Script | What it does |
|---|---|
| `probe.py <base> <authfile>` | Runs the integration's own client against the panel: both queries, one logo, a wrong-password check (expects a refused login), and the push channel for 20 s. |
| `bench.py <base> <authfile> [n]` | Times query variants over one kept-alive session: ids only, status only, the match query, and the full v0.1 query. Prints the median, p90 and max. |
| `ws_listen.py <base> <authfile> [seconds]` | Prints every push-channel frame with its arrival time. Leave it running while the owner changes a match on staging, to see which changes send `match_updated`. |

Never point them at production without the owner's say-so; the owner's rule is staging only.
