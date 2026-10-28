---
name: monitor-profile-tool
description: "MonitorProfile.exe (pro/debug tool, shipped) and the PGL Display Tool (player tool: design approved, 4 plans written, not built as of 2026-10-27; docs/HANDOFF.md in the repo)"
metadata:
  node_type: memory
  type: project
  originSessionId: 93872390-fa75-43be-a08a-b05c382fd58e
  modified: 2026-10-23T17:30:27.004Z
---

Goal stated by the user (2026-10-22): a standalone app players keep on their desktop with just two features, "save profile to file" and "apply saved profile to monitor". No startup, menus, AI, hotkeys (anti-goal: becoming ASUS Display Center). Bonus, opt-in per player: run at boot to apply the profile, and back up settings on shutdown, so a player's SSD booting at any tournament station brings their monitor settings. Stations use ASUS PG259QWS Ace (720 Hz) and G248QSG Ace (605 Hz).

Step 1, built 2026-10-23: `MonitorProfile.exe` in [[tournament-pc-scripts]] (`monitor-profile/`). It applies the newest row of a player's VCP.csv (the format written by ASUS's AsusDisplayVcpTool.exe, collected on the share as `ASUS Profiles\<player>.csv`) and reads every setting back. On 2026-10-24 the user tested it on a PG259QWS only (the G248QSG is untested): both the standard picture settings and the ASUS private codes E0-FF apply correctly (doubled-byte handling works). Then added: a row picker (rows for the connected model, newest first) and the private-codes box ticked by default. On 2026-10-24 a Scan tab was added for mapping (reads all 256 codes, shows what changed since the last scan, appends each scan with the user's note to scans.csv next to the exe); known codes are labelled per model in `ModelNames` in Profile.cs. Next: the user maps more codes with Scan and sends scans.csv.

**Why:** players' monitor settings get lost between stations; ASUS's own dump tool only reads. (Correction 2026-10-25: it does NOT upload; the Azure upload code is dead code. I told the user otherwise on 2026-10-22 and corrected it.)

**How to apply:** next steps are mapping the private codes, then "save profile" and the opt-in boot/shutdown mode. The shutdown backup should not overwrite the player's chosen profile (my suggestion, not yet confirmed by the user).

Private-code mapping, round 1 (2026-10-24, PG259QWS W9LMAS027987, file `ASUS Profiles\WORKING.CSV`; each OSD change shows in the next ASUS-tool run):
- F2 = RGB LED lighting: red 0x0002 -> green 0x0204 (both bytes moved; 0 in Eco).
- FC = bitfield of system on/off settings, baseline 0x11: bit 0 = power indicator (1 on), bit 7 = USB hub off in standby; bit 4 unknown.
- CC = OSD language (standard MCCS: 2 English, 3 French). Stand light: no code moved.
- CA went 1 -> 2 in the USB-hub run; unclear (maybe OSD menu open/closed).
- Eco mode (from Performance): E1 0->1, FD 0->64, F2 -> 0, DC/CB 0x020B -> 10, brightness 77->100, sharpness 8->5, and D3 E3 E4 E5 E7 EA FA -> 254 (254 = locked/unavailable). Those 7 are the likely gaming settings.
- Open risks for MonitorProfile: a profile saved in Eco has 254s (probably should not be written), and the Eco switch should be written before picture settings.

Round 2 (2026-10-24, F:\scans.csv from the Scan tab, same PG259QWS): 45 = OLED protection intensity (0 low, 1 middle, 2 high); F8 = OLED protection reminder in hours (0, 2, 4, 8); FC bit 4 = auto input detection (confirmed both ways); E1 is probably Eco (FD also moves with OLED protection, so likely status); 23 and 25 change by themselves (noise). The PG259QWS EDID name is exactly "PG259QWS". Gaming settings (D3 E3 E4 E5 E7 EA FA candidates) still untested. ASUS uses codes below E0 too (45), which Apply does not write.

Research 2026-10-25 (user can't scan for now): decompiled the dump tool, ASUS's `dwc` CLI DLL (github ASUS-Display/asus-display-control, binaries only) and DisplayWidget Center 2026-10-01. Full code map, ASUS's own profile code list/order and implications are in `monitor-profile/ASUS-RESEARCH.md` in [[tournament-pc-scripts]]. Key: ASUS uses the same dxva2 calls; PG259QWS is ProductLine "Ace" (XG248QSG is "Gaming"); DC high byte = Colour Richness, low byte = mode (0B = FPS 1); 23/25 are the position sensor (not noise); E5 Shadow Boost, EE ELMB, E0 overdrive; EB (OSD buttons) and EC (mode reset) are commands and FD bit 4 starts pixel cleaning, so Apply's "all E0-FF" had to become ASUS's allow-list (done 2026-10-26). Armoury Crate only does Aura lighting over USB. Decompiled sources were left in the Windows %TEMP%\asusre, ILSpy in %TEMP%\ilspy.

2026-10-26: the user decided MonitorProfile.exe stays a **pro/debug tool**; the player tool is a separate product to be planned from `monitor-profile/BRIEF.md` (goals in the user's words, constraints, what was tried, learnings, 9 open decisions, station test checklist). Build 2026-10-26 (shown in the window title, `Build` in MainForm.cs) writes ASUS's list in ASUS's order (`Order`/`Asus` in Profile.cs, power saving first), skips 254/0xFEFE and gains unless colour temp = User, keeps FD bits 4/7, turns overlays off after the mode, retries 3x, rewrites brightness/blue gain after 2 s, labels with `AsusNames`, and saves every code's maximum in a `Max` column of scans.csv. Deployed to Downloads\SSD; untested on a monitor, as are the Default/English buttons.

Decisions 2026-10-26 (recorded in BRIEF.md section 7): the player tool lives in its own folder in the player's Documents (exe + settings.csv + any other CSVs there); no off-site/NAS copy for now (player tool doesn't use the share); save writes a CSV, custom format welcome (record the current event at capture and the app's own settings); other CSVs found in the folder are imported on first run; no shutdown backup. Still open: save scope (current mode vs all), cross-model apply, OSD language, apply-on-boot, position sensor, reset-first.

2026-10-26 (later): the player tool is now the **PGL Display Tool**, designed in
`docs/superpowers/specs/2026-10-26-pgl-display-tool-design.md` in the repo
(supersedes BRIEF.md section 7 where they differ; awaiting the user's approval,
then superpowers:writing-plans). Key decisions the user made: booth LED colour
from the booth's MikroTik identity via MNDP (UDP 5678 broadcast; one RouterBoard
per booth, uplink ether1/sfp1; LLDP impossible without admin), six preset
colours only (no orange), no service, no tray; one exe, portable (startup off)
or installed by `ssd/6_install-display-tool.bat` (startup on, First Launch
until first save); Set English + Reset Monitor in the main window with
confirmations (toggle in gear); Optimized Defaults = curated defaults.csv;
cross-model apply allowed; save = current mode (all modes in gear); import of
old CSVs into an extended settings.csv with event title/subtitle/logo from
`events.csv` (Title,Subtitle,Start,End,Logo) on the share; USB kill-switch by
serial; image cloned without sysprep. Test toolkit built: `build/MndpProbe.exe`
from `display-tool/probe/` (+ `mndp-firewall.bat`), to run at a booth before
building. User supplies PNG artwork later.

**2026-10-26, booth test:** MNDP is OFF on the booth RouterBoards (ops policy,
stays off); LLDP is ON. The probe at a booth (10.97.25.113) heard MNDP only
from a wAP 60G link `MkT-wAP60G-Leto` (7.21.4, every 30 s) and the core
CRS326 `RouterOS` (6.48.6, every 60 s); capture saved in
`display-tool/probe/captures/`. Windows 11 has no user-readable LLDP (no
cmdlet/WMI/neighbour table; ms_lldp only transmits); the only in-box reader
is `pktmon` (admin). Design revised: installer registers a SYSTEM scheduled
task at startup running `C:\ProgramData\PGL Display Tool\lldp-capture.bat`
(admin-only folder) -> pktmon filter 0x88CC, 75 s, `lldp.pcapng`; the tool
parses the pcapng when newer than this boot. MNDP dropped from the product.
`display-tool/probe/lldp-probe.bat` (admin) is the booth test for this; its
pcapng becomes the parser fixture. Design doc still awaiting approval.

**2026-10-26, later:** pktmon alone captured NO LLDP on the booth PC (NIC
drops the multicast without promiscuous mode), while tcpdump on Linux saw it
(System Name `MkT-RB4011-SW-171`, RB4011, RouterOS 7.21.5, Port ID `ether4`,
Port Description `bridge/ether4`). User confirmed: the System Name string is
the booths.csv key. Mechanism now: NetEventPacketCapture session
(`Add-NetEventNetworkAdapter -PromiscuousMode`, EtherType 88CC filter) run by
the SYSTEM task, frames read back with `Get-WinEvent` (NDIS-PacketCapture
event 1001, byte[] property) into `lldp.txt` hex lines; the tool parses hex.
Verified locally (Wi-Fi self-test): session + promiscuous + Get-WinEvent work;
Wi-Fi gives native 802.11 frames. `lldp-probe.bat` v2 (polyglot) in
`display-tool/probe/`, deployed to Downloads\SSD; booth run still pending.
No third-party binaries (etl2pcapng was tried and dropped).

2026-10-27: design doc gained a gear toggle "LED control" (master off switch for
all lighting writes and the override; `LedControl` in options.csv). Share
folder confirmed: `\\cs2-fileshare.pgl.ro\public\Admin\Control\`. Artwork:
placeholder images for now. Design doc still awaiting approval (then
superpowers:writing-plans; build layer 1 first, it needs no booth result).

2026-10-27 booth 228 (HOME1, 10.97.25.20, Realtek 2.5GbE): v2 probe PROVED the
promiscuous NetEvent capture: 3 frames from MkT-RB4011-SW-228 (ether6, RouterOS
7.20.8) every 30 s + 4 own-PC LLDP frames (Windows LLDP driver, Chassis ID = PC
name); pktmon 0 even promiscuous. Fixture: display-tool/probe/captures/
2026-10-27-booth-LldpProbe-netevent-frames.txt. Probe outputs sit on the share
Control folder (the tool share folder). Capture mechanism settled; layer 3 unblocked.

2026-10-27 evening: design doc APPROVED; four implementation plans written in
docs/superpowers/plans/ (1 core, 2 events-import, 3 booth-colour, 4 xg248qsg),
no product code yet. Repo pushed to private GitHub clovisd/display-tool (master).
Next: user picks execution approach (subagent-driven recommended) then build layer 1.

2026-10-27 night: the user is handing the project off elsewhere. Added
`docs/HANDOFF.md` (state, reading order, what only the organiser supplies, rules
not in code), a Display Tool section in CLAUDE.md, README pointers, and the booth
ETL fixture `display-tool/probe/captures/2026-10-27-booth-LldpProbe-netevent.etl`
(copied from the share, sha256 77a4655e...43a2) so plan 3 needs nothing from the
share. Everything is pushed to origin/master. If this project comes back here,
start from docs/HANDOFF.md, not from these notes.
