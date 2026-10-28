---
name: pgl-network-dns
description: DNS layout of the pgl.ro work network and the Windows NRPT rule that breaks *.pgl.ro resolution
metadata:
  type: reference
---

This machine is WSL2 (NAT mode) on Windows, used on the pgl.ro office network (search domains vl6.ird.pgl.ro, ird.pgl.ro, pgl.ro). Office DNS servers (DHCP): 10.97.62.6 (ns-1.ird.pgl.ro) and 10.97.62.7; they deliberately strip AAAA records (clean NODATA) — the network is IPv4-only, which is normal here, not a fault. Root cause found 2026-09-18 for "can't reach *.pgl.ro": a manually-created Windows NRPT rule "PGL internal DNS" forced .pgl.ro queries to 10.101.62.6/.7 (unreachable from the office network), timing out resolution in every Windows app AND in WSL (whose 10.255.255.254 proxy forwards to the Windows resolver). Non-pgl.ro names resolved fine throughout. Fix: Remove-DnsClientNrptRule in admin PowerShell — not disabling IPv6, not resolv.conf edits. If the user works remotely via VPN and pgl.ro breaks again, the 10.101.62.x servers may be the VPN-side DNS and an NRPT rule pointing there may need re-adding for VPN use.
