---
name: delmotte-wifi-diagnosis
description: "Delmotte WiFi" no-internet investigation on the Windows laptop (CWD-FRAME13) — not a VPN/split-tunnel leftover
metadata:
  type: project
---

2026-10-09: user reported no internet on SSID "Delmotte WiFi" (192.168.50.0/24, gateway/DHCP/DNS 192.168.50.1, domain cl6.lan — one of the user's UniFi sites). CWD-NET is 192.168.8.0/24, also cl6.lan.
Checked and ruled out on Windows: no VPN profiles, no NRPT rules, no proxy, no persistent routes, no static IP, hosts file clean, no WireGuard tunnel ran in the prior 3 days.
Evidence pointed at the link/router: DHCP server NACKed the cached lease (192.168.50.227), NCSI logged SuspectArpProbeFailed (gateway stopped answering ARP), repeated driver disconnects on the Intel AX210.
Leftovers found: WiFiman Desktop (UniFi Teleport client) has a stale auto-start service WireGuardTunnel$wg4aad833f whose .conf no longer exists; official WireGuard app has tunnels peer19 and CHINA-Client-1.
Related: [[grandglise-unifi-audit]], [[pgl-network-dns]]

Update 2026-10-09 15:20, on site at CWD-FERME: laptop associates to TP6-01 BSSID 22:61:b4:dd:a4:99 (ch 44, -52..-56 dBm; Delmotte BSSIDs are 22:61:b4:dd:a4:98/99, CWD-NET is 26:61:b4:dd:a4:99 on the same radio). Gets real DHCP 192.168.50.227, correct routes, gateway MAC 9e:05:d6:69:8f:47, but ~97-99% packet loss to the gateway (occasional replies). WPA2-only temp profile made no difference. CWD-NET on the same AP also failed earlier; CWD-SPOT on other APs works. Leading suspect: 802.11ax interop between Intel AX210 driver 24.40.0.4 and EAP610 fw 1.6.7. Next tests need admin: wireless mode 802.11ac, Preferred Band 2.4 GHz (WinRT BSSID pinning did not force 2.4 GHz).
