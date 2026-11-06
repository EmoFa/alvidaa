# alvidaa findings — wiretap, endpoint map, in-kernel blocking (55A7KAU, 09.09O)

> Phase 4 items 1–3 ([HACK-YOUR-OWN.md](../../../../project/HACK-YOUR-OWN.md)),
> executed 2026-11-06 after boot-persistent root ([02-root-ssh.md](02-root-ssh.md)).
> OTA frozen owner-side before any of this.

## 1. Wiretap

- `iptables -I OUTPUT 1 -p tcp --syn -j LOG --log-prefix "ALVTAP "` plus a
  UDP/53 `ALVDNS` rule; read via `dmesg` over SSH. **LOG must sit above the
  block chain** — a LOG rule inserted before the ALV_BLOCK jump never sees
  REJECTed packets, making "blocked" indistinguishable from "not attempting".
- Idle-TV baseline (one app-launch cycle) captured 12 destinations:

| DST | What |
| --- | --- |
| 8.8.8.8 | **DoH evasion** (dns.google over :443, see below) — also direct DNS |
| 192.168.50.1 / 192.168.1.1 | gateways (incl. a stale 192.168.1.1 probe) |
| 192.168.50.209 :16794 | **the neighbour TCL TV** — Netflix MDX/DIAL cast discovery crossing the LAN |
| 20.170.76.123 | `ter-jrnl-oc` / `exc-jrnl-oc` (Fluentd journal) |
| 4.182.131.30 | `evt-oc` telemetry + `abtest-tv` |
| 20.113.0.141 | `rsc-ads` (monetization) |
| 98.67.150.220 | `policy-jrnl-oc` |
| 131.189.128.123 | `file-ul` upload |
| 143.244.62.9, 199.232.50.250, 52.2.65.18 | CDN/app content (Fastly, AWS) |
| 34.160.81.0, 35.186.224.24 | Google Cloud (YouTube) |

## 2. Endpoint map — no dump needed for tier 1

`/APPS/domain/domain_list.json` (read via the file bridge, uid 314, mode 6)
**self-declares every endpoint the TV firmware knows**, per region. This unit
ships the **`oc` (Oceania) map, ReleaseDate 2026-07-07** — all
`*.vidaahub.com`. Full list preserved in `firmware/ENDPOINTS.md` (working
copy, gitignored). Relevant tiers:

- **Telemetry/ads/journal (blocked):** `evt-oc`, `ter-jrnl-oc`, `exc-jrnl-oc`,
  `policy-jrnl-oc`, `rsc-ads`, `dvcstatus-dataretrv`, `file-ul`,
  `traffic-ui`, `abtest-tv`
- **Functional (unblocked):** appstore/odinstore, pay, auth/oauth, voice/TTS
  (`*-voice-oc`), ui.* content/layout/search/home, ecom, sport, msg, iot,
  `ota-tv` (OTA frozen owner-side at the settings level)
- **DoH evasion, by design:** `dohServers: {"google": "dns.google/dns-query"}`,
  `dohDomains: ["vidaahub.com"]` — vidaahub lookups bypass the LAN resolver
  via DoH. Counter: REJECT 8.8.8.8/8.8.4.4 :443 at OUTPUT (matches the
  reference-unit record).

Resolution check (from the operator PC): every blocked host resolves into the
same Azure/Akamai ranges the reference 50A51HUV wiretap saw — e.g.
`dvcstatus-dataretrv → 20.52.196.175` exactly matches the 09.01O record.

## 3. In-kernel blocking

- Dedicated chain **`ALV_BLOCK`** (flush+refill = idempotent), jumped from
  OUTPUT position 2 (LOG at 1 above it). 9 rules: 7 endpoint IPs +
  REJECT 8.8.8.8/8.8.4.4 :443.
- Applied live over SSH, **then baked into the re-arm postinst** (IPK v6) so
  every `re_sshd` boot re-applies the tier. Verified after re-arm:
  `ALV_BLOCK rules: 9`, single 8008 ACCEPT, root alive.
- **No `ip6tables` on this build** — IPv6 egress cannot be filtered from
  userspace (v6 targets like `2603:1020::…` remain unblocked if the LAN ever
  routes v6 to the TV; currently moot).
- `0.0.0.0`/null-resolution trap from the reference record applies to any
  future resolver-driven rule generation; the current set is static IPs, and
  the acceptance test counts rules *and* greps a live SYN log.
- Vendor chain untouched: `FIREWALL_IN_EULAON` keeps only our single 8008
  ACCEPT. Teardown: `iptables -F ALV_BLOCK; iptables -D OUTPUT -j ALV_BLOCK`,
  remove the LOG rules, delete the block section from the IPK postinst.

## Open (Phase 4 remainder)

- Full firmware image dump for the deep endpoint/kill-list (the
  `dd`-over-SSH method; the self-declared map covers the practical tier).
- Launcher server onto the TV's Node runtime; stock-home retirement
  (LAUNCHER_V2).
