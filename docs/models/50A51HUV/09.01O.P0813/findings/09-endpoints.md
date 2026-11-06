# alvidaa findings — UI internals and the endpoint map

> Split from the original FINDINGS.md lab notebook. Canonical record; the blog and STORY.md draw from these.

## 13. UI internals & the endpoint map (Oct 30)

All 12 partition images captured (byte-verified). p41 `/APPS` walked:

- **R2's canary is live on channelA**: `index.html` (650 B) = the stock
  webpack loader + a red `alvidaa` badge div, with the original preserved as
  `index.html.alvidaa-bak` — the canary-edit path validated on the real UI.
- **The stock home is a thin shell**: `app.js` is 3.8 KB; `sdk.js` (883 KB)
  carries the platform logic. `process.env.json`: `BRAND: HIS, AREA: NA,
  PLAT: 9602, REPORT: false`. `hisenseUI` version `9.00.01.25.080417`.
- **The complete vidaahub.com service map** (~30 subdomains) lives in
  `sdk.js`: home-ui, recommend-ui, layout-ui{,-eu}, search-ui, topic-ui,
  detail-ui, member-ui, odinstore-vidaa, sport-vidaa, tvmodules-vidaa,
  pay-vidaa, msg, web, voice/vidaa-voice/iot-voice, ota-tv, file-ul,
  file-dl-test (promovod), device-ecom, oauth-auth, geo-bas,
  vidaa-base-auth{,-eu}. Plus `voiceservice-eu.hismarttv.com`.
- **`static/config/brand/` = ~50 three-letter brand configs** (his, lwe,
  jvc, phi, pan, tel, …) — theming only; the cloud map is brand-independent.
  `static/presetData/basicNationalInfo` = an image blob with national flags
  + info JSON (the "network-fed" national content).
- **Kill-list tiers drafted** in `firmware/ENDPOINTS.md` (gitignored):
  ALLOW = ota-tv/auth/geo-bas/icon-CDN; BLOCK = recommend/home/layout/
  topic/sport/promovod; LOG-first = store/pay/msg/voice/uploads.
- **Telemetry upload domain is runtime-resolved**:
  `hi_logreport_service` uses `getDomain`/`getDomainForUpload` against
  `vidaahub.com`; its API surface: `uploadFunctionSwitch`,
  `uploadGeneralFieldLog`, `uploadStoredSelfDefinedLogFile`,
  `uploadTvBacktrace`, `uploadOemOtaFailedFile`. Confirm the exact host
  from the `TVOUT` wiretap before blocking.
- `/data` (p27) = per-app silos (YTTV, amazon, netflix, vudu, airplay, QDA,
  webui) — third-party app state; keep images private.

## DoH evasion — the layer that beats DNS blocking

`/APPS/domain/domain_list.json` ships `dohServers: ["dns.google/dns-query"]` + `dohDomains: ["vidaahub.com"]` — vidaahub lookups bypass the LAN resolver via DoH by design. REJECT 8.8.8.8/8.8.4.4 :443 from the TV, then the fallback resolver (AdGuard) and its domain rules bite. Tiered lists: firmware/adguard-blocklist.txt + firmware/tvfw. The map self-declares the telemetry/ad hosts (evt-na, *-jrnl-na, rsc-ads, dvcstatus-dataretrv, file-ul) and is uid-314-writable via the bridge (mode 6).

## First wiretap window (Oct 30 – Nov 2, settings OFF)

1153 kernel-log lines harvested over ~26 h. Results:

- **447 DoH bootstrap attempts to 8.8.8.8:443** — the evasion fires
  constantly even with telemetry off. Countermeasure deployed live:
  REJECT 8.8.8.8/8.8.4.4 :443 (tcp+udp) at OUTPUT → lookups fell back to
  the LAN resolver (AdGuard) immediately (verified: `nslookup` answers
  from 192.168.0.85 post-deploy).
- **Telemetry confirmed despite settings OFF** — wiretap SYN hits match
  the domain map by IP: `ter-jrnl-na` (data-tenant-fluentd, 20.170.76.123,
  14 connections — a Fluentd log collector), `dvcstatus-dataretrv`
  (20.52.196.175), `file-ul`/account (131.189.128.123, plus 131.189.69.51
  same prod-eu-c range). The "off" settings do not stop the journal
  collector.
- Monetization range: 20.113.x (rsc-ads → monetization-tenant-ads) —
  now REJECTed at OUTPUT.
- Content CDNs (98.67.x, 48.201.x, 72.144.x, 13.227.x = CloudFront,
  172.217.x = Google, 89.187.x = cdn77) — UI/content traffic, left
  unblocked; they are not the ads feed.
- Tier-1 IP blocks deployed live over the tailnet (ter-jrnl + rsc-ads
  first) — the iptables layer and AdGuard layer now overlap.
- The hourly collector (`wiretap.log`) continues; the window stays open
  for the full baseline before the deliberate ON-capture.

