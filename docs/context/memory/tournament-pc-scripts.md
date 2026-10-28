---
name: tournament-pc-scripts
description: Windows 11 tournament PC setup scripts (.bat) live in a git project at ~/tournament-pc-scripts; deployed copy in Downloads\SSD
metadata:
  type: project
---

The tournament PC setup scripts (IP, rename, activation, ~chain.bat, ASUS VCP.csv upload, Steam tournament mode, net toggle) are kept as a project at `/home/clovisd/tournament-pc-scripts`, created 2026-10-22. `ssd/` is the source of truth; `tools/deploy.sh` copies it to `C:\Users\clovisd\Downloads\SSD`, the folder PCs are set up from. CLAUDE.md there holds the image facts and batch gotchas; `tests/run_all.sh` tests through cmd.exe from WSL.

**Why:** the user asked for a project "for next time we need to update". As of 2026-10-22 they had tested every script on real tournament PCs and confirmed they work.

**How to apply:** when the user mentions the tournament scripts, the SSD folder, or player PC setup, work in that project. Edit, run tests, then deploy. Don't edit Downloads\SSD directly. The user writes "bash" but means batch (.bat). The project also builds `MonitorProfile.exe` from `monitor-profile/` (C# 5 via Windows' built-in csc.exe, `tools/build-exe.sh`); see [[monitor-profile-tool]]. Related: [[pgl-network-dns]] (cs2-fileshare.pgl.ro resolves via the pgl.ro DNS).

GitHub: private repo https://github.com/clovisd/display-tool (remote origin, branch
master), created 2026-10-27; gh at ~/.local/bin/gh is logged in as clovisd; git
identity set locally in the repo (clovisd / user email). No attribution lines in commits.
