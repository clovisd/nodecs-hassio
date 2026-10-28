# Phase 0 probe tools (read-only)

These are the scripts used on 2026-10-27/28 to explore the panel, cleaned for the repo. They
**never write to the panel**: no mutations, no button presses. The press tests in Phase 0.1 need
the owner's go-ahead and are deliberately not here.

Every script takes the panel's base URL and a credentials file as arguments. The file holds one
line, `user:password`. Keep it outside the repo, with `chmod 600`. Run them with the repo's venv
(`.venv/bin/python`) from the repo root.

**TLS:** certificates are **verified by default**. The panel's certificate isn't trusted out of
the box, so pass `--cafile <event-ca.pem>` to trust the event's CA. That matches spec §5.12. Use
`--insecure` only as a last resort: it prints a warning, and the credentials could then be
intercepted on the network.

| Script | What it does |
|---|---|
| `probe.py <base> <authfile> [--cafile PEM]` | Runs the integration's own client against the panel: both queries, one logo, a wrong-password check (expects a refused login), and the push channel for 20 s. |
| `bench.py <base> <authfile> [n] [--cafile PEM]` | Times query variants over one kept-alive session: ids only, status only, and the match query. Prints the median, p90 and max. |
| `ws_listen.py <base> <authfile> [seconds] [--cafile PEM]` | Prints every push-channel frame with its arrival time. Leave it running while the owner changes a match on staging, to see which changes send `match_updated`. |

Never point them at production without the owner's say-so; the owner's rule is staging only.