## The kernel backstop was silently dead at boot (2026-11-05)

The wiretap baseline above was measured against a firewall that was only
half applied. Found while building the OTA-freeze utility, by listing the
chain instead of trusting the script.

**Symptom.** `iptables -L OUTPUT -n` on a fresh boot returned an empty
chain. The policy file `/var/local/tvfw` was present and correct, and the
boot hook sources it, so nothing looked wrong.

**Cause 1 — the binary was not there yet.** The hook sources `tvfw` near
the top of the script, before `/usr/local/bin/iptables` is on the effective
path. Every `iptables` call in the file failed, and a shell script that
cannot find a command does not fail loudly enough to notice. The rules
simply never existed.

**Cause 2 — the host list resolves at boot.** Tier 1 loops over the
telemetry hostnames and calls `nslookup` at source time, which is the one
moment DNS is least reliable. Even with a working `iptables`, the second
half would have no-opped.

**Measured.** Sourcing `tvfw` by hand with the system fully up landed the
four Tier-0 DoH REJECTs (`8.8.8.8` / `8.8.4.4`, tcp+udp, :443) and nothing
else — Tier 1 still produced zero rules, confirming the DNS half fails
independently of the path half.

**Consequence for the record.** The 26-hour baseline in the section above
was taken with the kernel backstop absent. The resolver layer (AdGuard
per-client rules) and the 79 INPUT DROP rules were doing the work; the
OUTPUT backstop was not. Any claim that "the layers overlap" needs the
chain listed, not the script read.

**Fix shape** (landed with the OTA utility): the policy defers itself,
bounded-waits for `iptables` to exist, uses absolute paths, retries DNS
instead of trusting boot-time resolution, and re-applies a freeze from a
state sidecar. Acceptance is a rule *count*, not a successful source.

## `nslookup` returns `0.0.0.0` for a blocked host, and scripts rule-ify it (2026-11-05)

Found while verifying that Tier 1 actually applied. The policy resolves each
telemetry hostname and REJECTs the resulting addresses. Once AdGuard
NXDOMAIN-pins those hosts, busybox `nslookup` answers **`0.0.0.0`** rather
than failing, so the pipeline produced:

```sh
iptables -I OUTPUT 1 -d 0.0.0.0 -j REJECT
```

A rule that can never match a real destination, sitting in the chain
looking like protection. It was only visible because the acceptance test
counted rules instead of trusting "applied".

**The general trap:** any script that resolves a hostname and acts on the
answer must filter `0.0.0.0` and `::` explicitly. A resolver that returns a
null address for a blocked name is indistinguishable from a resolver that
returned a real one unless you check.

**Second-order trap, and the reason this is written down:** once the
resolver blocks everything, "Tier 1 added zero rules" becomes the *correct*
outcome — but it was a *bug* an hour earlier. A status line that prints
only the count cannot distinguish "the resolver is doing the work" from
"the loop silently failed again". Report which case it is, not just the
number.

## The layered status, measured live (2026-11-06 — `alvidaa privacy status`)

Issue #15 turned the manual measurement into `alvidaa privacy status|hits|doh`
(read-only, tools/alvidaa.py). First live run caught the layered design
doing exactly what it was built to catch:

- **Kernel layer empty this boot.** tvfw's marker says "applied at T+6s",
  but `iptables -L OUTPUT` holds zero rules at T+47480s — the rules were
  applied and have since vanished. The vendor's late firewall re-init is
  the suspect (our INPUT ACCEPT holes for 8770/2323/2222 survived, so a
  full flush is unlikely; nobody has re-run tvfw since). Unproven which
  mechanism — the status command exists so the next boot either reproduces
  it or clears it.
- **Resolver layer carried the whole load meanwhile.** All 7 Tier-1 hosts
  NXDOMAIN-pin via AdGuard (192.168.0.85) — `0.0.0.0`/`::` answers. The
  kill-list held at DNS even with the kernel backstop gone. That is the
  design assumption holding in practice, and the reason "0 rules" needed
  the per-case wording from the section above.
- **The wiretap has been disarmed since the `.11` move.** No LOG rules in
  any chain, `dmesg` carries zero TVOUT/TVDNS lines, and every one of the
  1198 lines in `wiretap.log` has `SRC=192.168.0.12` (the pre-move era);
  not one line exists from `.11`. The file's mtime keeps advancing while
  its size is static — mtime proves nothing; armed means LOG rules in the
  kernel, which is what the command checks.
- **Correction to the Oct 30 window record above:** the "447 DoH bootstrap
  attempts to 8.8.8.8:443" were **port 53** — plain DNS aimed straight at
  dns.google, bypassing the LAN resolver, not DoH-over-443. Tier 0 blocks
  :443 only, so the hardcoded-resolver :53 lane is a separate leak if it
  recurs. `alvidaa privacy doh` reports the two transports separately.
